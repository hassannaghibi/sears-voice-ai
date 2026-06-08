from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.technician import ApplianceType

if TYPE_CHECKING:
    from app.models.technician import Technician


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class AvailabilitySlot(Base, TimestampMixin):
    __tablename__ = "availability_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technicians.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_booked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    technician: Mapped["Technician"] = relationship("Technician", back_populates="slots")
    appointment: Mapped[Optional["Appointment"]] = relationship(
        "Appointment", back_populates="slot", uselist=False
    )


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_call_sid", "call_sid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technicians.id", ondelete="RESTRICT"), nullable=False
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("availability_slots.id", ondelete="RESTRICT"), nullable=False
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    appliance_type: Mapped[ApplianceType] = mapped_column(
        Enum(ApplianceType, name="appliancetype", native_enum=True, create_constraint=False), nullable=False
    )
    symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointmentstatus", native_enum=True, create_constraint=False),
        default=AppointmentStatus.pending,
        server_default="pending",
        nullable=False,
    )
    call_sid: Mapped[str] = mapped_column(String(64), nullable=False)

    technician: Mapped["Technician"] = relationship("Technician")
    slot: Mapped["AvailabilitySlot"] = relationship("AvailabilitySlot", back_populates="appointment")
