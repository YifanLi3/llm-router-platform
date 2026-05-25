# LLM Router & Execution Platform
# Phase 2 开发说明书

本阶段基于 Phase 1 的最小可用骨架继续演进，把“能跑起来的 API 链路”升级为“具备真实路由决策能力、支持多 Provider、并且在失败时能自动回退”的 LLM Router

## 1. 阶段目标

完成本阶段后，项目应满足以下要求：

- 启动一个 FastAPI 服务
- 打开接口文档：`http://localhost:8082/docs`
- 访问健康检查接口：`GET /health`
- 调用推理接口：`POST /route`
- 得到稳定的结构化 JSON 返回
- 同一个 `/route` 接口，对不同请求能体现不同的路由行为
- 至少支持 2 类 Provider
- 某个 Provider 或模型不可用时，系统能自动 fallback，而不是直接 500

`POST /route` 至少返回这些字段：

- `query_id`
- `response`
- `model_name`
- `provider`
- `tokens`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing`

其中 `routing` 建议至少包含：

- `reason`
- `confidence`
- `query_type`
- `token_count`
- `classification_confidence`
- `estimated_cost`
- `fallback_models`

## 2. 重点区别

Phase 1 的重点是：

- 打通 `API -> 路由 -> 推理` 主链路
- 能启动、能调用、能返回稳定 JSON
- 路由策略可以很简单
- 推理层可以先使用固定返回文本的 Provider

Phase 2 的重点是：

- 路由逻辑从“能选”升级为“会选”
- 从单一 Mock 扩展为多 Provider
- 引入配置驱动的模型清单与规则系统
- 引入 fallback / 降级机制
- 让 `/route` 返回“可解释路由信息”

 总结：

- Phase 1 解决“主链路能跑”
- Phase 2 解决“选模、Provider 可切换、失败不崩溃”

## 3. 实施范围

本阶段要求完成以下能力：

- 配置驱动的模型清单
- 配置驱动的路由规则
- 请求分类与 token 计数
- 能力过滤与综合打分选模
- 多 Provider 推理抽象
- 统一的推理输出结构
- 失败 fallback / 降级
- `/health` 展示 Provider 健康状态与模型可用性

## 4. 当前项目目录与职责

本项目是在 Phase 1 的简化结构上继续开发，目前采用扁平文件结构：

```text
/
├── config.yaml
├── config_loader.py
├── inference.py
├── main.py
├── requirements.txt
├── router.py
├── schema.py
├── test_main.py
└── docs/
    └── student_phase2_guide.md
```

各文件职责如下：

- `main.py`：创建 FastAPI 应用，暴露 `/health` 与 `/route`
- `config_loader.py`：读取并解析 `config.yaml`
- `schema.py`：定义请求、响应、配置和路由结构
- `router.py`：负责请求分类、规则匹配、能力过滤、打分选模
- `inference.py`：负责 Provider 调用、统一输出和 fallback
- `test_main.py`：基础接口测试
- `config.yaml`：统一管理模型、规则、端口与策略

## 5. 配置文件规范

本阶段继续使用项目根目录下的 `config.yaml`，重点关注以下配置项：

- `api.host`
- `api.port`
- `router.default_model`
- `router.strategy`
- `router.models`
- `router.routing_rules`
- `router.tier_cost_limits`

当前项目默认端口为：

```yaml
api:
  host: "0.0.0.0"
  port: 8082
```

模型配置建议至少包含：

- `provider`
- `provider_model`
- `max_tokens`
- `cost_per_1k_input`
- `cost_per_1k_output`
- `priority`
- `capabilities`
- `supported_tiers`
- `fallback_model`
- `api_key_env`
- `avg_latency_ms`
- `success_rate`

路由规则建议至少包含：

- `name`
- `condition`
- `candidates`
- `fallback`
- `reason`

规则表达式建议采用 Python 风格布尔表达式，例如：

```python
query_type == 'coding'
query_type == 'analysis' and token_count > 80
user_tier in ['premium', 'enterprise']
```

## 6. 数据契约设计

在 `schema.py` 中，本阶段建议定义并使用以下数据模型：

- `QueryRequest`
- `RoutingRuleConfig`
- `ModelConfig`
- `RouterConfig`
- `RoutingDecision`
- `RoutingInfo`
- `InferenceResult`
- `InferenceResponse`
- `HealthResponse`
- `AppConfig`

基本要求如下：

- `QueryRequest.query` 必须非空
- `user_tier` 只能是 `free`、`premium`、`enterprise`
- `InferenceResponse` 继续保持 Phase 1 的核心字段
- 新增 `provider` 与更完整的 `routing` 解释信息

请求模型建议至少包含：

- `query`
- `user_id`
- `user_tier`
- `max_tokens`
- `temperature`

响应模型建议至少包含：

- `query_id`
- `response`
- `model_name`
- `provider`
- `tokens.input`
- `tokens.output`
- `tokens.total`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing.reason`
- `routing.confidence`
- `routing.query_type`
- `routing.token_count`
- `routing.classification_confidence`
- `routing.estimated_cost`
- `routing.matched_rule`
- `routing.fallback_models`
- `routing.fallback_used`

## 7. 配置加载模块实现

在 `config_loader.py` 中实现统一配置加载函数，例如：

- `load_config()`

实现要求：

- 从项目根目录读取 `config.yaml`
- 解析 YAML
- 转为 `AppConfig`
- 为 API 层、路由模块与推理模块提供统一配置来源

## 8. 路由模块实现

在 `router.py` 中实现一个具备智能决策能力的路由器，例如：

- `QueryRouter`

模块职责：

- 输入：`QueryRequest`
- 输出：`RoutingDecision`

本阶段采用如下路由总流程：

1. 对 query 做分类，得到 `query_type`
2. 统计 `token_count`
3. 先做规则匹配
4. 再做能力过滤
5. 再对候选模型做打分排序
6. 生成 fallback 链
7. 返回可解释的 `RoutingDecision`

实现以下能力：

- 请求分类：如 `general`、`coding`、`analysis`、`reasoning`
- token 计数：输入长度与 token 数大致正相关
- 规则优先：命中规则时优先缩小候选集
- 能力过滤：校验 tier、max_tokens、capabilities
- 打分排序：综合成功率、成本、优先级、延迟、上下文适配度

示例策略：

- 如果 `query_type == 'coding'`，优先走代码能力模型
- 如果 `query_type == 'analysis' and token_count > 80`，优先走长上下文或分析模型
- 如果 `user_tier in ['premium', 'enterprise']`，允许进入更高优先级 Provider 候选池

## 9. 规则系统实现要求

路由规则是本阶段重点

### 9.1 统一表达式格式

推荐统一使用 Python 风格布尔表达式：

```python
query_type == 'analysis' and token_count > 80
```

不建议使用不规范写法，例如：

```text
analysis AND token_count > 50000
```

### 9.2 确保规则匹配过程安全可用

规则匹配过程必须满足：

- 规则写错时系统不能崩溃
- 错误规则可以被跳过
- 正确规则仍然能够继续工作

推荐做法：

- 使用 AST 或受限表达式解析
- 只允许有限的布尔与比较语法
- 禁止任意执行代码

## 10. 推理模块实现

在 `inference.py` 中实现以下组件：

- `BaseProvider`
- `LocalProvider`
- `OpenAIProvider`
- `AnthropicProvider`
- `InferenceEngine`

模块职责：

- 接收路由结果
- 根据模型名找到对应 Provider
- 返回统一结构的推理结果
- Provider 失败时按 fallback 链重试

### 10.1 统一输出要求

不论底层调用哪个 Provider，对上都统一输出 `InferenceResult`，至少包含：

- `response_text`
- `model_name`
- `provider`
- `token_count_input`
- `token_count_output`
- `latency_ms`
- `cost_usd`
- `cached`
- `fallback_used`
- `fallback_reason`
- `attempted_models`
- `provider_errors`

### 10.2 本阶段对调用的要求

本阶段以系统结构、接口契约、路由逻辑和 fallback 流程为重点，不要求必须完成真实外部模型服务的连通。

本阶段的实现要求如下：

- 推理层可以先不直接请求 OpenAI 
- Provider 层只要能够返回统一格式结果，即可完成本阶段主链路
- 代码结构需要保留后续接入真实 API 的扩展点

例如：

- `LocalProvider` 可以直接返回一段固定格式文本，例如 `Echo from {model_name}: ...`
- `OpenAIProvider` / `AnthropicProvider` 在没有配置 key 时，可以返回“当前不可用”，并触发 fallback
- 后续如果需要接入真实 API，只需要替换 Provider 内部调用逻辑，而不需要重写 API 层和路由层

也就是说，本阶段的重点是“系统结构和调用流程设计正确”，而不是“必须成功连上真实外部模型”。

### 10.3 fallback 要求

当 Provider 或模型不可用时，系统应：

1. 记录错误原因
2. 尝试 fallback 模型
3. 至少重试 1 次
4. 最终仍失败时返回可解释结果，而不是服务崩溃

## 11. API 层实现

### 11.1 创建应用入口

在 `main.py` 中创建 FastAPI 应用。

应用标题建议设置为：

```text
LLM Router Phase 2
```

### 11.2 实现健康检查接口

实现：

- `GET /health`

返回结果至少应包含：

- 系统整体状态
- 路由层健康状态
- 推理层健康状态
- 各 Provider 的可用模型列表
- 各 Provider 的不可用原因

示例结构：

```json
{
  "status": "healthy",
  "services": {
    "router": {
      "healthy": true,
      "details": {
        "default_model": "local-general",
        "model_count": 5,
        "strategy": "intelligent"
      }
    },
    "inference": {
      "healthy": true,
      "details": {
        "providers": {
          "local": {
            "healthy": true
          },
          "openai": {
            "healthy": false
          }
        }
      }
    }
  }
}
```

### 11.3 实现推理接口

实现：

- `POST /route`

接口处理流程如下：

1. 接收请求体并解析为 `QueryRequest`
2. 调用路由器生成 `RoutingDecision`
3. 调用推理引擎执行请求
4. 拼装统一响应
5. 返回结构化 JSON

建议统一返回格式如下：

```json
{
  "query_id": "string",
  "response": "string",
  "model_name": "string",
  "provider": "string",
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
    "query_type": "general",
    "token_count": 0,
    "classification_confidence": 0.0,
    "estimated_cost": 0.0,
    "matched_rule": "string or null",
    "fallback_models": [],
    "fallback_used": false,
    "fallback_reason": null,
    "attempted_models": [],
    "provider_errors": {}
  },
  "error": null
}
```

## 12. 启动入口规范

当前项目可直接通过以下命令启动：

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8082
```

如果希望保持与 Phase 1 一致的启动体验，也可以补充根目录 `main.py` 包装入口，使项目能够直接运行：

```bash
./venv/bin/python main.py
```

## 13. 测试要求

在 `test_main.py` 中使用 `fastapi.testclient.TestClient` 编写最小 smoke test 与阶段 2 核心行为测试。

最低测试要求如下：

- `/health` 返回 200
- `/route` 返回 200
- `/route` 的响应中包含 `model_name`
- `/route` 的响应中包含 `response`
- 代码类 query 能命中 coding 相关规则
- premium 用户请求在某些条件下能选到更高优先级模型
- 缺少外部 key 时能 fallback，而不是 500

运行方式如下：

```bash
./venv/bin/python -m pytest -q
```

## 14. 运行与验证说明

### 14.1 启动服务

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8082
```

### 14.2 打开接口文档

在浏览器中访问：

`http://localhost:8082/docs`

### 14.3 测试健康检查接口

```bash
curl -sS http://localhost:8082/health
```

### 14.4 测试推理接口

场景 1：free 用户的普通问题

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "hello, what is a cache hit rate?",
    "user_id": "u1",
    "user_tier": "free"
  }' | python3 -m json.tool
```

场景 2：代码类问题

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "write a python function to parse json",
    "user_id": "u2",
    "user_tier": "free"
  }' | python3 -m json.tool
```

场景 3：premium 用户问题

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "analyze tradeoffs of caching vs compression",
    "user_id": "u3",
    "user_tier": "premium"
  }' | python3 -m json.tool
```

### 14.5 fallback 演示

可以通过“不配置外部 API key”的方式主动制造失败，验证系统是否能自动降级。

例如：

- 不配置 `OPENAI_API_KEY`
- 对 premium 请求发起 `/route`
- 预期：不会 500，而是切到本地模型，并在返回中给出 fallback 说明

## 15. 预期结果说明

代码类 query 的返回通常具备以下特征：

- `query_type` 更偏向 `coding`
- `matched_rule` 可能命中 `coding_rule`
- `model_name` 更可能是代码能力模型
- `routing.reason` 中会出现 `Rule-based selection`

普通 query 的返回通常具备以下特征：

- `query_type` 更偏向 `general` 或 `analysis`
- 可能不命中显式规则
- 路由原因更可能是能力匹配与打分结果

premium 用户 query 的返回通常具备以下特征：

- 候选池允许更高优先级模型
- `matched_rule` 可能命中 premium 相关规则
- 如果外部 Provider 可用，`provider` 可能变为 `openai` 或 `anthropic`
- 如果外部 Provider 不可用，响应中应出现 `fallback_used = true`

## 16. 总结

本阶段最重要的不是接了多少外部服务，而是让系统具备以下真实能力：

- 会根据请求选择不同模型
- 会区分不同 Provider
- 会在 Provider 失败时自动回退
- 会把路由决策过程解释清楚
- 保持结构清晰，为后续接入真实监控、数据管道与策略系统留出扩展空间

本阶段应交付一个具备以下特征的系统：

- 能启动
- 能调用
- 能返回稳定 JSON
- 会根据请求类型和用户等级进行路由
- 至少支持 2 类 Provider
- Provider 失败不会直接导致接口崩溃
- 返回结果具备可解释性
