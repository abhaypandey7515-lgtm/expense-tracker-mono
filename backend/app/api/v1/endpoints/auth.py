"""Registration, login, logout."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_session, get_current_user
from app.core.config import settings
from app.core.security import hash_password, new_session_token, verify_password
from app.db.session import get_db
from app.models.session import AuthSession
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

_BAD_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong username or password")


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, display_name=u.display_name)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # PBKDF2 is deliberately slow, so keep it off the event loop.
    digest, salt = await asyncio.to_thread(hash_password, req.password)
    display = (req.display_name or "").strip() or req.username
    user = User(username=req.username, display_name=display, pw_hash=digest, salt=salt)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already taken") from None
    return _user_out(user)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.username == req.username.strip()))
    user = res.scalars().first()
    if user is None:
        # Hash anyway so response time does not reveal which usernames exist.
        await asyncio.to_thread(hash_password, req.password)
        raise _BAD_LOGIN
    ok = await asyncio.to_thread(verify_password, req.password, user.pw_hash, user.salt)
    if not ok:
        raise _BAD_LOGIN

    now = datetime.now(timezone.utc)
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at <= now))
    sess = AuthSession(
        token=new_session_token(),
        user_id=user.id,
        expires_at=now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
    )
    db.add(sess)
    await db.commit()
    return TokenResponse(token=sess.token, expires_at=sess.expires_at, user=_user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(sess: AuthSession = Depends(get_current_session), db: AsyncSession = Depends(get_db)):
    """Deletes the session row, so the token stops working immediately."""
    await db.delete(sess)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _user_out(user)
