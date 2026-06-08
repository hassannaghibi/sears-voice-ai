from __future__ import annotations

import base64
import json

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ANALYSIS_PROMPT = """You are an appliance diagnostic expert for Sears Home Services.
Analyze this photo of a home appliance and return a JSON object with:
- appliance_type: one of washer, dryer, refrigerator, dishwasher, oven, hvac, other
- visible_issues: list of specific visible problems or damage
- suggested_diagnosis: brief likely cause based on what you see
- confidence: low, medium, or high
Be concise and practical. Return JSON only."""


async def analyze_appliance_image(image_bytes: bytes, content_type: str = "image/jpeg") -> dict:
    """Send image to the configured vision provider and return structured diagnosis."""
    if settings.vision_llm_provider == "anthropic":
        return await _analyze_with_anthropic(image_bytes, content_type)
    return await _analyze_with_openai(image_bytes, content_type)


async def _analyze_with_openai(image_bytes: bytes, content_type: str) -> dict:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{content_type};base64,{b64}"

    response = await client.chat.completions.create(
        model=settings.openai_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        max_tokens=600,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    logger.info("vision_analysis_complete", provider="openai", response_length=len(raw))
    return _parse_json_response(raw)


async def _analyze_with_anthropic(image_bytes: bytes, content_type: str) -> dict:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    b64 = base64.b64encode(image_bytes).decode()
    media_type = content_type if content_type.startswith("image/") else "image/jpeg"

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ],
            }
        ],
    )

    raw = ""
    for block in response.content:
        if block.type == "text":
            raw += block.text

    logger.info("vision_analysis_complete", provider="anthropic", response_length=len(raw))
    return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "appliance_type": "other",
            "visible_issues": [],
            "suggested_diagnosis": raw,
            "confidence": "low",
        }
