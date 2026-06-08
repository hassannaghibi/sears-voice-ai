from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, SlotNotAvailableError
from app.models.appointment import AvailabilitySlot


class SlotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, slot_id: int) -> AvailabilitySlot | None:
        result = await self.db.execute(
            select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def get_available_slots(
        self, technician_id: int, target_date: date
    ) -> list[AvailabilitySlot]:
        from datetime import datetime, timezone

        day_start = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc
        )
        day_end = datetime(
            target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc
        )

        result = await self.db.execute(
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.technician_id == technician_id,
                AvailabilitySlot.is_booked == False,  # noqa: E712
                AvailabilitySlot.start_time >= day_start,
                AvailabilitySlot.start_time <= day_end,
            )
            .order_by(AvailabilitySlot.start_time)
        )
        return list(result.scalars().all())

    async def mark_booked(self, slot_id: int) -> AvailabilitySlot:
        """Atomic slot booking using SELECT ... FOR UPDATE."""
        result = await self.db.execute(
            select(AvailabilitySlot)
            .where(AvailabilitySlot.id == slot_id)
            .with_for_update()
        )
        slot = result.scalar_one_or_none()
        if slot is None:
            raise NotFoundError("Slot", slot_id)
        if slot.is_booked:
            raise SlotNotAvailableError(slot_id)
        slot.is_booked = True
        return slot
