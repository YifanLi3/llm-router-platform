"""Prometheus metrics for LLM routing and inference serving."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


REQUESTS = Counter(
    "llm_router_requests",
    "Total routed inference requests.",
    ["engine", "model", "status"],
)

REQUEST_DURATION = Histogram(
    "llm_router_request_duration_seconds",
    "End-to-end inference request duration.",
    ["engine", "model"],
)

TTFT = Histogram(
    "llm_router_ttft_seconds",
    "Time to first token.",
    ["engine", "model"],
)

TPOT = Histogram(
    "llm_router_tpot_seconds",
    "Time per output token.",
    ["engine", "model"],
)

TOKENS_PER_SECOND = Histogram(
    "llm_router_tokens_per_second",
    "Output token throughput.",
    ["engine", "model"],
)

ACTIVE_REQUESTS = Gauge(
    "llm_router_active_requests",
    "Requests currently executing per engine.",
    ["engine"],
)

KV_CACHE_USAGE = Gauge(
    "llm_router_engine_kv_cache_usage",
    "KV cache usage ratio for an inference engine.",
    ["engine"],
)

FALLBACKS = Counter(
    "llm_router_fallback",
    "Fallbacks triggered after a provider failure.",
    ["from_engine", "to_engine", "reason"],
)


def record_success(
    *,
    engine: str,
    model: str,
    duration_ms: int,
    ttft_ms: float | None,
    tpot_ms: float | None,
    tokens_per_second: float | None,
) -> None:
    """Record metrics for a completed successful request."""
    REQUESTS.labels(engine=engine, model=model, status="success").inc()
    REQUEST_DURATION.labels(engine=engine, model=model).observe(duration_ms / 1000)

    if ttft_ms is not None:
        TTFT.labels(engine=engine, model=model).observe(ttft_ms / 1000)
    if tpot_ms is not None:
        TPOT.labels(engine=engine, model=model).observe(tpot_ms / 1000)
    if tokens_per_second is not None:
        TOKENS_PER_SECOND.labels(engine=engine, model=model).observe(
            tokens_per_second
        )


def record_failure(*, engine: str, model: str) -> None:
    """Record an inference request that exhausted every fallback."""
    REQUESTS.labels(engine=engine, model=model, status="error").inc()


def record_fallback(
    *,
    from_engine: str,
    to_engine: str,
    reason: str,
) -> None:
    """Record one successful fallback transition."""
    FALLBACKS.labels(
        from_engine=from_engine,
        to_engine=to_engine,
        reason=reason,
    ).inc()


def set_engine_load(
    *,
    engine: str,
    active_requests: int,
    kv_cache_usage: float,
) -> None:
    """Set gauges from the latest LoadTracker snapshot."""
    ACTIVE_REQUESTS.labels(engine=engine).set(active_requests)
    KV_CACHE_USAGE.labels(engine=engine).set(kv_cache_usage)
