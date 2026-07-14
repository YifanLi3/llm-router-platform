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


    # ------------------------------------------------------------------
    # Pipeline stages (each independently testable)
    # ------------------------------------------------------------------

    def _classify(self, query: str) -> tuple[QueryType, float]:
        lowered = query.lower()
        for qt, kws in _KEYWORDS.items():
            hits = sum(1 for kw in kws if kw in lowered)
            if hits > 0:
                return qt, min(0.95, 0.60 + 0.10 * hits)
        return "general", 0.55

    def _count_tokens(self, query: str) -> int:
        return max(1, len(query) // _CHARS_PER_TOKEN)

    def _match_rules(
        self, ctx: dict
    ) -> tuple[list[str] | None, str | None, str | None]:
        """Return (candidate_names_or_None, matched_rule_name, rule_fallback).

        No match returns (None, None, None); the whole registry becomes the pool.
        """
        for rule in self.config.router.routing_rules:
            try:
                if safe_eval(rule.condition, ctx):
                    return list(rule.candidates), rule.name, rule.fallback
            except (RuleSyntaxError, RuleRuntimeError) as e:
                # Broken rule shouldn't kill routing; log-and-continue in prod.
                # logger.warning("skipping broken rule %r: %s", rule.name, e)
                continue

        return None, None, None

    def _filter_capabilities(
        self,
        *,
        candidates: List[str] | None,
        user_tier: UserTier,
        requested_max_tokens: int,
        token_count: int,
    ) -> list[str]:
        models = self.config.router.models
        pool = candidates if candidates is not None else list(models.keys())

        tier_limit = self.config.router.tier_cost_limits.get(user_tier, float("inf"))

        eligible: list[str] = []

        for name in pool:
            if name not in models:
                continue
            m = models[name]
            if user_tier not in m.supported_tiers:
                continue
            if requested_max_tokens > m.max_tokens:
                continue
            est = self._estimate_cost(m, token_count, requested_max_tokens)
            if est > tier_limit:
                continue
            eligible.append(name)
        return eligible
            


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
