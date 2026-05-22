from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from models.domain import FamilyMember, User
from schemas.payload import FamilyMemberCreate, FamilyMemberRead

router = APIRouter(prefix="/family", tags=["family"])


@router.get("/", response_model=list[FamilyMemberRead])
async def list_family_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FamilyMember)
        .where(FamilyMember.user_id == current_user.id)
        .order_by(FamilyMember.created_at)
    )
    return result.scalars().all()


@router.post("/", response_model=FamilyMemberRead, status_code=status.HTTP_201_CREATED)
async def create_family_member(
    payload: FamilyMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = FamilyMember(user_id=current_user.id, **payload.model_dump())
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_family_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await db.get(FamilyMember, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    if member.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.delete(member)
    await db.commit()
