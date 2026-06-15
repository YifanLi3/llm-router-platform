"""Rule-based query router for Phase 1.

Phase 1 routes purely by hard-coded rules, in this order:

1. very long query   -> long-context model
2. coding keywords   -> coding-pro model
3. everything else   -> the default model from config.yaml

Phase 2 will replace these rules with a config-driven rule engine
plus weighted scoring; the public interface (route()) will stay the
same so callers don't need to change.
"""

from app.schemas import AppConfig, QueryRequest, RoutingDecision


CODING_KEYWORDS = ("code", "function", "class", "bug", "python")
LONG_QUERY_CHAR_THRESHOLD = 1000


class QueryRouter:
    """Map a QueryRequest to a RoutingDecision."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def route(self, request: QueryRequest) -> RoutingDecision:
        query = request.query

        if len(query) > LONG_QUERY_CHAR_THRESHOLD:
            return self._decide(
                model_name="long-context",
                reason=f"Long input ({len(query)} chars) routed to long-context model.",
                confidence=0.90,
                query_type="long_context",
            )

        lowered = query.lower()
        if any(kw in lowered for kw in CODING_KEYWORDS):
            return self._decide(
                model_name="coding-pro",
                reason="Detected coding-related keywords in the query.",
                confidence=0.82,
                query_type="coding",
            )

        return self._decide(
            model_name=self.config.router.default_model,
            reason="Using default general-purpose model.",
            confidence=0.65,
            query_type="general",
        )

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
