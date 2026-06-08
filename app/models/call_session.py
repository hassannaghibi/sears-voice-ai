from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import JSON, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CallState(str, enum.Enum):
    GREETING = "GREETING"
    APPLIANCE_ID = "APPLIANCE_ID"
    SYMPTOM_COLLECTION = "SYMPTOM_COLLECTION"
    DIAGNOSIS = "DIAGNOSIS"
    RESOLUTION_CHECK = "RESOLUTION_CHECK"
    SCHEDULING_OFFER = "SCHEDULING_OFFER"
    TECHNICIAN_MATCH = "TECHNICIAN_MATCH"
    BOOKING = "BOOKING"
    CONFIRMATION = "CONFIRMATION"
    CALLBACK_CAPTURE = "CALLBACK_CAPTURE"
    TIER3_EMAIL = "TIER3_EMAIL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallSession(Base, TimestampMixin):
    __tablename__ = "call_sessions"
    __table_args__ = (Index("ix_call_sessions_call_sid", "call_sid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_sid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    state: Mapped[CallState] = mapped_column(
        Enum(CallState, name="callstate", native_enum=True, create_constraint=False),
        default=CallState.GREETING,
        nullable=False,
    )
    # JSON works across SQLite (tests) and PostgreSQL (production via JSONB in migration)
    context: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    appointment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )

    appointment: Mapped[Optional["app.models.appointment.Appointment"]] = relationship(
        "Appointment", foreign_keys=[appointment_id]
    )
