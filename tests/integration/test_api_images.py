"""Integration tests for Tier 3 image upload API."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.call_session import CallState
from app.repositories.call_session import CallSessionRepository


@pytest.mark.asyncio
async def test_create_upload_link_201(async_client, db_session):
    repo = CallSessionRepository(db_session)
    await repo.create("CA_image_test", initial_state=CallState.GREETING)

    with patch("app.services.upload.email_service.send_upload_link", new=AsyncMock()):
        response = await async_client.post(
            "/api/v1/images/upload-link",
            json={
                "call_sid": "CA_image_test",
                "email": "caller@example.com",
                "appliance_type": "washer",
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert "/voice/upload/" in data["upload_url"]
    assert data["token"]


@pytest.mark.asyncio
async def test_analyze_invalid_token_404(async_client):
    response = await async_client.post(
        "/api/v1/images/not-a-real-token/analyze",
        files={"photo": ("test.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_valid_token(async_client, db_session):
    repo = CallSessionRepository(db_session)
    await repo.create("CA_vision_test", initial_state=CallState.TIER3_EMAIL)
    await repo.update_context(
        "CA_vision_test",
        {
            "upload_token": "vision-token-xyz",
            "upload_token_expires": "2099-01-01T00:00:00+00:00",
        },
    )

    mock_analysis = {
        "appliance_type": "washer",
        "visible_issues": ["loose hose"],
        "suggested_diagnosis": "Check drain hose connection",
        "confidence": "medium",
    }

    with patch(
        "app.api.v1.routes.images.analyze_appliance_image",
        new=AsyncMock(return_value=mock_analysis),
    ):
        response = await async_client.post(
            "/api/v1/images/vision-token-xyz/analyze",
            files={"photo": ("test.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["appliance_type"] == "washer"
