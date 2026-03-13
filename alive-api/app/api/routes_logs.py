from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, Checkin

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("")
async def get_logs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    # Get total count
    count_res = await db.execute(
        select(func.count()).select_from(Checkin).where(Checkin.user_id == user.id)
    )
    total_count = count_res.scalar()

    # Get paginated logs
    res = await db.execute(
        select(Checkin)
        .where(Checkin.user_id == user.id)
        .order_by(Checkin.checked_in_at.desc())
        .limit(limit)
        .offset(offset)
    )
    checkins = res.scalars().all()

    logs = [
        {
            "id": str(c.id),
            "timestamp": c.checked_in_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ip_address": c.ip_address,
        }
        for c in checkins
    ]

    return {
        "logs": logs,
        "total_count": total_count,
        "has_more": offset + len(logs) < total_count,
    }
