from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_CHECKIN_PERIODS = [6, 12, 24, 48, 72, 168]

class SettingsUpdate(BaseModel):
    checkin_period_hours: int

    @field_validator("checkin_period_hours")
    @classmethod
    def validate_period(cls, v):
        if v not in ALLOWED_CHECKIN_PERIODS:
            raise ValueError(f"checkin_period_hours must be one of {ALLOWED_CHECKIN_PERIODS}")
        return v

@router.get("")
async def get_settings(user: User = Depends(get_current_user)):
    return {
        "checkin_period_hours": user.checkin_period_hours,
    }

@router.put("")
async def update_settings(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.checkin_period_hours = payload.checkin_period_hours
    await db.commit()
    await db.refresh(user)

    return {
        "checkin_period_hours": user.checkin_period_hours,
        "message": "Settings updated successfully",
    }
