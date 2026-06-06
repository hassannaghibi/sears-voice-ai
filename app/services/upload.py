from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.call_session import CallSessionRepository
from app.services import email as email_service


def generate_upload_token() -> str:
    return secrets.token_urlsafe(32)


def upload_url_for_token(token: str) -> str:
    base = settings.base_url.rstrip("/")
    return f"{base}/voice/upload/{token}"


def token_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.upload_link_ttl_hours)


async def create_upload_link(
    db: AsyncSession,
    call_sid: str,
    email: str,
    appliance_type: str,
) -> tuple[str, str]:
    """Generate token, persist to call session, send email. Returns (token, upload_url)."""
    token = generate_upload_token()
    expires = token_expires_at()
    upload_url = upload_url_for_token(token)

    repo = CallSessionRepository(db)
    await repo.update_context(
        call_sid,
        {
            "upload_token": token,
            "upload_token_expires": expires.isoformat(),
            "upload_email": email,
        },
    )

    await email_service.send_upload_link(email, appliance_type, call_sid, token=token)
    return token, upload_url


def is_token_expired(expires_iso: str | None) -> bool:
    if not expires_iso:
        return True
    try:
        expires = datetime.fromisoformat(expires_iso)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return datetime.now(UTC) > expires
    except ValueError:
        return True
