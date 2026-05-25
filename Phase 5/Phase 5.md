# LLM Router & Execution Platform

## Phase 5 开发说明书 —— LLM Gateway Console

本阶段在 Phase 1–4 已经完成的 "**智能路由 + 多 Provider + 本地推理 + 推理可观测**" 基础上，把项目正式升级为一个 **对外可用的生产形态 LLM Serving Gateway + Ops Console**。

完成本阶段后，项目应同时具备两个对外视角：

- **开发者视角**：暴露 **OpenAI 兼容协议**，任何 OpenAI SDK / LangChain / Cursor / Continue.dev 都能直接接入
- **运维与调试视角**：Streamlit **Chat 调试台 + Admin 控制台**，能直接验证模型可用性、流式链路与基础监控

本阶段是 **第一个强制要求接入真实推理后端并以真实结果作为验收依据** 的阶段。

---

## 1. 阶段目标

完成本阶段后，项目应满足以下要求：

- 启动一个 FastAPI 服务
- 打开接口文档：`http://localhost:8084/docs`
- 新增并对外暴露 **OpenAI 兼容接口**：
  - `POST /v1/chat/completions`（支持流式与非流式）
  - `GET  /v1/models`
- 新增 `GET /health` 的完整字段：`status` / `uptime_s` / `version` / `details`
- 启动 **Streamlit 双页前端**：
  - `app.py` —— Chat 调试页（带打字机效果）
  - `pages/1_Admin.py` —— 运行状态控制台
- 至少接入 **1 种真实推理后端**（vLLM / Ollama / OpenAI 兼容第三方任选其一）
- 必须开启 **CORS**，允许 Streamlit 直接调后端

`POST /v1/chat/completions` 必须返回 OpenAI 协议格式（详见第 6 节），至少包含：

- `id`（对应内部 `request_id`）
- `object = "chat.completion"`
- `model`
- `choices[].message.content`
- `choices[].finish_reason`
- `usage.prompt_tokens / completion_tokens / total_tokens`

流式响应必须严格遵守 OpenAI SSE 协议：每条 `data:` 是 `chat.completion.chunk` 对象，结束发 `data: [DONE]`。

---

## 2. 与前几个 Phase 的关系

| Phase | 解决的事 | 协议 / 接口 |
|---|---|---|
| 1 | 主链路打通 | 自定义 `/route` |
| 2 | 智能路由 + Fallback + 多 Provider | 自定义 `/route` |
| 3 | 可观测看板 | `/analytics`、`/quality/dashboard`、`/feedback` |
| 4 | 真实本地推理 + 流式 + 推理层指标 + 负载感知 | 自定义 `/route/stream`、`/metrics` |
| **5** | **OpenAI 兼容协议 + Chat 调试台 + 真后端验收** | **`/v1/chat/completions`、`/v1/models`** |

> **本阶段不重写 Phase 4 的路由、Provider、可观测能力**；本阶段只新增 "**对外的 OpenAI 兼容外壳 + Chat 调试 UI + 真实接入与验收**"。
> 内部依然走 Phase 2 的路由 + Phase 4 的真实 Provider + Phase 4 的负载感知调度。

一句话总结：

- Phase 1–4 做的是 **"对内的 Platform 能力"**
- **Phase 5 做的是 "对外的 Developer Experience + 真实可用性验收"**

---

## 3. 实施范围

本阶段必须完成：

1. OpenAI 兼容的 `POST /v1/chat/completions`（非流 + 流）
2. OpenAI 兼容的 `GET /v1/models`
3. `/v1/chat/completions` 内部转发至 Phase 2 路由 + Phase 4 真实 Provider
4. CORS 中间件
5. `GET /health` 字段补齐：`uptime_s`、`version`、`details.engine`
6. Streamlit Chat 调试页（流式打字机效果）
7. Streamlit Admin 控制台（健康 + 模型列表 + ≥ 1 张图）
8. **接入至少 1 个真实推理后端**，并用真实调用结果验收

本阶段 **非目标事项**：

- 不要求多用户登录 / 鉴权（API Key 字段可保留但不强制校验）
- 不要求自己实现 Embedding / Audio / Image 等 OpenAI 其他接口
- 不要求 Phase 4 已经覆盖的能力（路由、负载感知、Prometheus）做重写

---

## 4. 技术栈与环境要求

在 Phase 1–4 基础上新增（或确认已具备）：

- **requests**（Streamlit 前端调后端用）
- **plotly**（Admin 页表格 / 图表）
- **starlette CORSMiddleware**（FastAPI 自带）
- **sse-starlette**（Phase 4 已引入，沿用即可）

`requirements.txt` 新增：

```txt
requests>=2.32,<3.0
plotly>=5.22,<6.0
```

---

## 5. 项目目录扩展

在 Phase 4 目录基础上做前后端分离调整：

```text
/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口 + CORS
│   │   ├── api/
│   │   │   ├── health.py            # /health
│   │   │   ├── route.py             # 自定义 /route /route/stream (Phase 1-4)
│   │   │   ├── openai_compat.py     # 新增：/v1/chat/completions /v1/models
│   │   │   ├── analytics.py         # /analytics /quality/dashboard /feedback (Phase 3)
│   │   │   └── metrics.py           # /metrics (Phase 4)
│   │   ├── core/
│   │   │   ├── router.py            # Phase 2 路由
│   │   │   ├── inference.py         # Phase 2/4 推理引擎
│   │   │   ├── providers/           # Phase 4 真实 Provider
│   │   │   └── adapters/
│   │   │       └── openai_adapter.py    # 新增：内部 schema <-> OpenAI schema
│   │   ├── infra/                   # Phase 4 metrics / load_tracker / streaming
│   │   └── models/
│   │       ├── internal.py          # 内部 QueryRequest / InferenceResponse
│   │       └── openai.py            # 新增：OpenAI 协议的 Pydantic 模型
│   └── config.py
├── frontend/
│   ├── app.py                       # 新增：Chat 调试页（默认主页）
│   └── pages/
│       ├── 1_Admin.py               # 新增：Admin 控制台
│       └── 2_Inference_Engine.py    # Phase 4 已存在
├── config.yaml
└── README.md
```

模块职责说明：

- `openai_compat.py`：**只做协议转换和透传**，不重写路由逻辑
- `openai_adapter.py`：双向 schema 映射，是 Phase 5 的核心新增点
- `frontend/app.py`：作为 Streamlit 默认主页，必须是 Chat 页
- `frontend/pages/1_Admin.py`：管理员视角，**和 Phase 3 看板可以共用组件**

---

## 6. OpenAI 兼容协议契约

### 6.1 请求格式（`POST /v1/chat/completions`）

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

要求：

- `model` 必须是 `config.yaml` 中已定义的模型名
- `messages` 至少支持 `system / user / assistant` 三种 role
- 同时兼容 OpenAI 客户端常见可选字段（`top_p`、`presence_penalty`、`frequency_penalty`、`stop` 等），未实现时可静默忽略
- 兼容 `prompt`（旧式 completions 风格）作为可选：当未传 `messages` 时，把 `prompt` 拼成单条 `user` message

### 6.2 非流式响应格式

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

### 6.3 流式响应格式（SSE）

每个 chunk：

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

要求：

- 第一条 chunk 的 `delta` 必须包含 `"role": "assistant"`，后续 chunk 只发 `content`
- **结束信号必须是 `data: [DONE]`**（注意是字面 `[DONE]`，不是 JSON）
- 使用 `text/event-stream` 作为响应 `Content-Type`

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

模型清单**直接从 `config.yaml` 的 `router.models` 派生**，不允许在代码里写死。

### 6.5 与内部协议的关系

`/v1/chat/completions` 的实现必须遵循以下流程：

```
OpenAI 请求
    ↓ openai_adapter.from_openai()
QueryRequest (Phase 1 内部协议)
    ↓ QueryRouter.route()  (Phase 2)
RoutingDecision
    ↓ InferenceEngine.execute() / stream()  (Phase 2/4)
InferenceResult / AsyncIterator
    ↓ openai_adapter.to_openai() / to_openai_chunks()
OpenAI 响应
```

**严禁**绕开路由和 Provider 抽象，让 `/v1/chat/completions` 直接去调 OpenAI / vLLM。

---

## 7. 健康检查接口规范（增强）

`GET /health` 必须返回以下结构（Phase 3/4 字段保留并扩展）：

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
  "services": { ... 沿用 Phase 4 ... }
}
```

要求：

- `uptime_s` = 从进程启动到当前的秒数
- `version` 从 `config.py` 或 `__version__` 读取，不允许写 `"unknown"`
- `status` 的取值：`healthy` / `degraded` / `unhealthy`
  - 所有真实 engine 全部不可达：`degraded`（因为还有 `local_mock` 兜底）
  - 路由器初始化失败：`unhealthy`

---

## 8. CORS 配置要求

在 `backend/app/main.py` 中添加：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 本地开发可放开
    allow_methods=["*"],
    allow_headers=["*"],
)
```

要求：

- 必须能让浏览器中运行的 Streamlit 直接调通 `/v1/chat/completions`
- 生产部署时再收紧 `allow_origins` 到具体域名（在 README 中注明即可）

---

## 9. Streamlit Chat 调试页（`frontend/app.py`）

### 9.1 左侧配置区必须包含

- **API Base**：默认 `http://localhost:8084`
- **API Key**：文本框，可空（不强制鉴权）
- **Model 下拉框**：必须从 `GET /v1/models` 拉取，**不允许在前端硬编码**
- **Streaming 开关**：默认 **开启**
- 可选：System Prompt、Temperature、Max Tokens 滑块

### 9.2 右侧聊天区必须包含

- 对话历史（使用 `st.chat_message`）
- 发送按钮 / 输入框（`st.chat_input`）
- **流式模式下必须有打字机效果**（同一条助手消息逐 chunk 更新，使用 `st.empty()` + 累加字符串）
- 每条助手消息末尾显示 `latency_ms` 与 `tokens` 小字
- 出错时显示后端错误信息（连接失败 / 模型不存在 / 鉴权失败），**不允许吞错**

### 9.3 调用规范

- 调用后端必须使用 `POST /v1/chat/completions`，**不允许调内部 `/route`**
  - 理由：Chat 页同时充当 "**外部开发者会怎么用你的 Gateway**" 的演示
- 流式请求使用 `requests.post(stream=True)` + `iter_lines()`，自行解析 `data:` 前缀和 `[DONE]`

---

## 10. Streamlit Admin 控制台（`frontend/pages/1_Admin.py`）

### 10.1 必须展示

- **平台健康状态**（读取 `/health`，把 `status`、`uptime_s`、`version`、各 engine 状态用色块或表格展示）
- **模型信息列表**（读取 `/v1/models`，至少展示 `id` + `owned_by`；如果有能力可关联 `config.yaml` 中的 `capabilities`、`priority`）
- **至少 1 张图**：
  - 推荐复用 Phase 3 `/analytics` 的数据，画 "近 N 分钟请求数" 折线图
  - 或调 `/metrics` 解析 TTFT 分位数画柱状图
  - 用 `plotly` 实现

### 10.2 错误处理

后端不可用时：

- 顶部用红色 banner 提示 "后端不可达"
- 不允许显示伪造的随机数 / 占位假数据

---

## 11. 真实推理后端接入与验收

### 11.1 接入要求

**至少** 接入下列其中一种，并能在 Chat 页发起对话拿到真实结果：

| 选项 | 推荐场景 | 启动命令 |
|---|---|---|
| **vLLM**（OpenAI 兼容） | 有 NVIDIA GPU | `python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --port 8000` |
| **Ollama** | Mac M 系列 / 无 GPU | `ollama serve && ollama pull qwen2.5:7b` |
| **第三方 OpenAI 兼容** | 没有本地资源 | DeepSeek / Moonshot / 智谱 等任意一家 |

### 11.2 配置切换要求

- **后端地址、模型名、API Key 必须从配置 / 环境变量读取**，不允许写死在代码中
- `config.yaml` 中至少配置 2 个可选模型，让 `/v1/models` 返回 ≥ 2 条记录

### 11.3 验收口径

本阶段**唯一**的功能正确性判定依据：

> **在 Streamlit Chat 页发起一次真实对话，开启 Streaming，能看到逐 token 输出，且最终结果非 Echo / 非 Mock。**

如果只能拿到 Mock 返回，本阶段视为 **未通过**。

---

## 12. 启动与验证

### 12.1 启动顺序

```bash
# 1. 启动真实推理后端（任选其一）
ollama serve &        # 或 vLLM

# 2. 启动 Gateway
./venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8084

# 3. 启动前端
./venv/bin/python -m streamlit run frontend/app.py
```

### 12.2 端到端验证清单

| 验证项 | 命令 / 操作 | 期望 |
|---|---|---|
| API 文档 | 打开 `http://localhost:8084/docs` | 同时看到 `/route`、`/v1/chat/completions`、`/v1/models` |
| 模型列表 | `curl -s :8084/v1/models` | 至少 2 条记录，与 `config.yaml` 一致 |
| 非流式 Chat | 用 `openai` Python SDK 调（见下） | 能拿到真实文本 |
| 流式 Chat | 用 `openai` SDK + `stream=True` | 逐 chunk 输出，无 [DONE] 解析报错 |
| Chat 调试页 | 浏览器打开 Streamlit | 能打字、有打字机效果 |
| Admin 页 | 浏览器打开 | 健康 + 模型 + 1 张图都正常 |
| CORS | 浏览器 devtools 查看 | 无 CORS 报错 |
| 后端宕机 | 关掉 ollama / vllm，再用 Chat 页发请求 | 友好错误提示，不 500 不假数据 |

### 12.3 用 OpenAI SDK 验证（关键）

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

> **这是本阶段最有说服力的演示**：你的 Gateway 能被官方 OpenAI SDK 直接调通。面试时可以现场跑。

---

## 13. 测试要求

在 `tests/` 中新增：

- `test_openai_compat.py`
  - `/v1/models` 返回结构正确
  - `/v1/chat/completions` 非流式返回符合 OpenAI 协议
  - 流式响应每条 `data:` 是合法 JSON，最后必须有 `data: [DONE]`
  - `model` 字段为不存在的值时返回 4xx，错误信息符合 OpenAI 风格（含 `error.message`、`error.type`）
- `test_health.py`
  - `/health` 返回的 `uptime_s` 单调递增
  - 真实 engine 不可用时 `status` 降级为 `degraded`，不返回 5xx

---

## 14. 自检清单

提交前请逐项确认：

- [ ] `GET /v1/models` 返回与 `config.yaml` 一致的模型列表
- [ ] `POST /v1/chat/completions` 非流式响应字段完全符合 OpenAI 协议
- [ ] `POST /v1/chat/completions` 流式响应严格使用 `data: ... \n\n`，结束发 `data: [DONE]`
- [ ] OpenAI 官方 Python SDK 能直接调通（非流 + 流均通过）
- [ ] CORS 配置生效，浏览器中调用无报错
- [ ] `/health` 返回 `uptime_s`、`version`、`details.engine`
- [ ] Streamlit Chat 页：流式打字机效果正常，错误能展示
- [ ] Streamlit Admin 页：健康 / 模型 / 图表都展示真实数据，不假数据
- [ ] 至少 1 个真实 engine 跑通端到端对话（非 Mock）
- [ ] 模型名、后端地址、API Key 全部从配置 / 环境变量读取
- [ ] 所有 pytest 用例通过

---

## 15. 阶段总结与面试讲法

完成 Phase 1–5 后，你的项目已经是一个**结构完整、对内对外都能讲清楚故事**的 LLM Gateway：

| 层 | 能力 | 对应 Phase |
|---|---|---|
| **对外协议层** | OpenAI 兼容 API + Chat 调试台 | **Phase 5** |
| **路由调度层** | 规则 + 综合打分 + 负载感知 + Fallback | Phase 2 + Phase 4 |
| **推理执行层** | 多 Provider + vLLM/Ollama 真实接入 + SSE | Phase 2 + Phase 4 |
| **可观测层** | Streamlit 看板 + Prometheus + TTFT/TPOT | Phase 3 + Phase 4 |
| **工程基础** | FastAPI + Pydantic + 配置驱动 + 分层 + 单测 | Phase 1 |

### 面试时的 30 秒讲法

> "我做了一个**生产形态的 LLM Gateway**：
> - **对外**暴露 **OpenAI 兼容协议**，任何 OpenAI SDK 或 LangChain 客户端可以零成本接入；
> - **对内**根据请求类型、用户等级、和后端 vLLM 的 **KV cache / queue depth** 实时负载做智能路由；
> - 支持 **SSE 流式输出**，实测 **TTFT / TPOT / tokens-per-second**，通过 **Prometheus** 暴露；
> - 任何 Provider 失败都会按 fallback 链自动切到下一个，不会 500；
> - 配套 **Streamlit Chat 调试台 + Admin 监控控制台**，可以现场演示。"

### 演示路径建议

面试现场如果时间允许，按这个顺序演示最有冲击力：

1. 打开 Streamlit Chat 页，发一条消息，看到流式打字机
2. 切到 Admin 页，看到健康状态和图表
3. **打开终端，用官方 `openai` Python SDK 调通自己 Gateway** ← 最有说服力
4. 杀掉 vLLM，再发一次请求，看到 fallback 到 Ollama，无任何 500
5. 打开 `/metrics`，给面试官看真实的 TTFT / TPOT 分位数

---

## 16. 与 Phase 6+ 的关系（前瞻）

Phase 5 完成后，本项目作为 **"应用层 LLM Gateway"** 已经接近工业级完成度。再往下走有两条独立方向：

- **方向 A：继续做 Gateway 高级特性**（Phase 6 候选）
  - 语义缓存（embedding + 相似度）
  - Rate limiting / 配额
  - Prompt template 管理
  - 多租户与审计日志

- **方向 B：另起一个项目走 Inference Engine 核心**（强烈推荐与本项目并行）
  - mini-vLLM：Continuous Batching + 简化版 PagedAttention + Prefix Cache
  - 量化部署对比实验
  - Triton / CUDA kernel 优化

> 如果目标岗位是 **AI Platform / LLM Infra**：Phase 1–5 足够主打。
> 如果目标岗位是 **vLLM / TensorRT-LLM / SGLang 这种深度推理引擎团队**：必须再做方向 B。
