"""Config-driven intelligent router (Phase 2).

Pipeline for one request:
    classify -> tokenise -> rules -> capability filter -> score -> fallback

The public API `.route(request)` is unchanged from Phase 1; only the
internals became config-aware.
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

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
        logger.debug(
            "QueryRouter initialised",
            extra={
                "num_models": len(config.router.models),
                "num_rules":  len(config.router.routing_rules),
                "strategy":   config.router.strategy,
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, request: QueryRequest) -> RoutingDecision:
        # 1. classify + tokenise
        query_type, cls_conf = self._classify(request.query)
        token_count = self._count_tokens(request.query)
        if query_type == "general" and token_count > _LONG_CONTEXT_TOKENS:
            query_type, cls_conf = "long_context", 0.85

        logger.debug(
            "classified",
            extra={
                "query_type":  query_type,
                "cls_conf":    cls_conf,
                "token_count": token_count,
                "user_tier":   request.user_tier,
            },
        )

        # 2. rule matching
        ctx = {
            "query_type": query_type,
            "token_count": token_count,
            "user_tier": request.user_tier,
        }
        candidates, matched_rule, rule_fallback = self._match_rules(ctx)

        logger.debug(
            "rule matching done",
            extra={"matched_rule": matched_rule, "candidates": candidates},
        )

        # 3. capability filter
        eligible = self._filter_capabilities(
            candidates=candidates,
            user_tier=request.user_tier,
            requested_max_tokens=request.max_tokens,
            token_count=token_count,
        )

        logger.debug("capability filter", extra={"eligible": eligible})

        # 4. graceful degradation
        if not eligible:
            logger.warning(
                "no eligible model, degrading to default",
                extra={
                    "user_tier":   request.user_tier,
                    "query_type":  query_type,
                    "matched_rule": matched_rule,
                },
            )
            return self._degrade(
                query_type=query_type,
                token_count=token_count,
                cls_conf=cls_conf,
                matched_rule=matched_rule,
                reason="No model passed capability filter; using default.",
            )

        # 5. score & rank
        ranked = self._rank(
            eligible=eligible,
            query_type=query_type,
            token_count=token_count,
            requested_max_tokens=request.max_tokens,
        )
        top_name, top_score, top_breakdown = ranked[0]

        # 6. fallback chain
        fallback_models = self._build_fallback_chain(
            top=top_name,
            ranked_tail=[n for n, _, _ in ranked[1:]],
            rule_fallback=rule_fallback,
            model_static_fallback=self.config.router.models[top_name].fallback_model,
        )

        # 7. assemble decision
        est_cost = self._estimate_cost(
            self.config.router.models[top_name], token_count, request.max_tokens
        )
        reason = (
            (f"[rule={matched_rule}] " if matched_rule else "[no rule matched] ")
            + f"scored {len(eligible)} candidate(s); top={top_name} ({top_score:.3f})"
        )

        # One INFO line per request. Contains everything an operator needs
        # to answer "why did this request go to model X?".
        logger.info(
            "route decided",
            extra={
                "user_tier":       request.user_tier,
                "query_type":      query_type,
                "matched_rule":    matched_rule,
                "selected_model":  top_name,
                "score":           round(top_score, 4),
                "fallback_models": fallback_models,
                "est_cost":        round(est_cost, 6),
            },
        )

        return RoutingDecision(
            selected_model=top_name,
            routing_reason=reason,
            confidence=min(0.99, 0.60 + top_score * 0.4),
            query_type=query_type,
            token_count=token_count,
            classification_confidence=cls_conf,
            estimated_cost=est_cost,
            matched_rule=matched_rule,
            fallback_models=fallback_models,
            score_breakdown=top_breakdown,
        )


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
        candidates: list[str] | None,
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
                logger.warning("rule references unknown model", extra={"model": name})
                continue
            m = models[name]
            if user_tier not in m.supported_tiers:
                logger.debug(
                    "filtered: tier not supported",
                    extra={"model": name, "user_tier": user_tier},
                )
                continue
            if requested_max_tokens > m.max_tokens:
                logger.debug(
                    "filtered: max_tokens exceeds model capacity",
                    extra={"model": name, "req": requested_max_tokens, "cap": m.max_tokens},
                )
                continue
            est = self._estimate_cost(m, token_count, requested_max_tokens)
            if est > tier_limit:
                logger.debug(
                    "filtered: over tier cost limit",
                    extra={"model": name, "est_cost": est, "limit": tier_limit},
                )
                continue
            eligible.append(name)
        return eligible


    def _rank(
        self,
        *,
        eligible: list[str],
        query_type: str,
        token_count: int,
        requested_max_tokens: int,
    ) -> list[tuple[str, float, dict[str, float]]]:
        models = self.config.router.models

        latencies = [models[n].avg_latency_ms for n in eligible]
        costs = [self._estimate_cost(models[n] ,token_count, requested_max_tokens)
                for n in eligible]

        priorities = [models[n].priority for n in eligible]

        max_lat = max(latencies) or 1
        max_cost = max(costs) or 1
        max_prio = max(priorities) or 1

        scored: list[tuple[str, float, dict[str, float]]] = []

        for i, name in enumerate(eligible):
            m = models[name]
            s_success       = m.success_rate
            s_latency       = 1.0 - (latencies[i] / max_lat)
            s_cost          = 1.0 - (costs[i] / max_cost)
            s_priority      = 1.0 - (priorities[i] / max_prio)
            s_capability    = 1.0 if query_type in m.capabilities else 0.0

            total = (W_SUCCESS      * s_success
                    + W_LATENCY     * s_latency
                    + W_COST        * s_cost
                    + W_PRIORITY    * s_priority
                    + W_CAPABILITY  * s_capability)

            breakdown = {
                "success":    round(W_SUCCESS    * s_success,    4),
                "latency":    round(W_LATENCY    * s_latency,    4),
                "cost":       round(W_COST       * s_cost,       4),
                "priority":   round(W_PRIORITY   * s_priority,   4),
                "capability": round(W_CAPABILITY * s_capability, 4),
                "total":      round(total, 4),
            }

            scored.append((name, total, breakdown))

        scored.sort(key=lambda x: x[1], reverse=True)
        logger.debug(
            "ranking complete",
            extra={"ranked": [(n, round(s, 4)) for n, s, _ in scored]},
        )
        return scored
            
    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def _estimate_cost(
        self, m: ModelConfig, input_tokens: int, output_tokens: int
    ) -> float:
        return (input_tokens  / 1000.0 * m.cost_per_1k_input
              + output_tokens / 1000.0 * m.cost_per_1k_output)

    def _build_fallback_chain(
        self,
        *,
        top: str,
        ranked_tail: list[str],
        rule_fallback: str | None,
        model_static_fallback: str | None,
    ) -> list[str]:
        models = self.config.router.models
        chain: list[str] = []

        def _push(name: str | None) -> None:
            if not name or name == top or name in chain or name not in models:
                return
            chain.append(name)

        for n in ranked_tail:
            _push(n)
        _push(rule_fallback)
        _push(model_static_fallback)
        return chain

    def _degrade(
        self,
        *,
        query_type: str,
        token_count: int,
        cls_conf: float,
        matched_rule: str | None,
        reason: str,
    ) -> RoutingDecision:
        default = self.config.router.default_model
        return RoutingDecision(
            selected_model=default,
            routing_reason=reason,
            confidence=0.50,
            query_type=query_type,
            token_count=token_count,
            classification_confidence=cls_conf,
            estimated_cost=0.0,
            matched_rule=matched_rule,
            fallback_models=[],
            score_breakdown={},
        )


# ---------------------------------------------------------------------------
# Self-test:  uv run python -m app.services.router
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.core.config import get_config
    from app.core.logging import configure_logging
    configure_logging(level="DEBUG")
    router = QueryRouter(get_config())
    cases = [
        ("greeting/free",       "hello",                                              "free"),
        ("coding/free",         "write a python function to reverse a list",          "free"),
        ("analysis/premium",    "please analyze and compare these three trends " * 5, "premium"),
        ("reasoning/premium",   "why does this proof derive the theorem?",            "premium"),
        ("long/enterprise",     "a " * 700,                                           "enterprise"),
        ("expensive/free",      "please analyze deeply " * 30,                        "free"),
    ]
    for label, q, tier in cases:
        req = QueryRequest(query=q, user_id="u1", user_tier=tier, max_tokens=512)
        d = router.route(req)
        print(f"[{label:<20}] {d.selected_model:<16} "
              f"type={d.query_type:<12} rule={str(d.matched_rule):<22} "
              f"score={d.score_breakdown.get('total', 0):.3f} "
              f"fb={d.fallback_models}")
