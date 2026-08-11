"""Tests for Phase 4's background engine-load tracker."""

from __future__ import annotations

import asyncio
import time

from app.infra.load_tracker import LoadTracker
from app.schemas import RuntimeLoadSnapshot


def test_refresh_once_caches_engine_snapshot():
    async def fetch_vllm_load() -> RuntimeLoadSnapshot:
        return RuntimeLoadSnapshot(
            engine="vllm",
            kv_cache_usage=0.42,
            active_requests=3,
            queue_depth=1,
            gpu_utilization=0.75,
            updated_at=time.time(),
        )

    async def scenario() -> None:
        tracker = LoadTracker()
        tracker.register("vllm", fetch_vllm_load)

        assert tracker.get_snapshot("vllm") is None

        await tracker.refresh_once()

        snapshot = tracker.get_snapshot("vllm")
        assert snapshot is not None
        assert snapshot.engine == "vllm"
        assert snapshot.kv_cache_usage == 0.42
        assert snapshot.active_requests == 3
        assert snapshot.queue_depth == 1

    asyncio.run(scenario())


def test_failed_engine_refresh_does_not_crash_tracker():
    async def failing_fetcher() -> RuntimeLoadSnapshot:
        raise ConnectionError("vLLM is offline")

    async def scenario() -> None:
        tracker = LoadTracker()
        tracker.register("vllm", failing_fetcher)

        await tracker.refresh_once()

        # A failing engine is logged, but other work can continue.
        assert tracker.get_snapshot("vllm") is None

    asyncio.run(scenario())


def test_background_polling_stops_cleanly():
    calls = 0

    async def fetch_local_load() -> RuntimeLoadSnapshot:
        nonlocal calls
        calls += 1
        return RuntimeLoadSnapshot(
            engine="local_mock",
            updated_at=time.time(),
        )

    async def scenario() -> None:
        tracker = LoadTracker(poll_interval_seconds=0.01)
        tracker.register("local_mock", fetch_local_load)

        await tracker.start()
        await asyncio.sleep(0.03)
        await tracker.stop()

        assert calls >= 1
        assert tracker.get_snapshot("local_mock") is not None

    asyncio.run(scenario())
