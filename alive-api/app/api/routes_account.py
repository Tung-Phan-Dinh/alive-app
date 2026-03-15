import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.core.apple_auth import revoke_apple_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])

class DeleteAccountReq(BaseModel):
    confirm: str

@router.delete("", status_code=204)
async def delete_account(
    payload: DeleteAccountReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user account and all associated data.

    For Apple Sign-In users, this also attempts to revoke the Apple token
    as required by App Store guidelines.
    """
    if payload.confirm != "DELETE":
        raise HTTPException(status_code=400, detail="Must confirm with 'DELETE'")

    # For Apple users, attempt token revocation (App Store requirement)
    if user.auth_provider == "apple":
        # Note: We don't currently store refresh_token, so this will log a warning
        # but still proceed with deletion. To fully comply with Apple's requirements,
        # store the refresh_token during sign-in and pass it here.
        await revoke_apple_token(refresh_token=None)
        logger.info(f"Apple account deletion initiated for user {user.id}")

    await db.delete(user)
    await db.commit()

    return Response(status_code=204)
