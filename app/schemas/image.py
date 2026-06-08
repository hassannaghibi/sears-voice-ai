from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UploadLinkRequest(BaseModel):
    call_sid: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    appliance_type: str


class UploadLinkResponse(BaseModel):
    upload_url: str
    token: str
    expires_at: datetime


class VisionAnalysisResponse(BaseModel):
    appliance_type: str
    visible_issues: list[str] = Field(default_factory=list)
    suggested_diagnosis: str = ""
    confidence: str = "medium"
    call_sid: str | None = None
