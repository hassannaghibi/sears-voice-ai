from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories.appointment import AppointmentRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
)
from app.services.scheduling import book_appointment

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
):
    appointment = await book_appointment(payload.slot_id, payload, db)
    # Reload with technician relationship
    repo = AppointmentRepository(db)
    full = await repo.get_by_id(appointment.id)
    return AppointmentResponse.model_validate(full)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = AppointmentRepository(db)
    appointment = await repo.get_by_id(appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment", appointment_id)
    return AppointmentResponse.model_validate(appointment)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment_status(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = AppointmentRepository(db)
    appointment = await repo.update_status(appointment_id, payload.status)
    return AppointmentResponse.model_validate(appointment)
