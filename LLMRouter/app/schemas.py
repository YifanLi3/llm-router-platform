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


class ServiceHealth(BaseModel):
    healthy: bool


class HealthResponse(BaseModel):
    """Body of GET /health response."""

    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    services: dict[str, ServiceHealth] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2) Internal models -- passed between router and inference engine only
# ---------------------------------------------------------------------------

QueryType = Literal["general", "coding", "long_context"]


class RoutingDecision(BaseModel):
    """Output of QueryRouter.route(). Internal to the service."""

    selected_model: str
    routing_reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    query_type: QueryType = "general"


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


class RouterConfig(BaseModel):
    default_model: str
    models: dict[str, ModelConfig]


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

    print("[3] invalid user_tier should be rejected:")
    try:
        QueryRequest(query="hi", user_id="u1", user_tier="vip")  # type: ignore[arg-type]
    except ValidationError as e:
        print("     OK ->", e.errors()[0]["msg"])

    print("[4] nested InferenceResponse roundtrip:")
    resp = InferenceResponse(
        query_id="q-1",
        response="Echo from general-small: hello",
        model_name="general-small",
        tokens=TokenUsage(input=1, output=4, total=5),
        cost_usd=0.000009,
        latency_ms=1,
        cached=False,
        routing=RoutingInfo(reason="default", confidence=0.65, query_type="general"),
    )
    print("    ", resp.model_dump())
