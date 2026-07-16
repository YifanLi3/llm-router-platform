"""HTTP endpoints.
Endpoints in this module are pure "glue" -- they only do:
1. parse the incoming request (already validated by Pydantic)
2. call the router and inference engine
3. assemble the wire-format InferenceResponse to return
Any real logic belongs in app/services/.
"""

import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends

from app.core.config import get_config
from app.schemas import (
    HealthResponse,
    InferenceResponse,
    QueryRequest,
    RoutingInfo,
    ServiceHealth,
    TokenUsage,
)
from app.services.inference import InferenceEngine
from app.services.router import QueryRouter

api_router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons: built once on first call, reused for the lifetime of the process
# ---------------------------------------------------------------------------

@lru_cache
def get_query_router() -> QueryRouter:
    return QueryRouter(get_config())

@lru_cache
def get_inference_engine() -> InferenceEngine:
    return InferenceEngine(get_config())

# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        services={
            "router":    ServiceHealth(healthy=True),
            "inference": ServiceHealth(healthy=True),
        },
    )

# ---------------------------------------------------------------------------
# POST /route
# ---------------------------------------------------------------------------

@api_router.post("/route", response_model=InferenceResponse)
def route(
    request: QueryRequest,
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
) -> InferenceResponse:
    query_id = str(uuid.uuid4())
    decision = query_router.route(request)
    result = engine.run(request, decision)
    return InferenceResponse(
        query_id=query_id,
        response=result.response_text,
        model_name=result.model_name,
        tokens=TokenUsage(
            input=result.input_tokens,
            output=result.output_tokens,
            total=result.input_tokens + result.output_tokens,
        ),
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        cached=result.cached,
        routing=RoutingInfo(
            reason=decision.routing_reason,
            confidence=decision.confidence,
            query_type=decision.query_type,
            token_count=decision.token_count,
            classification_confidence=decision.classification_confidence,
            estimated_cost=decision.estimated_cost,
            matched_rule=decision.matched_rule,
            fallback_models=decision.fallback_models,
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
            attempted_models=result.attempted_models,
            provider_errors=result.provider_errors,
        ),
        provider=result.provider,
        error=None,
    )