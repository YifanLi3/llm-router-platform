# LLM Router & Execution Platform

## Phase 1 开发说明书

本阶段要求从零创建一个最小可用的 LLM 路由系统，完成 `API -> 路由 -> 推理` 主链路的搭建、联调与验收。

## 1. 阶段目标与交付成果

完成本阶段后，项目应满足以下交付要求：

- 启动一个 FastAPI 服务
- 打开接口文档：`http://localhost:8081/docs`
- 访问健康检查接口：`GET /health`
- 调用推理接口：`POST /route`
- 得到稳定的结构化 JSON 返回

`POST /route` 至少返回这些字段：

- `query_id`
- `response`
- `model_name`
- `tokens`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing`

## 2. 本阶段实施范围与非目标事项

本阶段仅要求完成最小可用主链路，以下能力不属于本阶段实施范围：

- 不要求 Kafka、ClickHouse、Flink
- 不要求 Prometheus、Grafana
- 不要求 Streamlit 看板
- 不要求 Slack Bot
- 不要求真实调用 OpenAI、Anthropic、vLLM
- 不要求数据库或业务数据集

说明：本阶段推理层允许使用 Mock Provider，因此实现重点在于系统结构、接口契约与模块分层，不要求准备训练数据、业务数据或外部服务依赖。

## 3. 技术栈与环境要求

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- PyYAML
- Pytest

## 4. 项目初始化与环境准备

### 4.1 创建项目目录

在本地工作目录下创建项目文件夹，例如：

```bash
mkdir One
cd One
```

### 4.2 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
./venv/bin/python -m pip install -U pip
```

在项目根目录创建 `requirements.txt`：

```txt
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic>=2.7,<3.0
PyYAML>=6.0,<7.0
pytest>=8.0,<9.0
httpx>=0.27,<1.0
```

然后安装依赖：

```bash
./venv/bin/python -m pip install -r requirements.txt
```

## 5. 项目目录结构规范

项目建议采用如下标准目录结构：

```text
One/
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   └── config.py
│   ├── services/
│   │   ├── inference.py
│   │   └── router.py
│   ├── __init__.py
│   ├── main.py
│   └── schemas.py
├── docs/
│   └── student_phase1_guide.md
├── tests/
│   └── test_api.py
├── config.yaml
├── main.py
├── requirements.txt
└── README.md
```

目录职责说明如下：

- `app/main.py`：创建 FastAPI 应用并启动服务
- `app/api/routes.py`：只处理 HTTP 请求和响应编排
- `app/core/config.py`：读取配置文件
- `app/services/router.py`：负责选模型
- `app/services/inference.py`：负责推理执行
- `app/schemas.py`：定义请求、响应和配置数据结构
- `tests/test_api.py`：基础接口测试
- `main.py`：根目录启动入口

## 6. 配置文件规范

在项目根目录创建 `config.yaml`：

```yaml
api:
  host: "0.0.0.0"
  port: 8081

router:
  default_model: "general-small"
  models:
    general-small:
      provider: "mock"
      max_tokens: 1024
      cost_per_1k_input: 0.001
      cost_per_1k_output: 0.002
      priority: 1
      capabilities:
        - general
        - chat
    coding-pro:
      provider: "mock"
      max_tokens: 2048
      cost_per_1k_input: 0.002
      cost_per_1k_output: 0.004
      priority: 2
      capabilities:
        - coding
        - debugging
        - general
    long-context:
      provider: "mock"
      max_tokens: 8192
      cost_per_1k_input: 0.003
      cost_per_1k_output: 0.006
      priority: 3
      capabilities:
        - general
        - long_context
```

本阶段重点关注以下配置项：

- `api.host`
- `api.port`
- `router.default_model`
- `router.models`

## 7. 数据契约设计

在 `app/schemas.py` 中完成以下数据模型定义：

- `QueryRequest`
- `RoutingDecision`
- `InferenceResult`
- `InferenceResponse`
- `HealthResponse`
- `AppConfig`

基本要求：

- `QueryRequest.query` 必须非空
- `user_tier` 只能是 `free`、`premium`、`enterprise`

请求模型建议至少包含以下字段：

- `query`
- `user_id`
- `user_tier`
- `max_tokens`
- `temperature`

响应模型建议至少包含以下字段：

- `query_id`
- `response`
- `model_name`
- `tokens.input`
- `tokens.output`
- `tokens.total`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing.reason`
- `routing.confidence`
- `routing.query_type`

## 8. 配置加载模块实现

在 `app/core/config.py` 中实现配置加载函数，例如：

- `get_config()`

实现要求：

- 从项目根目录读取 `config.yaml`
- 解析 YAML
- 转为 `AppConfig`

该模块的作用是为 API 层、路由模块和推理模块提供统一配置来源。

## 9. 路由模块实现

在 `app/services/router.py` 中实现一个最小路由器类，例如：

- `QueryRouter`

模块职责：

- 输入：`QueryRequest`
- 输出：`RoutingDecision`

基本要求：

- 能选出一个 `selected_model`
- 能给出一个 `routing_reason`
- 最好给出一个简单的 `confidence`

建议采用以下最小路由策略：

1. 如果 query 很长，例如长度大于 1000，优先走 `long-context`
2. 如果 query 中包含 `code`、`function`、`class`、`bug`、`python` 等关键词，走 `coding-pro`
3. 其他情况走默认模型 `general-small`

说明：本阶段不要求使用机器学习分类器，基于规则的路由策略即可满足要求。

## 10. 推理模块实现

在 `app/services/inference.py` 中实现以下组件：

- `MockProvider`
- `InferenceEngine`

模块职责：

- 接收路由结果
- 返回一段文本
- 同时返回 tokens、latency、cost 等指标

建议实现方式如下：

- `response_text = f"Echo from {model_name}: {query[:200]}"`
- 输入 token 数可用 `len(query.split())` 估算
- 输出 token 数可用 `len(response_text.split())` 估算
- 延迟可使用 `time.time()` 计算
- 费用可根据配置里的单价做一个简单估算

本阶段不要求真实模型调用，因此返回结果应具备可预测、可解释、可重复的特点。

## 11. API 层实现

### 11.1 创建应用入口

在 `app/main.py` 中创建 FastAPI 应用。

应用标题建议设置为：

- `LLM Router & Execution Platform`

### 11.2 实现健康检查接口

实现：

- `GET /health`

返回结果至少应包含：

```json
{
  "status": "healthy",
  "services": {
    "router": { "healthy": true },
    "inference": { "healthy": true }
  }
}
```

### 11.3 实现推理接口

实现：

- `POST /route`

接口处理流程如下：

1. 接收请求体并解析为 `QueryRequest`
2. 调用路由器选模型
3. 调用推理引擎处理 query
4. 拼装统一响应
5. 返回结构化 JSON

建议统一采用如下返回格式：

```json
{
  "query_id": "string",
  "response": "string",
  "model_name": "string",
  "tokens": {
    "input": 0,
    "output": 0,
    "total": 0
  },
  "cost_usd": 0.0,
  "latency_ms": 0,
  "cached": false,
  "routing": {
    "reason": "string",
    "confidence": 0.0,
    "query_type": "general"
  }
}
```

## 12. 启动入口规范

建议在项目根目录保留一个 `main.py`，作为统一启动入口，例如：

- 从 `app.main` 导入 `app`
- 从 `app.main` 导入 `run`
- 在 `if __name__ == "__main__"` 中调用 `run()`

采用该入口后，可使用以下命令启动项目：

```bash
./venv/bin/python main.py
```

这样可以降低启动复杂度，避免学生记忆额外的运行参数。

## 13. 测试要求

在 `tests/test_api.py` 中使用 `fastapi.testclient.TestClient` 编写最小 smoke test。

最低测试要求如下：

- `/health` 返回 200
- `/route` 返回 200
- `/route` 的响应中包含 `model_name`
- `/route` 的响应中包含 `response`

运行方式如下：

```bash
./venv/bin/python -m pytest -q
```

## 14. 运行与验证说明

### 14.1 启动服务

```bash
./venv/bin/python main.py
```

### 14.2 打开接口文档

在浏览器中访问：

```text
http://localhost:8081/docs
```

### 14.3 测试健康检查接口

```bash
curl -sS http://localhost:8081/health
```

### 14.4 测试推理接口

```bash
curl -sS http://localhost:8081/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Write a Python function to reverse a list",
    "user_id": "u1",
    "user_tier": "free"
  }' | python3 -m json.tool
```

## 15. 预期结果示例

编程类 query 的示例返回可参考：

```json
{
  "query_id": "14e611c2-7ada-49d0-b02c-5235a662769f",
  "response": "Echo from coding-pro: Write a Python function to reverse a list",
  "model_name": "coding-pro",
  "tokens": {
    "input": 8,
    "output": 11,
    "total": 19
  },
  "cost_usd": 0.00006,
  "latency_ms": 1,
  "cached": false,
  "routing": {
    "reason": "Detected coding-related keywords in the query.",
    "confidence": 0.82,
    "query_type": "coding"
  }
}
```

普通问题的示例返回可参考：

```json
{
  "query_id": "f1f979e0-48ba-46d3-b310-a73c38f32042",
  "response": "Echo from general-small: What is the capital of France?",
  "model_name": "general-small",
  "tokens": {
    "input": 6,
    "output": 9,
    "total": 15
  },
  "cost_usd": 0.000024,
  "latency_ms": 1,
  "cached": false,
  "routing": {
    "reason": "Using default general-purpose model.",
    "confidence": 0.65,
    "query_type": "general"
  }
}
```

## 16. 提交前自检清单

提交前请逐项确认：

- `http://localhost:8081/docs` 可打开
- `GET /health` 返回 200 且是 JSON
- `POST /route` 对正常输入返回稳定字段
- `query` 为空时返回校验错误
- `user_tier` 非法时返回校验错误
- 至少两条不同 query 能让路由结果发生差异，或理由发生差异
- `pytest` 能通过

## 17. 常见问题说明

### 17.1 端口被占用

如果 `8081` 被占用，可以：

- 先结束占用进程
- 或修改 `config.yaml` 中的 `api.port`

### 17.2 页面无法访问

通常是服务没有启动。请先执行：

```bash
./venv/bin/python main.py
```

再访问：

```text
http://localhost:8081/docs
```

### 17.3 是否需要准备数据集

不需要。本阶段是系统骨架搭建，不依赖业务数据集。

## 18. 阶段总结

本阶段最重要的不是功能数量，而是主链路打通、接口结构稳定以及代码职责清晰。

本阶段应交付一个具备以下特征的最小系统：

- 能启动
- 能调用
- 能返回稳定 JSON
- 代码职责分层清楚
- 能为后续真实 Provider 接入留出扩展空间

