from __future__ import annotations

import asyncio
import base64
import json

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.call_session import CallState
from app.repositories.call_session import CallSessionRepository
from app.voice.audio import pcm16_to_ulaw, ulaw_to_pcm16
from app.core.config import settings
from app.voice.context import load_context_block
from app.voice.session import RealtimeSession
from app.voice.tools import dispatch_tool

logger = get_logger(__name__)

SLOW_TOOLS = frozenset(
    {"find_available_technicians", "book_appointment", "send_image_upload_link"}
)


async def _send_filler(session: RealtimeSession) -> None:
    """Brief spoken filler while a slow tool runs (PROJECT_STANDARDS latency rule)."""
    await session.send_event(
        {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "Say briefly: One moment while I look that up for you.",
            },
        }
    )


async def run(websocket: WebSocket, call_sid: str, db: AsyncSession) -> None:
    """Route to OpenAI Realtime or Anthropic voice pipeline based on VOICE_LLM_PROVIDER."""
    if settings.voice_llm_provider == "anthropic":
        from app.voice import anthropic_bridge

        await anthropic_bridge.run(websocket, call_sid, db)
        return

    await run_openai(websocket, call_sid, db)


async def run_openai(websocket: WebSocket, call_sid: str, db: AsyncSession) -> None:
    """
    OpenAI Realtime audio bridge: two concurrent asyncio tasks.
    Task A: Twilio → OpenAI
    Task B: OpenAI → Twilio
    """
    context_block = await load_context_block(call_sid, db)
    session = RealtimeSession(call_sid, extra_instructions=context_block)

    try:
        await session.connect()
    except Exception as exc:
        logger.error("bridge_connect_failed", call_sid=call_sid, error=str(exc))
        await _update_failed(call_sid, db)
        await websocket.close()
        return

    stream_sid: str | None = None

    async def twilio_to_openai() -> None:
        nonlocal stream_sid
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event_type = msg.get("event")

                if event_type == "start":
                    stream_sid = msg.get("start", {}).get("streamSid")
                    logger.info("twilio_stream_started", call_sid=call_sid, stream_sid=stream_sid)

                elif event_type == "media":
                    ulaw_b64 = msg.get("media", {}).get("payload", "")
                    ulaw_bytes = base64.b64decode(ulaw_b64)
                    pcm_bytes = ulaw_to_pcm16(ulaw_bytes)
                    pcm_b64 = base64.b64encode(pcm_bytes).decode()
                    await session.send_event(
                        {"type": "input_audio_buffer.append", "audio": pcm_b64}
                    )

                elif event_type == "stop":
                    logger.info("twilio_stream_stopped", call_sid=call_sid)
                    break

        except Exception as exc:
            logger.error("twilio_to_openai_error", call_sid=call_sid, error=str(exc))

    async def openai_to_twilio() -> None:
        try:
            while True:
                event = await session.recv_event()
                if event is None:
                    break

                event_type = event.get("type", "")
                session.handle_event(event)

                if event_type == "response.audio.delta":
                    pcm_b64 = event.get("delta", "")
                    if pcm_b64 and stream_sid:
                        pcm_bytes = base64.b64decode(pcm_b64)
                        ulaw_bytes = pcm16_to_ulaw(pcm_bytes)
                        ulaw_b64 = base64.b64encode(ulaw_bytes).decode()
                        twilio_msg = json.dumps(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": ulaw_b64},
                            }
                        )
                        await websocket.send_text(twilio_msg)

                elif event_type == "response.function_call_arguments.done":
                    tool_name = event.get("name", "")
                    call_id = event.get("call_id", "")
                    raw_args = event.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}

                    if tool_name in SLOW_TOOLS:
                        await _send_filler(session)

                    result = await dispatch_tool(tool_name, args, db, call_sid)

                    await session.send_event(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result),
                            },
                        }
                    )
                    await session.send_event({"type": "response.create"})

                elif event_type == "error":
                    await _update_failed(call_sid, db)
                    break

        except Exception as exc:
            logger.error("openai_to_twilio_error", call_sid=call_sid, error=str(exc))

    task_a = asyncio.create_task(twilio_to_openai())
    task_b = asyncio.create_task(openai_to_twilio())

    results = await asyncio.gather(task_a, task_b, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            logger.error("bridge_task_exception", call_sid=call_sid, error=str(r))

    await session.close()
    try:
        await websocket.close()
    except Exception:
        pass


async def _update_failed(call_sid: str, db: AsyncSession) -> None:
    try:
        repo = CallSessionRepository(db)
        await repo.update_state(call_sid, CallState.FAILED)
        await db.commit()
    except Exception as exc:
        logger.error("failed_state_update_error", call_sid=call_sid, error=str(exc))
