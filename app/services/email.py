from __future__ import annotations

import secrets

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TWILIO_EMAIL_URL = "https://comms.twilio.com/v1/Emails"


async def send_upload_link(email: str, appliance_type: str, call_sid: str) -> str:
    """
    1. Generate unique token
    2. Build upload URL
    3. Send email via Twilio Email API (uses existing Account SID + Auth Token)
    4. Return the upload URL
    """
    token = secrets.token_urlsafe(32)
    upload_url = f"{settings.base_url}/voice/upload/{token}"

    subject = f"Sears Home Services — Upload a Photo of Your {appliance_type.title()}"
    html_body = (
        "<p>Hello,</p>"
        "<p>Thank you for contacting Sears Home Services.</p>"
        f"<p>To help us diagnose your <strong>{appliance_type}</strong> issue, please upload a photo "
        f"using the secure link below. This link expires in {settings.upload_link_ttl_hours} hours.</p>"
        f'<p><a href="{upload_url}" style="font-size:16px;">Upload Photo &rarr;</a></p>'
        "<p>Once we receive your photo, our team will follow up with next steps.</p>"
        "<p>&mdash; Sears Home Services</p>"
    )
    text_body = (
        f"Upload a photo of your {appliance_type} to help us diagnose the issue:\n"
        f"{upload_url}\n\n"
        f"This link expires in {settings.upload_link_ttl_hours} hours.\n"
        "— Sears Home Services"
    )

    payload = {
        "from": {"address": settings.from_email, "name": "Sears Home Services"},
        "to": [{"address": email}],
        "content": {
            "subject": subject,
            "html": html_body,
            "text": text_body,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TWILIO_EMAIL_URL,
                json=payload,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                timeout=15.0,
            )
        response.raise_for_status()
        operation_id = response.json().get("operationId", "unknown")
        logger.info(
            "upload_link_sent",
            email=email,
            call_sid=call_sid,
            status_code=response.status_code,
            operation_id=operation_id,
            upload_url=upload_url,
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "upload_link_failed",
            email=email,
            call_sid=call_sid,
            status_code=exc.response.status_code,
            response_body=exc.response.text,
            error=str(exc),
        )
        raise
    except Exception as exc:
        logger.error("upload_link_failed", email=email, call_sid=call_sid, error=str(exc))
        raise

    return upload_url
