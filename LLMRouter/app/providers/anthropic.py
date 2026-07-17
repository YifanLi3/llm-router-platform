"""Anthropic provider placeholder for Phase 2."""

from __future__ import annotations

from app.providers.unavailable import ExternalProviderPlaceholder


class AnthropicProvider(ExternalProviderPlaceholder):
    """Validate Anthropic availability until a real SDK call is added."""

    def __init__(self) -> None:
        super().__init__("anthropic")
