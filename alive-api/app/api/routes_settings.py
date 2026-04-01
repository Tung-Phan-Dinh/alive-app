from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_CHECKIN_PERIODS = [6, 12, 24, 48, 72, 168]

class SettingsUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    checkin_period_hours: Optional[int] = None

    @field_validator("checkin_period_hours")
    @classmethod
    def validate_period(cls, v):
        if v is not None and v not in ALLOWED_CHECKIN_PERIODS:
            raise ValueError(f"checkin_period_hours must be one of {ALLOWED_CHECKIN_PERIODS}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v

@router.get("")
async def get_settings(user: User = Depends(get_current_user)):
    return {
        "name": user.name,
        "checkin_period_hours": user.checkin_period_hours,
    }

@router.put("")
async def update_settings(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.name is not None:
        user.name = payload.name if payload.name else None
    if payload.checkin_period_hours is not None:
        user.checkin_period_hours = payload.checkin_period_hours

    await db.commit()
    await db.refresh(user)

    return {
        "name": user.name,
        "checkin_period_hours": user.checkin_period_hours,
        "message": "Settings updated successfully",
    }
