from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import AvailabilitySlot


class ApplianceType(str, enum.Enum):
    washer = "washer"
    dryer = "dryer"
    refrigerator = "refrigerator"
    dishwasher = "dishwasher"
    oven = "oven"
    hvac = "hvac"
    other = "other"


class Technician(Base, TimestampMixin):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    service_areas: Mapped[list["ServiceArea"]] = relationship(
        "ServiceArea", back_populates="technician", cascade="all, delete-orphan"
    )
    specialties: Mapped[list["Specialty"]] = relationship(
        "Specialty", back_populates="technician", cascade="all, delete-orphan"
    )
    slots: Mapped[list["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot", back_populates="technician", cascade="all, delete-orphan"
    )


class ServiceArea(Base):
    __tablename__ = "service_areas"
    __table_args__ = (Index("ix_service_areas_zip_code", "zip_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technicians.id", ondelete="CASCADE"), nullable=False
    )
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    technician: Mapped["Technician"] = relationship("Technician", back_populates="service_areas")


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technicians.id", ondelete="CASCADE"), nullable=False
    )
    appliance_type: Mapped[ApplianceType] = mapped_column(
        Enum(ApplianceType, native_enum=False),
        nullable=False,
    )

    technician: Mapped["Technician"] = relationship("Technician", back_populates="specialties")
