from __future__ import annotations

from pydantic import BaseModel

from app.schemas.slot import SlotResponse


class TechnicianResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str

    model_config = {"from_attributes": True}


class TechnicianWithAvailability(TechnicianResponse):
    available_slots: list[SlotResponse] = []
