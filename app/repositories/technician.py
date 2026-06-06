from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.technician import ApplianceType, ServiceArea, Specialty, Technician


class TechnicianRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, technician_id: int) -> Technician | None:
        result = await self.db.execute(
            select(Technician)
            .options(
                selectinload(Technician.service_areas),
                selectinload(Technician.specialties),
            )
            .where(Technician.id == technician_id)
        )
        return result.scalar_one_or_none()

    async def find_by_zip_and_specialty(
        self, zip_code: str, appliance_type: ApplianceType
    ) -> list[Technician]:
        result = await self.db.execute(
            select(Technician)
            .join(Technician.service_areas)
            .join(Technician.specialties)
            .where(
                ServiceArea.zip_code == zip_code,
                Specialty.appliance_type == appliance_type,
            )
            .options(
                selectinload(Technician.service_areas),
                selectinload(Technician.specialties),
                selectinload(Technician.slots),
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def list_all(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Technician], int]:
        offset = (page - 1) * page_size

        count_result = await self.db.execute(select(func.count()).select_from(Technician))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Technician)
            .options(
                selectinload(Technician.service_areas),
                selectinload(Technician.specialties),
            )
            .offset(offset)
            .limit(page_size)
            .order_by(Technician.id)
        )
        return list(result.scalars().all()), total
