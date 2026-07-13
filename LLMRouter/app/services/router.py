"""Config-driven intelligent router (Phase 2).

Pipeline for one request:
    classify -> tokenise -> rules -> capability filter -> score -> fallback

The public API `.route(request)` is unchanged from Phase 1; only the
internals became config-aware.
"""

from __future__ import annotations

from app.core.rules import RuleRuntimeError, RuleSyntaxError, safe_eval

from app.schemas import (
    AppConfig,
    ModelConfig,
    QueryRequest,
    QueryType,
    RoutingDecision,
    UserTier,
)

# ---------------------------------------------------------------------------
# Classification & tokenisation constants
# ---------------------------------------------------------------------------

# Keywords per query type; first bucket with a hit wins.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "coding":    ("code", "function", "class", "bug", "python", "javascript",
                  "typescript", "compile", "traceback", "algorithm", "debug"),
    "analysis":  ("analyze", "analysis", "compare", "summari", "review",
                  "evaluate", "trend"),
    "reasoning": ("why", "reason", "because", "therefore", "proof",
                  "prove", "derive"),
}

_CHARS_PER_TOKEN = 4                # rough English/code approximation
_LONG_CONTEXT_TOKENS = 500          # promote "general" -> "long_context" above this

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------
W_SUCCESS    = 0.20
W_LATENCY    = 0.15
W_COST       = 0.15
W_PRIORITY   = 0.15
W_CAPABILITY = 0.35
assert abs(W_SUCCESS + W_LATENCY + W_COST + W_PRIORITY + W_CAPABILITY - 1.0) < 1e-9

class QueryRouter:
    """Map a QueryRequest to a RoutingDecision using config + scoring."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, request: QueryRequest) -> RoutingDecision:
        # 1. classify + tokenise
        query_type, cls_conf = self._classify(request.query)
        token_count = self._count_tokens(request.query)
        if query_type == "general" and token_count > _LONG_CONTEXT_TOKENS:
            query_type, cls_conf = "long_context", 0.85

    def _decide(
        self,
        *,
        model_name: str,
        reason: str,
        confidence: float,
        query_type: str,
    ) -> RoutingDecision:
        """Build a RoutingDecision, falling back to the default model if
        the requested one isn't declared in config.yaml.
        """
        models = self.config.router.models
        default = self.config.router.default_model

        if model_name not in models:
            return RoutingDecision(
                selected_model=default,
                routing_reason=(
                    f"Requested model '{model_name}' not in config; "
                    f"falling back to default '{default}'."
                ),
                confidence=0.50,
                query_type=query_type,
            )

        return RoutingDecision(
            selected_model=model_name,
            routing_reason=reason,
            confidence=confidence,
            query_type=query_type,
        )


# ---------------------------------------------------------------------------
# Self-test:  uv run python -m app.services.router
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from app.core.config import get_config

    router = QueryRouter(get_config())

    cases = [
        ("normal greeting", "hello"),
        ("coding keyword",  "Write a python function to reverse a list"),
        ("class keyword",   "Help me debug this class"),
        ("long input",      "a " * 600),
    ]

    for label, q in cases:
        req = QueryRequest(query=q, user_id="u1", user_tier="free")
        d = router.route(req)
        print(f"[{label:<18}] -> model={d.selected_model:<14} "
              f"type={d.query_type:<13} reason={d.routing_reason}")
