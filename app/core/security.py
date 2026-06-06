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
    Returns True if valid, False otherwise.
    Never skip in any environment.
    """
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    # For form-encoded bodies (standard Twilio webhooks)
    body = await request.form()
    params = dict(body)

    valid = _validator.validate(url, params, signature)
    if not valid:
        logger.warning(
            "twilio_signature_invalid",
            url=url,
            signature=signature[:20] + "...",
        )
    return valid
