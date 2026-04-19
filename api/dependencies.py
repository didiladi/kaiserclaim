from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.domain import User


async def get_current_user(
    user_id: UUID,  # In production replace with JWT extraction
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Minimal auth stub — accepts user_id as a query/header param.
    Replace with proper JWT middleware before going multi-user / SaaS.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
