from __future__ import annotations

import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.logging import get_logger
from app.voice.prompts import TOOL_DEFINITIONS, build_system_prompt

logger = get_logger(__name__)

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"


class RealtimeSession:
    def __init__(self, call_sid: str) -> None:
        self.call_sid = call_sid
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.session_id: str | None = None

    async def connect(self, max_attempts: int = 3) -> None:
        """Connect with exponential backoff retry."""
        delays = [1, 2, 4]
        for attempt in range(max_attempts):
            try:
                self.ws = await websockets.connect(
                    OPENAI_WS_URL,
                    additional_headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "OpenAI-Beta": "realtime=v1",
                    },
                    ping_interval=20,
                    ping_timeout=10,
                )
                logger.info(
                    "openai_ws_connected", call_sid=self.call_sid, attempt=attempt + 1
                )
                await self._send_session_update()
                return
            except Exception as exc:
                logger.warning(
                    "openai_ws_connect_failed",
                    call_sid=self.call_sid,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delays[attempt])
                else:
                    raise

    async def _send_session_update(self) -> None:
        await self.send_event(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "silence_duration_ms": 600,
                        "threshold": 0.5,
                    },
                    "tools": TOOL_DEFINITIONS,
                    "tool_choice": "auto",
                    "instructions": build_system_prompt(),
                },
            }
        )

    async def send_event(self, event: dict) -> None:
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps(event))

    async def recv_event(self) -> dict | None:
        if self.ws is None:
            return None
        try:
            raw = await self.ws.recv()
            return json.loads(raw)
        except ConnectionClosed:
            return None

    async def close(self) -> None:
        if self.ws and not self.ws.closed:
            await self.ws.close()
            logger.info("openai_ws_closed", call_sid=self.call_sid)

    def handle_event(self, event: dict) -> None:
        event_type = event.get("type", "")

        if event_type == "session.created":
            self.session_id = event.get("session", {}).get("id")
            logger.info(
                "openai_session_created",
                call_sid=self.call_sid,
                session_id=self.session_id,
            )

        elif event_type == "input_audio_buffer.speech_started":
            logger.debug("speech_started", call_sid=self.call_sid)

        elif event_type == "response.done":
            transcript = (
                event.get("response", {})
                .get("output", [{}])[0]
                .get("content", [{}])[0]
                .get("transcript", "")
            )
            if transcript:
                logger.info(
                    "transcript", call_sid=self.call_sid, text=transcript[:200]
                )

        elif event_type == "error":
            logger.error("openai_error", call_sid=self.call_sid, payload=event)
