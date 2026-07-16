"""Deterministic local provider used for development and tests."""

from __future__ import annotations

import time

from app.providers.base import BaseProvider
from app.schemas import InferenceResult, ModelConfig


class MockProvider(BaseProvider):
    """A fake LLM that echoes the prompt with calculated usage."""

    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        started_at = time.perf_counter()

        response_text = f"Echo from {model_name}: {query[:200]}"
        input_tokens = max(1, len(query.split()))
        output_tokens = len(response_text.split())

        cost_usd = (
            input_tokens / 1000.0 * model_cfg.cost_per_1k_input
            + output_tokens / 1000.0 * model_cfg.cost_per_1k_output
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        return InferenceResult(
            response_text=response_text,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=False,
            provider="mock",
        )