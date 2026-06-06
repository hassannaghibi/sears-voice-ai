"""Unit tests for repository CRUD operations."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, SlotNotAvailableError
from app.models.call_session import CallState
from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician
from app.models.appointment import AvailabilitySlot
from app.repositories.call_session import CallSessionRepository
from app.repositories.slot import SlotRepository
from app.repositories.technician import TechnicianRepository

from datetime import UTC, datetime, timedelta


@pytest_asyncio.fixture
async def sample_technician(db_session: AsyncSession) -> Technician:
    tech = Technician(name="Test Tech", email="test@example.com", phone="+13125550099")
    db_session.add(tech)
    db_session.add(ServiceArea(technician=tech, zip_code="60601"))
    db_session.add(Specialty(technician=tech, appliance_type=ApplianceType.washer))
    await db_session.flush()
    return tech


@pytest_asyncio.fixture
async def sample_slot(db_session: AsyncSession, sample_technician: Technician) -> AvailabilitySlot:
    now = datetime.now(UTC)
    slot = AvailabilitySlot(
        technician_id=sample_technician.id,
        start_time=now + timedelta(days=1, hours=9),
        end_time=now + timedelta(days=1, hours=11),
        is_booked=False,
    )
    db_session.add(slot)
    await db_session.flush()
    return slot


@pytest.mark.asyncio
async def test_technician_get_by_id(db_session: AsyncSession, sample_technician: Technician):
    repo = TechnicianRepository(db_session)
    tech = await repo.get_by_id(sample_technician.id)
    assert tech is not None
    assert tech.name == "Test Tech"


@pytest.mark.asyncio
async def test_technician_get_by_id_not_found(db_session: AsyncSession):
    repo = TechnicianRepository(db_session)
    tech = await repo.get_by_id(99999)
    assert tech is None


@pytest.mark.asyncio
async def test_technician_find_by_zip_and_specialty(
    db_session: AsyncSession, sample_technician: Technician
):
    repo = TechnicianRepository(db_session)
    results = await repo.find_by_zip_and_specialty("60601", ApplianceType.washer)
    assert len(results) >= 1
    assert any(t.id == sample_technician.id for t in results)


@pytest.mark.asyncio
async def test_technician_find_no_match(db_session: AsyncSession):
    repo = TechnicianRepository(db_session)
    results = await repo.find_by_zip_and_specialty("99999", ApplianceType.hvac)
    assert results == []


@pytest.mark.asyncio
async def test_slot_mark_booked(db_session: AsyncSession, sample_slot: AvailabilitySlot):
    repo = SlotRepository(db_session)
    slot = await repo.mark_booked(sample_slot.id)
    assert slot.is_booked is True


@pytest.mark.asyncio
async def test_slot_mark_booked_twice_raises(
    db_session: AsyncSession, sample_slot: AvailabilitySlot
):
    repo = SlotRepository(db_session)
    await repo.mark_booked(sample_slot.id)
    with pytest.raises(SlotNotAvailableError):
        await repo.mark_booked(sample_slot.id)


@pytest.mark.asyncio
async def test_call_session_create_and_update(db_session: AsyncSession):
    repo = CallSessionRepository(db_session)
    session = await repo.create("CA_test_001")
    assert session.state == CallState.GREETING

    updated = await repo.update_state("CA_test_001", CallState.DIAGNOSIS)
    assert updated.state == CallState.DIAGNOSIS


@pytest.mark.asyncio
async def test_call_session_update_context_merges(db_session: AsyncSession):
    repo = CallSessionRepository(db_session)
    await repo.create("CA_test_002")
    await repo.update_context("CA_test_002", {"symptoms": {"type": "washer"}})
    await repo.update_context("CA_test_002", {"zip_code": "60601"})

    session = await repo.get_by_call_sid("CA_test_002")
    assert session.context.get("symptoms") is not None
    assert session.context.get("zip_code") == "60601"


@pytest.mark.asyncio
async def test_call_session_not_found_raises(db_session: AsyncSession):
    repo = CallSessionRepository(db_session)
    with pytest.raises(NotFoundError):
        await repo.update_state("CA_nonexistent", CallState.FAILED)
