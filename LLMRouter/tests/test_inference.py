"""Tests for provider dispatch and fallback execution."""

from app.core.config import get_config
from app.schemas import QueryRequest, RoutingDecision
from app.services.inference import InferenceEngine

import pytest
from app.services.inference import InferenceExhaustedError


def test_local_model_succeeds_without_fallback():
    engine = InferenceEngine(get_config())

    result = engine.run(
        QueryRequest(query="hello", user_id="u1"),
        RoutingDecision(
            selected_model="general-small",
            routing_reason="test",
            confidence=1.0,
        ),
    )

    assert result.model_name == "general-small"
    assert result.provider == "local"
    assert result.fallback_used is False
    assert result.attempted_models == ["general-small"]
    assert result.provider_errors == {}


def test_unavailable_openai_falls_back_to_local(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = InferenceEngine(get_config())

    result = engine.run(
        QueryRequest(query="explain this proof", user_id="u1", user_tier="premium"),
        RoutingDecision(
            selected_model="reasoning-heavy",
            routing_reason="test",
            confidence=1.0,
            fallback_models=["coding-pro", "general-small"],
        ),
    )

    # reasoning-heavy is configured with provider=openai and requires
    # OPENAI_API_KEY. It is deliberately unavailable in local Phase 2.
    assert result.model_name == "coding-pro"
    assert result.provider == "local"
    assert result.fallback_used is True
    assert result.attempted_models == ["reasoning-heavy", "coding-pro"]
    assert "reasoning-heavy" in result.provider_errors
    assert "OPENAI_API_KEY" in result.provider_errors["reasoning-heavy"]

def test_all_failed_models_raise_explainable_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = InferenceEngine(get_config())

    with pytest.raises(InferenceExhaustedError) as exc_info:
        engine.run(
            QueryRequest(
                query="explain this proof",
                user_id="u1",
                user_tier="premium",
            ),
            RoutingDecision(
                selected_model="reasoning-heavy",
                routing_reason="test",
                confidence=1.0,
                fallback_models=[],
            ),
        )

    error = exc_info.value
    assert error.attempted_models == ["reasoning-heavy"]
    assert "reasoning-heavy" in error.provider_errors
    assert "OPENAI_API_KEY" in error.provider_errors["reasoning-heavy"]