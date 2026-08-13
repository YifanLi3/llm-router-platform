# LLM Router & Execution Platform

## Phase 5 Development Specification — LLM Gateway Console

Building on the "**intelligent routing + multiple providers + local inference + inference observability**" completed in Phases 1–4, this phase formally upgrades the project into a **production-ready, externally usable LLM Serving Gateway + Ops Console**.

After completing this phase, the project should provide two external perspectives:

- **Developer perspective**: Expose an **OpenAI-compatible protocol** that any OpenAI SDK / LangChain / Cursor / Continue.dev can integrate with directly
- **Operations and debugging perspective**: A Streamlit **Chat debugging console + Admin console** for directly validating model availability, streaming paths, and basic monitoring

This phase is the **first to require integration with a real inference backend and use real results as the acceptance criterion**.

---

## 1. Phase Goals

After completing this phase, the project must satisfy the following requirements:

- Start a FastAPI service
- Open the API documentation: `http://localhost:8084/docs`
- Add and externally expose **OpenAI-compatible endpoints**:
  - `POST /v1/chat/completions` (supports streaming and non-streaming)
  - `GET  /v1/models`
- Add all fields to `GET /health`: `status` / `uptime_s` / `version` / `details`
- Start a **two-page Streamlit frontend**:
  - `app.py` — Chat debugging page (with typewriter effect)
  - `pages/1_Admin.py` — runtime status console
- Integrate at least **one real inference backend** (choose one of vLLM / Ollama / OpenAI-compatible third party)
- **Enable CORS** to allow Streamlit to call the backend directly

`POST /v1/chat/completions` must return the OpenAI protocol format (see Section 6), including at minimum:

- `id` (corresponding to the internal `request_id`)
- `object = "chat.completion"`
- `model`
- `choices[].message.content`
- `choices[].finish_reason`
- `usage.prompt_tokens / completion_tokens / total_tokens`

Streaming responses must strictly follow the OpenAI SSE protocol: every `data:` record is a `chat.completion.chunk` object, and the stream ends with `data: [DONE]`.

---

## 2. Relationship to Previous Phases

| Phase | What It Solves | Protocol / Endpoint |
|---|---|---|
| 1 | Establish the main request path | Custom `/route` |
| 2 | Intelligent routing + fallback + multiple providers | Custom `/route` |
| 3 | Observability dashboard | `/analytics`, `/quality/dashboard`, `/feedback` |
| 4 | Real local inference + streaming + inference-layer metrics + load awareness | Custom `/route/stream`, `/metrics` |
| **5** | **OpenAI-compatible protocol + Chat debugging console + real-backend acceptance** | **`/v1/chat/completions`, `/v1/models`** |

> **Do not rewrite the routing, provider, or observability capabilities from Phase 4** in this phase; this phase only adds an "**external OpenAI-compatible shell + Chat debugging UI + real integration and acceptance**."
> Internally, continue using Phase 2 routing + Phase 4 real providers + Phase 4 load-aware scheduling.

In one sentence:

- Phases 1–4 build **"internal platform capabilities"**
- **Phase 5 builds "external developer experience + real usability acceptance"**

---

## 3. Implementation Scope

This phase must complete:

1. OpenAI-compatible `POST /v1/chat/completions` (non-streaming and streaming)
2. OpenAI-compatible `GET /v1/models`
3. Internal forwarding from `/v1/chat/completions` to Phase 2 routing + Phase 4 real providers
4. CORS middleware
5. Complete `GET /health` fields: `uptime_s`, `version`, and `details.engine`
6. Streamlit Chat debugging page (streaming typewriter effect)
7. Streamlit Admin console (health + model list + ≥ 1 chart)
8. **Integrate at least one real inference backend and validate it with a real invocation result**

This phase's **non-goals**:

- Multi-user login / authentication is not required (an API key field may be retained, but validation is not required)
- You do not need to implement other OpenAI endpoints such as Embeddings / Audio / Image
- Do not rewrite capabilities already covered by Phase 4 (routing, load awareness, Prometheus)

---

## 4. Technology Stack and Environment Requirements

Add (or confirm the presence of) the following on top of Phases 1–4:

- **requests** (for the Streamlit frontend to call the backend)
- **plotly** (for Admin-page tables / charts)
- **starlette CORSMiddleware** (included with FastAPI)
- **sse-starlette** (introduced in Phase 4; continue using it)

Add to `requirements.txt`:

```txt
requests>=2.32,<3.0
plotly>=5.22,<6.0
```

---

## 5. Project Directory Extension

Based on the Phase 4 directory, separate the frontend and backend:

```text
/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI entry point + CORS
│   │   ├── api/
│   │   │   ├── health.py            # /health
│   │   │   ├── route.py             # Custom /route /route/stream (Phases 1-4)
│   │   │   ├── openai_compat.py     # New: /v1/chat/completions /v1/models
│   │   │   ├── analytics.py         # /analytics /quality/dashboard /feedback (Phase 3)
│   │   │   └── metrics.py           # /metrics (Phase 4)
│   │   ├── core/
│   │   │   ├── router.py            # Phase 2 routing
│   │   │   ├── inference.py         # Phase 2/4 inference engine
│   │   │   ├── providers/           # Phase 4 real providers
│   │   │   └── adapters/
│   │   │       └── openai_adapter.py    # New: internal schema <-> OpenAI schema
│   │   ├── infra/                   # Phase 4 metrics / load_tracker / streaming
│   │   └── models/
│   │       ├── internal.py          # Internal QueryRequest / InferenceResponse
│   │       └── openai.py            # New: OpenAI protocol Pydantic models
│   └── config.py
├── frontend/
│   ├── app.py                       # New: Chat debugging page (default home page)
│   └── pages/
│       ├── 1_Admin.py               # New: Admin console
│       └── 2_Inference_Engine.py    # Already exists in Phase 4
├── config.yaml
└── README.md
```

Module responsibilities:

- `openai_compat.py`: **only performs protocol conversion and pass-through**; do not rewrite routing logic
- `openai_adapter.py`: bidirectional schema mapping; the core new addition in Phase 5
- `frontend/app.py`: the default Streamlit home page and must be the Chat page
- `frontend/pages/1_Admin.py`: administrator perspective; **may reuse components from the Phase 3 dashboard**

---

## 6. OpenAI-Compatible Protocol Contract

### 6.1 Request Format (`POST /v1/chat/completions`)

```json
{
  "model": "vllm-qwen-7b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a haiku about caching."}
  ],
  "max_tokens": 256,
  "temperature": 0.7,
  "stream": false
}
```

Requirements:

- `model` must be a model name defined in `config.yaml`
- `messages` must support at least the three roles `system / user / assistant`
- Also support common optional fields used by OpenAI clients (`top_p`, `presence_penalty`, `frequency_penalty`, `stop`, etc.); silently ignore them when not implemented
- Optionally support `prompt` (legacy completions style): when `messages` is absent, convert `prompt` into a single `user` message

### 6.2 Non-Streaming Response Format

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1716595200,
  "model": "vllm-qwen-7b",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Cache lines hum..."},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 32,
    "total_tokens": 50
  }
}
```

### 6.3 Streaming Response Format (SSE)

Each chunk:

```text
data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","created":1716595200,
       "model":"vllm-qwen-7b",
       "choices":[{"index":0,"delta":{"content":"Cache "},"finish_reason":null}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","created":1716595200,
       "model":"vllm-qwen-7b",
       "choices":[{"index":0,"delta":{"content":"lines "},"finish_reason":null}]}

...

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","created":1716595200,
       "model":"vllm-qwen-7b",
       "choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

Requirements:

- The `delta` in the first chunk must contain `"role": "assistant"`; subsequent chunks send only `content`
- **The completion signal must be `data: [DONE]`** (note that `[DONE]` is literal, not JSON)
- Use `text/event-stream` as the response `Content-Type`

### 6.4 `GET /v1/models`

```json
{
  "object": "list",
  "data": [
    {"id": "vllm-qwen-7b",   "object": "model", "owned_by": "local"},
    {"id": "ollama-qwen-7b", "object": "model", "owned_by": "local"},
    {"id": "openai-gpt-4o-mini", "object": "model", "owned_by": "openai"}
  ]
}
```

The model list must be **derived directly from `router.models` in `config.yaml`**; hard-coding it in code is not allowed.

### 6.5 Relationship to the Internal Protocol

The implementation of `/v1/chat/completions` must follow this flow:

```
OpenAI request
    ↓ openai_adapter.from_openai()
QueryRequest (Phase 1 internal protocol)
    ↓ QueryRouter.route()  (Phase 2)
RoutingDecision
    ↓ InferenceEngine.execute() / stream()  (Phases 2/4)
InferenceResult / AsyncIterator
    ↓ openai_adapter.to_openai() / to_openai_chunks()
OpenAI response
```

It is **strictly prohibited** to bypass the routing and provider abstractions and have `/v1/chat/completions` call OpenAI / vLLM directly.

---

## 7. Health Check Endpoint Specification (Enhanced)

`GET /health` must return the following structure (retain and extend the Phase 3/4 fields):

```json
{
  "status": "healthy",
  "uptime_s": 1234,
  "version": "0.5.0",
  "details": {
    "engine": "vllm",
    "router_strategy": "load_aware",
    "providers": { "vllm": true, "ollama": true, "openai": false }
  },
  "services": { ... retain Phase 4 fields ... }
}
```

Requirements:

- `uptime_s` = seconds elapsed from process startup to the present
- Read `version` from `config.py` or `__version__`; `"unknown"` is not allowed
- Valid values for `status`: `healthy` / `degraded` / `unhealthy`
  - All real engines unavailable: `degraded` (because `local_mock` remains as a fallback)
  - Router initialization fails: `unhealthy`

---

## 8. CORS Configuration Requirements

Add the following in `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # May be open during local development
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Requirements:

- Streamlit running in the browser must be able to call `/v1/chat/completions` directly
- Tighten `allow_origins` to specific domains for production deployments (it is sufficient to document this in the README)

---

## 9. Streamlit Chat Debugging Page (`frontend/app.py`)

### 9.1 The Left-Side Configuration Area Must Include

- **API Base**: default `http://localhost:8084`
- **API Key**: text field; may be empty (authentication is not required)
- **Model dropdown**: must be fetched from `GET /v1/models`; **hard-coding it in the frontend is not allowed**
- **Streaming toggle**: enabled by **default**
- Optional: System Prompt, Temperature, and Max Tokens sliders

### 9.2 The Right-Side Chat Area Must Include

- Conversation history (use `st.chat_message`)
- Send button / input field (`st.chat_input`)
- **Typewriter effect is required in streaming mode** (update the same assistant message chunk by chunk, using `st.empty()` + an accumulated string)
- Display `latency_ms` and `tokens` in small text at the end of each assistant message
- Display backend error details when errors occur (connection failure / missing model / authentication failure); **do not swallow errors**

### 9.3 Invocation Contract

- The backend must be called using `POST /v1/chat/completions`; **calling the internal `/route` is not allowed**
  - Rationale: the Chat page also demonstrates "**how external developers would use your Gateway**"
- For streaming requests, use `requests.post(stream=True)` + `iter_lines()`, and parse the `data:` prefix and `[DONE]` yourself

---

## 10. Streamlit Admin Console (`frontend/pages/1_Admin.py`)

### 10.1 Must Display

- **Platform health status** (read `/health` and display `status`, `uptime_s`, `version`, and each engine's status using colored blocks or a table)
- **Model information list** (read `/v1/models`, displaying at least `id` + `owned_by`; if possible, associate `capabilities` and `priority` from `config.yaml`)
- **At least 1 chart**:
  - Recommended: reuse data from the Phase 3 `/analytics` endpoint to draw a "request count in the last N minutes" line chart
  - Or call `/metrics`, parse TTFT percentiles, and draw a bar chart
  - Implement it with `plotly`

### 10.2 Error Handling

When the backend is unavailable:

- Display a red banner at the top stating "Backend unavailable"
- Do not display fabricated random numbers / placeholder fake data

---

## 11. Real Inference Backend Integration and Acceptance

### 11.1 Integration Requirements

Integrate **at least** one of the following and obtain a real result by starting a conversation on the Chat page:

| Option | Recommended Scenario | Startup Command |
|---|---|---|
| **vLLM** (OpenAI-compatible) | NVIDIA GPU available | `python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --port 8000` |
| **Ollama** | Mac M-series / no GPU | `ollama serve && ollama pull qwen2.5:7b` |
| **Third-party OpenAI-compatible** | No local resources | Any provider such as DeepSeek / Moonshot / Zhipu |

### 11.2 Configuration Switching Requirements

- **Backend address, model name, and API key must be read from configuration / environment variables**; hard-coding them in code is not allowed
- Configure at least two selectable models in `config.yaml`, so `/v1/models` returns ≥ 2 records

### 11.3 Acceptance Criteria

The **only** basis for determining functional correctness in this phase:

> **Start a real conversation on the Streamlit Chat page with Streaming enabled; token-by-token output must appear, and the final result must be neither Echo nor Mock.**

If only Mock responses can be obtained, this phase is considered **not passed**.

---

## 12. Startup and Validation

### 12.1 Startup Order

```bash
# 1. Start a real inference backend (choose one)
ollama serve &        # or vLLM

# 2. Start the Gateway
./venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8084

# 3. Start the frontend
./venv/bin/python -m streamlit run frontend/app.py
```

### 12.2 End-to-End Validation Checklist

| Validation Item | Command / Action | Expected Result |
|---|---|---|
| API documentation | Open `http://localhost:8084/docs` | See `/route`, `/v1/chat/completions`, and `/v1/models` |
| Model list | `curl -s :8084/v1/models` | At least 2 records, matching `config.yaml` |
| Non-streaming Chat | Call with the `openai` Python SDK (see below) | Real text is returned |
| Streaming Chat | Use the `openai` SDK + `stream=True` | Chunk-by-chunk output, with no `[DONE]` parsing error |
| Chat debugging page | Open Streamlit in a browser | Supports chatting and has a typewriter effect |
| Admin page | Open in a browser | Health + models + 1 chart all work |
| CORS | Inspect browser devtools | No CORS errors |
| Backend down | Stop ollama / vllm, then make a request from the Chat page | Friendly error message; no 500 and no fake data |

### 12.3 Validate with the OpenAI SDK (Critical)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8084/v1", api_key="EMPTY")

resp = client.chat.completions.create(
    model="vllm-qwen-7b",
    messages=[{"role": "user", "content": "Hello, who are you?"}],
)
print(resp.choices[0].message.content)

stream = client.chat.completions.create(
    model="vllm-qwen-7b",
    messages=[{"role": "user", "content": "Count from 1 to 5"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

> **This is the most compelling demonstration for this phase**: your Gateway can be called directly through the official OpenAI SDK. You can run it live during an interview.

---

## 13. Testing Requirements

Add the following under `tests/`:

- `test_openai_compat.py`
  - `/v1/models` returns the correct structure
  - The non-streaming `/v1/chat/completions` response conforms to the OpenAI protocol
  - Every `data:` record in the streaming response is valid JSON, and the final record must be `data: [DONE]`
  - When the `model` field contains a nonexistent value, return 4xx with an OpenAI-style error (including `error.message` and `error.type`)
- `test_health.py`
  - `uptime_s` returned by `/health` increases monotonically
  - When real engines are unavailable, `status` degrades to `degraded` and does not return 5xx

---

## 14. Self-Check Checklist

Confirm each item before submitting:

- [ ] `GET /v1/models` returns a model list consistent with `config.yaml`
- [ ] The non-streaming response from `POST /v1/chat/completions` fully conforms to the OpenAI protocol
- [ ] The streaming response from `POST /v1/chat/completions` strictly uses `data: ... \n\n` and ends with `data: [DONE]`
- [ ] The official OpenAI Python SDK can call it directly (both non-streaming and streaming pass)
- [ ] CORS configuration is active, with no browser invocation errors
- [ ] `/health` returns `uptime_s`, `version`, and `details.engine`
- [ ] Streamlit Chat page: streaming typewriter effect works and errors are displayed
- [ ] Streamlit Admin page: health / models / chart all display real data, not fake data
- [ ] At least one real engine completes an end-to-end conversation (not Mock)
- [ ] Model name, backend address, and API key are all read from configuration / environment variables
- [ ] All pytest cases pass

---

## 15. Phase Summary and Interview Pitch

After completing Phases 1–5, your project is an LLM Gateway with a **complete structure and a clear internal and external story**:

| Layer | Capability | Corresponding Phase |
|---|---|---|
| **External protocol layer** | OpenAI-compatible API + Chat debugging console | **Phase 5** |
| **Routing and scheduling layer** | Rules + composite scoring + load awareness + fallback | Phase 2 + Phase 4 |
| **Inference execution layer** | Multiple providers + real vLLM/Ollama integration + SSE | Phase 2 + Phase 4 |
| **Observability layer** | Streamlit dashboard + Prometheus + TTFT/TPOT | Phase 3 + Phase 4 |
| **Engineering foundation** | FastAPI + Pydantic + configuration-driven design + layering + unit tests | Phase 1 |

### 30-Second Interview Pitch

> "I built a **production-ready LLM Gateway**:
> - **Externally**, it exposes an **OpenAI-compatible protocol**, so any OpenAI SDK or LangChain client can integrate with it at zero cost;
> - **Internally**, it performs intelligent routing based on request type, user tier, and real-time backend vLLM **KV cache / queue depth** load;
> - It supports **SSE streaming output**, measures **TTFT / TPOT / tokens-per-second**, and exposes them through **Prometheus**;
> - If any provider fails, it automatically switches to the next provider according to the fallback chain, avoiding 500 errors;
> - It includes a **Streamlit Chat debugging console + Admin monitoring console** for live demonstrations."

### Recommended Demo Path

If time permits during an interview, this demonstration order is most compelling:

1. Open the Streamlit Chat page, send a message, and show streaming typewriter output
2. Switch to the Admin page to show health status and charts
3. **Open a terminal and call your Gateway with the official `openai` Python SDK** ← most persuasive
4. Stop vLLM, make another request, and show fallback to Ollama with no 500 errors
5. Open `/metrics` and show the interviewer real TTFT / TPOT percentiles

---

## 16. Relationship to Phase 6+ (Outlook)

After Phase 5, this project is close to industrial-grade maturity as an **"application-layer LLM Gateway."** There are two independent directions to continue:

- **Direction A: Continue building advanced Gateway features** (Phase 6 candidates)
  - Semantic caching (embedding + similarity)
  - Rate limiting / quotas
  - Prompt template management
  - Multi-tenancy and audit logs

- **Direction B: Start a separate project focused on the inference-engine core** (strongly recommended in parallel with this project)
  - mini-vLLM: Continuous Batching + simplified PagedAttention + Prefix Cache
  - Quantized-deployment comparison experiments
  - Triton / CUDA kernel optimization

> If your target role is **AI Platform / LLM Infra**: Phases 1–5 are enough to be your main showcase.
> If your target role is on a deep inference-engine team such as **vLLM / TensorRT-LLM / SGLang**: you must also complete Direction B.
