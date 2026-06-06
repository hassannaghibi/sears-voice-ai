from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SlotNotAvailableError
from app.models.appointment import Appointment, AvailabilitySlot
from app.models.technician import ApplianceType, Technician
from app.repositories.appointment import AppointmentRepository
from app.repositories.slot import SlotRepository
from app.repositories.technician import TechnicianRepository
from app.schemas.appointment import AppointmentCreate


@dataclass
class TechnicianWithSlots:
    technician: Technician
    slots: list[AvailabilitySlot]


@dataclass
class AvailabilitySearchResult:
    technicians: list[TechnicianWithSlots]
    matched_date: date
    used_fallback_date: bool


def normalize_zip_code(zip_code: str) -> tuple[str | None, str | None]:
    """Return (normalized_zip, error_code). error_code is partial_zip or invalid_zip."""
    digits = "".join(c for c in zip_code if c.isdigit())
    if len(digits) == 5:
        return digits, None
    if len(digits) == 9:
        return digits[:5], None
    if len(digits) < 5:
        return None, "partial_zip"
    return None, "invalid_zip"


async def find_available_technicians(
    zip_code: str,
    appliance_type: ApplianceType,
    preferred_date: date,
    db: AsyncSession,
) -> list[TechnicianWithSlots]:
    """
    1. Find technicians with zip_code in their service_areas
    2. Filter to those with the given appliance_type specialty
    3. Load their unbooked slots for preferred_date
    4. Sort by available slot count DESC, return top 3
    5. Return [] (never raise) when no match
    """
    tech_repo = TechnicianRepository(db)
    slot_repo = SlotRepository(db)

    technicians = await tech_repo.find_by_zip_and_specialty(zip_code, appliance_type)
    if not technicians:
        return []

    results: list[TechnicianWithSlots] = []
    for technician in technicians:
        slots = await slot_repo.get_available_slots(technician.id, preferred_date)
        if slots:
            results.append(TechnicianWithSlots(technician=technician, slots=slots))

    results.sort(key=lambda r: len(r.slots), reverse=True)
    return results[:3]


async def find_availability_with_fallback(
    zip_code: str,
    appliance_type: ApplianceType,
    preferred_date: date,
    db: AsyncSession,
    max_days: int = 14,
) -> AvailabilitySearchResult:
    """Search preferred date first, then scan forward up to max_days for open slots."""
    for offset in range(max_days):
        check_date = preferred_date + timedelta(days=offset)
        results = await find_available_technicians(zip_code, appliance_type, check_date, db)
        if results:
            return AvailabilitySearchResult(
                technicians=results,
                matched_date=check_date,
                used_fallback_date=offset > 0,
            )
    return AvailabilitySearchResult(
        technicians=[],
        matched_date=preferred_date,
        used_fallback_date=False,
    )


async def book_appointment(
    slot_id: int,
    data: AppointmentCreate,
    db: AsyncSession,
) -> Appointment:
    """
    Atomic booking:
    1. SELECT ... FOR UPDATE on the slot
    2. If is_booked, raise SlotNotAvailableError
    3. INSERT appointment
    4. UPDATE slot SET is_booked=TRUE
    5. Commit (handled by get_db dependency)
    """
    slot_repo = SlotRepository(db)
    appt_repo = AppointmentRepository(db)

    # Will raise SlotNotAvailableError if already booked
    slot = await slot_repo.mark_booked(slot_id)

    appt_data = data.model_dump()
    appt_data["technician_id"] = slot.technician_id
    appointment = await appt_repo.create(appt_data)
    return appointment
