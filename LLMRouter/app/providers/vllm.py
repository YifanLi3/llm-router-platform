"""vLLM provider using its OpenAI-compatible HTTP API."""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator

import httpx

from app.providers.base import BaseProvider, ProviderUnavailableError
from app.schemas import (
    EngineConfig,
    InferenceMetrics,
    InferenceResult,
    ModelConfig,
    RuntimeLoadSnapshot,
)

_TIMEOUT_SECONDS = 60.0


class VLLMProvider(BaseProvider):
    """Call a remotely running vLLM OpenAI-compatible server."""

    def __init__(self, engine_config: EngineConfig) -> None:
        self.engine_config = engine_config

    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        """Generate one non-streaming completion through vLLM."""
        started_at = time.perf_counter()

        try:
            response = httpx.post(
                f"{self.engine_config.base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": model_cfg.provider_model
                    or self.engine_config.served_model_name,
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": model_cfg.max_tokens,
                    "temperature": 0.7,
                    "stream": False,
                },
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderUnavailableError(
                f"vLLM request failed: {error}"
            ) from error

        try:
            response_text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderUnavailableError(
                "vLLM returned an unexpected completion format."
            ) from error

        usage = payload.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        tokens_per_second = None
        if output_tokens > 0 and latency_ms > 0:
            tokens_per_second = output_tokens / (latency_ms / 1000)

        return InferenceResult(
            response_text=response_text,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,
            latency_ms=latency_ms,
            cached=False,
            provider="vllm",
            engine="vllm",
            metrics=InferenceMetrics(
                tokens_per_second=tokens_per_second,
                total_latency_ms=latency_ms,
            ),
        )

    async def stream(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Yield text deltas from vLLM's OpenAI-compatible SSE stream."""
        del model_name
        payload = {
            "model": model_cfg.provider_model
            or self.engine_config.served_model_name,
            "messages": [{"role": "user", "content": query}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                async with client.stream(
                    "POST",
                    f"{self.engine_config.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        raw_data = line.removeprefix("data: ").strip()

                        if raw_data == "[DONE]":
                            return

                        event = json.loads(raw_data)
                        delta = event["choices"][0]["delta"].get("content")

                        if delta:
                            yield delta

        except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
            raise ProviderUnavailableError(
                f"vLLM streaming request failed: {error}"
            ) from error

    async def fetch_runtime_load(self) -> RuntimeLoadSnapshot:
        """Read vLLM Prometheus metrics and convert them to a load snapshot."""
        metrics_url = (
            f"{self._service_base_url()}{self.engine_config.metrics_endpoint}"
        )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(metrics_url)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(
                f"could not fetch vLLM metrics: {error}"
            ) from error

        metrics_text = response.text

        active_requests = int(
            self._read_metric(metrics_text, "vllm:num_requests_running") or 0
        )
        queue_depth = int(
            self._read_metric(metrics_text, "vllm:num_requests_waiting") or 0
        )

        kv_cache_usage = (
            self._read_metric(metrics_text, "vllm:gpu_cache_usage_perc") or 0.0
        )

        # Some vLLM versions export 0-100, while others export 0-1.
        if kv_cache_usage > 1.0:
            kv_cache_usage /= 100.0

        return RuntimeLoadSnapshot(
            engine="vllm",
            kv_cache_usage=min(kv_cache_usage, 1.0),
            active_requests=active_requests,
            queue_depth=queue_depth,
            updated_at=time.time(),
        )

    def health(self) -> bool:
        """Return whether vLLM responds to its health endpoint."""
        try:
            response = httpx.get(
                f"{self._service_base_url()}{self.engine_config.health_endpoint}",
                timeout=5.0,
            )
            return response.is_success
        except httpx.HTTPError:
            return False

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}

        if self.engine_config.api_key:
            headers["Authorization"] = (
                f"Bearer {self.engine_config.api_key}"
            )

        return headers

    def _service_base_url(self) -> str:
        """Convert http://host:8000/v1 into http://host:8000."""
        return self.engine_config.base_url.removesuffix("/v1")

    @staticmethod
    def _read_metric(metrics_text: str, metric_name: str) -> float | None:
        """Read the first matching Prometheus sample from plain-text metrics."""
        pattern = rf"^{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+([0-9.eE+-]+)$"

        for line in metrics_text.splitlines():
            match = re.match(pattern, line)

            if match:
                return float(match.group(1))

        return None