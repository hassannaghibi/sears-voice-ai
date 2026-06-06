from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> Appointment:
        appointment = Appointment(**data)
        self.db.add(appointment)
        await self.db.flush()
        await self.db.refresh(appointment)
        return appointment

    async def get_by_id(self, appointment_id: int) -> Appointment | None:
        result = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.technician))
            .where(Appointment.id == appointment_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, appointment_id: int, status: AppointmentStatus) -> Appointment:
        result = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.technician))
            .where(Appointment.id == appointment_id)
        )
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise NotFoundError("Appointment", appointment_id)
        appointment.status = status
        await self.db.flush()
        return appointment

    async def get_by_call_sid(self, call_sid: str) -> Appointment | None:
        result = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.technician))
            .where(Appointment.call_sid == call_sid)
        )
        return result.scalar_one_or_none()
