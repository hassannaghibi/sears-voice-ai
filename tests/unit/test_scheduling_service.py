"""Unit tests for SchedulingService."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import SlotNotAvailableError
from app.models.appointment import AvailabilitySlot
from app.models.technician import ApplianceType, Technician
from app.services.scheduling import (
    TechnicianWithSlots,
    find_availability_with_fallback,
    find_available_technicians,
    normalize_zip_code,
)


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

    import app.services.scheduling as svc
    original_tech_repo = svc.TechnicianRepository
    original_slot_repo = svc.SlotRepository
    svc.TechnicianRepository = lambda db: tech_repo
    svc.SlotRepository = lambda db: slot_repo

    try:
        results = await find_available_technicians("60601", ApplianceType.washer, date.today(), db)
        assert len(results) == 3
        # Sorted DESC: tech3 (8), tech1 (5), tech2 (2)
        assert results[0].technician.id == 3
        assert results[1].technician.id == 1
        assert results[2].technician.id == 2
    finally:
        svc.TechnicianRepository = original_tech_repo
        svc.SlotRepository = original_slot_repo


@pytest.mark.asyncio
async def test_find_available_no_match_returns_empty():
    """When no technicians match, should return empty list without raising."""
    db = AsyncMock()
    tech_repo = AsyncMock()
    slot_repo = AsyncMock()

    tech_repo.find_by_zip_and_specialty.return_value = []

    import app.services.scheduling as svc
    original_tech_repo = svc.TechnicianRepository
    original_slot_repo = svc.SlotRepository
    svc.TechnicianRepository = lambda db: tech_repo
    svc.SlotRepository = lambda db: slot_repo

    try:
        results = await find_available_technicians("99999", ApplianceType.hvac, date.today(), db)
        assert results == []
    finally:
        svc.TechnicianRepository = original_tech_repo
        svc.SlotRepository = original_slot_repo


def test_normalize_zip_code():
    assert normalize_zip_code("60601") == ("60601", None)
    assert normalize_zip_code("60601-1234") == ("60601", None)
    assert normalize_zip_code("60")[1] == "partial_zip"


@pytest.mark.asyncio
async def test_find_availability_with_fallback_uses_next_day():
    db = AsyncMock()
    tech_repo = AsyncMock()
    slot_repo = AsyncMock()
    tech = _make_technician(1, "Tech 1")
    tech_repo.find_by_zip_and_specialty.return_value = [tech]

    call_count = 0

    async def fake_get_slots(tech_id, target_date):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return []
        return [_make_slot(1, tech_id, 10)]

    slot_repo.get_available_slots.side_effect = fake_get_slots

    import app.services.scheduling as svc
    original_tech_repo = svc.TechnicianRepository
    original_slot_repo = svc.SlotRepository
    svc.TechnicianRepository = lambda db: tech_repo
    svc.SlotRepository = lambda db: slot_repo

    try:
        result = await find_availability_with_fallback(
            "60601", ApplianceType.washer, date.today(), db
        )
        assert result.used_fallback_date is True
        assert len(result.technicians) == 1
    finally:
        svc.TechnicianRepository = original_tech_repo
        svc.SlotRepository = original_slot_repo


@pytest.mark.asyncio
async def test_book_appointment_slot_conflict_raises():
    """When slot is already taken, SlotNotAvailableError should propagate."""
    from unittest.mock import patch, AsyncMock as AM
    from app.schemas.appointment import AppointmentCreate
    from app.services.scheduling import book_appointment
    from app.models.technician import ApplianceType

    db = AM()
    slot_repo = AM()
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

    import app.services.scheduling as svc
    original_slot_repo = svc.SlotRepository
    svc.SlotRepository = lambda db: slot_repo

    try:
        with pytest.raises(SlotNotAvailableError):
            await book_appointment(42, payload, db)
    finally:
        svc.SlotRepository = original_slot_repo
