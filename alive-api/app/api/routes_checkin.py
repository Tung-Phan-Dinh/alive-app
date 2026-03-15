from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone, timedelta

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, Checkin, TriggerEvent

router = APIRouter(tags=["checkin"])

@router.post("/check-in")
async def check_in(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    was_dead = user.is_dead

    user.last_active_at = now
    user.is_dead = False

    ip = request.client.host if request.client else None
    db.add(Checkin(user_id=user.id, checked_in_at=now, ip_address=ip))

    # Resurrection: resolve any active trigger events
    if was_dead:
        await db.execute(
            update(TriggerEvent)
            .where(
                TriggerEvent.user_id == user.id,
                TriggerEvent.status == "triggered",
            )
            .values(
                status="resolved",
                resolved_at=now,
                updated_at=now,
            )
        )

    await db.commit()

    next_deadline = now + timedelta(hours=user.checkin_period_hours)

    response = {
        "success": True,
        "message": "Check-in recorded. Stay alive!",
        "next_deadline": next_deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds_until_deadline": int((next_deadline - now).total_seconds()),
    }

    if was_dead:
        response["message"] = "Welcome back! You've been resurrected."
        response["resurrected"] = True

    return response

@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    last = user.last_active_at

    if not last:
        return {
            "is_dead": False,
            "last_active_at": None,
            "next_deadline": None,
            "seconds_remaining": None,
            "status": "safe",
        }

    last_utc = last.replace(tzinfo=timezone.utc)
    next_deadline = last_utc + timedelta(hours=user.checkin_period_hours)
    seconds_remaining = max(0, int((next_deadline - now).total_seconds()))

    # Status thresholds based on checkin period
    total_seconds = user.checkin_period_hours * 3600
    halftime_seconds = total_seconds // 2

    if seconds_remaining == 0:
        s = "dead"
    elif seconds_remaining <= 3600:  # Last 1 hour
        s = "critical"
    elif seconds_remaining <= halftime_seconds:  # Halftime to 1 hour
        s = "warning"
    else:  # First half of countdown
        s = "safe"

    return {
        "is_dead": (s == "dead"),
        "last_active_at": last_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_deadline": next_deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds_remaining": seconds_remaining,
        "status": s,
    }
