from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.call_session import CallSessionRepository


def format_call_context(context: dict) -> str:
    """Serialize persisted call context for injection into LLM instructions."""
    if not context:
        return ""

    lines: list[str] = []
    symptoms = context.get("symptoms")
    if symptoms:
        lines.append(
            "Symptoms collected: "
            f"appliance={symptoms.get('appliance_type')}, "
            f"description={symptoms.get('symptom_description')}, "
            f"started={symptoms.get('started_when')}, "
            f"error_codes={symptoms.get('error_codes')}"
        )

    callback = context.get("callback")
    if callback:
        lines.append(
            "Callback info: "
            f"phone={callback.get('phone_number')}, "
            f"zip={callback.get('zip_code')}, "
            f"appliance={callback.get('appliance_type')}"
        )

    vision = context.get("vision_analysis")
    if vision:
        lines.append(
            "Photo analysis: "
            f"appliance={vision.get('appliance_type')}, "
            f"diagnosis={vision.get('suggested_diagnosis')}, "
            f"issues={vision.get('visible_issues')}"
        )

    if context.get("upload_email"):
        lines.append(f"Upload link sent to: {context.get('upload_email')}")

    if not lines:
        return ""

    return "\n## Known caller context (do not re-ask)\n" + "\n".join(f"- {line}" for line in lines)


async def load_context_block(call_sid: str, db: AsyncSession) -> str:
    repo = CallSessionRepository(db)
    session = await repo.get_by_call_sid(call_sid)
    if session is None:
        return ""
    return format_call_context(session.context or {})
