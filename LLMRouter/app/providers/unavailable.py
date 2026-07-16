"""Provider used until a real external SDK integration is added."""

from __future__ import annotations

import os

from app.providers.base import BaseProvider, ProviderUnavailableError
from app.schemas import InferenceResult, ModelConfig


class ExternalProviderPlaceholder(BaseProvider):
    """Reject external calls when credentials or an SDK integration are absent."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        if not model_cfg.api_key_env:
            raise ProviderUnavailableError(
                f"{self.provider_name!r} has no api_key_env configured."
            )

        if not os.getenv(model_cfg.api_key_env):
            raise ProviderUnavailableError(
                f"{self.provider_name!r} is unavailable: "
                f"environment variable {model_cfg.api_key_env!r} is not set."
            )

        raise ProviderUnavailableError(
            f"{self.provider_name!r} credentials exist, but its SDK integration "
            "has not been implemented yet."
        )