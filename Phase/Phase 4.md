# LLM Router & Execution Platform

## Phase 4 Development Specification

Building on the "API + intelligent routing + multiple providers + observable dashboard" completed in Phases 1–3, this phase continues advancing the project toward **Inference Infra**, enabling **"real local inference + inference-layer observability + load-based intelligent scheduling."**

After completing this phase, the project should evolve from an "application-layer LLM Gateway" into a **"Hybrid LLM Serving Platform with a local inference engine."**

---

## 1. Phase Objectives

After completing this phase, the project should meet the following requirements:

- Start a FastAPI service
- Open the API documentation: `http://localhost:8083/docs`
- Integrate at least **one real, runnable local inference backend** (either vLLM or Ollama)
- Support **streaming output**: add `POST /route/stream` using **SSE (Server-Sent Events)**
- Expose **core inference-layer metrics**: `TTFT`, `TPOT`, `tokens_per_second`, `active_requests`, `kv_cache_usage`
- Expose a **Prometheus metrics endpoint**: `GET /metrics`
- Support a routing strategy that **selects based on real runtime load** (queue length / KV cache usage / GPU utilization)
- Have the same `/route` endpoint demonstrate different routing behavior for identical requests under different load conditions

Building on Phase 2, `POST /route` must add at least the following fields to `routing`:

- `engine`: `vllm` / `ollama` / `openai` / `local_mock`
- `runtime_load`: a current real-time load snapshot for the selected engine
- `load_score`: a load-based score

`POST /route/stream` must return at least the following event types (SSE):

- `meta`: routing information (one-time)
- `token`: each incremental token / chunk
- `done`: completion event with final statistics (TTFT, TPOT, tokens, cost)
- `error`: error event

---

## 2. Core Differences from Phases 1–3

| Dimension | Phases 1–3 | Phase 4 |
|---|---|---|
| Inference backend | All mock | At least one real local engine (vLLM / Ollama) |
| Output format | One-shot JSON | One-shot JSON + **SSE streaming** |
| Routing basis | Rules + capabilities + static weighted scoring | **Add real-time load signals** (KV cache, queue depth) |
| Metrics | Application layer (success rate, P95, cost) | **Inference layer (TTFT / TPOT / tokens/s / KV cache)** |
| Metrics exposure | Fetched directly by Streamlit dashboard | **Prometheus `/metrics`** + Streamlit |
| Dashboard | Overview / Models / Performance | Add an **Inference Engine** page |

In summary:

- Phases 1–3 solve "**can route, does not crash, is observable**"
- Phase 4 solves "**can truly perform local inference, exposes underlying inference metrics, and can schedule based on load**"

---

## 3. Implementation Scope

This phase requires the following capabilities:

1. Real local inference provider integration
2. Streaming output (SSE)
3. Inference-layer metric collection and aggregation
4. Prometheus metric exposure
5. Real-time load-based routing scoring
6. A new Inference Engine dashboard page
7. Inference engine runtime status exposed through health checks

This phase's **non-goals**:

- You are not required to implement PagedAttention / Continuous Batching yourself (vLLM provides these)
- Multi-GPU / Tensor Parallel is not required
- Quantization (INT4 / AWQ / GPTQ) is not required
- Training or fine-tuning is not required

> These non-goals are deeper Inference Infra topics. It is recommended to practice them separately in a future standalone project (a mini inference engine), rather than mixing them into this project.

---

## 4. Technology Stack and Environment Requirements

Add the following on top of Phases 1–3:

- **vLLM ≥ 0.6** (recommended; requires an NVIDIA GPU. Use the Ollama path if no GPU is available)
- **Ollama** (an alternative for systems without a GPU / Apple Silicon)
- **httpx** (asynchronous requests to Ollama / vLLM's OpenAI-compatible API; introduced in Phase 1)
- **sse-starlette** (an SSE implementation that works well with FastAPI)
- **prometheus-client** (Prometheus metrics)
- **tiktoken** (accurate token counting, replacing `split()` estimation)

Add the following to `requirements.txt`:

```txt
sse-starlette>=2.1,<3.0
prometheus-client>=0.20,<1.0
tiktoken>=0.7,<1.0
# Choose one:
# vllm>=0.6.0   # Use with an NVIDIA GPU
# Or start a local service through the Ollama CLI; no pip package is required.
```

---

## 5. Project Directory Extensions

Extend the Phase 2/3 directory structure as follows:

```text
/
├── config.yaml
├── config_loader.py
├── inference.py
├── main.py
├── router.py
├── schema.py
├── test_main.py
├── providers/
│   ├── __init__.py
│   ├── base.py              # BaseProvider (retained from Phase 2)
│   ├── local_mock.py        # LocalProvider (retained from Phase 2)
│   ├── openai_provider.py   # OpenAIProvider (retained from Phase 2)
│   ├── vllm_provider.py     # New: vLLM provider
│   └── ollama_provider.py   # New: Ollama provider
├── infra/
│   ├── __init__.py
│   ├── metrics.py           # New: Prometheus metric definitions
│   ├── load_tracker.py      # New: real-time load collection and cache
│   └── streaming.py         # New: SSE helpers
├── dashboard/
│   └── pages/
│       └── 8_Inference_Engine.py   # New dashboard page
└── docs/
    └── student_phase4_guide.md
```

Responsibilities of the new modules:

- `providers/vllm_provider.py`: calls local models through vLLM's OpenAI-compatible API and supports both non-streaming and streaming requests
- `providers/ollama_provider.py`: calls local models through the Ollama HTTP API and supports both non-streaming and streaming requests
- `infra/metrics.py`: defines and registers Prometheus metrics (Counter / Histogram / Gauge)
- `infra/load_tracker.py`: periodically fetches engine runtime status (queue / KV cache) for the router to read
- `infra/streaming.py`: handles SSE encoding/decoding, event serialization, and heartbeats

---

## 6. Configuration File Extensions

Add the following configuration block to `config.yaml`:

```yaml
api:
  host: "0.0.0.0"
  port: 8083

engines:
  vllm:
    enabled: true
    base_url: "http://127.0.0.1:8000/v1"
    api_key: "EMPTY"
    served_model_name: "Qwen2.5-7B-Instruct"
    health_endpoint: "/health"
    metrics_endpoint: "/metrics"
    max_concurrent_requests: 32

  ollama:
    enabled: true
    base_url: "http://127.0.0.1:11434"
    served_model_name: "qwen2.5:7b"
    max_concurrent_requests: 8

router:
  default_model: "vllm-qwen-7b"
  strategy: "load_aware"          # New: load_aware / intelligent / rule_only
  load_weights:
    success_rate: 0.30
    cost: 0.15
    priority: 0.10
    latency: 0.20
    kv_cache_usage: 0.15          # New
    queue_depth: 0.10             # New

  models:
    vllm-qwen-7b:
      provider: "vllm"
      engine: "vllm"
      provider_model: "Qwen2.5-7B-Instruct"
      capabilities: [general, coding, chat]
      supported_tiers: [free, premium, enterprise]
      max_tokens: 4096
      cost_per_1k_input: 0.0
      cost_per_1k_output: 0.0
      priority: 1
      fallback_model: "ollama-qwen-7b"

    ollama-qwen-7b:
      provider: "ollama"
      engine: "ollama"
      provider_model: "qwen2.5:7b"
      capabilities: [general, coding, chat]
      supported_tiers: [free, premium, enterprise]
      max_tokens: 4096
      cost_per_1k_input: 0.0
      cost_per_1k_output: 0.0
      priority: 2
      fallback_model: "local-mock"

    local-mock:
      provider: "local"
      engine: "local_mock"
      capabilities: [general]
      supported_tiers: [free, premium, enterprise]
      max_tokens: 1024
      priority: 99
```

New configuration item descriptions:

- `engines.*`: connection information for each real inference engine
- `router.strategy = load_aware`: enables the load-based routing strategy
- `router.load_weights`: factor weights in the composite score (including the new KV cache and queue depth factors)
- `models[*].engine`: identifies the physical engine behind the model and is used for load queries

---

## 7. Data Contract Extensions

Extend or add the following models in `schema.py`:

```text
RuntimeLoadSnapshot
  - engine: str
  - kv_cache_usage: float       # 0.0 ~ 1.0
  - active_requests: int
  - queue_depth: int
  - gpu_utilization: float | None
  - updated_at: float

InferenceMetrics
  - ttft_ms: float | None       # Time To First Token
  - tpot_ms: float | None       # Time Per Output Token
  - tokens_per_second: float | None
  - total_latency_ms: int

EngineConfig
  - enabled: bool
  - base_url: str
  - served_model_name: str
  - max_concurrent_requests: int
```

New fields in `RoutingInfo`:

- `engine`
- `load_score`
- `runtime_load: RuntimeLoadSnapshot | None`

New fields in `InferenceResult`:

- `engine`
- `metrics: InferenceMetrics`
- `streamed: bool`

---

## 8. Real Inference Provider Implementation

### 8.1 vLLM Provider Implementation Requirements

vLLM exposes a service through an OpenAI-compatible API. It is recommended to start it as a separate process:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-prefix-caching
```

`providers/vllm_provider.py` must implement:

- `async generate(query, model_name, max_tokens, temperature) -> InferenceResult`
- `async stream(query, ...) -> AsyncIterator[str]`
- `async health() -> bool`: calls `GET /health`
- `async fetch_runtime_load() -> RuntimeLoadSnapshot`: fetches `GET /metrics` and parses the following Prometheus metrics
  - `vllm:num_requests_running`
  - `vllm:num_requests_waiting`
  - `vllm:gpu_cache_usage_perc`

### 8.2 Ollama Provider Implementation Requirements

`providers/ollama_provider.py` must implement:

- `async generate(...)`: calls `POST /api/generate` with `stream=false`
- `async stream(...)`: calls `POST /api/generate` with `stream=true` and parses NDJSON line by line
- `async health() -> bool`: calls `GET /api/tags`
- `async fetch_runtime_load() -> RuntimeLoadSnapshot`: Ollama does not expose KV cache metrics, so approximate load using the number of currently in-progress requests (maintain an in-flight counter within the Provider)

### 8.3 Unified Requirements

Regardless of the Provider, each must:

- Return `InferenceResult`, with at least one valid value among **TTFT, TPOT, and tokens/s** in `InferenceResult.metrics` (all three should be available for streaming output)
- Raise an identifiable exception on failure so that `InferenceEngine` can trigger fallback
- Use **tiktoken** strictly for token counting; do not use `split()` estimation

---

## 9. SSE Streaming Endpoint Implementation

### 9.1 New Endpoint

```text
POST /route/stream
```

The request body is identical to `/route`.

### 9.2 Event Protocol

Use SSE. Event types (`event:`) and payloads (`data:`) are as follows:

```text
event: meta
data: {"query_id": "...", "model_name": "vllm-qwen-7b", "engine": "vllm",
       "routing": { ... same structure as /route ... }}

event: token
data: {"delta": "Hello"}

event: token
data: {"delta": ", world"}

event: done
data: {"tokens": {"input": 12, "output": 34, "total": 46},
       "cost_usd": 0.0,
       "metrics": {"ttft_ms": 87, "tpot_ms": 22.4, "tokens_per_second": 44.6,
                   "total_latency_ms": 870}}

event: error
data: {"error": "engine unavailable", "fallback_used": true}
```

### 9.3 Implementation Requirements

- `sse-starlette`'s `EventSourceResponse` is recommended
- A `meta` event must be emitted before producing the first `token` event
- **TTFT** = time from receiving the HTTP request to the first `token` event
- **TPOT** = the average interval per token, starting with the second token
- When an engine fails, fallback should occur after streaming has already begun: emit an `error` event and, when appropriate, switch to the fallback engine to continue pushing output (best-effort implementation is sufficient)

### 9.4 Test Method

```bash
curl -N -sS http://localhost:8083/route/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Write a short poem about caching",
    "user_id": "u1",
    "user_tier": "free"
  }'
```

`-N` disables buffering; events should stream one at a time.

---

## 10. Inference-Layer Metric Collection and Prometheus Exposure

### 10.1 Required Metrics

Define at least the following Prometheus metrics in `infra/metrics.py`:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `llm_router_requests_total` | Counter | `engine`, `model`, `status` | Total number of requests |
| `llm_router_ttft_seconds` | Histogram | `engine`, `model` | TTFT distribution |
| `llm_router_tpot_seconds` | Histogram | `engine`, `model` | TPOT distribution |
| `llm_router_tokens_per_second` | Histogram | `engine`, `model` | Output throughput |
| `llm_router_request_duration_seconds` | Histogram | `engine`, `model` | End-to-end latency |
| `llm_router_active_requests` | Gauge | `engine` | Requests in progress |
| `llm_router_engine_kv_cache_usage` | Gauge | `engine` | KV cache utilization (vLLM only) |
| `llm_router_fallback_total` | Counter | `from_engine`, `to_engine`, `reason` | Number of fallback triggers |

### 10.2 Exposure Endpoint

```text
GET /metrics
```

Return the standard Prometheus text format:

```text
# HELP llm_router_requests_total ...
# TYPE llm_router_requests_total counter
llm_router_requests_total{engine="vllm",model="vllm-qwen-7b",status="success"} 42
...
```

The implementation can directly use `prometheus_client.generate_latest()` + `CONTENT_TYPE_LATEST`.

### 10.3 Verification

```bash
curl -sS http://localhost:8083/metrics | head -n 30
```

---

## 11. Real-Time Load-Based Routing Strategy

### 11.1 LoadTracker Implementation Requirements

Implement the following in `infra/load_tracker.py`:

- Start a background asynchronous task that calls `fetch_runtime_load()` for all enabled engines **every 2 seconds**
- Cache the latest snapshot in memory
- Provide a synchronous access interface: `get_snapshot(engine: str) -> RuntimeLoadSnapshot | None`
- Start it in `app.on_event("startup")` and shut it down gracefully on `shutdown`

### 11.2 Application in the Router

In `router.py`, when `strategy == "load_aware"`, the recommended composite scoring formula is:

```text
score = w_success * success_rate
      + w_priority * (1 / priority)
      - w_latency  * normalized(avg_latency_ms)
      - w_cost     * normalized(cost_per_1k_output)
      - w_kv       * runtime_load.kv_cache_usage
      - w_queue    * normalized(runtime_load.queue_depth)
```

Where:

- Weights come from `config.yaml: router.load_weights`
- If `runtime_load is None` (the engine is not enabled or collection fails), use a neutral value for the related terms (such as 0.5)
- Select the candidate model with the highest final score

### 11.3 Demonstration Scenario

Start two engines (vLLM + Ollama, or two Ollama instances), then use a concurrent script to send a burst of requests to vLLM. You should observe:

- New requests begin to favor Ollama (because vLLM's `kv_cache_usage` / `queue_depth` increases)
- The `RoutingInfo.runtime_load` field reflects this change
- After the pressure is removed, routing returns to vLLM

> This is the capability in this phase with the strongest Inference Infra flavor, **and the most valuable story to tell in interviews**.

---

## 12. Health Check Extensions

Building on Phases 2/3, add an `engines` section to `GET /health`:

```json
{
  "status": "healthy",
  "services": {
    "router": { "healthy": true, "strategy": "load_aware" },
    "inference": {
      "healthy": true,
      "engines": {
        "vllm": {
          "healthy": true,
          "kv_cache_usage": 0.42,
          "active_requests": 3,
          "queue_depth": 0
        },
        "ollama": {
          "healthy": true,
          "active_requests": 0,
          "queue_depth": 0
        },
        "local_mock": { "healthy": true }
      }
    }
  }
}
```

---

## 13. New Streamlit Dashboard Page

Add a page on top of the Phase 3 dashboard:

### `Inference Engine`

Page purpose:

- Display real-time load for each engine
- Display quantiles for TTFT / TPOT / tokens-per-second
- Display the number of fallback triggers and their reason distribution

Required backend endpoints:

- `GET /health` (for real-time load snapshots)
- `GET /metrics` (parse Prometheus text to obtain quantiles)
- Or add `GET /inference/stats`, with aggregated results returned by the backend (recommended to avoid parsing Prometheus in the frontend)

Implementation requirements:

- Display at least one line chart (active_requests over the most recent N minutes)
- Display at least one bar chart (TTFT P50/P95 by engine)
- Include four metric cards at the top: total requests, average TTFT, average tokens/s, and number of fallbacks

---

## 14. Testing Requirements

Add the following test cases to `test_main.py`:

- `/route/stream` successfully returns SSE and receives at least the `meta`, `token`, and `done` event types
- `/metrics` returns 200 and its text includes `llm_router_requests_total`
- When all real engines are unavailable, `/route` can still fall back to `local_mock` and does not return 500
- The `RoutingInfo.engine` field correctly reflects the engine actually used after a request
- `LoadTracker` does not throw an exception that kills the background task when an engine is unreachable

---

## 15. Startup and Verification

### 15.1 Start a Local Inference Engine (Choose One)

**Option A: vLLM (recommended; requires an NVIDIA GPU)**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-prefix-caching
```

**Option B: Ollama (also works without a GPU; recommended for Mac M-series)**

```bash
ollama serve &
ollama pull qwen2.5:7b
```

### 15.2 Start the Router

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8083
```

### 15.3 End-to-End Verification Checklist

| Check | Command | Expected Result |
|---|---|---|
| API documentation | Open `http://localhost:8083/docs` | `/route/stream` and `/metrics` are visible |
| Health check | `curl -s :8083/health` | The engines section contains real status |
| Non-streaming inference | `curl -s :8083/route -d '...'` | Uses a real engine; `response` is not an Echo |
| Streaming inference | `curl -N -s :8083/route/stream -d '...'` | Token-by-token output is visible |
| Prometheus | `curl -s :8083/metrics` | Contains ttft / tpot / requests_total |
| Load routing | Load vLLM with concurrent requests and observe whether subsequent requests switch to Ollama | Routing switches |
| Dashboard | Open the Streamlit `Inference Engine` page | Charts contain real data |

---

## 16. Self-Check Checklist

Confirm each item before submitting:

- [ ] At least one real local engine can complete end-to-end inference
- [ ] `/route/stream` produces an SSE event stream that conforms to the protocol
- [ ] The three TTFT, TPOT, and tokens/s metrics can be measured correctly in streaming responses
- [ ] `/metrics` returns valid Prometheus text
- [ ] The `LoadTracker` background task runs reliably for ≥ 10 minutes without crashing
- [ ] The router demonstrates load-based preference with `strategy=load_aware`
- [ ] When all real engines are unavailable, it still falls back to `local_mock` without returning 500
- [ ] tiktoken has replaced `split()` token estimation
- [ ] The dashboard's Inference Engine page displays real data
- [ ] All pytest tests pass

---

## 17. Phase Summary and Interview Narrative

This phase no longer delivers merely "an API gateway that can route"; it delivers a **"hybrid LLM serving platform with local inference, inference-layer observability, and load-aware scheduling."**

In interviews, you can present the project through the following **three-layer story**:

1. **Application layer (Phases 1–3)**: FastAPI + Pydantic + configuration-driven design + multiple Providers + Fallback + Streamlit dashboard, demonstrating "engineering capability + system design + observability"
2. **Inference layer (Phase 4)**: integrates vLLM/Ollama, **measures TTFT / TPOT / tokens-per-second**, and exposes them to monitoring through Prometheus
3. **Scheduling layer (Phase 4)**: uses vLLM's real `kv_cache_usage` and `queue_depth` for load-aware routing, demonstrating an understanding of how **Continuous Batching / KV Cache** work

> Note: after this phase, **the project itself is still not an Inference Engine in the strict sense** (PagedAttention, CUDA kernels, quantization, and similar topics remain out of scope). If your target role is in a deep infrastructure team such as vLLM / TensorRT-LLM / SGLang, present this project as "Platform / Serving experience" together with a separate **mini inference engine** project.
