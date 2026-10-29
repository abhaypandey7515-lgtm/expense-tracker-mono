"""Authentication and authorization dependencies shared by every protected route."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.session import AuthSession
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="Session token returned by POST /auth/login")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not logged in or session expired",
    headers={"WWW-Authenticate": "Bearer"},
)


def _aware(dt: datetime) -> datetime:
    # SQLite hands datetimes back naive; they were stored as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def get_current_session(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthSession:
    """Resolve the bearer token to a live server-side session, or answer 401."""
    if creds is None or not creds.credentials:
        raise _UNAUTHENTICATED
    sess = await db.get(AuthSession, creds.credentials)
    if sess is None:
        raise _UNAUTHENTICATED
    if _aware(sess.expires_at) <= datetime.now(timezone.utc):
        await db.delete(sess)
        await db.commit()
        raise _UNAUTHENTICATED
    return sess


async def get_current_user(
    sess: AuthSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, sess.user_id)
    if user is None:
        raise _UNAUTHENTICATED
    return user


async def require_member(
    group_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupMember:
    """Authorization: the caller must belong to the group named in the URL (403 otherwise).

    A group that does not exist gets the same answer as one the caller is not in, so ids
    cannot be probed.
    """
    res = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user.id)
    )
    member = res.scalars().first()
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")
    return member
