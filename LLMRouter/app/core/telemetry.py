"""In-memory telemetry backing the Phase 3 dashboard endpoints.

This store intentionally keeps a bounded, process-local history. It is enough
for local development and demonstrates the data flow; a production deployment
would replace it with durable metrics and event storage.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime, timezone


_MAX_RECORDS = 10_000
_SLO_P95_LATENCY_MS = 1_000


@dataclass(frozen=True)
class RequestRecord:
    query_id: str
    user_tier: str
    model_name: str
    provider: str
    success: bool
    latency_ms: int
    cost_usd: float
    cached: bool
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _percentile_95(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, (len(ordered) * 95 + 99) // 100 - 1)
    return float(ordered[index])


class TelemetryStore:
    """Thread-safe, bounded telemetry store for one API process."""

    def __init__(self) -> None:
        self._records: deque[RequestRecord] = deque(maxlen=_MAX_RECORDS)
        self._feedback_count = 0
        self._lock = Lock()

    def record(self, record: RequestRecord) -> None:
        with self._lock:
            self._records.append(record)

    def submit_feedback(self) -> int:
        with self._lock:
            self._feedback_count += 1
            return self._feedback_count

    def analytics(self) -> dict:
        with self._lock:
            records = list(self._records)

        total = len(records)
        successful = sum(record.success for record in records)
        failed = total - successful
        latencies = [record.latency_ms for record in records]
        total_cost = sum(record.cost_usd for record in records)
        cached = sum(record.cached for record in records)

        by_model: dict[tuple[str, str], list[RequestRecord]] = defaultdict(list)
        by_tier: dict[str, list[RequestRecord]] = defaultdict(list)
        for record in records:
            by_model[(record.model_name, record.provider)].append(record)
            by_tier[record.user_tier].append(record)

        models = [
            {
                "model_name": model_name,
                "provider": provider,
                "request_count": len(group),
                "success_rate": sum(item.success for item in group) / len(group),
                "average_latency_ms": sum(item.latency_ms for item in group) / len(group),
                "p95_latency_ms": _percentile_95([item.latency_ms for item in group]),
                "total_cost_usd": sum(item.cost_usd for item in group),
            }
            for (model_name, provider), group in sorted(by_model.items())
        ]
        user_tiers = [
            {
                "user_tier": tier,
                "request_count": len(group),
                "total_cost_usd": sum(item.cost_usd for item in group),
            }
            for tier, group in sorted(by_tier.items())
        ]

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total if total else 0.0,
            "average_latency_ms": sum(latencies) / total if total else 0.0,
            "p95_latency_ms": _percentile_95(latencies),
            "total_cost_usd": total_cost,
            "cache_hit_rate": cached / total if total else 0.0,
            "models": models,
            "user_tiers": user_tiers,
        }

    def quality_dashboard(self) -> dict:
        analytics = self.analytics()
        hotspots = [
            model["model_name"]
            for model in analytics["models"]
            if model["request_count"] >= 1
            and model["p95_latency_ms"] > _SLO_P95_LATENCY_MS
        ]
        return {
            "request_count": analytics["total_requests"],
            "success_rate": analytics["success_rate"],
            "error_rate": 1.0 - analytics["success_rate"],
            "average_latency_ms": analytics["average_latency_ms"],
            "p95_latency_ms": analytics["p95_latency_ms"],
            "slo_latency_compliant": analytics["p95_latency_ms"] <= _SLO_P95_LATENCY_MS,
            "hotspots": hotspots,
        }

    def recent_records(self, limit: int = 50) -> list[dict]:
        """Return the newest telemetry records for dashboard troubleshooting."""
        with self._lock:
            records = list(self._records)[-limit:]
        return [
            {
                "created_at": record.created_at,
                "query_id": record.query_id,
                "user_tier": record.user_tier,
                "model_name": record.model_name,
                "provider": record.provider,
                "success": record.success,
                "latency_ms": record.latency_ms,
                "cost_usd": record.cost_usd,
                "cached": record.cached,
                "error": record.error,
            }
            for record in reversed(records)
        ]

    @property
    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def feedback_count(self) -> int:
        with self._lock:
            return self._feedback_count