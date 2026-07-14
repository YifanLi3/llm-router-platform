"""Unit tests for Phase 2's intelligent QueryRouter."""

import pytest

from app.core.config import get_config
from app.schemas import QueryRequest
from app.services.router import QueryRouter


@pytest.fixture(scope="module")
def router() -> QueryRouter:
    return QueryRouter(get_config())


def _req(query: str, tier: str = "free", max_tokens: int = 512) -> QueryRequest:
    return QueryRequest(query=query, user_id="u1", user_tier=tier,
                        max_tokens=max_tokens)


class TestClassification:
    def test_coding_keyword(self, router):
        d = router.route(_req("write a python function"))
        assert d.query_type == "coding"

    def test_analysis_keyword(self, router):
        d = router.route(_req("please analyze this quarterly trend", tier="premium"))
        assert d.query_type == "analysis"

    def test_general_fallback(self, router):
        d = router.route(_req("hello there"))
        assert d.query_type == "general"


class TestRuleMatching:
    def test_coding_rule_matched(self, router):
        d = router.route(_req("debug this python bug"))
        assert d.matched_rule == "coding_route"
        assert d.selected_model == "coding-pro"

    def test_no_rule_matched_for_greeting(self, router):
        d = router.route(_req("hi"))
        assert d.matched_rule is None
        # falls back to general-small via scoring
        assert d.selected_model == "general-small"


class TestCapabilityFilter:
    def test_free_tier_cannot_use_long_context(self, router):
        # a long analysis query would prefer long-context, but free tier
        # is not in long-context.supported_tiers -> must degrade
        d = router.route(_req("analyze " * 40, tier="free"))
        assert d.selected_model != "long-context"

    def test_premium_can_use_long_context(self, router):
        d = router.route(_req("analyze " * 40, tier="premium"))
        # long-context is now allowed; either it wins or reasoning-heavy does
        assert d.selected_model in ("long-context", "reasoning-heavy")


class TestScoreBreakdown:
    def test_breakdown_keys_present(self, router):
        d = router.route(_req("write a python function"))
        for k in ("success", "latency", "cost", "priority", "capability", "total"):
            assert k in d.score_breakdown

    def test_totals_are_between_zero_and_one(self, router):
        d = router.route(_req("hello"))
        assert 0.0 <= d.score_breakdown["total"] <= 1.0


class TestFallbackChain:
    def test_fallback_chain_excludes_selected(self, router):
        d = router.route(_req("write a python function"))
        assert d.selected_model not in d.fallback_models

    def test_fallback_chain_no_duplicates(self, router):
        d = router.route(_req("write a python function"))
        assert len(d.fallback_models) == len(set(d.fallback_models))


class TestGracefulDegradation:
    def test_max_tokens_beyond_all_models_degrades(self, router):
        # No model has 100_000 tokens capacity -> filter empties -> _degrade
        d = router.route(_req("hi", tier="enterprise", max_tokens=32000))
        assert d.selected_model == "general-small"  # default fallback
        assert "capability" in d.routing_reason or "default" in d.routing_reason.lower()