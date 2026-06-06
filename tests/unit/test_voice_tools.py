"""Unit tests for voice tool handlers."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import SlotNotAvailableError
from app.voice.tools import (
    dispatch_tool,
    handle_book_appointment,
    handle_collect_callback_number,
    handle_collect_symptoms,
    handle_find_available_technicians,
    handle_send_image_upload_link,
    handle_update_call_state,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_handle_find_available_technicians_found(mock_db):
    from app.models.technician import Technician
    from app.models.appointment import AvailabilitySlot
    from datetime import UTC, datetime, timedelta
    from app.services.scheduling import TechnicianWithSlots

    tech = MagicMock(spec=Technician)
    tech.id = 1
    tech.name = "Marcus Johnson"

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    slot = MagicMock(spec=AvailabilitySlot)
    slot.id = 10
    slot.start_time = tomorrow.replace(hour=9)
    slot.end_time = tomorrow.replace(hour=11)

    with patch("app.voice.tools.find_availability_with_fallback", new=AsyncMock(
        return_value=MagicMock(
            technicians=[TechnicianWithSlots(technician=tech, slots=[slot])],
            matched_date=tomorrow.date(),
            used_fallback_date=False,
        )
    )):
        result = await handle_find_available_technicians(
            {"zip_code": "60601", "appliance_type": "washer"}, mock_db, "CA_test"
        )
    assert result["available"] is True
    assert len(result["options"]) == 1
    assert result["options"][0]["technician_name"] == "Marcus Johnson"


@pytest.mark.asyncio
async def test_handle_find_available_technicians_not_found(mock_db):
    with patch("app.voice.tools.find_availability_with_fallback", new=AsyncMock(
        return_value=MagicMock(technicians=[], matched_date=date.today(), used_fallback_date=False)
    )):
        result = await handle_find_available_technicians(
            {"zip_code": "99999", "appliance_type": "hvac"}, mock_db, "CA_test"
        )
    assert result["available"] is False


@pytest.mark.asyncio
async def test_handle_book_appointment_success(mock_db):
    from app.models.appointment import Appointment
    appt = MagicMock(spec=Appointment)
    appt.id = 5
    appt.technician_id = 1

    with patch("app.voice.tools.book_appointment", new=AsyncMock(return_value=appt)):
        result = await handle_book_appointment(
            {
                "slot_id": 10,
                "customer_name": "Jane Doe",
                "customer_phone": "+13125550100",
                "zip_code": "60601",
                "appliance_type": "washer",
                "symptoms": "Not spinning",
            },
            mock_db,
            "CA_test",
        )
    assert result["success"] is True
    assert result["appointment_id"] == 5


@pytest.mark.asyncio
async def test_handle_book_appointment_slot_taken(mock_db):
    with patch("app.voice.tools.book_appointment", new=AsyncMock(side_effect=SlotNotAvailableError(10))):
        result = await handle_book_appointment(
            {
                "slot_id": 10,
                "customer_name": "Jane Doe",
                "customer_phone": "+13125550100",
                "zip_code": "60601",
                "appliance_type": "washer",
                "symptoms": "Not spinning",
            },
            mock_db,
            "CA_test",
        )
    assert result["error"] == "slot_taken"


@pytest.mark.asyncio
async def test_handle_collect_symptoms(mock_db):
    repo = AsyncMock()
    repo.update_context = AsyncMock()
    repo.update_state = AsyncMock()

    with patch("app.voice.tools.CallSessionRepository", return_value=repo):
        result = await handle_collect_symptoms(
            {
                "appliance_type": "washer",
                "symptom_description": "Not spinning",
                "started_when": "yesterday",
                "error_codes": "E5",
            },
            mock_db,
            "CA_test",
        )
    assert result["saved"] is True
    repo.update_context.assert_called_once()
    repo.update_state.assert_called_once()


@pytest.mark.asyncio
async def test_handle_collect_callback_number(mock_db):
    repo = AsyncMock()
    with patch("app.voice.tools.CallSessionRepository", return_value=repo):
        result = await handle_collect_callback_number(
            {"phone_number": "+13125550200", "zip_code": "99999", "appliance_type": "hvac"},
            mock_db,
            "CA_test",
        )
    assert result["saved"] is True


@pytest.mark.asyncio
async def test_dispatch_tool_unknown(mock_db):
    result = await dispatch_tool("nonexistent_tool", {}, mock_db, "CA_test")
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_update_call_state(mock_db):
    repo = AsyncMock()
    with patch("app.voice.tools.CallSessionRepository", return_value=repo):
        result = await handle_update_call_state(
            {"new_state": "DIAGNOSIS"}, mock_db, "CA_test"
        )
    assert result["updated"] is True
    assert result["state"] == "DIAGNOSIS"


@pytest.mark.asyncio
async def test_handle_find_available_partial_zip(mock_db):
    result = await handle_find_available_technicians(
        {"zip_code": "606", "appliance_type": "washer"}, mock_db, "CA_test"
    )
    assert result["error"] == "partial_zip"


@pytest.mark.asyncio
async def test_handle_send_image_upload_link(mock_db):
    with patch("app.voice.tools.upload_service.create_upload_link", new=AsyncMock(
        return_value=("tok123", "http://test/voice/upload/tok123")
    )), patch("app.voice.tools.CallSessionRepository") as mock_repo_cls:
        mock_repo_cls.return_value.update_state = AsyncMock()
        result = await handle_send_image_upload_link(
            {"email": "user@example.com", "appliance_type": "washer"},
            mock_db,
            "CA_test",
        )
    assert result["sent"] is True
    assert result["email"] == "user@example.com"
