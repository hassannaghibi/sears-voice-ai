from __future__ import annotations

try:
    import audioop
except ImportError:
    import audioop_lts as audioop  # Python 3.13+


def ulaw_to_pcm16(ulaw_bytes: bytes, in_rate: int = 8000, out_rate: int = 24000) -> bytes:
    """μ-law 8kHz → PCM16 24kHz (format required by OpenAI Realtime API)."""
    pcm = audioop.ulaw2lin(ulaw_bytes, 2)
    if in_rate != out_rate:
        pcm, _ = audioop.ratecv(pcm, 2, 1, in_rate, out_rate, None)
    return pcm


def pcm16_to_ulaw(pcm_bytes: bytes, in_rate: int = 24000, out_rate: int = 8000) -> bytes:
    """PCM16 24kHz → μ-law 8kHz (format required by Twilio Media Streams)."""
    if in_rate != out_rate:
        pcm_bytes, _ = audioop.ratecv(pcm_bytes, 2, 1, in_rate, out_rate, None)
    return audioop.lin2ulaw(pcm_bytes, 2)
