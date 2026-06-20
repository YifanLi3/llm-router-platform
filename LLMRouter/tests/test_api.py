"""Smoke tests for Phase 1 API endpoints.
Uses FastAPI's TestClient, which talks to the app directly in-process
(no real network, no real uvicorn). Fast, deterministic, no flakes.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "services" in body

# ---------------------------------------------------------------------------
# /route -- happy paths
# ---------------------------------------------------------------------------

def test_route_basic_returns_required_fields():
    r = client.post("/route", json={
        "query":     "hello",
        "user_id":   "u1",
        "user_tier": "free",
    })
    assert r.status_code == 200
    body = r.json()
    for field in ("query_id", "response", "model_name", "tokens",
                  "cost_usd", "latency_ms", "cached", "routing"):
        assert field in body, f"missing field: {field}"
def test_route_default_picks_general_small():
    r = client.post("/route", json={
        "query":     "What is the capital of France?",
        "user_id":   "u1",
        "user_tier": "free",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["model_name"] == "general-small"
    assert body["routing"]["query_type"] == "general"
def test_route_coding_keyword_picks_coding_pro():
    r = client.post("/route", json={
        "query":     "write a python function to reverse a list",
        "user_id":   "u1",
        "user_tier": "free",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["model_name"] == "coding-pro"
    assert body["routing"]["query_type"] == "coding"
# ---------------------------------------------------------------------------
# /route -- validation errors should return 422
# ---------------------------------------------------------------------------
def test_route_empty_query_returns_422():
    r = client.post("/route", json={
        "query":     "",
        "user_id":   "u1",
        "user_tier": "free",
    })
    assert r.status_code == 422
def test_route_invalid_tier_returns_422():
    r = client.post("/route", json={
        "query":     "hi",
        "user_id":   "u1",
        "user_tier": "vip",
    })
    assert r.status_code == 422