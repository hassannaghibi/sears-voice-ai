from __future__ import annotations

from app.voice.prompts import TOOL_DEFINITIONS


def anthropic_tool_definitions() -> list[dict]:
    """Convert OpenAI Realtime tool defs to Anthropic Messages API format."""
    tools: list[dict] = []
    for tool in TOOL_DEFINITIONS:
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
        )
    return tools
