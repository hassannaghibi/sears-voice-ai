from __future__ import annotations

import asyncio
import io

import edge_tts

from app.voice.audio import pcm16_to_ulaw
from pydub import AudioSegment


async def text_to_ulaw(text: str, voice: str = "en-US-AriaNeural") -> bytes:
    """Convert spoken text to μ-law 8 kHz bytes for Twilio Media Streams."""
    communicate = edge_tts.Communicate(text, voice)
    mp3_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_buffer.write(chunk["data"])

    mp3_buffer.seek(0)
    audio = AudioSegment.from_file(mp3_buffer, format="mp3")
    audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
    pcm = audio.raw_data
    return pcm16_to_ulaw(pcm, in_rate=8000, out_rate=8000)


async def stream_text_to_twilio(
    websocket,
    stream_sid: str,
    text: str,
    chunk_ms: int = 40,
) -> None:
    """Send TTS audio to Twilio in small chunks to reduce latency."""
    import base64
    import json

    ulaw = await text_to_ulaw(text)
    if not ulaw:
        return

    # 8 kHz μ-law → 40 ms ≈ 320 bytes per chunk
    bytes_per_chunk = max(160, int(8000 * chunk_ms / 1000))
    for offset in range(0, len(ulaw), bytes_per_chunk):
        chunk = ulaw[offset : offset + bytes_per_chunk]
        payload = base64.b64encode(chunk).decode()
        await websocket.send_text(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }
            )
        )
        await asyncio.sleep(chunk_ms / 1000)
