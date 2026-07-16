"""Provider interface and provider-specific errors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import InferenceResult, ModelConfig


class ProviderError(RuntimeError):
    """Base error for a provider call that failed."""


class ProviderUnavailableError(ProviderError):
    """Provider cannot serve the request, for example due to a missing API key."""


class BaseProvider(ABC):
    """Every inference provider implements generate()."""

    @abstractmethod
    def generate(
        self,
        *,
        query: str,
        model_name: str,
        model_cfg: ModelConfig,
    ) -> InferenceResult:
        """Generate one completion or raise ProviderError."""