from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.appointment import AppointmentStatus
from app.models.technician import ApplianceType
from app.schemas.technician import TechnicianResponse


class AppointmentCreate(BaseModel):
    slot_id: int
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    zip_code: str
    appliance_type: ApplianceType
    symptoms: str
    call_sid: str


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class AppointmentResponse(BaseModel):
    id: int
    slot_id: int
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    zip_code: str
    appliance_type: ApplianceType
    symptoms: str
    call_sid: str
    status: AppointmentStatus
    technician: TechnicianResponse
    created_at: datetime

    model_config = {"from_attributes": True}
