"""Mock inference engine for Phase 1.
In Phase 1 every model in config.yaml uses provider='mock'; this file
implements a single MockProvider that returns predictable echoed
responses along with realistic-looking token counts, latency, and cost.
Phase 2 will introduce real providers (LocalProvider, OpenAIProvider,
AnthropicProvider) plus a fallback chain. The public interface here --
InferenceEngine.run(request, decision) -> InferenceResult -- will not
change, so the rest of the project will keep working unmodified.
"""

import time

from app.schemas import (
    AppConfig,
    InferenceResult,
    ModelConfig,
    QueryRequest,
    RoutingDecision,
)

