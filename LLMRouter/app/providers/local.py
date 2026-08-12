"""Deterministic local provider used for development and tests."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from app.core.tokenization import count_tokens
from app.providers.base import BaseProvider
from app.schemas import InferenceResult, ModelConfig


class LocalProvider(BaseProvider):
    """A local stand-in that echoes the prompt with calculated usage."""

    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        started_at = time.perf_counter()

        response_text = f"Echo from {model_name}: {query[:200]}"
        input_tokens = max(1, count_tokens(query))
        output_tokens = count_tokens(response_text)
        cost_usd = (
            input_tokens / 1000.0 * model_cfg.cost_per_1k_input
            + output_tokens / 1000.0 * model_cfg.cost_per_1k_output
        )

        return InferenceResult(
            response_text=response_text,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            cached=False,
            provider="local",
        )

    async def stream(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Yield deterministic local response chunks for SSE development."""
        del max_tokens, temperature, model_cfg

        response_text = f"Echo from {model_name}: {query[:200]}"
        for index, word in enumerate(response_text.split()):
            prefix = "" if index == 0 else " "
            yield f"{prefix}{word}"

            # Give the event loop a chance to flush one SSE event.
            await asyncio.sleep(0)
