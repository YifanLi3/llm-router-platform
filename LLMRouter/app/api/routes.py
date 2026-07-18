"""HTTP endpoints.
Endpoints in this module are pure "glue" -- they only do:
1. parse the incoming request (already validated by Pydantic)
2. call the router and inference engine
3. assemble the wire-format InferenceResponse to return
Any real logic belongs in app/services/.
"""

import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_config
from app.core.telemetry import RequestRecord, TelemetryStore
from app.schemas import (
    AnalyticsResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    InferenceResponse,
    QueryRequest,
    QualityDashboardResponse,
    RoutingInfo,
    ServiceHealth,
    StatusResponse,
    TokenUsage,
    LogsResponse,
)
from app.services.inference import InferenceEngine, InferenceExhaustedError
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


@lru_cache
def get_telemetry() -> TelemetryStore:
    return TelemetryStore()

# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@api_router.get("/health", response_model=HealthResponse)
def health(
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
) -> HealthResponse:
    cfg = query_router.config
    providers = engine.provider_health()

    all_providers_healthy = all(
        provider["healthy"] for provider in providers.values()
    )
    status = "healthy" if all_providers_healthy else "degraded"

    return HealthResponse(
        status=status,
        services={
            "router": ServiceHealth(
                healthy=True,
                details={
                    "default_model": cfg.router.default_model,
                    "model_count": len(cfg.router.models),
                    "strategy": cfg.router.strategy,
                    "rule_count": len(cfg.router.routing_rules),
                },
            ),
            "inference": ServiceHealth(
                healthy=any(
                    provider["healthy"] for provider in providers.values()
                ),
                details={"providers": providers},
            ),
        },
    )


@api_router.get("/status", response_model=StatusResponse)
def status(
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> StatusResponse:
    providers = engine.provider_health()
    overall = "healthy" if all(item["healthy"] for item in providers.values()) else "degraded"
    return StatusResponse(
        status=overall,
        router_mode=query_router.config.router.strategy,
        telemetry_records=telemetry.record_count,
        details={"providers": providers},
    )


@api_router.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> AnalyticsResponse:
    return AnalyticsResponse.model_validate(telemetry.analytics())


@api_router.get("/quality/dashboard", response_model=QualityDashboardResponse)
def quality_dashboard(
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> QualityDashboardResponse:
    return QualityDashboardResponse.model_validate(telemetry.quality_dashboard())


@api_router.post("/feedback", response_model=FeedbackResponse)
def feedback(
    request: FeedbackRequest,
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> FeedbackResponse:
    feedback_count = telemetry.submit_feedback()
    return FeedbackResponse(accepted=True, feedback_count=feedback_count)

@api_router.get("/logs", response_model=LogsResponse)
def logs(
    limit: int = Query(default=50, ge=1, le=200),
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> LogsResponse:
    return LogsResponse(
        records=telemetry.recent_records(limit),
        feedback_count=telemetry.feedback_count,
    )

# ---------------------------------------------------------------------------
# POST /route
# ---------------------------------------------------------------------------

@api_router.post("/route", response_model=InferenceResponse)
def route(
    request: QueryRequest,
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> InferenceResponse:
    query_id = str(uuid.uuid4())
    decision = query_router.route(request)
    try:
        result = engine.run(request, decision)
    except InferenceExhaustedError as error:
        telemetry.record(
            RequestRecord(
                query_id=query_id,
                user_tier=request.user_tier,
                model_name=decision.selected_model,
                provider="unavailable",
                success=False,
                latency_ms=0,
                cost_usd=0.0,
                cached=False,
                error=str(error),
            )
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "No configured inference model could serve this request.",
                "attempted_models": error.attempted_models,
                "provider_errors": error.provider_errors,
            },
        ) from error

    response = InferenceResponse(
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
    telemetry.record(
        RequestRecord(
            query_id=query_id,
            user_tier=request.user_tier,
            model_name=result.model_name,
            provider=result.provider,
            success=True,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            cached=result.cached,
        )
    )
    return response