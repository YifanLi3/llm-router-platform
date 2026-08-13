# LLM Router & Execution Platform

## Phase 1 Development Specification

This phase requires creating a minimal viable LLM routing system from scratch, including building, integrating, and validating the primary `API -> routing -> inference` workflow.

## 1. Phase Goals and Deliverables

Upon completing this phase, the project must meet the following deliverable requirements:

- Start a FastAPI service
- Open the API documentation: `http://localhost:8081/docs`
- Access the health check endpoint: `GET /health`
- Call the inference endpoint: `POST /route`
- Receive a stable, structured JSON response

`POST /route` must return at least the following fields:

- `query_id`
- `response`
- `model_name`
- `tokens`
- `cost_usd`
- `latency_ms`
- `cached`
- `routing`

## 2. Implementation Scope and Non-Goals

This phase only requires completing the minimum viable primary workflow. The following capabilities are out of scope:

- Kafka, ClickHouse, and Flink are not required
- Prometheus and Grafana are not required
- A Streamlit dashboard is not required
- A Slack Bot is not required
- Actual calls to OpenAI, Anthropic, or vLLM are not required
- A database or business dataset is not required

Note: The inference layer may use a Mock Provider in this phase. Therefore, the implementation should focus on system architecture, interface contracts, and module layering; training data, business data, and external service dependencies are not required.

## 3. Technology Stack and Environment Requirements

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- PyYAML
- Pytest

## 4. Project Initialization and Environment Setup

### 4.1 Create the Project Directory

Create a project folder in your local working directory, for example:

```bash
mkdir One
cd One
```

### 4.2 Create a Virtual Environment and Install Dependencies

```bash
python3 -m venv venv
./venv/bin/python -m pip install -U pip
```

Create `requirements.txt` in the project root:

```txt
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic>=2.7,<3.0
PyYAML>=6.0,<7.0
pytest>=8.0,<9.0
httpx>=0.27,<1.0
```

Then install the dependencies:

```bash
./venv/bin/python -m pip install -r requirements.txt
```

## 5. Project Directory Structure

The project is recommended to use the following standard directory structure:

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

The responsibilities of these directories and files are as follows:

- `app/main.py`: Creates the FastAPI application and starts the service
- `app/api/routes.py`: Handles only HTTP requests and response orchestration
- `app/core/config.py`: Reads the configuration file
- `app/services/router.py`: Selects a model
- `app/services/inference.py`: Executes inference
- `app/schemas.py`: Defines request, response, and configuration data structures
- `tests/test_api.py`: Basic API tests
- `main.py`: Root-level application entry point

## 6. Configuration File Specification

Create `config.yaml` in the project root:

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

This phase focuses on the following configuration items:

- `api.host`
- `api.port`
- `router.default_model`
- `router.models`

## 7. Data Contract Design

Define the following data models in `app/schemas.py`:

- `QueryRequest`
- `RoutingDecision`
- `InferenceResult`
- `InferenceResponse`
- `HealthResponse`
- `AppConfig`

Basic requirements:

- `QueryRequest.query` must not be empty
- `user_tier` may only be `free`, `premium`, or `enterprise`

The request model should include at least the following fields:

- `query`
- `user_id`
- `user_tier`
- `max_tokens`
- `temperature`

The response model should include at least the following fields:

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

## 8. Configuration Loading Module

Implement a configuration-loading function in `app/core/config.py`, for example:

- `get_config()`

Implementation requirements:

- Read `config.yaml` from the project root
- Parse YAML
- Convert it to `AppConfig`

This module provides a unified configuration source for the API layer, routing module, and inference module.

## 9. Routing Module

Implement a minimal router class in `app/services/router.py`, for example:

- `QueryRouter`

Module responsibilities:

- Input: `QueryRequest`
- Output: `RoutingDecision`

Basic requirements:

- Select a `selected_model`
- Provide a `routing_reason`
- Preferably provide a simple `confidence`

The following minimal routing strategy is recommended:

1. If the query is very long, for example, longer than 1000 characters, prioritize `long-context`
2. If the query contains keywords such as `code`, `function`, `class`, `bug`, or `python`, route it to `coding-pro`
3. Route all other cases to the default model, `general-small`

Note: This phase does not require a machine-learning classifier. A rule-based routing strategy is sufficient.

## 10. Inference Module

Implement the following components in `app/services/inference.py`:

- `MockProvider`
- `InferenceEngine`

Module responsibilities:

- Receive the routing result
- Return a text response
- Also return metrics such as tokens, latency, and cost

The following implementation approach is recommended:

- `response_text = f"Echo from {model_name}: {query[:200]}"`
- Estimate input token count using `len(query.split())`
- Estimate output token count using `len(response_text.split())`
- Calculate latency using `time.time()`
- Estimate cost simply based on the unit prices in the configuration

This phase does not require actual model calls, so results should be predictable, explainable, and repeatable.

## 11. API Layer

### 11.1 Create the Application Entry Point

Create the FastAPI application in `app/main.py`.

The recommended application title is:

- `LLM Router & Execution Platform`

### 11.2 Implement the Health Check Endpoint

Implement:

- `GET /health`

The response must include at least:

```json
{
  "status": "healthy",
  "services": {
    "router": { "healthy": true },
    "inference": { "healthy": true }
  }
}
```

### 11.3 Implement the Inference Endpoint

Implement:

- `POST /route`

The endpoint processing flow is as follows:

1. Receive the request body and parse it as `QueryRequest`
2. Call the router to select a model
3. Call the inference engine to process the query
4. Assemble a unified response
5. Return structured JSON

The following unified response format is recommended:

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

## 12. Application Entry Point Specification

It is recommended to keep a `main.py` in the project root as the unified application entry point, for example:

- Import `app` from `app.main`
- Import `run` from `app.main`
- Call `run()` in `if __name__ == "__main__"`

With this entry point, the project can be started using:

```bash
./venv/bin/python main.py
```

This reduces startup complexity and prevents students from having to remember additional runtime arguments.

## 13. Testing Requirements

Write a minimal smoke test in `tests/test_api.py` using `fastapi.testclient.TestClient`.

The minimum test requirements are:

- `/health` returns 200
- `/route` returns 200
- The `/route` response includes `model_name`
- The `/route` response includes `response`

Run tests as follows:

```bash
./venv/bin/python -m pytest -q
```

## 14. Running and Validation

### 14.1 Start the Service

```bash
./venv/bin/python main.py
```

### 14.2 Open the API Documentation

Visit the following URL in a browser:

```text
http://localhost:8081/docs
```

### 14.3 Test the Health Check Endpoint

```bash
curl -sS http://localhost:8081/health
```

### 14.4 Test the Inference Endpoint

```bash
curl -sS http://localhost:8081/route \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Write a Python function to reverse a list",
    "user_id": "u1",
    "user_tier": "free"
  }' | python3 -m json.tool
```

## 15. Expected Result Examples

An example response for a coding-related query:

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

An example response for a general question:

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

## 16. Pre-Submission Checklist

Before submitting, confirm each of the following:

- `http://localhost:8081/docs` opens successfully
- `GET /health` returns 200 and JSON
- `POST /route` returns stable fields for valid input
- An empty `query` returns a validation error
- An invalid `user_tier` returns a validation error
- At least two different queries produce different routing results or routing reasons
- `pytest` passes

## 17. Frequently Asked Questions

### 17.1 Port Is Already in Use

If port `8081` is already in use, you can:

- Terminate the process using the port
- Or change `api.port` in `config.yaml`

### 17.2 Page Cannot Be Accessed

The service usually has not been started. First run:

```bash
./venv/bin/python main.py
```

Then visit:

```text
http://localhost:8081/docs
```

### 17.3 Is a Dataset Required?

No. This phase builds the system skeleton and does not depend on a business dataset.

## 18. Phase Summary

The most important outcomes of this phase are not the number of features, but establishing the primary workflow, stabilizing the interface structure, and clearly separating code responsibilities.

This phase should deliver a minimal system with the following characteristics:

- Can be started
- Can be called
- Returns stable JSON
- Has clearly layered code responsibilities
- Leaves room for future integration with real Providers
