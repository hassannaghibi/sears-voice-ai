"""Unit tests for AppointmentRepository."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.appointment import AppointmentStatus, AvailabilitySlot
from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician
from app.repositories.appointment import AppointmentRepository


@pytest.mark.asyncio
async def test_appointment_create_and_get(db_session: AsyncSession):
    tech = Technician(name="Appt Tech", email="appt@example.com", phone="+13125550111")
    db_session.add(tech)
    db_session.add(ServiceArea(technician=tech, zip_code="60601"))
    db_session.add(Specialty(technician=tech, appliance_type=ApplianceType.washer))
    await db_session.flush()

    now = datetime.now(UTC)
    slot = AvailabilitySlot(
        technician_id=tech.id,
        start_time=now + timedelta(days=2, hours=9),
        end_time=now + timedelta(days=2, hours=11),
        is_booked=True,
    )
    db_session.add(slot)
    await db_session.flush()

    repo = AppointmentRepository(db_session)
    appt = await repo.create(
        {
            "technician_id": tech.id,
            "slot_id": slot.id,
            "customer_name": "Jane Doe",
            "customer_phone": "+13125550123",
            "zip_code": "60601",
            "appliance_type": ApplianceType.washer,
            "symptoms": "Not draining",
            "call_sid": "CA_appt_test",
        }
    )
    assert appt.id is not None

    loaded = await repo.get_by_id(appt.id)
    assert loaded is not None
    assert loaded.customer_name == "Jane Doe"
    assert loaded.technician.name == "Appt Tech"


@pytest.mark.asyncio
async def test_appointment_update_status(db_session: AsyncSession):
    tech = Technician(name="Status Tech", email="status@example.com", phone="+13125550112")
    db_session.add(tech)
    await db_session.flush()

    now = datetime.now(UTC)
    slot = AvailabilitySlot(
        technician_id=tech.id,
        start_time=now + timedelta(days=3, hours=10),
        end_time=now + timedelta(days=3, hours=12),
        is_booked=True,
    )
    db_session.add(slot)
    await db_session.flush()

    repo = AppointmentRepository(db_session)
    appt = await repo.create(
        {
            "technician_id": tech.id,
            "slot_id": slot.id,
            "customer_name": "Bob",
            "customer_phone": "+13125550124",
            "zip_code": "60601",
            "appliance_type": ApplianceType.dryer,
            "symptoms": "No heat",
            "call_sid": "CA_status_test",
        }
    )

    updated = await repo.update_status(appt.id, AppointmentStatus.confirmed)
    assert updated.status == AppointmentStatus.confirmed


@pytest.mark.asyncio
async def test_appointment_get_by_id_not_found(db_session: AsyncSession):
    repo = AppointmentRepository(db_session)
    assert await repo.get_by_id(99999) is None


@pytest.mark.asyncio
async def test_appointment_update_status_not_found(db_session: AsyncSession):
    repo = AppointmentRepository(db_session)
    with pytest.raises(NotFoundError):
        await repo.update_status(99999, AppointmentStatus.cancelled)
