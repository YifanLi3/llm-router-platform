# LLM Gateway Console

本项目需实现一个面向生产形态的“LLM Serving Gateway + Ops Console”系统。

后端作为统一推理入口（Gateway），对外提供稳定的生成接口与流式输出能力，对内负责把请求路由/适配到真实推理后端，并输出可用于运维与排障的基础运行信息。

前端作为运维与调试控制台（Console），提供 Chat 交互调试与 Admin 运行状态面板，便于快速验证模型可用性、接口兼容性、流式链路、以及基础监控数据展示。

本项目要求接入至少一种“真实推理后端”（本地或云端均可），并以真实后端的调用结果作为验收依据。
- **接口契约（API Contract）**：请求/响应字段稳定、可验证，便于前后端与未来组件对接
- **流式输出（SSE Streaming）**：支持边生成边展示，提升交互体验并贴近真实推理链路
- **可观测性（Observability）**：至少提供健康检查与基础运行信息，支持 Admin 页面展示
- **工程结构（Maintainability）**：模块清晰，便于测试、扩展与团队协作

---

## 1. 技术栈与约束

- Python 3.11+
- 后端：FastAPI + Uvicorn + Pydantic
- 前端：Streamlit
- HTTP 客户端： requests
- 图表：Plotly 

**重要约束：**
- 接入真实推理后端才能通过
- 不允许把核心逻辑堆在一个超长文件里；必须有清晰的模块划分（便于维护与评分）

**参考目录结构**

llm-infra-project/
├── backend/                  # 后端服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 入口、CORS 配置
│   │   ├── api/              # 路由层 (health, completions)
│   │   ├── core/             # 核心层 (推理后端适配适配器、状态统计)
│   │   └── models/           # Pydantic 数据模型层
│   └── config.py             # 环境变量与后端配置
├── frontend/                 # 前端 Streamlit
│   ├── app.py                # 主页 (默认可作为 Chat 页面)
│   └── pages/                # Streamlit 规定多页目录
│       └── 1_Admin.py        # Admin 监控页面
└── README.md

---

## 2. 功能模块划分

后端建议至少分成三类模块：
- **API 层**：接收请求、校验参数、返回响应
- **核心层**：推理后端适配与模型状态管理
- **数据模型层**：定义请求/响应的数据结构

前端建议至少分成两页：
- **Chat 页面**：发起生成请求并展示对话（含流式）
- **Admin 页面**：展示平台健康与模型状态

---

## 3. 后端功能（Backend）

### 3.1 生成请求与生成结果

后端需要接收“生成请求”，并返回“生成结果”。参考字段如下

**生成请求（CompletionRequest）支持：**

- request_id：请求唯一标识（前端可传；若不传，后端生成）
- model：模型名称（字符串）
- prompt：用户输入文本（可选）
- messages：消息列表（可选，用于对话式输入；至少支持 user/assistant/system 角色）
- max_tokens：生成上限（可给默认值）
- temperature：随机性参数（可给默认值）
- stream：是否开启流式输出（默认关闭；前端可开启）

**生成结果（CompletionResponse）包含：**

- request_id：与请求对应
- model：本次处理使用的模型名称
- text：生成的文本
- usage：token 统计（prompt_tokens、completion_tokens、total_tokens）
- latency_ms：本次请求耗时（毫秒）
- finish_reason：结束原因（固定为 stop 即可）

### 3.2 推理后端接入

需要在后端实现“可插拔的推理后端适配层”，将统一的 `CompletionRequest` 转换为真实模型的调用，并把真实模型返回结果映射回 `CompletionResponse`。

**必须满足：**
- **至少接入一种真实推理后端**：  
  - 本地推理服务（例如本机部署的模型服务）  
  - OpenAI 兼容协议的服务（包括自建或第三方）  
  - 其他可用的 HTTP 推理服务（只要能完成文本生成与流式生成）
- **支持配置切换**：能通过配置/环境变量切换后端地址、模型名、鉴权信息（如 API Key），避免写死在代码里
- **对接非流式与流式**：  
  - 非流式：一次性拿到完整文本  
  - 流式：能把增量文本逐段返回给前端（SSE）
- **可靠性**：当真实后端不可用时，后端需要返回可读的错误信息（例如连接失败、鉴权失败、模型不存在），前端应能展示错误提示

**可选：**

- 支持多个模型名称（至少 3 个可选项），并能正确传递到真实后端
- 统一 token/latency 统计口径（真实后端返回不了 token 时允许做合理估算，但需保持字段存在）

### 3.3 接口内容参考

#### 3.3.1 健康检查
- 路径：/health
- 作用：告诉前端“服务是否正常”
- 返回字段至少包含：
  - status：例如 healthy / degraded
  - uptime_s：服务运行时长（秒）
  - version：版本号
  - details：可包含 engine 名称等信息

#### 3.3.2 非流式文本生成
- 路径：/v1/chat/completions
- 作用：一次性返回生成结果（适合最简单对接）
- 行为要求：
  - 接收生成请求（包含 model 与 prompt/messages）
  - 返回生成结果（包含 text、usage、latency_ms 等）

#### 3.3.3 流式文本生成（SSE）
- 路径：/v1/chat/completions
- 作用：让前端边生成边显示
- 行为要求：
  - 前端开启 stream 后，后端需要分段推送“增量文本 delta”
  - 最后必须明确发出“结束信号”（例如 [DONE]）

### 3.4 跨域访问（CORS）

必须允许前端访问后端接口

实现方式不限，只要能正常访问即可

---

## 4. 前端功能（Streamlit）

### 4.1 Chat 页面

**左侧配置区至少包含：**
- API Base：后端地址（默认指向本机后端）
- API Key：可选（不强制做鉴权）
- Model 下拉框：至少包含以下 3 个
  - llama-3.1-8b-instruct
  - mistral-7b-instruct
  - mixtral-8x7b-instruct
- Streaming 开关：默认开启
- 可选：System Prompt、Temperature、Max Tokens

**右侧聊天区至少包含：**
- 对话历史
- 发送消息后：
  - 非流式：一次性显示助手完整回复
  - 流式：同一条助手消息逐段更新（打字机效果）
- 可选：显示耗时（latency_ms）

### 4.2 Admin 页面

至少展示以下内容：
- 平台健康状态（读取 /health）
- 模型信息列表（读取 /v1/models；如果暂时没做，可先做占位但需要说明）
- 至少 1 个图表（可用历史统计数据或后端统计数据）
