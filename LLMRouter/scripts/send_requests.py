"""Send sample traffic to the local LLM Router API."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8081"

REQUESTS = [
    {
        "query": "hello",
        "user_id": "demo-free-1",
        "user_tier": "free",
    },
    {
        "query": "write a python function to reverse a list",
        "user_id": "demo-free-2",
        "user_tier": "free",
    },
    {
        "query": "analyze and compare the trends in this data",
        "user_id": "demo-premium-1",
        "user_tier": "premium",
    },
    {
        "query": "why does this proof work?",
        "user_id": "demo-premium-2",
        "user_tier": "premium",
    },
]


def send_request(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url=f"{BASE_URL}/route",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    for index, payload in enumerate(REQUESTS, start=1):
        try:
            result = send_request(payload)

            print(
                f"[{index}] "
                f"tier={payload['user_tier']:<10} "
                f"model={result['model_name']:<16} "
                f"provider={result['provider']:<10} "
                f"fallback={result['routing']['fallback_used']}"
            )
        except Exception as error:
            print(f"[{index}] FAILED: {error}")


if __name__ == "__main__":
    main()