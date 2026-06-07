"""Unit tests for SchedulingService."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import SlotNotAvailableError
from app.models.appointment import AvailabilitySlot
from app.models.technician import ApplianceType, Technician
from app.services.scheduling import TechnicianWithSlots, find_available_technicians


def _make_technician(tech_id: int, name: str) -> Technician:
    t = MagicMock(spec=Technician)
    t.id = tech_id
    t.name = name
    return t


def _make_slot(slot_id: int, tech_id: int, hour: int) -> AvailabilitySlot:
    s = MagicMock(spec=AvailabilitySlot)
    s.id = slot_id
    s.technician_id = tech_id
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    s.start_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, 0, tzinfo=UTC)
    s.end_time = s.start_time + timedelta(hours=2)
    s.is_booked = False
    return s


@pytest.mark.asyncio
async def test_find_available_returns_top_3_sorted():
    """Should return top 3 technicians sorted by available slot count DESC."""
    db = AsyncMock()
    tech_repo = AsyncMock()
    slot_repo = AsyncMock()

    techs = [_make_technician(i, f"Tech {i}") for i in range(1, 5)]
    slot_counts = {1: 5, 2: 2, 3: 8, 4: 1}

    tech_repo.find_by_zip_and_specialty.return_value = techs

    async def fake_get_slots(tech_id, target_date):
        return [_make_slot(i, tech_id, 9 + i) for i in range(slot_counts[tech_id])]

    slot_repo.get_available_slots.side_effect = fake_get_slots

    with (
        patch("app.services.scheduling.TechnicianRepository", return_value=tech_repo),
        patch("app.services.scheduling.SlotRepository", return_value=slot_repo),
    ):
        results = await find_available_technicians("60601", ApplianceType.washer, date.today(), db)

    assert len(results) == 3
    # Sorted DESC: tech3 (8), tech1 (5), tech2 (2)
    assert results[0].technician.id == 3
    assert results[1].technician.id == 1
    assert results[2].technician.id == 2


@pytest.mark.asyncio
async def test_find_available_no_match_returns_empty():
    """When no technicians match, should return empty list without raising."""
    db = AsyncMock()
    tech_repo = AsyncMock()
    slot_repo = AsyncMock()

    tech_repo.find_by_zip_and_specialty.return_value = []

    with (
        patch("app.services.scheduling.TechnicianRepository", return_value=tech_repo),
        patch("app.services.scheduling.SlotRepository", return_value=slot_repo),
    ):
        results = await find_available_technicians("99999", ApplianceType.hvac, date.today(), db)

    assert results == []


@pytest.mark.asyncio
async def test_book_appointment_slot_conflict_raises():
    """When slot is already taken, SlotNotAvailableError should propagate."""
    from app.models.technician import ApplianceType
    from app.schemas.appointment import AppointmentCreate
    from app.services.scheduling import book_appointment

    db = AsyncMock()
    slot_repo = AsyncMock()
    slot_repo.mark_booked.side_effect = SlotNotAvailableError(42)

    payload = AppointmentCreate(
        slot_id=42,
        customer_name="Jane Doe",
        customer_phone="+13125550100",
        zip_code="60601",
        appliance_type=ApplianceType.washer,
        symptoms="Not spinning",
        call_sid="CA_test",
    )

    with patch("app.services.scheduling.SlotRepository", return_value=slot_repo):
        with pytest.raises(SlotNotAvailableError):
            await book_appointment(42, payload, db)
