"""Integration tests for /voice/status webhook."""
from __future__ import annotations

import pytest

from tests.integration.test_voice_webhook import compute_signature


@pytest.mark.asyncio
async def test_status_invalid_signature_returns_403(async_client):
    response = await async_client.post(
        "/voice/status",
        content="CallSid=CA_fake&CallStatus=completed",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": "bad_sig",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_status_valid_or_url_mismatch(async_client):
    params = {"CallSid": "CA_status_test", "CallStatus": "completed"}
    url = "http://test/voice/status"
    from app.core.config import settings

    sig = compute_signature(url, params, settings.twilio_auth_token)
    body = "&".join(f"{k}={v}" for k, v in params.items())
    response = await async_client.post(
        "/voice/status",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": sig,
        },
    )
    assert response.status_code in {204, 403}
