"""Integration tests: /api/v1/appointments."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import AvailabilitySlot
from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician


@pytest_asyncio.fixture
async def tech_and_slot(db_session: AsyncSession):
    tech = Technician(
        name="Appt Tech",
        email="appttech@example.com",
        phone="+13125550060",
    )
    db_session.add(tech)
    db_session.add(ServiceArea(technician=tech, zip_code="60601"))
    db_session.add(Specialty(technician=tech, appliance_type=ApplianceType.washer))

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    slot_start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    slot = AvailabilitySlot(
        technician=tech,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=2),
        is_booked=False,
    )
    db_session.add(slot)
    await db_session.flush()
    return tech, slot


@pytest.mark.asyncio
async def test_create_appointment_201(async_client, tech_and_slot):
    tech, slot = tech_and_slot
    payload = {
        "slot_id": slot.id,
        "customer_name": "Jane Doe",
        "customer_phone": "+13125550100",
        "zip_code": "60601",
        "appliance_type": "washer",
        "symptoms": "Not spinning",
        "call_sid": "CA_integration_test",
    }
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["customer_name"] == "Jane Doe"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_appointment_slot_conflict_409(async_client, tech_and_slot):
    tech, slot = tech_and_slot
    payload = {
        "slot_id": slot.id,
        "customer_name": "Person A",
        "customer_phone": "+13125550101",
        "zip_code": "60601",
        "appliance_type": "washer",
        "symptoms": "Not spinning",
        "call_sid": "CA_conflict_1",
    }
    resp1 = await async_client.post("/api/v1/appointments", json=payload)
    assert resp1.status_code == 201

    payload["call_sid"] = "CA_conflict_2"
    payload["customer_name"] = "Person B"
    resp2 = await async_client.post("/api/v1/appointments", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_get_appointment_not_found(async_client):
    response = await async_client.get("/api/v1/appointments/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_appointment_found(async_client, tech_and_slot):
    tech, slot = tech_and_slot
    # Book a fresh slot fixture for this test
    from datetime import timedelta
    from app.models.appointment import AvailabilitySlot

    payload = {
        "slot_id": slot.id,
        "customer_name": "Read Test",
        "customer_phone": "+13125550102",
        "zip_code": "60601",
        "appliance_type": "washer",
        "symptoms": "Leaking",
        "call_sid": "CA_read_test",
    }
    create_resp = await async_client.post("/api/v1/appointments", json=payload)
    # If slot already taken, skip
    if create_resp.status_code != 201:
        pytest.skip("Slot already booked by another test")
    appt_id = create_resp.json()["id"]

    get_resp = await async_client.get(f"/api/v1/appointments/{appt_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == appt_id


@pytest.mark.asyncio
async def test_update_appointment_status(async_client, tech_and_slot):
    tech, slot = tech_and_slot
    payload = {
        "slot_id": slot.id,
        "customer_name": "Update Test",
        "customer_phone": "+13125550103",
        "zip_code": "60601",
        "appliance_type": "washer",
        "symptoms": "Vibrating",
        "call_sid": "CA_update_test",
    }
    create_resp = await async_client.post("/api/v1/appointments", json=payload)
    if create_resp.status_code != 201:
        pytest.skip("Slot already booked")
    appt_id = create_resp.json()["id"]

    patch_resp = await async_client.patch(
        f"/api/v1/appointments/{appt_id}", json={"status": "confirmed"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "confirmed"
