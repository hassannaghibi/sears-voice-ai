from __future__ import annotations

import json
import xml.sax.saxutils as saxutils

from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import validate_twilio_signature
from app.models.call_session import CallState
from app.repositories.call_session import CallSessionRepository
from app.voice.anthropic_tools import anthropic_tool_definitions
from app.voice.prompts import build_system_prompt
from app.voice.tools import SLOW_TOOLS, dispatch_tool

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Twilio Polly Neural voice — reliable, high quality, no external TTS API needed
_VOICE = "Polly.Joanna-Neural"

GREETING = (
    "Hello, thank you for calling Sears Home Services. "
    "I'm Alex, your service advisor. "
    "Which appliance can I help you with today?"
)


def _twiml_say_gather(text: str, action_url: str) -> str:
    """Return a TwiML response that speaks text then listens for speech."""
    safe = saxutils.escape(text)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Say voice="{_VOICE}">{safe}</Say>'
        f'<Gather input="speech" action="{action_url}" method="POST" '
        'speechTimeout="3" timeout="10"/>'
        f"<Redirect>{action_url}</Redirect>"
        "</Response>"
    )


def _twiml_say_hangup(text: str) -> str:
    """Speak text then hang up."""
    safe = saxutils.escape(text)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Say voice="{_VOICE}">{safe}</Say>'
        "<Hangup/>"
        "</Response>"
    )


async def _run_claude(
    messages: list[dict],
    db: AsyncSession,
    call_sid: str,
) -> tuple[str, bool]:
    """
    Run Claude with a tool loop.
    Returns (spoken_reply, should_hangup).
    """
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    tools = anthropic_tool_definitions()
    system = build_system_prompt()
    reply = ""
    should_hangup = False

    for _ in range(6):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b.text for b in response.content if b.type == "text"]
        reply = " ".join(text_blocks).strip()

        if response.stop_reason != "tool_use" or not tool_uses:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            args = tu.input if isinstance(tu.input, dict) else {}
            result = await dispatch_tool(tu.name, args, db, call_sid)

            # Detect end-of-call state transitions
            if tu.name == "update_call_state" and args.get("new_state") in (
                "COMPLETED", "CALLBACK_CAPTURE"
            ):
                should_hangup = True

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return reply or "I'm sorry, I didn't catch that. Could you repeat?", should_hangup


@router.post("/inbound")
async def inbound_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not await validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid", "")
    if not call_sid:
        raise HTTPException(status_code=400, detail="Missing CallSid")

    repo = CallSessionRepository(db)
    await repo.create(call_sid, initial_state=CallState.GREETING)

    respond_url = f"{settings.base_url}/voice/respond"
    logger.info("inbound_call_received", call_sid=call_sid)
    return Response(
        content=_twiml_say_gather(GREETING, respond_url),
        media_type="application/xml",
    )


@router.post("/respond")
async def voice_respond(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not await validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid", "")
    speech_result = form.get("SpeechResult", "").strip()

    respond_url = f"{settings.base_url}/voice/respond"

    repo = CallSessionRepository(db)
    session = await repo.get_by_call_sid(call_sid)
    if not session:
        return Response(
            content=_twiml_say_hangup("Thank you for calling Sears Home Services. Goodbye!"),
            media_type="application/xml",
        )

    if not speech_result:
        return Response(
            content=_twiml_say_gather(
                "I didn't catch that. Could you please go ahead?", respond_url
            ),
            media_type="application/xml",
        )

    context = session.context or {}
    messages: list[dict] = context.get("messages", [])

    logger.info("voice_respond", call_sid=call_sid, speech=speech_result[:120])
    messages.append({"role": "user", "content": speech_result})

    try:
        reply, should_hangup = await _run_claude(messages, db, call_sid)
    except Exception as exc:
        logger.error("claude_error", call_sid=call_sid, error=str(exc))
        reply = "I'm sorry, I'm having some trouble right now. Please call back shortly."
        should_hangup = True

    if reply:
        messages.append({"role": "assistant", "content": reply})

    # Persist conversation (cap at 30 messages to stay within DB column limits)
    context["messages"] = messages[-30:]
    await repo.update_context(call_sid, {"messages": context["messages"]})

    logger.info("voice_respond_done", call_sid=call_sid, hangup=should_hangup, reply=reply[:100])

    if should_hangup:
        return Response(
            content=_twiml_say_hangup(reply),
            media_type="application/xml",
        )
    return Response(
        content=_twiml_say_gather(reply, respond_url),
        media_type="application/xml",
    )


@router.post("/status")
async def call_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not await validate_twilio_signature(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status_val = form.get("CallStatus", "")

    if not call_sid:
        return Response(status_code=204)

    terminal_states = {"completed", "failed", "busy", "no-answer", "canceled"}
    if call_status_val in terminal_states:
        new_state = (
            CallState.COMPLETED if call_status_val == "completed" else CallState.FAILED
        )
        try:
            repo = CallSessionRepository(db)
            await repo.update_state(call_sid, new_state)
        except Exception as exc:
            logger.warning("status_update_failed", call_sid=call_sid, error=str(exc))

    logger.info("call_status_update", call_sid=call_sid, call_status=call_status_val)
    return Response(status_code=204)


@router.get("/upload/{token}", response_class=HTMLResponse)
async def upload_form(token: str):
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
  <p>Please upload a clear photo of your appliance and the problem area.</p>
  <form enctype="multipart/form-data" method="post" action="/voice/upload/{token}/submit">
    <p><input type="file" name="photo" accept="image/*" required></p>
    <p><button class="btn" type="submit">Upload Photo</button></p>
  </form>
  <p><small>Upload link expires in 24 hours.</small></p>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/upload/{token}/submit")
async def upload_submit(
    token: str,
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
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
