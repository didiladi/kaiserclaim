import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.domain import User

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API token",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_api_token(authorization: str | None) -> None:
    """Constant-time check of `Authorization: Bearer <token>` against API_TOKEN.

    Fails closed: if API_TOKEN is unset, or still a CHANGE_ME placeholder from
    the example files, nothing is accepted.
    """
    expected = get_settings().api_token
    scheme, _, supplied = (authorization or "").partition(" ")
    if (
        not expected
        or expected.lower().startswith("change")
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(
            supplied.encode(), expected.encode()
        )
    ):
        raise _UNAUTHORIZED


async def get_current_user(
    user_id: UUID,  # still a plain param: single-user app, the token is the credential
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require the static bearer token, then load the user.

    The token authenticates the caller; user_id only selects the tenant row.
    Replace with per-user JWTs before going multi-user / SaaS.
    """
    verify_api_token(authorization)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
