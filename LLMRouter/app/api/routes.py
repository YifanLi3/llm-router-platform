"""HTTP endpoints.
Endpoints in this module are pure "glue" -- they only do:
1. parse the incoming request (already validated by Pydantic)
2. call the router and inference engine
3. assemble the wire-format InferenceResponse to return
Any real logic belongs in app/services/.
"""

import json
import time
import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_config
from app.core.telemetry import RequestRecord, TelemetryStore
from app.core.tokenization import count_tokens
from app.infra import metrics
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

def get_query_router(request: Request) -> QueryRouter:
    """Return the lifespan-managed router with access to LoadTracker."""
    router = getattr(request.app.state, "query_router", None)
    if router is None:
        # Supports direct TestClient use outside its lifespan context.
        return QueryRouter(get_config())
    return router

@lru_cache
def get_inference_engine() -> InferenceEngine:
    return InferenceEngine(get_config())


@lru_cache
def get_telemetry() -> TelemetryStore:
    return TelemetryStore()

# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@api_router.get("/metrics", response_class=Response)
def prometheus_metrics() -> Response:
    """Expose Prometheus text metrics for monitoring systems."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@api_router.get("/health", response_model=HealthResponse)
def health(
    request: Request,
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
) -> HealthResponse:
    cfg = query_router.config
    providers = engine.provider_health()
    tracker = getattr(request.app.state, "load_tracker", None)
    engines: dict[str, dict] = {}
    for engine_name, engine_cfg in cfg.engines.items():
        snapshot = tracker.get_snapshot(engine_name) if tracker else None
        engines[engine_name] = {
            "enabled": engine_cfg.enabled,
            "healthy": engine_name == "local_mock"
            or (engine_cfg.enabled and snapshot is not None),
            "active_requests": snapshot.active_requests if snapshot else 0,
            "queue_depth": snapshot.queue_depth if snapshot else 0,
            "kv_cache_usage": snapshot.kv_cache_usage if snapshot else 0.0,
        }

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
                details={"providers": providers, "engines": engines},
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
    if decision.runtime_load is not None:
        metrics.set_engine_load(
            engine=decision.engine,
            active_requests=decision.runtime_load.active_requests,
            kv_cache_usage=decision.runtime_load.kv_cache_usage,
        )

    try:
        result = engine.run(request, decision)
    except InferenceExhaustedError as error:
        metrics.record_failure(
            engine=decision.engine,
            model=decision.selected_model,
        )
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
            engine=decision.engine,
            runtime_load=decision.runtime_load,
            load_score=decision.load_score,
        ),
        provider=result.provider,
        error=None,
        inference_metrics=result.metrics,
    )
    metrics.record_success(
        engine=result.engine,
        model=result.model_name,
        duration_ms=result.latency_ms,
        ttft_ms=result.metrics.ttft_ms,
        tpot_ms=result.metrics.tpot_ms,
        tokens_per_second=result.metrics.tokens_per_second,
    )
    if result.fallback_used:
        metrics.record_fallback(
            from_engine=decision.engine,
            to_engine=result.engine,
            reason="provider_error",
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


@api_router.post("/route/stream")
async def route_stream(
    request: QueryRequest,
    query_router: QueryRouter = Depends(get_query_router),
    engine: InferenceEngine = Depends(get_inference_engine),
    telemetry: TelemetryStore = Depends(get_telemetry),
) -> EventSourceResponse:
    """Stream routed inference as meta, token, done, and error SSE events."""
    query_id = str(uuid.uuid4())
    decision = query_router.route(request)

    if decision.runtime_load is not None:
        metrics.set_engine_load(
            engine=decision.engine,
            active_requests=decision.runtime_load.active_requests,
            kv_cache_usage=decision.runtime_load.kv_cache_usage,
        )

    routing = RoutingInfo(
        reason=decision.routing_reason,
        confidence=decision.confidence,
        query_type=decision.query_type,
        token_count=decision.token_count,
        classification_confidence=decision.classification_confidence,
        estimated_cost=decision.estimated_cost,
        matched_rule=decision.matched_rule,
        fallback_models=decision.fallback_models,
        engine=decision.engine,
        runtime_load=decision.runtime_load,
        load_score=decision.load_score,
    )

    async def events():
        started_at = time.perf_counter()
        first_token_at: float | None = None
        token_timestamps: list[float] = []
        output_parts: list[str] = []
        final_model = decision.selected_model
        final_provider = "unknown"
        final_engine = decision.engine
        fallback_used = False
        fallback_notice_sent = False

        yield {
            "event": "meta",
            "data": json.dumps(
                {
                    "query_id": query_id,
                    "model_name": decision.selected_model,
                    "engine": decision.engine,
                    "routing": routing.model_dump(mode="json"),
                }
            ),
        }

        try:
            async for chunk in engine.stream(request, decision):
                now = time.perf_counter()
                if first_token_at is None:
                    first_token_at = now
                token_timestamps.append(now)
                output_parts.append(chunk.delta)
                final_model = chunk.model_name
                final_provider = chunk.provider
                final_engine = chunk.engine
                fallback_used = chunk.fallback_used

                if fallback_used and not fallback_notice_sent:
                    fallback_notice_sent = True
                    yield {
                        "event": "error",
                        "data": json.dumps(
                            {
                                "error": "Primary provider failed; continuing on fallback.",
                                "fallback_used": True,
                            }
                        ),
                    }

                yield {
                    "event": "token",
                    "data": json.dumps({"delta": chunk.delta}),
                }

            finished_at = time.perf_counter()
            total_latency_ms = int((finished_at - started_at) * 1000)
            ttft_ms = (
                (first_token_at - started_at) * 1000
                if first_token_at is not None
                else None
            )
            tpot_ms = None
            if len(token_timestamps) > 1:
                tpot_ms = (
                    (token_timestamps[-1] - token_timestamps[0])
                    / (len(token_timestamps) - 1)
                    * 1000
                )

            response_text = "".join(output_parts)
            input_tokens = count_tokens(request.query)
            output_tokens = count_tokens(response_text)
            tokens_per_second = (
                output_tokens / (total_latency_ms / 1000)
                if output_tokens and total_latency_ms
                else None
            )
            model_cfg = engine.config.router.models[final_model]
            cost_usd = (
                input_tokens / 1000 * model_cfg.cost_per_1k_input
                + output_tokens / 1000 * model_cfg.cost_per_1k_output
            )

            metrics.record_success(
                engine=final_engine,
                model=final_model,
                duration_ms=total_latency_ms,
                ttft_ms=ttft_ms,
                tpot_ms=tpot_ms,
                tokens_per_second=tokens_per_second,
            )
            if fallback_used:
                metrics.record_fallback(
                    from_engine=decision.engine,
                    to_engine=final_engine,
                    reason="provider_error",
                )

            telemetry.record(
                RequestRecord(
                    query_id=query_id,
                    user_tier=request.user_tier,
                    model_name=final_model,
                    provider=final_provider,
                    success=True,
                    latency_ms=total_latency_ms,
                    cost_usd=cost_usd,
                    cached=False,
                )
            )

            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "model_name": final_model,
                        "provider": final_provider,
                        "fallback_used": fallback_used,
                        "tokens": {
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                        },
                        "cost_usd": cost_usd,
                        "metrics": {
                            "ttft_ms": ttft_ms,
                            "tpot_ms": tpot_ms,
                            "tokens_per_second": tokens_per_second,
                            "total_latency_ms": total_latency_ms,
                        },
                    }
                ),
            }
        except InferenceExhaustedError as error:
            metrics.record_failure(
                engine=decision.engine,
                model=decision.selected_model,
            )
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
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": "No configured inference model could serve this request.",
                        "fallback_used": bool(decision.fallback_models),
                        "attempted_models": error.attempted_models,
                        "provider_errors": error.provider_errors,
                    }
                ),
            }

    return EventSourceResponse(events())