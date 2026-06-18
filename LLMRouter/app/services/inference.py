"""Mock inference engine for Phase 1.
In Phase 1 every model in config.yaml uses provider='mock'; this file
implements a single MockProvider that returns predictable echoed
responses along with realistic-looking token counts, latency, and cost.
Phase 2 will introduce real providers (LocalProvider, OpenAIProvider,
AnthropicProvider) plus a fallback chain. The public interface here --
InferenceEngine.run(request, decision) -> InferenceResult -- will not
change, so the rest of the project will keep working unmodified.
"""

import time

from app.schemas import (
    AppConfig,
    InferenceResult,
    ModelConfig,
    QueryRequest,
    RoutingDecision,
)

class MockProvider:
    """A fake LLM that echoes the prompt back, with realistic usage stats."""

    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        t0 = time.time()

        response_text = f"Echo from {model_name}: {query[:200]}"
        input_tokens = len(query.split())
        output_tokens = len(response_text.split())
        cost_usd = (
            input_tokens * model_cfg.cost_per_1k_input
            + output_tokens * model_cfg.cost_per_1k_output
        ) / 1000.0

        latency_ms = int((time.time() - t0) * 1000)

        return InferenceResult(
            response_text=response_text,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=False,
        )

class InferenceEngine:
    """Orchestrator: look up the chosen model in config, dispatch to provider."""

    def __init__(self, config:AppConfig) -> None:
        self.config = config
        self.provider = MockProvider()

    def run(
        self,
        request: QueryRequest,
        decision: RoutingDecision,
    ) -> InferenceResult:
        
        model_name = decision.selected_model

        if model_name not in self.config.router.models:
            raise ValueError(
                f"Model '{model_name}' chosen by router is not declared in config.yaml"
            )

        model_cfg = self.config.router.models[model_name]

        return self.provider.generate(
            query=request.query,
            model_name=model_name,
            model_cfg=model_cfg,
        )

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