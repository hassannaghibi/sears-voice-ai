from __future__ import annotations

import asyncio
import base64
import json
import struct
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.call_session import CallState
from app.repositories.call_session import CallSessionRepository
from app.voice.anthropic_tools import anthropic_tool_definitions
from app.voice.audio import ulaw_to_pcm16
from app.voice.context import load_context_block
from app.voice.prompts import build_system_prompt
from app.voice.tools import SLOW_TOOLS, dispatch_tool
from app.voice.tts import stream_text_to_twilio

logger = get_logger(__name__)

_whisper_model = None
_whisper_lock = asyncio.Lock()


async def _get_whisper_model():
    global _whisper_model
    async with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            _whisper_model = await asyncio.to_thread(
                WhisperModel, "tiny.en", device="cpu", compute_type="int8"
            )
        return _whisper_model


def _pcm_energy(pcm16: bytes) -> float:
    if len(pcm16) < 2:
        return 0.0
    samples = struct.unpack(f"<{len(pcm16) // 2}h", pcm16)
    if not samples:
        return 0.0
    return sum(abs(s) for s in samples) / len(samples)


async def _transcribe_pcm(pcm16_8k: bytes) -> str:
    if len(pcm16_8k) < 3200:
        return ""

    model = await _get_whisper_model()
    import tempfile

    import os
    import wave

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        with wave.open(wav_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(pcm16_8k)

        segments, _ = await asyncio.to_thread(
            model.transcribe, wav_path, beam_size=1, vad_filter=True
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass


async def _run_claude_turn(
    client: AsyncAnthropic,
    messages: list[dict[str, Any]],
    db: AsyncSession,
    call_sid: str,
    websocket: WebSocket | None = None,
    stream_sid: str | None = None,
    context_block: str = "",
) -> str:
    """Run Claude with tool loop; return final spoken text."""
    tools = anthropic_tool_definitions()
    system = build_system_prompt() + context_block

    for _ in range(6):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        text_blocks = [block.text for block in response.content if block.type == "text"]
        spoken = " ".join(text_blocks).strip()

        if response.stop_reason != "tool_use" or not tool_uses:
            return spoken or "I'm sorry, I didn't catch that. Could you repeat?"

        messages.append({"role": "assistant", "content": response.content})
        tool_results: list[dict[str, Any]] = []

        for tool_use in tool_uses:
            tool_name = tool_use.name
            args = tool_use.input if isinstance(tool_use.input, dict) else {}

            if tool_name in SLOW_TOOLS and websocket and stream_sid:
                await stream_text_to_twilio(
                    websocket, stream_sid, "One moment while I look that up for you."
                )

            result = await dispatch_tool(tool_name, args, db, call_sid)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return spoken or "Let me know if you'd like to continue."


async def run(websocket: WebSocket, call_sid: str, db: AsyncSession) -> None:
    """Anthropic voice path: local Whisper STT → Claude → edge-tts."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    initial_context = await load_context_block(call_sid, db)
    messages: list[dict[str, Any]] = []
    context_injected = False

    stream_sid: str | None = None
    utterance_pcm = bytearray()
    in_speech = False
    silence_frames = 0
    speech_frames = 0

    ENERGY_THRESHOLD = 350.0
    SILENCE_FRAMES_TO_END = 25  # ~500 ms at 20 ms/frame
    MIN_SPEECH_FRAMES = 8

    greeting = (
        "Hello, thank you for calling Sears Home Services. "
        "I'm Alex, your service advisor. Which appliance can I help you with today?"
    )

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event_type = msg.get("event")

            if event_type == "start":
                stream_sid = msg.get("start", {}).get("streamSid")
                logger.info("anthropic_stream_started", call_sid=call_sid, stream_sid=stream_sid)
                if stream_sid:
                    await stream_text_to_twilio(websocket, stream_sid, greeting)

            elif event_type == "media" and stream_sid:
                ulaw_b64 = msg.get("media", {}).get("payload", "")
                ulaw_bytes = base64.b64decode(ulaw_b64)
                pcm16_8k = ulaw_to_pcm16(ulaw_bytes, in_rate=8000, out_rate=8000)
                energy = _pcm_energy(pcm16_8k)

                if energy >= ENERGY_THRESHOLD:
                    in_speech = True
                    silence_frames = 0
                    speech_frames += 1
                    utterance_pcm.extend(pcm16_8k)
                elif in_speech:
                    silence_frames += 1
                    utterance_pcm.extend(pcm16_8k)
                    if silence_frames >= SILENCE_FRAMES_TO_END and speech_frames >= MIN_SPEECH_FRAMES:
                        transcript = await _transcribe_pcm(bytes(utterance_pcm))
                        utterance_pcm.clear()
                        in_speech = False
                        silence_frames = 0
                        speech_frames = 0

                        if not transcript:
                            continue

                        logger.info("anthropic_transcript", call_sid=call_sid, text=transcript[:200])
                        messages.append({"role": "user", "content": transcript})

                        reply = await _run_claude_turn(
                            client,
                            messages,
                            db,
                            call_sid,
                            websocket,
                            stream_sid,
                            initial_context if not context_injected else "",
                        )
                        context_injected = True
                        if reply:
                            messages.append({"role": "assistant", "content": reply})
                            await stream_text_to_twilio(websocket, stream_sid, reply)

            elif event_type == "stop":
                logger.info("anthropic_stream_stopped", call_sid=call_sid)
                break

    except Exception as exc:
        logger.error("anthropic_bridge_error", call_sid=call_sid, error=str(exc))
        await _update_failed(call_sid, db)
    finally:
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
