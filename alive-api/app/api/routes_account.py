from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/account", tags=["account"])

class DeleteAccountReq(BaseModel):
    confirm: str

@router.delete("", status_code=204)
async def delete_account(
    payload: DeleteAccountReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.confirm != "DELETE":
        raise HTTPException(status_code=400, detail="Must confirm with 'DELETE'")

    await db.delete(user)
    await db.commit()

    return Response(status_code=204)
