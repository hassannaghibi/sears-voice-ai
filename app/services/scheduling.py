from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
