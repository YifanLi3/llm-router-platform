"""Pydantic data contracts shared across the LLM Router.

The file is organised in three sections, each with a different lifetime:

1. Wire models    -> cross the HTTP boundary (request / response bodies)
2. Internal models -> passed between router and inference engine; never leak to HTTP
3. Config models  -> mirror config.yaml; produced by app/core/config.py

Keeping these three categories visually separated makes it obvious which
schema you may change without breaking which contract.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1) Wire models -- request / response bodies for HTTP endpoints
# ---------------------------------------------------------------------------

UserTier = Literal["free", "premium", "enterprise"]

QueryType = Literal["general", "coding", "analysis", "reasoning", "long_context"]


class QueryRequest(BaseModel):
    """Body of POST /route.

    `query` must be non-empty -- Pydantic raises 422 automatically so we
    do not need to validate it again in the route handler.
    """

    query: str = Field(min_length=1, description="User prompt; non-empty")
    user_id: str = Field(min_length=1)
    user_tier: UserTier = "free"
    max_tokens: int = Field(default=512, ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0


class RoutingInfo(BaseModel):
    """Routing explanation surfaced to the client in /route responses."""

    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    query_type: str = "general"

    token_count: int = 0
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_cost: float=Field(default=0.0, ge=0.0)
    matched_rule: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None
    attempted_models: list[str] = Field(default_factory=list)
    provider_errors: dict[str, str] = Field(default_factory=dict)


class InferenceResponse(BaseModel):
    """Body of POST /route response."""

    query_id: str
    response: str
    model_name: str
    tokens: TokenUsage
    cost_usd: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    cached: bool = False
    routing: RoutingInfo

    provider: str = "local"
    error: str | None = None


class ServiceHealth(BaseModel):
    healthy: bool
    details: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Body of GET /health response."""

    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    services: dict[str, ServiceHealth] = Field(default_factory=dict)


class ModelAnalytics(BaseModel):
    model_name: str
    provider: str
    request_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    average_latency_ms: float = Field(ge=0.0)
    p95_latency_ms: float = Field(ge=0.0)
    total_cost_usd: float = Field(ge=0.0)


class TierAnalytics(BaseModel):
    user_tier: UserTier
    request_count: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0.0)


class AnalyticsResponse(BaseModel):
    total_requests: int = Field(ge=0)
    successful_requests: int = Field(ge=0)
    failed_requests: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    average_latency_ms: float = Field(ge=0.0)
    p95_latency_ms: float = Field(ge=0.0)
    total_cost_usd: float = Field(ge=0.0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0)
    models: list[ModelAnalytics] = Field(default_factory=list)
    user_tiers: list[TierAnalytics] = Field(default_factory=list)


class QualityDashboardResponse(BaseModel):
    request_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    error_rate: float = Field(ge=0.0, le=1.0)
    average_latency_ms: float = Field(ge=0.0)
    p95_latency_ms: float = Field(ge=0.0)
    slo_latency_compliant: bool
    hotspots: list[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    router_mode: str
    telemetry_records: int = Field(ge=0)
    details: dict = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    query_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    accepted: bool
    feedback_count: int = Field(ge=0)


# ---------------------------------------------------------------------------
# 2) Internal models -- passed between router and inference engine only
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """Output of QueryRouter.route(). Internal to the service."""

    selected_model: str
    routing_reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    query_type: QueryType = "general"

    token_count: int = 0
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_cost: float=Field(default=0.0, ge=0.0)
    matched_rule: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class InferenceResult(BaseModel):
    """Output of InferenceEngine.run().

    The API layer converts this into InferenceResponse before returning to
    the client (e.g. it folds input_tokens/output_tokens into TokenUsage).
    """

    response_text: str
    model_name: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    cached: bool = False

    provider: str = "local"
    fallback_used: bool = False
    fallback_reason: str | None = None
    attempted_models: list[str] = Field(default_factory=list)
    provider_errors: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 3) Config models -- mirror the structure of config.yaml
# ---------------------------------------------------------------------------


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8081, ge=1, le=65535)


class ModelConfig(BaseModel):
    """One entry under router.models in config.yaml."""

    provider: str
    max_tokens: int = Field(ge=1)
    cost_per_1k_input: float = Field(ge=0.0)
    cost_per_1k_output: float = Field(ge=0.0)
    priority: int = Field(default=99, ge=1)
    capabilities: list[str] = Field(default_factory=list)

    provider_model: str | None = None
    supported_tiers: list[UserTier] = Field(
        default_factory=lambda: ["free", "premium", "enterprise"]
    )
    fallback_model: str | None = None
    api_key_env: str | None = None
    avg_latency_ms: int = Field(default=100, ge=0)
    success_rate: float = Field(default=0.99, ge=0.0, le=1.0)

class RoutingRuleConfig(BaseModel):
    """One entry under router.routing_rules in config.yaml."""

    name: str
    condition: str                                  # AST-evaluated boolean expression
    candidates: list[str] = Field(default_factory=list)
    fallback: str | None = None
    reason: str = ""


class RouterConfig(BaseModel):
    default_model: str
    models: dict[str, ModelConfig]

    strategy: Literal["rule_only", "intelligent"] = "intelligent"
    routing_rules: list[RoutingRuleConfig] = Field(default_factory=list)
    tier_cost_limits: dict[str, float] = Field(default_factory=dict)

class AppConfig(BaseModel):
    api: ApiConfig
    router: RouterConfig


# ---------------------------------------------------------------------------
# Self-test: `uv run python -m app.schemas`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pydantic import ValidationError

    print("[1] valid QueryRequest:")
    req = QueryRequest(query="hello", user_id="u1", user_tier="free")
    print("    ", req.model_dump())

    print("[2] empty query should be rejected:")
    try:
        QueryRequest(query="", user_id="u1", user_tier="free")
    except ValidationError as e:
        print("     OK ->", e.errors()[0]["msg"])

    print("[3] new RoutingDecision fields default sensibly:")
    d = RoutingDecision(
        selected_model="general-small",
        routing_reason="default",
        confidence=0.65,
    )
    print("     token_count     =", d.token_count)
    print("     fallback_models =", d.fallback_models)
    print("     matched_rule    =", d.matched_rule)

    print("[4] new RoutingRuleConfig works:")
    rule = RoutingRuleConfig(
        name="coding_rule",
        condition="query_type == 'coding'",
        candidates=["coding-pro"],
        reason="Detected coding-related keywords",
    )
    print("    ", rule.model_dump())
    print("[5] InferenceResult.provider defaults to 'mock' (backwards compat):")
    result = InferenceResult(
        response_text="hi",
        model_name="general-small",
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0,
        latency_ms=0,
    )
    print("     provider         =", result.provider)
    print("     attempted_models =", result.attempted_models)
