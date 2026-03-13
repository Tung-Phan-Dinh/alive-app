from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)

def err(code: str, message: str, status_code: int):
    raise HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": {}}})

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        err("INVALID_TOKEN", "Missing token", 401)

    try:
        user_id = decode_token(creds.credentials)
    except Exception:
        err("INVALID_TOKEN", "JWT token expired or invalid", 401)

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        err("INVALID_TOKEN", "User not found", 401)
    return user
