"""Integration tests: GET /health."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "env" in data
