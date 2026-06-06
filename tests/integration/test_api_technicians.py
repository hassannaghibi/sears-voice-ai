"""Integration tests: /api/v1/technicians."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import AvailabilitySlot
from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician


@pytest_asyncio.fixture
async def seeded_technician(db_session: AsyncSession) -> Technician:
    tech = Technician(
        name="Integration Tech",
        email="integ@example.com",
        phone="+13125550050",
    )
    db_session.add(tech)
    db_session.add(ServiceArea(technician=tech, zip_code="60601"))
    db_session.add(Specialty(technician=tech, appliance_type=ApplianceType.washer))

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    slot_start = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    db_session.add(
        AvailabilitySlot(
            technician=tech,
            start_time=slot_start,
            end_time=slot_start + timedelta(hours=2),
            is_booked=False,
        )
    )
    await db_session.flush()
    return tech


@pytest.mark.asyncio
async def test_list_technicians_by_zip_specialty_date(
    async_client, seeded_technician: Technician
):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    response = await async_client.get(
        f"/api/v1/technicians?zip=60601&specialty=washer&date={tomorrow}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(t["id"] == seeded_technician.id for t in data["data"])


@pytest.mark.asyncio
async def test_list_technicians_no_match_zip(async_client, seeded_technician: Technician):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    response = await async_client.get(
        f"/api/v1/technicians?zip=99999&specialty=washer&date={tomorrow}"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_technician_availability_not_found(async_client):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    response = await async_client.get(f"/api/v1/technicians/99999/availability?date={tomorrow}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_technician_availability_found(async_client, seeded_technician: Technician):
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    response = await async_client.get(
        f"/api/v1/technicians/{seeded_technician.id}/availability?date={tomorrow}"
    )
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) >= 1


@pytest.mark.asyncio
async def test_list_technicians_pagination(async_client):
    response = await async_client.get("/api/v1/technicians?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
