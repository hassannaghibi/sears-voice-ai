from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.technician import ApplianceType
from app.repositories.slot import SlotRepository
from app.repositories.technician import TechnicianRepository
from app.schemas.common import PaginatedResponse
from app.schemas.slot import SlotResponse
from app.schemas.technician import TechnicianWithAvailability
from app.services.scheduling import find_available_technicians

router = APIRouter(prefix="/technicians", tags=["technicians"])


@router.get("", response_model=PaginatedResponse[TechnicianWithAvailability])
async def list_technicians(
    zip: str | None = Query(None, description="5-digit zip code"),
    specialty: ApplianceType | None = Query(None),
    date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if zip and specialty and date:
        results = await find_available_technicians(zip, specialty, date, db)
        items = [
            TechnicianWithAvailability(
                id=r.technician.id,
                name=r.technician.name,
                email=r.technician.email,
                phone=r.technician.phone,
                available_slots=[SlotResponse.model_validate(s) for s in r.slots],
            )
            for r in results
        ]
        return PaginatedResponse(data=items, total=len(items), page=1, page_size=len(items) or 1)

    # Fallback: return all technicians paginated
    repo = TechnicianRepository(db)
    technicians, total = await repo.list_all(page=page, page_size=page_size)
    items = [
        TechnicianWithAvailability(
            id=t.id,
            name=t.name,
            email=t.email,
            phone=t.phone,
            available_slots=[],
        )
        for t in technicians
    ]
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)


@router.get("/{technician_id}/availability", response_model=list[SlotResponse])
async def get_technician_availability(
    technician_id: int,
    date: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    repo = TechnicianRepository(db)
    technician = await repo.get_by_id(technician_id)
    if technician is None:
        raise NotFoundError("Technician", technician_id)

    slot_repo = SlotRepository(db)
    slots = await slot_repo.get_available_slots(technician_id, date)
    return [SlotResponse.model_validate(s) for s in slots]
