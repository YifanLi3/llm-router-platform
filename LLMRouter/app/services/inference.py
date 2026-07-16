"""Inference orchestration with provider dispatch and fallback retries."""

from __future__ import annotations

import logging

from app.providers.base import BaseProvider, ProviderError
from app.providers.mock import MockProvider
from app.providers.unavailable import ExternalProviderPlaceholder
from app.schemas import AppConfig, InferenceResult, QueryRequest, RoutingDecision

logger = logging.getLogger(__name__)

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

            attempted_models.append(model_name)
            provider = self._get_provider(model_cfg.provider)

            try:
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
        raise RuntimeError(
            "All inference attempts failed. "
            f"attempted={attempted_models}, errors={provider_errors}"
        )
    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Return the implementation for a configured provider name."""
        if provider_name == "mock":
            return MockProvider()
        # Phase 2 deliberately does not call external APIs yet.
        # Missing credentials produce a normal fallback instead of a 500.
        return ExternalProviderPlaceholder(provider_name)


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