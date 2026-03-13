from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, Contact

router = APIRouter(prefix="/contacts", tags=["contacts"])

class ContactCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    death_message: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    death_message: Optional[str] = None

class ContactResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    death_message: Optional[str]

def contact_to_response(contact: Contact) -> dict:
    return {
        "id": str(contact.id),
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "death_message": contact.death_message,
        "created_at": contact.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if contact.created_at else None,
    }

@router.get("")
async def list_contacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Contact).where(Contact.user_id == user.id)
    )
    contacts = res.scalars().all()
    return {"contacts": [contact_to_response(c) for c in contacts]}

@router.post("")
async def create_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contact = Contact(
        user_id=user.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        death_message=payload.death_message,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact_to_response(contact)

@router.get("/{contact_id}")
async def get_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    )
    contact = res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact_to_response(contact)

@router.put("/{contact_id}")
async def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    )
    contact = res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.name is not None:
        contact.name = payload.name
    if payload.email is not None:
        contact.email = payload.email
    if payload.phone is not None:
        contact.phone = payload.phone
    if payload.death_message is not None:
        contact.death_message = payload.death_message

    await db.commit()
    await db.refresh(contact)
    return contact_to_response(contact)

@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
    )
    contact = res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    await db.delete(contact)
    await db.commit()
    return {"success": True, "message": "Contact deleted"}
