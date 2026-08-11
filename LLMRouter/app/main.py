"""FastAPI application setup and lifecycle management."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.core.config import get_config
from app.infra.load_tracker import LoadTracker
from app.providers.vllm import VLLMProvider
from app.schemas import RuntimeLoadSnapshot


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start and stop background inference-infrastructure components."""
    cfg = get_config()
    tracker = LoadTracker(poll_interval_seconds=2.0)

    async def fetch_local_mock_load() -> RuntimeLoadSnapshot:
        """Local Echo provider has no queue, GPU, or KV cache."""
        return RuntimeLoadSnapshot(
            engine="local_mock",
            kv_cache_usage=0.0,
            active_requests=0,
            queue_depth=0,
            gpu_utilization=None,
            updated_at=time.time(),
        )

    tracker.register("local_mock", fetch_local_mock_load)

    vllm_config = cfg.engines.get("vllm")
    if vllm_config is not None and vllm_config.enabled:
        vllm_provider = VLLMProvider(vllm_config)
        tracker.register("vllm", vllm_provider.fetch_runtime_load)

    app.state.load_tracker = tracker
    await tracker.refresh_once()
    await tracker.start()

    try:
        yield
    finally:
        await tracker.stop()


app = FastAPI(
    title="LLM Router & Execution Platform",
    lifespan=lifespan,
)
app.include_router(api_router)


def run() -> None:
    """Run the API with the host and port from config.yaml."""
    import uvicorn

    from app.core.logging import configure_logging

    configure_logging()
    cfg = get_config()

    uvicorn.run(
        "app.main:app",
        host=cfg.api.host,
        port=cfg.api.port,
    )