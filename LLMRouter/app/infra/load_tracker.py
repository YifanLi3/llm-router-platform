"""Background collection and in-memory caching of inference-engine load."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from threading import Lock

from app.schemas import RuntimeLoadSnapshot

logger = logging.getLogger(__name__)

LoadFetcher = Callable[[], Awaitable[RuntimeLoadSnapshot]]


class LoadTracker:
    """Poll registered engines and cache their most recent load snapshots."""

    def __init__(self, poll_interval_seconds: float = 2.0) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._fetchers: dict[str, LoadFetcher] = {}
        self._snapshots: dict[str, RuntimeLoadSnapshot] = {}
        self._lock = Lock()

        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def register(self, engine: str, fetcher: LoadFetcher) -> None:
        """Register one async function that reads an engine's live load."""
        self._fetchers[engine] = fetcher

    def get_snapshot(self, engine: str) -> RuntimeLoadSnapshot | None:
        """Return the latest cached snapshot without waiting for network I/O."""
        with self._lock:
            return self._snapshots.get(engine)

    async def refresh_once(self) -> None:
        """Fetch each registered engine once; one failure never stops others."""
        await asyncio.gather(
            *(
                self._refresh_engine(engine, fetcher)
                for engine, fetcher in self._fetchers.items()
            )
        )

    async def _refresh_engine(self, engine: str, fetcher: LoadFetcher) -> None:
        try:
            snapshot = await fetcher()
        except Exception as error:
            logger.warning(
                "could not refresh engine load",
                extra={"engine": engine, "error": str(error)},
            )
            return

        with self._lock:
            self._snapshots[engine] = snapshot

    async def start(self) -> None:
        """Start the periodic polling task once."""
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())
            logger.info(
                "load tracker started",
                extra={"poll_interval_seconds": self._poll_interval_seconds},
            )

    async def stop(self) -> None:
        """Stop and await the periodic polling task."""
        if self._task is None:
            return

        self._stop_event.set()
        await self._task
        self._task = None
        logger.info("load tracker stopped")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self.refresh_once()

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass