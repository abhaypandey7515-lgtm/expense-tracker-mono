"""Groups and memberships. Every route needs a logged-in user; per-group routes need membership."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_member
from app.core.security import new_invite_code
from app.core.uuid7 import uuid7_str
from app.db.session import get_db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import GroupCreate, GroupDetail, GroupJoin, GroupOut, MemberOut

router = APIRouter(prefix="/groups", tags=["Groups & Memberships"])


def _group_out(g: Group) -> GroupOut:
    return GroupOut(id=g.id, name=g.name, invite_code=g.invite_code, created_at=g.created_at)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(req: GroupCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a group; the creator becomes its owner. Share the invite code to add others."""
    for _ in range(10):
        code = new_invite_code()
        taken = await db.execute(select(Group.id).where(Group.invite_code == code))
        if taken.first() is None:
            break
    else:  # pragma: no cover
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate invite code")
    group = Group(id=uuid7_str(), name=req.name, invite_code=code)
    db.add(group)
    await db.flush()
    db.add(GroupMember(id=uuid7_str(), group_id=group.id, user_id=user.id, role="owner"))
    await db.commit()
    return _group_out(group)


@router.post("/join", response_model=GroupOut)
async def join_group(req: GroupJoin, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Join with a 6-character invite code (case-insensitive). Joining twice is harmless."""
    res = await db.execute(select(Group).where(Group.invite_code == req.invite_code.strip().upper()))
    group = res.scalars().first()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invalid invite code")
    exists = await db.execute(
        select(GroupMember.id).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
    )
    if exists.first() is None:
        db.add(GroupMember(id=uuid7_str(), group_id=group.id, user_id=user.id))
        await db.commit()
    return _group_out(group)


@router.get("", response_model=List[GroupOut])
async def my_groups(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id)
        .order_by(Group.id)
    )
    return [_group_out(g) for g in res.scalars().all()]


@router.get("/{group_id}", response_model=GroupDetail)
async def group_detail(
    group_id: str,
    _member: GroupMember = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    group = await db.get(Group, group_id)
    res = await db.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.id)
    )
    members = [
        MemberOut(user_id=u.id, username=u.username, display_name=u.display_name, role=m.role)
        for m, u in res.all()
    ]
    return GroupDetail(**_group_out(group).model_dump(), members=members)
