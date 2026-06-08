from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    is_booked: bool

    model_config = {"from_attributes": True}
