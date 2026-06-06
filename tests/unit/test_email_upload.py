"""Unit tests for email and upload services."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email import send_upload_link
from app.services.upload import create_upload_link, is_token_expired


def test_normalize_zip_from_scheduling():
    from app.services.scheduling import normalize_zip_code

    assert normalize_zip_code("60601")[0] == "60601"
    assert normalize_zip_code("60601-1234")[0] == "60601"
    assert normalize_zip_code("606")[1] == "partial_zip"
    assert normalize_zip_code("abcde")[1] == "invalid_zip"


def test_is_token_expired():
    from datetime import UTC, datetime, timedelta

    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert is_token_expired(future) is False
    assert is_token_expired(past) is True
    assert is_token_expired(None) is True


@pytest.mark.asyncio
async def test_send_upload_link_builds_voice_url():
    with patch("app.services.email.sendgrid.SendGridAPIClient") as mock_sg:
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg.return_value.send.return_value = mock_response

        url = await send_upload_link(
            "user@example.com", "washer", "CA_email_test", token="test-token-abc"
        )
        assert "/voice/upload/test-token-abc" in url


@pytest.mark.asyncio
async def test_create_upload_link_persists_token(mock_db=None):
    db = AsyncMock()
    repo = AsyncMock()
    repo.update_context = AsyncMock()

    with patch("app.services.upload.CallSessionRepository", return_value=repo), patch(
        "app.services.upload.email_service.send_upload_link", new=AsyncMock()
    ):
        token, url = await create_upload_link(db, "CA_up", "a@b.com", "washer")

    assert token
    assert "/voice/upload/" in url
    repo.update_context.assert_called_once()
    ctx = repo.update_context.call_args[0][1]
    assert ctx["upload_token"] == token
