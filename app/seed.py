"""Idempotent database seeder — 8 Chicago-metro technicians with 15 slots each."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging, get_logger
from app.models.appointment import AvailabilitySlot
from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician

configure_logging()
logger = get_logger(__name__)

TECHNICIANS = [
    {
        "name": "Marcus Johnson",
        "email": "marcus.johnson@sears-tech.example.com",
        "phone": "+13125550001",
        "zip_codes": ["60601", "60614"],
        "specialties": [ApplianceType.washer, ApplianceType.dryer],
    },
    {
        "name": "Elena Rodriguez",
        "email": "elena.rodriguez@sears-tech.example.com",
        "phone": "+13125550002",
        "zip_codes": ["60626", "60629"],
        "specialties": [ApplianceType.refrigerator, ApplianceType.dishwasher],
    },
    {
        "name": "David Park",
        "email": "david.park@sears-tech.example.com",
        "phone": "+13125550003",
        "zip_codes": ["60641", "60657"],
        "specialties": [ApplianceType.oven, ApplianceType.hvac],
    },
    {
        "name": "Priya Patel",
        "email": "priya.patel@sears-tech.example.com",
        "phone": "+13125550004",
        "zip_codes": ["60618", "60608"],
        "specialties": [ApplianceType.washer, ApplianceType.refrigerator],
    },
    {
        "name": "James O'Brien",
        "email": "james.obrien@sears-tech.example.com",
        "phone": "+13125550005",
        "zip_codes": ["60601", "60618"],
        "specialties": [ApplianceType.hvac, ApplianceType.dryer],
    },
    {
        "name": "Aaliyah Thompson",
        "email": "aaliyah.thompson@sears-tech.example.com",
        "phone": "+13125550006",
        "zip_codes": ["60614", "60626"],
        "specialties": [ApplianceType.dishwasher, ApplianceType.oven],
    },
    {
        "name": "Wei Chen",
        "email": "wei.chen@sears-tech.example.com",
        "phone": "+13125550007",
        "zip_codes": ["60629", "60641"],
        "specialties": [ApplianceType.refrigerator, ApplianceType.washer, ApplianceType.dryer],
    },
    {
        "name": "Sofia Mendez",
        "email": "sofia.mendez@sears-tech.example.com",
        "phone": "+13125550008",
        "zip_codes": ["60657", "60608"],
        "specialties": [ApplianceType.oven, ApplianceType.dishwasher, ApplianceType.hvac],
    },
]


def _generate_slots(technician_id: int, now: datetime) -> list[AvailabilitySlot]:
    """Generate 15 slots over the next 14 days, 9AM–5PM, 2-hour windows, weekdays only."""
    slots: list[AvailabilitySlot] = []
    today = now.date()
    slot_count = 0
    day_offset = 1  # start tomorrow

    while slot_count < 15:
        check_date = today + timedelta(days=day_offset)
        day_offset += 1

        if check_date.weekday() >= 5:  # skip Sat/Sun
            continue

        # 9 AM, 11 AM, 1 PM, 3 PM — up to 4 slots per day
        for hour in [9, 11, 13, 15]:
            if slot_count >= 15:
                break
            start = datetime(
                check_date.year, check_date.month, check_date.day, hour, 0, 0, tzinfo=UTC
            )
            end = start + timedelta(hours=2)
            slots.append(
                AvailabilitySlot(
                    technician_id=technician_id,
                    start_time=start,
                    end_time=end,
                    is_booked=False,
                )
            )
            slot_count += 1

    return slots


async def run() -> None:
    async with AsyncSessionLocal() as session:
        # Idempotency check
        result = await session.execute(select(func.count()).select_from(Technician))
        existing_count = result.scalar_one()

        if existing_count >= len(TECHNICIANS):
            logger.info("seed_skipped", existing_technicians=existing_count)
            return

        now = datetime.now(UTC)
        total_slots = 0

        for tech_data in TECHNICIANS:
            technician = Technician(
                name=tech_data["name"],
                email=tech_data["email"],
                phone=tech_data["phone"],
            )
            session.add(technician)
            await session.flush()  # get technician.id

            for zip_code in tech_data["zip_codes"]:
                session.add(ServiceArea(technician_id=technician.id, zip_code=zip_code))

            for appliance in tech_data["specialties"]:
                session.add(Specialty(technician_id=technician.id, appliance_type=appliance))

            slots = _generate_slots(technician.id, now)
            for slot in slots:
                session.add(slot)
            total_slots += len(slots)

        await session.commit()
        logger.info("seed_complete", technicians=len(TECHNICIANS), slots=total_slots)
        print(f"Seed complete — {len(TECHNICIANS)} technicians, {total_slots} slots")


if __name__ == "__main__":
    asyncio.run(run())
