"""Small HTTP client for the LLM Router dashboard."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

API_BASE_URL = os.getenv("ROUTER_API_URL", "http://localhost:8081")

class DashboardApiError(RuntimeError):
    """The dashboard cannot obtain valid data from the backend."""

def fetch_json(path: str) -> dict[str, Any]:
    """Fetch one JSON endpoint from the FastAPI backend."""
    url = f"{API_BASE_URL}{path}"

    try:
        with urlopen(url, timeout=3) as response:
            if response.status != 200:
                raise DashboardApiError(
                    f"Backend returned HTTP {response.status} for {path}."
                )
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise DashboardApiError(
            f"Backend unavailable at {API_BASE_URL}: {error}"
        ) from error