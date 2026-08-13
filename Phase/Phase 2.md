# LLM Router & Execution Platform
# Phase 2 Development Specification

Building on the minimum viable skeleton from Phase 1, this phase evolves the “working API pipeline” into an LLM Router with real routing decisions, multi-provider support, and automatic fallback on failures.

## 1. Phase Objectives

After completing this phase, the project must meet the following requirements:

- Start a FastAPI service
- Open the API documentation: `http://localhost:8082/docs`
- Access the health check endpoint: `GET /health`
- Call the inference endpoint: `POST /route`
- Receive stable, structured JSON responses
- Have the same `/route` endpoint demonstrate different routing behavior for different requests
- Support at least 2 provider types
- Automatically fall back when a provider or model is unavailable instead of returning a direct 500 error

`POST /route` must return at least the following fields:

- `query_id`
- `response`
- `model_name`
- `provider`
- `tokens`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing`

At minimum, `routing` should include:

- `reason`
- `confidence`
- `query_type`
- `token_count`
- `classification_confidence`
- `estimated_cost`
- `fallback_models`

## 2. Key Differences

Phase 1 focuses on:

- Connecting the main `API -> routing -> inference` pipeline
- Starting the service, accepting calls, and returning stable JSON
- Allowing a simple routing strategy
- Initially using a provider that returns fixed text in the inference layer

Phase 2 focuses on:

- Evolving routing logic from “able to select” to “able to select intelligently”
- Expanding from a single mock to multiple providers
- Introducing a configuration-driven model registry and rule system
- Introducing fallback / graceful-degradation mechanisms
- Making `/route` return explainable routing information

Summary:

- Phase 1 solves “the main pipeline runs”
- Phase 2 solves “model selection, switchable providers, and resilience to failures”

## 3. Implementation Scope

This phase requires the following capabilities:

- Configuration-driven model registry
- Configuration-driven routing rules
- Request classification and token counting
- Capability filtering and composite model-scoring selection
- Multi-provider inference abstraction
- A unified inference output structure
- Failure fallback / graceful degradation
- `/health` displays provider health and model availability

## 4. Current Project Structure and Responsibilities

This project continues development from the simplified Phase 1 structure and currently uses a flat file layout:

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

Each file has the following responsibility:

- `main.py`: creates the FastAPI application and exposes `/health` and `/route`
- `config_loader.py`: reads and parses `config.yaml`
- `schema.py`: defines request, response, configuration, and routing structures
- `router.py`: handles request classification, rule matching, capability filtering, and model scoring/selection
- `inference.py`: handles provider calls, unified output, and fallback
- `test_main.py`: basic endpoint tests
- `config.yaml`: centrally manages models, rules, ports, and policies

## 5. Configuration File Specification

This phase continues to use `config.yaml` in the project root. Focus on the following configuration items:

- `api.host`
- `api.port`
- `router.default_model`
- `router.strategy`
- `router.models`
- `router.routing_rules`
- `router.tier_cost_limits`

The default project port is:

```yaml
api:
  host: "0.0.0.0"
  port: 8082
```

Model configuration should include at least:

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

Routing rules should include at least:

- `name`
- `condition`
- `candidates`
- `fallback`
- `reason`

Rule expressions should use Python-style Boolean expressions, for example:

```python
query_type == 'coding'
query_type == 'analysis' and token_count > 80
user_tier in ['premium', 'enterprise']
```

## 6. Data Contract Design

In `schema.py`, this phase should define and use the following data models:

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

The basic requirements are:

- `QueryRequest.query` must not be empty
- `user_tier` may only be `free`, `premium`, or `enterprise`
- `InferenceResponse` continues to retain the core Phase 1 fields
- Add `provider` and more complete explanatory `routing` information

The request model should include at least:

- `query`
- `user_id`
- `user_tier`
- `max_tokens`
- `temperature`

The response model should include at least:

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

## 7. Configuration Loader Implementation

Implement a unified configuration-loading function in `config_loader.py`, for example:

- `load_config()`

Implementation requirements:

- Read `config.yaml` from the project root
- Parse YAML
- Convert it to `AppConfig`
- Provide a unified configuration source for the API layer, routing module, and inference module

## 8. Routing Module Implementation

Implement a router with intelligent decision-making capabilities in `router.py`, for example:

- `QueryRouter`

Module responsibilities:

- Input: `QueryRequest`
- Output: `RoutingDecision`

This phase uses the following end-to-end routing flow:

1. Classify the query to obtain `query_type`
2. Count `token_count`
3. Match rules first
4. Filter by capabilities
5. Score and rank candidate models
6. Generate the fallback chain
7. Return an explainable `RoutingDecision`

Implement the following capabilities:

- Request classification, such as `general`, `coding`, `analysis`, and `reasoning`
- Token counting: input length should be roughly positively correlated with token count
- Rule priority: when a rule matches, narrow the candidate set first
- Capability filtering: validate tier, `max_tokens`, and `capabilities`
- Score ranking: combine success rate, cost, priority, latency, and context-fit factors

Example policies:

- If `query_type == 'coding'`, prioritize models with coding capabilities
- If `query_type == 'analysis' and token_count > 80`, prioritize long-context or analysis models
- If `user_tier in ['premium', 'enterprise']`, allow higher-priority providers into the candidate pool

## 9. Rule System Implementation Requirements

Routing rules are a focus of this phase.

### 9.1 Unified Expression Format

Use Python-style Boolean expressions consistently:

```python
query_type == 'analysis' and token_count > 80
```

Avoid nonstandard formats, for example:

```text
analysis AND token_count > 50000
```

### 9.2 Ensure Safe and Reliable Rule Matching

The rule-matching process must meet the following requirements:

- The system must not crash when a rule is written incorrectly
- Invalid rules may be skipped
- Valid rules must continue to work

Recommended approach:

- Use AST or restricted expression parsing
- Allow only a limited Boolean and comparison syntax
- Prohibit arbitrary code execution

## 10. Inference Module Implementation

Implement the following components in `inference.py`:

- `BaseProvider`
- `LocalProvider`
- `OpenAIProvider`
- `AnthropicProvider`
- `InferenceEngine`

Module responsibilities:

- Receive the routing result
- Find the corresponding provider by model name
- Return inference results in a unified structure
- Retry through the fallback chain when a provider fails

### 10.1 Unified Output Requirements

Regardless of the underlying provider invoked, return a unified `InferenceResult` to the upper layer. It must include at least:

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

### 10.2 Invocation Requirements for This Phase

This phase emphasizes system structure, interface contracts, routing logic, and the fallback flow. Connectivity to real external model services is not required.

Implementation requirements for this phase:

- The inference layer does not need to directly request OpenAI yet
- The provider layer can complete the main pipeline as long as it returns results in the unified format
- The code structure must preserve extension points for connecting to real APIs later

For example:

- `LocalProvider` may directly return fixed-format text, such as `Echo from {model_name}: ...`
- `OpenAIProvider` / `AnthropicProvider` may return “currently unavailable” when no key is configured and trigger fallback
- If real APIs need to be integrated later, only the internal provider invocation logic needs to be replaced; the API and routing layers do not need to be rewritten

In other words, the focus of this phase is “correct system structure and invocation-flow design,” rather than “successfully connecting to real external models.”

### 10.3 Fallback Requirements

When a provider or model is unavailable, the system must:

1. Record the error reason
2. Attempt a fallback model
3. Retry at least once
4. Return an explainable result if it ultimately still fails, rather than crashing the service

## 11. API Layer Implementation

### 11.1 Create the Application Entry Point

Create the FastAPI application in `main.py`.

Set the application title to:

```text
LLM Router Phase 2
```

### 11.2 Implement the Health Check Endpoint

Implement:

- `GET /health`

The response must include at least:

- Overall system status
- Routing-layer health status
- Inference-layer health status
- Available model lists for each provider
- Reasons each provider is unavailable

Example structure:

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

### 11.3 Implement the Inference Endpoint

Implement:

- `POST /route`

The endpoint processing flow is:

1. Receive the request body and parse it as `QueryRequest`
2. Call the router to generate a `RoutingDecision`
3. Call the inference engine to execute the request
4. Assemble the unified response
5. Return structured JSON

Use the following unified response format:

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

## 12. Startup Entry-Point Specification

The current project can be started directly with the following command:

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8082
```

To retain the same startup experience as Phase 1, you may also add a root-level `main.py` wrapper entry point so the project can run directly:

```bash
./venv/bin/python main.py
```

## 13. Testing Requirements

Use `fastapi.testclient.TestClient` in `test_main.py` to write minimum smoke tests and core Phase 2 behavior tests.

Minimum testing requirements:

- `/health` returns 200
- `/route` returns 200
- The `/route` response includes `model_name`
- The `/route` response includes `response`
- Coding queries can match coding-related rules
- Under certain conditions, premium-user requests can select higher-priority models
- When an external key is missing, fallback occurs instead of a 500 error

Run the tests as follows:

```bash
./venv/bin/python -m pytest -q
```

## 14. Running and Verification Guide

### 14.1 Start the Service

```bash
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8082
```

### 14.2 Open the API Documentation

Open the following in a browser:

`http://localhost:8082/docs`

### 14.3 Test the Health Check Endpoint

```bash
curl -sS http://localhost:8082/health
```

### 14.4 Test the Inference Endpoint

Scenario 1: A general question from a free user

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "hello, what is a cache hit rate?",
    "user_id": "u1",
    "user_tier": "free"
  }' | python3 -m json.tool
```

Scenario 2: A coding question

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "write a python function to parse json",
    "user_id": "u2",
    "user_tier": "free"
  }' | python3 -m json.tool
```

Scenario 3: A premium-user question

```bash
curl -sS http://localhost:8082/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "analyze tradeoffs of caching vs compression",
    "user_id": "u3",
    "user_tier": "premium"
  }' | python3 -m json.tool
```

### 14.5 Fallback Demonstration

You can deliberately induce failure by not configuring an external API key to verify whether the system degrades automatically.

For example:

- Do not configure `OPENAI_API_KEY`
- Send `/route` for a premium request
- Expected result: no 500 error; instead, the request switches to a local model and returns fallback details

## 15. Expected Results

Responses for coding queries typically have the following characteristics:

- `query_type` tends toward `coding`
- `matched_rule` may match `coding_rule`
- `model_name` is more likely to be a coding-capable model
- `routing.reason` includes `Rule-based selection`

Responses for general queries typically have the following characteristics:

- `query_type` tends toward `general` or `analysis`
- An explicit rule may not match
- The routing reason is more likely based on capability matching and scoring results

Responses for premium-user queries typically have the following characteristics:

- The candidate pool permits higher-priority models
- `matched_rule` may match a premium-related rule
- If an external provider is available, `provider` may become `openai` or `anthropic`
- If an external provider is unavailable, the response must include `fallback_used = true`

## 16. Summary

The most important aspect of this phase is not how many external services are connected, but whether the system has the following real capabilities:

- Select different models based on the request
- Distinguish among different providers
- Automatically fall back when a provider fails
- Clearly explain the routing decision process
- Maintain a clear structure and leave extension space for future integration of real monitoring, data pipelines, and policy systems

This phase must deliver a system with the following characteristics:

- Can start
- Can accept calls
- Can return stable JSON
- Routes based on request type and user tier
- Supports at least 2 provider types
- Provider failures do not directly crash the endpoint
- Returns explainable results
