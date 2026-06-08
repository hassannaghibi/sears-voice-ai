from __future__ import annotations

from fastapi import Request
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_validator = RequestValidator(settings.twilio_auth_token)


async def validate_twilio_signature(request: Request) -> bool:
    """
    Validate the X-Twilio-Signature header against the request body.

    The app runs behind nginx, so request.url reflects the internal Docker
    address (http://0.0.0.0:8000/...) rather than the public HTTPS URL that
    Twilio signed. We reconstruct the canonical URL from settings.base_url.
    """
    signature = request.headers.get("X-Twilio-Signature", "")

    # Reconstruct the exact URL Twilio used when computing the signature
    path = request.url.path
    query = request.url.query
    canonical_url = settings.base_url.rstrip("/") + path
    if query:
        canonical_url += "?" + query

    # For form-encoded bodies (standard Twilio webhooks)
    body = await request.form()
    params = dict(body)

    valid = _validator.validate(canonical_url, params, signature)
    if not valid:
        logger.warning(
            "twilio_signature_invalid",
            canonical_url=canonical_url,
            signature=signature[:20] + "...",
        )
    return valid
