"""Shared token counting with a stable tiktoken fallback encoding."""

from __future__ import annotations

import logging
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_encoding() -> tiktoken.Encoding | None:
    """Load the tiktoken vocabulary, falling back if it is unavailable."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except OSError as error:
        logger.warning(
            "tiktoken vocabulary unavailable; using whitespace token fallback",
            extra={"error": str(error)},
        )
        return None


def count_tokens(text: str) -> int:
    """Return a token count, preferring tiktoken when its vocabulary is cached."""
    if not text:
        return 0

    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))

    return len(text.split())
