from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.logging import get_logger
from app.core.security import validate_twilio_signature
from app.models.call_session import CallState
from app.repositories.call_session import CallSessionRepository
from app.voice import bridge

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/inbound")
async def inbound_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Always validate Twilio signature
    if not await validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid", "")

    if not call_sid:
        raise HTTPException(status_code=400, detail="Missing CallSid")

    # Create call session
    repo = CallSessionRepository(db)
    await repo.create(call_sid, initial_state=CallState.GREETING)

    ws_url = f"wss://{settings.base_url.replace('https://', '').replace('http://', '')}/voice/stream/{call_sid}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}"/>
  </Connect>
</Response>"""

    logger.info("inbound_call_received", call_sid=call_sid)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def call_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not await validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")

    if not call_sid:
        return Response(status_code=204)

    terminal_states = {"completed", "failed", "busy", "no-answer", "canceled"}
    if call_status in terminal_states:
        new_state = (
            CallState.COMPLETED if call_status == "completed" else CallState.FAILED
        )
        try:
            repo = CallSessionRepository(db)
            await repo.update_state(call_sid, new_state)
        except Exception as exc:
            logger.warning("status_update_failed", call_sid=call_sid, error=str(exc))

    logger.info("call_status_update", call_sid=call_sid, call_status=call_status)
    return Response(status_code=204)


@router.websocket("/stream/{call_sid}")
async def media_stream(websocket: WebSocket, call_sid: str):
    await websocket.accept()
    logger.info("websocket_accepted", call_sid=call_sid)

    # Use a fresh DB session for the WebSocket lifetime
    async with AsyncSessionLocal() as db:
        try:
            await bridge.run(websocket, call_sid, db)
        except Exception as exc:
            logger.error("websocket_error", call_sid=call_sid, error=str(exc))
        finally:
            await db.commit()


@router.get("/upload/{token}", response_class=HTMLResponse)
async def upload_form(token: str):
    """Stub upload page — Tier 3 visual diagnosis."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sears Home Services — Upload Photo</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 600px; margin: 40px auto; padding: 20px; }}
    h1 {{ color: #003087; }}
    .btn {{ background: #003087; color: white; padding: 12px 24px; border: none;
            border-radius: 6px; font-size: 16px; cursor: pointer; }}
    .btn:hover {{ background: #002060; }}
  </style>
</head>
<body>
  <h1>Sears Home Services</h1>
  <h2>Upload Appliance Photo</h2>
  <p>Please upload a clear photo of your appliance and the problem area.
     Our team will review it and follow up with you shortly.</p>
  <form enctype="multipart/form-data" method="post" action="/voice/upload/{token}/submit">
    <p><input type="file" name="photo" accept="image/*" required></p>
    <p><button class="btn" type="submit">Upload Photo</button></p>
  </form>
  <p><small>Token: {token[:8]}... | Upload link expires in 24 hours.</small></p>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/upload/{token}/submit")
async def upload_submit(
    token: str,
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Browser form handler — forwards to vision analysis."""
    from app.api.v1.routes.images import analyze_uploaded_image

    result = await analyze_uploaded_image(token, photo, db)
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Upload Received</title>
<style>body {{ font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }}
h1 {{ color: #003087; }}</style></head>
<body>
  <h1>Thank you!</h1>
  <p>Your photo was received and analyzed successfully.</p>
  <p><strong>Appliance:</strong> {result.appliance_type}</p>
  <p><strong>Diagnosis:</strong> {result.suggested_diagnosis}</p>
  <p>Our team will follow up if needed. You may close this window.</p>
</body></html>""",
        status_code=200,
    )
