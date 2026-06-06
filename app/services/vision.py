from __future__ import annotations

import base64

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
Be concise and practical."""


async def analyze_appliance_image(image_bytes: bytes, content_type: str = "image/jpeg") -> dict:
    """Send image to GPT-4o Vision and return structured diagnosis."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{content_type};base64,{b64}"

    response = await client.chat.completions.create(
        model="gpt-4o",
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
    logger.info("vision_analysis_complete", response_length=len(raw))

    import json

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "appliance_type": "other",
            "visible_issues": [],
            "suggested_diagnosis": raw,
            "confidence": "low",
        }
