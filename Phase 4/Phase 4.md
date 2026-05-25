# LLM Router & Execution Platform

## Phase 4 开发说明书

本阶段在 Phase 1–3 已经完成的 "API + 智能路由 + 多 Provider + 可观测看板" 的基础上，把项目向 **Inference Infra** 方向继续推进，让系统具备 **"真实本地推理 + 推理层可观测 + 基于负载的智能调度"** 的能力。

完成本阶段后，项目应从一个 "应用层 LLM Gateway" 升级为一个 **"带本地推理引擎的混合推理平台 (Hybrid LLM Serving Platform)"**。

---

## 1. 阶段目标

完成本阶段后，项目应满足以下要求：

- 启动一个 FastAPI 服务
- 打开接口文档：`http://localhost:8083/docs`
- 至少接入 **1 个真实可运行的本地推理后端**（vLLM 或 Ollama 任选其一）
- 支持 **流式输出**：新增 `POST /route/stream` 使用 **SSE (Server-Sent Events)**
- 暴露 **推理层核心指标**：`TTFT`、`TPOT`、`tokens_per_second`、`active_requests`、`kv_cache_usage`
- 暴露 **Prometheus 指标接口**：`GET /metrics`
- 路由策略支持 **基于真实运行时负载的选择**（队列长度 / KV cache 使用率 / GPU 利用率）
- 同一个 `/route` 接口，对相同请求在不同负载情况下能体现不同的路由行为

`POST /route` 在 Phase 2 基础上，`routing` 字段至少新增：

- `engine`：`vllm` / `ollama` / `openai` / `local_mock`
- `runtime_load`：所选 engine 当前的实时负载快照
- `load_score`：基于负载的打分

`POST /route/stream` 至少应返回以下事件类型（SSE）：

- `meta`：路由信息（一次性）
- `token`：每个增量 token / chunk
- `done`：结束事件，附带最终统计（TTFT、TPOT、tokens、cost）
- `error`：错误事件

---

## 2. 与 Phase 1–3 的核心区别

| 维度 | Phase 1–3 | Phase 4 |
|---|---|---|
| 推理后端 | 全 Mock | 至少 1 个真实本地引擎 (vLLM / Ollama) |
| 输出形式 | 一次性 JSON | 一次性 JSON + **SSE 流式** |
| 路由依据 | 规则 + 能力 + 静态权重打分 | **加入实时负载信号**（KV cache、queue depth） |
| 指标 | 应用层（成功率、P95、cost） | **推理层（TTFT / TPOT / tokens/s / KV cache）** |
| 指标暴露 | Streamlit 看板自取 | **Prometheus `/metrics`** + Streamlit |
| 看板 | Overview / Models / Performance | 新增 **Inference Engine** 页 |

一句话总结：

- Phase 1–3 解决 "**会路由、不崩溃、看得见**"
- Phase 4 解决 "**真的能本地推理、看得见推理底层指标、能按负载调度**"

---

## 3. 实施范围

本阶段要求完成以下能力：

1. 真实本地推理 Provider 接入
2. 流式输出（SSE）
3. 推理层指标采集与统计
4. Prometheus 指标暴露
5. 基于实时负载的路由打分
6. 看板新增 Inference Engine 页
7. 健康检查中暴露推理引擎运行态

本阶段 **非目标事项**：

- 不要求自己实现 PagedAttention / Continuous Batching（这些由 vLLM 提供）
- 不要求多 GPU / Tensor Parallel
- 不要求量化（INT4 / AWQ / GPTQ）
- 不要求训练或微调

> 上述非目标事项是更深一层的 Inference Infra 课题，建议放到下一个独立项目（mini inference engine）单独练，不要在本项目里混合。

---

## 4. 技术栈与环境要求

在 Phase 1–3 基础上新增：

- **vLLM ≥ 0.6**（推荐，需要 NVIDIA GPU；如无 GPU 可使用 Ollama 路线）
- **Ollama**（无 GPU / Apple Silicon 替代方案）
- **httpx**（异步请求 Ollama / vLLM 的 OpenAI 兼容接口，已在 Phase 1 引入）
- **sse-starlette**（FastAPI 友好的 SSE 实现）
- **prometheus-client**（Prometheus 指标）
- **tiktoken**（精确 token 计数，替代 `split()` 估算）

`requirements.txt` 新增：

```txt
sse-starlette>=2.1,<3.0
prometheus-client>=0.20,<1.0
tiktoken>=0.7,<1.0
# 二选一：
# vllm>=0.6.0   # 有 GPU 时使用
# 或者通过 ollama CLI 启动本地服务，无需 pip 包
```

---

## 5. 项目目录扩展

在 Phase 2/3 目录基础上扩展，目录建议如下：

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
│   ├── base.py              # BaseProvider（沿用 Phase 2）
│   ├── local_mock.py        # LocalProvider（沿用 Phase 2）
│   ├── openai_provider.py   # OpenAIProvider（沿用 Phase 2）
│   ├── vllm_provider.py     # 新增：vLLM Provider
│   └── ollama_provider.py   # 新增：Ollama Provider
├── infra/
│   ├── __init__.py
│   ├── metrics.py           # 新增：Prometheus 指标定义
│   ├── load_tracker.py      # 新增：实时负载采集与缓存
│   └── streaming.py         # 新增：SSE 工具函数
├── dashboard/
│   └── pages/
│       └── 8_Inference_Engine.py   # 新增看板页
└── docs/
    └── student_phase4_guide.md
```

各新增模块职责：

- `providers/vllm_provider.py`：通过 vLLM 的 OpenAI 兼容 API 调用本地模型，支持非流与流式
- `providers/ollama_provider.py`：通过 Ollama HTTP API 调用本地模型，支持非流与流式
- `infra/metrics.py`：定义并注册 Prometheus 指标（Counter / Histogram / Gauge）
- `infra/load_tracker.py`：周期性拉取各引擎的运行态（queue / kv cache），供路由器读取
- `infra/streaming.py`：SSE 编解码、事件序列化、心跳处理

---

## 6. 配置文件扩展

在 `config.yaml` 中新增以下配置块：

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
  strategy: "load_aware"          # 新增：load_aware / intelligent / rule_only
  load_weights:
    success_rate: 0.30
    cost: 0.15
    priority: 0.10
    latency: 0.20
    kv_cache_usage: 0.15          # 新增
    queue_depth: 0.10             # 新增

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

新增配置项说明：

- `engines.*`：每个真实推理引擎的连接信息
- `router.strategy = load_aware`：启用基于负载的路由策略
- `router.load_weights`：综合打分中各因子权重（含新增的 KV cache、queue depth）
- `models[*].engine`：标识该模型背后的物理引擎，用于负载查询

---

## 7. 数据契约扩展

在 `schema.py` 中扩展或新增以下模型：

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

`RoutingInfo` 新增字段：

- `engine`
- `load_score`
- `runtime_load: RuntimeLoadSnapshot | None`

`InferenceResult` 新增字段：

- `engine`
- `metrics: InferenceMetrics`
- `streamed: bool`

---

## 8. 真实推理 Provider 实现

### 8.1 vLLM Provider 实现要求

vLLM 通过 OpenAI 兼容 API 暴露服务，建议以独立进程方式启动：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-prefix-caching
```

`providers/vllm_provider.py` 需要实现：

- `async generate(query, model_name, max_tokens, temperature) -> InferenceResult`
- `async stream(query, ...) -> AsyncIterator[str]`
- `async health() -> bool`：调 `GET /health`
- `async fetch_runtime_load() -> RuntimeLoadSnapshot`：抓 `GET /metrics`，解析以下 Prometheus 指标
  - `vllm:num_requests_running`
  - `vllm:num_requests_waiting`
  - `vllm:gpu_cache_usage_perc`

### 8.2 Ollama Provider 实现要求

`providers/ollama_provider.py` 需要实现：

- `async generate(...)`：调 `POST /api/generate`，`stream=false`
- `async stream(...)`：调 `POST /api/generate`，`stream=true`，逐行解析 NDJSON
- `async health() -> bool`：调 `GET /api/tags`
- `async fetch_runtime_load() -> RuntimeLoadSnapshot`：Ollama 不暴露 KV cache，可用 "当前进行中的请求数" 近似（自己在 Provider 内部维护一个 in-flight 计数器）

### 8.3 统一要求

无论哪个 Provider，对上都必须：

- 输出 `InferenceResult`，且 `InferenceResult.metrics` 中 **TTFT、TPOT、tokens/s** 字段至少有有效值之一（流式输出时三个都应该有）
- 失败时抛出可识别的异常，由 `InferenceEngine` 触发 fallback
- 严格使用 **tiktoken** 做 token 计数，不再使用 `split()` 估算

---

## 9. SSE 流式接口实现

### 9.1 新增接口

```text
POST /route/stream
```

请求体与 `/route` 完全一致。

### 9.2 事件协议

使用 SSE，事件类型 (`event:`) 与负载 (`data:`) 如下：

```text
event: meta
data: {"query_id": "...", "model_name": "vllm-qwen-7b", "engine": "vllm",
       "routing": { ... 同 /route ... }}

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

### 9.3 实现要求

- 推荐使用 `sse-starlette` 的 `EventSourceResponse`
- 必须在产出第一个 `token` 事件前先发出 `meta` 事件
- **TTFT** = 从收到 HTTP 请求到首个 `token` 事件的时间
- **TPOT** = 第二个 token 起，每个 token 的平均时间间隔
- 当 engine 失败时，应在已经开始流式输出之后做 fallback：发出 `error` 事件，并视情况切换到 fallback engine 继续推送（实现 best-effort 即可）

### 9.4 测试方法

```bash
curl -N -sS http://localhost:8083/route/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Write a short poem about caching",
    "user_id": "u1",
    "user_tier": "free"
  }'
```

`-N` 关闭缓冲，应看到事件逐条流出。

---

## 10. 推理层指标采集与 Prometheus 暴露

### 10.1 必须采集的指标

在 `infra/metrics.py` 中至少定义以下 Prometheus 指标：

| 指标名 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `llm_router_requests_total` | Counter | `engine`, `model`, `status` | 请求总数 |
| `llm_router_ttft_seconds` | Histogram | `engine`, `model` | TTFT 分布 |
| `llm_router_tpot_seconds` | Histogram | `engine`, `model` | TPOT 分布 |
| `llm_router_tokens_per_second` | Histogram | `engine`, `model` | 输出吞吐 |
| `llm_router_request_duration_seconds` | Histogram | `engine`, `model` | 端到端延迟 |
| `llm_router_active_requests` | Gauge | `engine` | 进行中请求 |
| `llm_router_engine_kv_cache_usage` | Gauge | `engine` | KV cache 使用率（仅 vLLM） |
| `llm_router_fallback_total` | Counter | `from_engine`, `to_engine`, `reason` | fallback 触发次数 |

### 10.2 暴露接口

```text
GET /metrics
```

返回 Prometheus 标准文本格式：

```text
# HELP llm_router_requests_total ...
# TYPE llm_router_requests_total counter
llm_router_requests_total{engine="vllm",model="vllm-qwen-7b",status="success"} 42
...
```

实现可以直接使用 `prometheus_client.generate_latest()` + `CONTENT_TYPE_LATEST`。

### 10.3 验证

```bash
curl -sS http://localhost:8083/metrics | head -n 30
```

---

## 11. 基于实时负载的路由策略

### 11.1 LoadTracker 实现要求

`infra/load_tracker.py` 中实现：

- 启动一个后台异步任务，**每 2 秒** 调用所有已启用 engine 的 `fetch_runtime_load()`
- 把最新快照缓存在内存里
- 提供同步访问接口 `get_snapshot(engine: str) -> RuntimeLoadSnapshot | None`
- 在 `app.on_event("startup")` 启动，`shutdown` 优雅关闭

### 11.2 路由器中的应用

在 `router.py` 中，当 `strategy == "load_aware"` 时，综合打分公式建议为：

```text
score = w_success * success_rate
      + w_priority * (1 / priority)
      - w_latency  * normalized(avg_latency_ms)
      - w_cost     * normalized(cost_per_1k_output)
      - w_kv       * runtime_load.kv_cache_usage
      - w_queue    * normalized(runtime_load.queue_depth)
```

其中：

- 权重来自 `config.yaml: router.load_weights`
- 若 `runtime_load is None`（引擎未启用或采集失败），相关项以中性值代入（如 0.5）
- 最终选择 score 最高的候选模型

### 11.3 演示场景

启动两个 engine（vLLM + Ollama 或两个 Ollama 实例），用并发脚本对 vLLM 压一波请求，期望看到：

- 新请求开始倾向于走 Ollama（因为 vLLM 的 `kv_cache_usage` / `queue_depth` 变高）
- `RoutingInfo.runtime_load` 字段能反映这种变化
- 压力撤去后，路由会重新回到 vLLM

> 这是本阶段最具 Inference Infra 味道的能力，**也是面试时最值得讲的故事**。

---

## 12. 健康检查扩展

`GET /health` 在 Phase 2/3 基础上，新增 `engines` 部分：

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

## 13. Streamlit 看板新增页

在 Phase 3 看板基础上新增一页：

### `Inference Engine`

页面作用：

- 展示每个 engine 的实时负载
- 展示 TTFT / TPOT / tokens-per-second 的分位数
- 展示 fallback 触发次数与原因分布

需要的后端接口：

- `GET /health`（取实时负载快照）
- `GET /metrics`（解析 Prometheus 文本，取分位数）
- 或者新增 `GET /inference/stats` 由后端聚合好返回（推荐，避免前端解析 Prometheus）

实现要求：

- 至少展示 1 张折线图（最近 N 分钟的 active_requests）
- 至少展示 1 张柱状图（按 engine 的 TTFT P50/P95）
- 顶部 4 个指标卡：总请求数、平均 TTFT、平均 tokens/s、fallback 次数

---

## 14. 测试要求

在 `test_main.py` 中新增以下用例：

- `/route/stream` 能正常返回 SSE，至少能收到 `meta`、`token`、`done` 三种事件
- `/metrics` 返回 200，且文本中包含 `llm_router_requests_total`
- 当所有真实 engine 都不可用时，`/route` 仍能 fallback 到 `local_mock`，不返回 500
- `RoutingInfo.engine` 字段在请求后能正确反映实际所用引擎
- `LoadTracker` 在 engine 不可达时不会抛异常导致后台任务死掉

---

## 15. 启动与验证

### 15.1 启动本地推理引擎（任选其一）

**方案 A：vLLM（推荐，需要 NVIDIA GPU）**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-prefix-caching
```

**方案 B：Ollama（无 GPU 也可，Mac M 系列推荐）**

```bash
ollama serve &
ollama pull qwen2.5:7b
```

### 15.2 启动 Router

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8083
```

### 15.3 端到端验证清单

| 验证项 | 命令 | 期望 |
|---|---|---|
| API 文档 | 打开 `http://localhost:8083/docs` | 能看到 `/route/stream`、`/metrics` |
| 健康检查 | `curl -s :8083/health` | engines 部分有真实状态 |
| 非流式推理 | `curl -s :8083/route -d '...'` | 走真实 engine，`response` 非 Echo |
| 流式推理 | `curl -N -s :8083/route/stream -d '...'` | 能看到逐 token 输出 |
| Prometheus | `curl -s :8083/metrics` | 含 ttft / tpot / requests_total |
| 负载路由 | 并发压 vLLM，观察后续请求是否切到 Ollama | 路由切换 |
| 看板 | 打开 Streamlit `Inference Engine` 页 | 图表有真实数据 |

---

## 16. 自检清单

提交前请逐项确认：

- [ ] 至少 1 个真实本地 engine 能跑通端到端推理
- [ ] `/route/stream` 能产出符合协议的 SSE 事件流
- [ ] TTFT、TPOT、tokens/s 三个指标在流式响应中能被正确测出
- [ ] `/metrics` 返回有效的 Prometheus 文本
- [ ] `LoadTracker` 后台任务能稳定运行 ≥ 10 分钟不崩
- [ ] 路由器在 `strategy=load_aware` 下能体现出基于负载的偏好
- [ ] 真实 engine 全部不可用时，仍能 fallback 到 `local_mock`，不 500
- [ ] tiktoken 替换掉了 `split()` 的 token 估算
- [ ] 看板 Inference Engine 页能看到真实数据
- [ ] 所有 pytest 用例通过

---

## 17. 阶段总结与面试讲法建议

本阶段交付的不再只是 "一个能路由的 API 网关"，而是一个 **"带本地推理 + 推理层可观测 + 负载感知调度的混合 LLM 服务平台"**。

面试时可以按下面的 **三层故事** 来讲这个项目：

1. **应用层（Phase 1–3）**：FastAPI + Pydantic + 配置驱动 + 多 Provider + Fallback + Streamlit 看板，体现 "工程能力 + 系统设计 + 可观测性"
2. **推理层（Phase 4）**：接入 vLLM/Ollama，**实测 TTFT / TPOT / tokens-per-second**，并通过 Prometheus 暴露给监控
3. **调度层（Phase 4）**：基于 vLLM 真实 `kv_cache_usage` 和 `queue_depth` 做负载感知路由，体现对 **Continuous Batching / KV Cache** 工作原理的理解

> 注意：本阶段做完后，**项目本身仍然不算严格意义的 Inference Engine**（PagedAttention、CUDA kernel、量化等仍未涉及）。如果目标岗位是 vLLM / TensorRT-LLM / SGLang 这类深度 Infra 团队，建议本项目作为 "Platform / Serving 经验" 配合一个独立的 **mini inference engine** 项目一起呈现。
