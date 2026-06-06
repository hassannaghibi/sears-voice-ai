from __future__ import annotations

import sendgrid
from sendgrid.helpers.mail import Mail

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_upload_link(
    email: str,
    appliance_type: str,
    call_sid: str,
    *,
    token: str | None = None,
) -> str:
    """
    1. Use provided token or generate unique token
    2. Build upload URL
    3. Send SendGrid email with the link
    4. Return the upload URL
    """
    from app.services.upload import generate_upload_token, upload_url_for_token

    if token is None:
        token = generate_upload_token()
    upload_url = upload_url_for_token(token)

    subject = f"Sears Home Services — Upload a Photo of Your {appliance_type.title()}"
    html_body = f"""
    <p>Hello,</p>
    <p>Thank you for contacting Sears Home Services.</p>
    <p>To help us diagnose your <strong>{appliance_type}</strong> issue, please upload a photo
    using the secure link below. This link expires in {settings.upload_link_ttl_hours} hours.</p>
    <p><a href="{upload_url}" style="font-size:16px;">Upload Photo →</a></p>
    <p>Once we receive your photo, our team will follow up with next steps.</p>
    <p>— Sears Home Services</p>
    """

    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        message = Mail(
            from_email=settings.from_email,
            to_emails=email,
            subject=subject,
            html_content=html_body,
        )
        response = sg.send(message)
        logger.info(
            "upload_link_sent",
            email=email,
            call_sid=call_sid,
            status_code=response.status_code,
            upload_url=upload_url,
        )
    except Exception as exc:
        logger.error("upload_link_failed", email=email, call_sid=call_sid, error=str(exc))
        raise

    return upload_url
