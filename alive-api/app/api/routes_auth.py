from fastapi import APIRouter, Depends, HTTPException, Request
import logging

logger = logging.getLogger(__name__)
from pydantic import BaseModel, EmailStr, Field, field_validator
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
from app.core.apple_auth import verify_apple_token, AppleAuthError
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
    user_email: Optional[EmailStr] = None
    nonce: Optional[str] = None

    @field_validator('user_email', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == '':
            return None
        return v

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

    # Look up by Google provider_id first, then by email+google pair
    res = await db.execute(
        select(User).where(
            User.auth_provider == "google",
            User.provider_id == google_user_id
        )
    )
    user = res.scalar_one_or_none()

    if user:
        # Existing user - update email if changed
        if email != user.email:
            user.email = email
            await db.commit()
            await db.refresh(user)
    else:
        # New Google user (same email with different provider is allowed)
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

@router.post("/apple/debug")
async def apple_debug(request: Request):
    """Debug endpoint to see raw request body"""
    body = await request.json()
    logger.info(f"Apple auth request body: {body}")
    return {"received_keys": list(body.keys()), "body": body}

@router.post("/apple")
async def apple_login(payload: AppleAuthReq, db: AsyncSession = Depends(get_db)):
    """
    Apple Sign-In - verifies identity_token with Apple's JWKS keys.

    The identity_token is a JWT signed by Apple containing the user's
    Apple ID (sub claim) and optionally their email.
    """
    # Verify the Apple identity token
    try:
        claims = await verify_apple_token(
            identity_token=payload.identity_token,
            nonce=payload.nonce
        )
    except AppleAuthError as e:
        if e.code == "SERVER_ERROR":
            raise HTTPException(
                status_code=500,
                detail={"error": {"code": e.code, "message": e.message, "details": e.details}}
            )
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}}
        )

    apple_user_id = claims.sub

    # Lookup user by Apple provider_id
    res = await db.execute(
        select(User).where(
            User.auth_provider == "apple",
            User.provider_id == apple_user_id
        )
    )
    user = res.scalar_one_or_none()

    if user:
        # Existing user - optionally update email if changed
        if claims.email and claims.email != user.email:
            user.email = claims.email
            await db.commit()
            await db.refresh(user)
    else:
        # New user - need email
        email = claims.email or payload.user_email
        if not email:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Email required for first Apple sign-in",
                        "details": {
                            "hint": "Pass user_email in request body if Apple doesn't provide it"
                        }
                    }
                }
            )

        # Create new Apple user (same email with different provider is now allowed)
        user = User(
            email=email,
            auth_provider="apple",
            provider_id=apple_user_id,
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
    # Check if email already registered with local auth
    res = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.auth_provider == "local"
        )
    )
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
    # Only find local auth users for password login
    res = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.auth_provider == "local"
        )
    )
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
