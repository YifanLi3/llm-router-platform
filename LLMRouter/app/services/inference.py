"""Inference orchestration with provider dispatch and fallback retries."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseProvider, ProviderError, ProviderUnavailableError
from app.providers.local import LocalProvider
from app.providers.openai import OpenAIProvider
from app.providers.vllm import VLLMProvider
from app.schemas import (
    AppConfig,
    InferenceResult,
    InferenceStreamChunk,
    QueryRequest,
    RoutingDecision,
)

logger = logging.getLogger(__name__)

class InferenceExhaustedError(RuntimeError):
    """Raised when every selected and fallback model has failed.
    """

    def __init__(
        self,
        attempted_models: list[str],
        provider_errors: dict[str, str],
    ) -> None:
        self.attempted_models = attempted_models
        self.provider_errors = provider_errors

        super().__init__(
            f"All inference attempts failed: {attempted_models}"
        )

class InferenceEngine:
    """Call the selected provider, then retry the routing fallback chain."""

    def __init__(self, config:AppConfig) -> None:
        self.config = config

    def run(
        self,
        request: QueryRequest,
        decision: RoutingDecision,
    ) -> InferenceResult:
        # selected model first; fallbacks only run after a real failure.
        model_names = [decision.selected_model, *decision.fallback_models]

        attempted_models: list[str] = []
        provider_errors: dict[str, str] = {}

        for model_name in model_names:
            model_cfg = self.config.router.models.get(model_name)
            if model_cfg is None:
                provider_errors[model_name] = "Model is not declared in config.yaml."
                continue

            try:
                attempted_models.append(model_name)
                provider = self._get_provider(model_cfg.provider)
                result = provider.generate(
                    query=request.query,
                    model_name=model_name,
                    model_cfg=model_cfg,
                )

                fallback_used = model_name != decision.selected_model
                fallback_reason = None
                if fallback_used:
                    primary_error = provider_errors.get(decision.selected_model)
                    fallback_reason = (
                        f"Primary model {decision.selected_model!r} failed: "
                        f"{primary_error}"
                    )

                logger.info(
                    "inference succeeded",
                    extra={
                        "model": model_name,
                        "provider": model_cfg.provider,
                        "fallback_used": fallback_used,
                        "attempts": attempted_models,
                    },
                )
                return result.model_copy(
                    update={
                        "fallback_used": fallback_used,
                        "fallback_reason": fallback_reason,
                        "attempted_models": attempted_models,
                        "provider_errors": provider_errors,
                    }
                )
            except ProviderError as error:
                provider_errors[model_name] = str(error)
                logger.warning(
                    "inference attempt failed; trying next fallback",
                    extra={
                        "model": model_name,
                        "provider": model_cfg.provider,
                        "error": str(error),
                    },
                )
        # No model in the selected + fallback chain succeeded.
        raise InferenceExhaustedError(
            attempted_models=attempted_models,
            provider_errors=provider_errors,
        )

    async def stream(
        self,
        request: QueryRequest,
        decision: RoutingDecision,
    ) -> AsyncIterator[InferenceStreamChunk]:
        """Stream chunks from the selected provider, retrying fallbacks on error."""
        model_names = [decision.selected_model, *decision.fallback_models]
        attempted_models: list[str] = []
        provider_errors: dict[str, str] = {}

        for model_name in model_names:
            model_cfg = self.config.router.models.get(model_name)
            if model_cfg is None:
                provider_errors[model_name] = "Model is not declared in config.yaml."
                continue

            try:
                attempted_models.append(model_name)
                provider = self._get_provider(model_cfg.provider)
                stream_method = getattr(provider, "stream", None)
                if stream_method is None:
                    raise ProviderUnavailableError(
                        f"Provider {model_cfg.provider!r} does not support streaming."
                    )

                fallback_used = model_name != decision.selected_model
                async for delta in stream_method(
                    query=request.query,
                    model_name=model_name,
                    model_cfg=model_cfg,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                ):
                    yield InferenceStreamChunk(
                        delta=delta,
                        model_name=model_name,
                        provider=model_cfg.provider,
                        engine=model_cfg.engine,
                        fallback_used=fallback_used,
                    )

                logger.info(
                    "streaming inference completed",
                    extra={
                        "model": model_name,
                        "provider": model_cfg.provider,
                        "fallback_used": fallback_used,
                        "attempts": attempted_models,
                    },
                )
                return

            except ProviderError as error:
                provider_errors[model_name] = str(error)
                logger.warning(
                    "streaming inference attempt failed; trying fallback",
                    extra={
                        "model": model_name,
                        "provider": model_cfg.provider,
                        "error": str(error),
                    },
                )

        raise InferenceExhaustedError(
            attempted_models=attempted_models,
            provider_errors=provider_errors,
        )

    def provider_health(self) -> dict[str, dict[str, object]]:
        """Describe configured providers without sending inference requests."""
        providers: dict[str, dict[str, object]] = {}

        for model_name, model_cfg in self.config.router.models.items():
            provider_name = model_cfg.provider

            if provider_name not in providers:
                providers[provider_name] = {
                    "healthy": provider_name == "local",
                    "models": [],
                }

            providers[provider_name]["models"].append(model_name)

            if provider_name != "local":
                providers[provider_name]["healthy"] = False

                if not model_cfg.api_key_env:
                    reason = "No API-key environment variable is configured."
                else:
                    reason = (
                        f"External provider is unavailable: "
                        f"{model_cfg.api_key_env!r} is not configured locally "
                        "or its real SDK integration is not implemented."
                    )

                providers[provider_name]["reason"] = reason

        return providers

    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Return the implementation for a configured provider name."""
        if provider_name == "local":
            return LocalProvider()
        if provider_name == "openai":
            return OpenAIProvider()
        if provider_name == "anthropic":
            return AnthropicProvider()
        if provider_name == "vllm":
            engine_config = self.config.engines.get("vllm")
            if engine_config is None:
                raise ProviderUnavailableError(
                    "vLLM provider is configured, but no 'vllm' engine exists."
                )
            if not engine_config.enabled:
                raise ProviderUnavailableError(
                    "vLLM engine is disabled in config.yaml."
                )
            return VLLMProvider(engine_config)
        raise ValueError(f"Unsupported provider {provider_name!r}.")


# ---------------------------------------------------------------------------
# Self-test:  uv run python -m app.services.inference
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.core.config import get_config
    from app.services.router import QueryRouter

    cfg = get_config()
    router = QueryRouter(cfg)
    engine = InferenceEngine(cfg)

    cases = [
        ("general", "What is the capital of France?"),
        ("coding",  "Write a python function to reverse a list"),
        ("long",    "a " * 600),
    ]

    for label, q in cases:
        req = QueryRequest(query=q, user_id="u1", user_tier="free")
        decision = router.route(req)
        result = engine.run(req, decision)

        print(f"--- [{label}] ---")
        print(f"  selected_model = {result.model_name}")
        print(f"  response_text  = {result.response_text[:80]}...")
        print(f"  tokens         = in:{result.input_tokens}  out:{result.output_tokens}")
        print(f"  cost_usd       = {result.cost_usd:.8f}")
        print(f"  latency_ms     = {result.latency_ms}")
        print()