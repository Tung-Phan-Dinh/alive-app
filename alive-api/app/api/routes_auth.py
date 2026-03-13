from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta, timezone

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.db.session import get_db
from app.db.models import User
from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import settings
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class DevLoginReq(BaseModel):
    email: EmailStr

class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthReq(BaseModel):
    id_token: str

class AppleAuthReq(BaseModel):
    identity_token: str
    user_email: EmailStr

@router.post("/dev")
async def dev_login(payload: DevLoginReq, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user:
        user = User(email=payload.email, auth_provider="local")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
            "checkin_period_hours": user.checkin_period_hours,
            "last_active_at": user.last_active_at.strftime("%Y-%m-%dT%H:%M:%SZ") if user.last_active_at else None,
            "is_dead": bool(user.is_dead),
        }
    }

def get_next_deadline(user: User) -> Optional[str]:
    if user.last_active_at:
        deadline = user.last_active_at.replace(tzinfo=timezone.utc) + timedelta(hours=user.checkin_period_hours)
        return deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None

@router.post("/google")
async def google_login(payload: GoogleAuthReq, db: AsyncSession = Depends(get_db)):
    """Google OAuth login - verifies id_token with Google's public keys"""
    # Try web client ID first, then iOS client ID
    allowed_client_ids = [
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_IOS_CLIENT_ID,
    ]
    allowed_client_ids = [cid for cid in allowed_client_ids if cid]  # Remove empty

    idinfo = None
    last_error = None

    for client_id in allowed_client_ids:
        try:
            idinfo = id_token.verify_oauth2_token(
                payload.id_token,
                google_requests.Request(),
                client_id
            )
            break  # Token verified successfully
        except ValueError as e:
            last_error = e
            continue

    if idinfo is None:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(last_error)}")

    # Token is valid, extract user info
    email = idinfo.get("email")
    google_user_id = idinfo.get("sub")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            auth_provider="google",
            provider_id=google_user_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
            "checkin_period_hours": user.checkin_period_hours,
            "last_active_at": user.last_active_at.strftime("%Y-%m-%dT%H:%M:%SZ") if user.last_active_at else None,
            "is_dead": bool(user.is_dead),
            "next_deadline": get_next_deadline(user),
        }
    }

@router.post("/apple")
async def apple_login(payload: AppleAuthReq, db: AsyncSession = Depends(get_db)):
    """Fake Apple OAuth login for development"""
    res = await db.execute(select(User).where(User.email == payload.user_email))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email=payload.user_email,
            auth_provider="apple",
            provider_id=f"apple_{payload.identity_token[:16]}",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
            "checkin_period_hours": user.checkin_period_hours,
            "last_active_at": user.last_active_at.strftime("%Y-%m-%dT%H:%M:%SZ") if user.last_active_at else None,
            "is_dead": bool(user.is_dead),
            "next_deadline": get_next_deadline(user),
        }
    }

@router.post("/register")
async def register(payload: RegisterReq, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        auth_provider="local",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
            "checkin_period_hours": user.checkin_period_hours,
            "last_active_at": None,
            "is_dead": False,
        }
    }

@router.post("/login")
async def login(payload: LoginReq, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
            "checkin_period_hours": user.checkin_period_hours,
            "last_active_at": user.last_active_at.strftime("%Y-%m-%dT%H:%M:%SZ") if user.last_active_at else None,
            "is_dead": bool(user.is_dead),
        }
    }

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    last = user.last_active_at
    next_deadline = None
    if last:
        deadline = last.replace(tzinfo=timezone.utc) + timedelta(hours=user.checkin_period_hours)
        next_deadline = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id": str(user.id),
        "email": user.email,
        "auth_provider": user.auth_provider,
        "checkin_period_hours": user.checkin_period_hours,
        "last_active_at": last.strftime("%Y-%m-%dT%H:%M:%SZ") if last else None,
        "is_dead": bool(user.is_dead),
        "next_deadline": next_deadline,
    }
