"""Expenses, settlements, balances, debt simplification and undo.

Every route depends on `require_member`, so only members of the group in the URL get through.
"""

from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_member
from app.core.money import split_equally
from app.core.uuid7 import uuid7_str
from app.db.session import get_db
from app.utils import ActionKind, ActivityStack, DebtSimplificationEngine, StackFrame
from app.models.action import Action
from app.models.expense import Expense, ExpenseShare
from app.models.group import GroupMember
from app.models.settlement import Settlement
from app.schemas.expense import (
    BalancesOut, CategoryTotal, ExpenseCreate, ExpenseOut, PlanOut, SettlementCreate, SettlementOut,
    ShareOut, StackFrameOut, TransferOut, UndoOut,
)
from app.services import ledger

router = APIRouter(prefix="/groups/{group_id}", tags=["Expenses & Debt Simplification"])


def _bad(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail)


def _expense_out(e: Expense, names: Dict[str, str]) -> ExpenseOut:
    return ExpenseOut(
        id=e.id, group_id=e.group_id, payer_id=e.payer_id, payer_name=names.get(e.payer_id, "?"),
        amount_minor=e.amount_minor, description=e.description, category=e.category,
        created_at=e.created_at,
        shares=[ShareOut(user_id=s.user_id, share_minor=s.share_minor) for s in e.shares],
    )


def _settlement_out(s: Settlement, names: Dict[str, str]) -> SettlementOut:
    return SettlementOut(
        id=s.id, group_id=s.group_id, from_user_id=s.from_user_id, from_name=names.get(s.from_user_id, "?"),
        to_user_id=s.to_user_id, to_name=names.get(s.to_user_id, "?"),
        amount_minor=s.amount_minor, created_at=s.created_at,
    )


# ---------------------------------------------------------------- expenses
@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    group_id: str,
    req: ExpenseCreate,
    member: GroupMember = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    ids = await ledger.member_ids(db, group_id)
    id_set = set(ids)
    amount = req.amount_minor
    payer = req.payer_id or member.user_id
    if payer not in id_set:
        raise _bad("Payer is not in this group")

    if req.shares is not None:
        shares = req.shares_minor
        if not shares:
            raise _bad("Pick at least one participant")
        if sum(shares.values()) != amount:
            raise _bad("Custom shares must add up to the total amount")
    else:
        participants = ids if req.participants is None else list(dict.fromkeys(req.participants))
        if not participants:
            raise _bad("Pick at least one participant")
        shares = split_equally(amount, participants)
    if not set(shares) <= id_set:
        raise _bad("Participant is not in this group")

    expense = Expense(
        id=uuid7_str(), group_id=group_id, payer_id=payer, amount_minor=amount,
        description=req.description, category=req.category or "General",
        shares=[ExpenseShare(id=uuid7_str(), user_id=u, share_minor=s) for u, s in shares.items()],
    )
    db.add(expense)
    await db.flush()
    db.add(Action(id=uuid7_str(), group_id=group_id, kind=ActionKind.EXPENSE.value, ref_id=expense.id))
    await db.commit()
    names = await ledger.display_names(db, [payer])
    return _expense_out(expense, names)


@router.get("/expenses", response_model=List[ExpenseOut])
async def list_expenses(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    exps = await ledger.active_expenses(db, group_id)
    names = await ledger.display_names(db, list({e.payer_id for e in exps}))
    return [_expense_out(e, names) for e in exps]


# ------------------------------------------------------------- settlements
@router.post("/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
async def record_settlement(
    group_id: str,
    req: SettlementCreate,
    _m: GroupMember = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    """Record that one member paid another (typically a transfer suggested by /plan)."""
    id_set = set(await ledger.member_ids(db, group_id))
    if req.from_user_id not in id_set or req.to_user_id not in id_set:
        raise _bad("Both people must be in this group")
    if req.from_user_id == req.to_user_id:
        raise _bad("Can't pay yourself")
    st = Settlement(
        id=uuid7_str(), group_id=group_id, from_user_id=req.from_user_id,
        to_user_id=req.to_user_id, amount_minor=req.amount_minor,
    )
    db.add(st)
    await db.flush()
    db.add(Action(id=uuid7_str(), group_id=group_id, kind=ActionKind.SETTLEMENT.value, ref_id=st.id))
    await db.commit()
    names = await ledger.display_names(db, [st.from_user_id, st.to_user_id])
    return _settlement_out(st, names)


@router.get("/settlements", response_model=List[SettlementOut])
async def list_settlements(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    sets = await ledger.active_settlements(db, group_id)
    names = await ledger.display_names(db, list({u for s in sets for u in (s.from_user_id, s.to_user_id)}))
    return [_settlement_out(s, names) for s in sets]


# ----------------------------------------------------- balances and the plan
@router.get("/balances", response_model=BalancesOut)
async def balances(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    """Net balance per member (hash map). Positive = is owed money, negative = owes money."""
    ids = await ledger.member_ids(db, group_id)
    exp_d, set_d, exps = await ledger.load_ledger(db, group_id)
    bal = DebtSimplificationEngine.compute_net_balances(exp_d, set_d, ids)
    names = await ledger.display_names(db, list(bal))
    return BalancesOut(
        group_id=group_id, balances=bal, names=names,
        is_balanced=sum(bal.values()) == 0,
        total_spend_minor=sum(e.amount_minor for e in exps),
    )


@router.get("/plan", response_model=PlanOut)
async def settlement_plan(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    """Fewest payments that settle the group (directed graph + heaps, at most N-1 transfers)."""
    ids = await ledger.member_ids(db, group_id)
    exp_d, set_d, _ = await ledger.load_ledger(db, group_id)
    res = DebtSimplificationEngine.simplify_debts(exp_d, set_d, ids)
    names = await ledger.display_names(db, ids)
    return PlanOut(
        group_id=group_id,
        transfers=[
            TransferOut(
                from_user_id=t.from_user, from_name=names.get(t.from_user, "?"),
                to_user_id=t.to_user, to_name=names.get(t.to_user, "?"), amount_minor=t.amount_minor,
            )
            for t in res.transfers
        ],
        original_transactions_count=res.original_transactions_count,
        simplified_transactions_count=res.simplified_transactions_count,
        transactions_eliminated=res.transactions_eliminated,
        efficiency_gain_percent=res.efficiency_gain_percent,
    )


@router.get("/categories", response_model=List[CategoryTotal])
async def category_totals(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    totals: Dict[str, int] = defaultdict(int)
    for e in await ledger.active_expenses(db, group_id):
        totals[e.category] += e.amount_minor
    return [CategoryTotal(category=c, total_minor=t) for c, t in sorted(totals.items(), key=lambda kv: -kv[1])]


# --------------------------------------------------------------------- undo
async def _load_stack(db: AsyncSession, group_id: str) -> ActivityStack:
    """Rebuild the group's LIFO stack from un-undone actions, oldest first."""
    res = await db.execute(
        select(Action).where(Action.group_id == group_id, Action.undone.is_(False)).order_by(Action.id)
    )
    stack = ActivityStack()
    for a in res.scalars().all():
        stack.push(StackFrame(id=a.id, group_id=a.group_id, kind=ActionKind(a.kind), ref_id=a.ref_id))
    return stack


@router.get("/activity", response_model=List[StackFrameOut])
async def activity_stack(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    """The undo stack, most recent first."""
    stack = await _load_stack(db, group_id)
    return [StackFrameOut(id=f.id, kind=f.kind.value, ref_id=f.ref_id) for f in stack.to_list()]


@router.post("/undo", response_model=UndoOut)
async def undo(group_id: str, _m: GroupMember = Depends(require_member), db: AsyncSession = Depends(get_db)):
    """Pop the newest expense or payment and void it. Balances are recomputed from what remains."""
    stack = await _load_stack(db, group_id)
    frame = stack.pop()
    if frame is None:
        return UndoOut(success=False, message="Nothing to undo", remaining_stack_size=0)

    if frame.kind is ActionKind.EXPENSE:
        row = await db.get(Expense, frame.ref_id)
        message = f"Undid expense: {row.description}"
    else:
        row = await db.get(Settlement, frame.ref_id)
        message = "Undid settlement payment"
    row.voided = True
    action = await db.get(Action, frame.id)
    action.undone = True
    await db.commit()
    return UndoOut(success=True, undone_kind=frame.kind.value, message=message, remaining_stack_size=stack.size())
