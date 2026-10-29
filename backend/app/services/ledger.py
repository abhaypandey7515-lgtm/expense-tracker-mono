"""Database reads that feed the DSA engines."""

from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.group import GroupMember
from app.models.settlement import Settlement
from app.models.user import User


async def member_ids(db: AsyncSession, group_id: str) -> List[str]:
    res = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id).order_by(GroupMember.id)
    )
    return list(res.scalars().all())


async def display_names(db: AsyncSession, user_ids: List[str]) -> Dict[str, str]:
    if not user_ids:
        return {}
    res = await db.execute(select(User.id, User.display_name).where(User.id.in_(user_ids)))
    return {uid: name for uid, name in res.all()}


async def active_expenses(db: AsyncSession, group_id: str) -> List[Expense]:
    res = await db.execute(
        select(Expense).where(Expense.group_id == group_id, Expense.voided.is_(False)).order_by(Expense.id.desc())
    )
    return list(res.scalars().all())


async def active_settlements(db: AsyncSession, group_id: str) -> List[Settlement]:
    res = await db.execute(
        select(Settlement)
        .where(Settlement.group_id == group_id, Settlement.voided.is_(False))
        .order_by(Settlement.id.desc())
    )
    return list(res.scalars().all())


async def load_ledger(
    db: AsyncSession, group_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Expense]]:
    """Return (expense dicts, settlement dicts, expense rows) for the DSA engines."""
    exps = await active_expenses(db, group_id)
    sets = await active_settlements(db, group_id)
    expense_dicts = [
        {
            "payer_id": e.payer_id,
            "amount_minor": e.amount_minor,
            "shares": [{"user_id": s.user_id, "share_minor": s.share_minor} for s in e.shares],
        }
        for e in exps
    ]
    settlement_dicts = [
        {"from_user_id": s.from_user_id, "to_user_id": s.to_user_id, "amount_minor": s.amount_minor}
        for s in sets
    ]
    return expense_dicts, settlement_dicts, exps
