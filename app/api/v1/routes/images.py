from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories.call_session import CallSessionRepository
from app.schemas.image import UploadLinkRequest, UploadLinkResponse, VisionAnalysisResponse
from app.services.upload import create_upload_link, is_token_expired, token_expires_at
from app.services.vision import analyze_appliance_image

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/upload-link", response_model=UploadLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_image_upload_link(
    payload: UploadLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a signed upload token and email the link to the caller."""
    repo = CallSessionRepository(db)
    session = await repo.get_by_call_sid(payload.call_sid)
    if session is None:
        raise NotFoundError("CallSession", payload.call_sid)

    token, upload_url = await create_upload_link(
        db, payload.call_sid, payload.email, payload.appliance_type
    )
    return UploadLinkResponse(
        upload_url=upload_url,
        token=token,
        expires_at=token_expires_at(),
    )


@router.post("/{token}/analyze", response_model=VisionAnalysisResponse)
async def analyze_uploaded_image(
    token: str,
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Receive an uploaded image and run GPT-4o Vision analysis."""
    repo = CallSessionRepository(db)
    session = await repo.get_by_upload_token(token)
    if session is None:
        raise HTTPException(status_code=404, detail="Invalid or expired upload link")

    expires = session.context.get("upload_token_expires")
    if is_token_expired(expires):
        raise HTTPException(status_code=410, detail="Upload link has expired")

    content_type = photo.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await photo.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10 MB")

    analysis = await analyze_appliance_image(image_bytes, content_type)
    await repo.update_context(
        session.call_sid,
        {
            "vision_analysis": analysis,
            "vision_analyzed_at": datetime.now(UTC).isoformat(),
        },
    )

    return VisionAnalysisResponse(
        appliance_type=analysis.get("appliance_type", "other"),
        visible_issues=analysis.get("visible_issues", []),
        suggested_diagnosis=analysis.get("suggested_diagnosis", ""),
        confidence=analysis.get("confidence", "medium"),
        call_sid=session.call_sid,
    )
