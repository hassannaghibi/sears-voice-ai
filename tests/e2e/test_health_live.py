"""End-to-end smoke tests (run against deployed stack or in-container)."""
from __future__ import annotations

import os

import httpx
import pytest

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.mark.e2e
def test_health_endpoint_live():
    """Smoke test: deployed API responds on /health."""
    try:
        response = httpx.get(f"{BASE}/health", timeout=10.0)
    except httpx.ConnectError:
        pytest.skip(f"E2E target not reachable at {BASE}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
