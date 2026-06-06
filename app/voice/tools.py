from __future__ import annotations

import time
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SlotNotAvailableError
from app.core.logging import get_logger
from app.models.call_session import CallState
from app.models.technician import ApplianceType
from app.repositories.call_session import CallSessionRepository
from app.schemas.appointment import AppointmentCreate
from app.services import email as email_service
from app.services.scheduling import book_appointment, find_available_technicians

logger = get_logger(__name__)


async def handle_find_available_technicians(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    zip_code = args.get("zip_code", "")
    appliance_str = args.get("appliance_type", "other")
    preferred_date_str = args.get("preferred_date")

    try:
        appliance_type = ApplianceType(appliance_str)
    except ValueError:
        appliance_type = ApplianceType.other

    if preferred_date_str:
        try:
            preferred_date = datetime.strptime(preferred_date_str, "%Y-%m-%d").date()
        except ValueError:
            preferred_date = date.today()
    else:
        preferred_date = date.today()

    results = await find_available_technicians(zip_code, appliance_type, preferred_date, db)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "tool_called",
        tool_name="find_available_technicians",
        call_sid=call_sid,
        duration_ms=duration_ms,
        result_count=len(results),
    )

    if not results:
        return {"available": False}

    options = []
    for r in results:
        slots_data = []
        for slot in r.slots[:3]:
            slots_data.append(
                {
                    "slot_id": slot.id,
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "day": slot.start_time.strftime("%A"),
                    "time": slot.start_time.strftime("%I:%M %p").lstrip("0"),
                }
            )
        options.append(
            {
                "technician_id": r.technician.id,
                "technician_name": r.technician.name,
                "slots": slots_data,
            }
        )

    return {"available": True, "options": options}


async def handle_book_appointment(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    try:
        payload = AppointmentCreate(
            slot_id=args["slot_id"],
            customer_name=args["customer_name"],
            customer_phone=args["customer_phone"],
            customer_email=args.get("customer_email"),
            zip_code=args["zip_code"],
            appliance_type=ApplianceType(args["appliance_type"]),
            symptoms=args["symptoms"],
            call_sid=call_sid,
        )
        appointment = await book_appointment(payload.slot_id, payload, db)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "tool_called",
            tool_name="book_appointment",
            call_sid=call_sid,
            duration_ms=duration_ms,
            appointment_id=appointment.id,
        )
        return {
            "success": True,
            "appointment_id": appointment.id,
            "technician_id": appointment.technician_id,
        }
    except SlotNotAvailableError:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.warning(
            "tool_slot_taken", tool_name="book_appointment", call_sid=call_sid, duration_ms=duration_ms
        )
        return {
            "error": "slot_taken",
            "message": "That slot was just taken. Let me find you another option.",
        }


async def handle_collect_symptoms(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    session_repo = CallSessionRepository(db)
    await session_repo.update_context(
        call_sid,
        {
            "symptoms": {
                "appliance_type": args.get("appliance_type"),
                "symptom_description": args.get("symptom_description"),
                "started_when": args.get("started_when"),
                "error_codes": args.get("error_codes", "none"),
            }
        },
    )
    await session_repo.update_state(call_sid, CallState.DIAGNOSIS)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "tool_called", tool_name="collect_symptoms", call_sid=call_sid, duration_ms=duration_ms
    )
    return {"saved": True}


async def handle_collect_callback_number(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    session_repo = CallSessionRepository(db)
    await session_repo.update_context(
        call_sid,
        {
            "callback": {
                "phone_number": args.get("phone_number"),
                "zip_code": args.get("zip_code"),
                "appliance_type": args.get("appliance_type"),
            }
        },
    )
    await session_repo.update_state(call_sid, CallState.CALLBACK_CAPTURE)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "tool_called",
        tool_name="collect_callback_number",
        call_sid=call_sid,
        duration_ms=duration_ms,
    )
    return {"saved": True}


async def handle_send_image_upload_link(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    email = args["email"]
    appliance_type = args.get("appliance_type", "appliance")

    try:
        upload_url = await email_service.send_upload_link(email, appliance_type, call_sid)
        session_repo = CallSessionRepository(db)
        await session_repo.update_context(
            call_sid, {"upload_email": email, "upload_url": upload_url}
        )
        await session_repo.update_state(call_sid, CallState.TIER3_EMAIL)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "tool_called",
            tool_name="send_image_upload_link",
            call_sid=call_sid,
            duration_ms=duration_ms,
        )
        return {"sent": True, "email": email}
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.error(
            "tool_failed",
            tool_name="send_image_upload_link",
            call_sid=call_sid,
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {"sent": False, "error": str(exc)}


async def handle_update_call_state(
    args: dict, db: AsyncSession, call_sid: str
) -> dict:
    start = time.perf_counter()
    new_state_str = args.get("new_state", "GREETING")
    try:
        new_state = CallState(new_state_str)
    except ValueError:
        new_state = CallState.GREETING

    session_repo = CallSessionRepository(db)
    await session_repo.update_state(call_sid, new_state)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "tool_called",
        tool_name="update_call_state",
        call_sid=call_sid,
        new_state=new_state_str,
        duration_ms=duration_ms,
    )
    return {"updated": True, "state": new_state_str}


TOOL_HANDLERS = {
    "find_available_technicians": handle_find_available_technicians,
    "book_appointment": handle_book_appointment,
    "collect_symptoms": handle_collect_symptoms,
    "collect_callback_number": handle_collect_callback_number,
    "send_image_upload_link": handle_send_image_upload_link,
    "update_call_state": handle_update_call_state,
}


async def dispatch_tool(
    tool_name: str, args: dict, db: AsyncSession, call_sid: str
) -> dict:
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        logger.warning("unknown_tool", tool_name=tool_name, call_sid=call_sid)
        return {"error": f"Unknown tool: {tool_name}"}
    return await handler(args, db, call_sid)
