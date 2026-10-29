from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.money import parse_amount


def _to_minor(v) -> int:
    # Raising ValueError inside a validator becomes a clean HTTP 422.
    return parse_amount(v)


class ExpenseCreate(BaseModel):
    """Amounts are decimal money like "450.50". Equal split between `participants`
    (default: everyone), or exact `shares` that must add up to the total."""

    amount: Decimal
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(default="General", max_length=50)
    payer_id: Optional[str] = None
    participants: Optional[List[str]] = None
    shares: Optional[Dict[str, Decimal]] = None

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        _to_minor(v)
        return v

    @field_validator("description", "category", mode="before")
    @classmethod
    def _strip(cls, v):
        # Strip first, so min_length applies to the trimmed text ("   " is rejected).
        return v.strip() if isinstance(v, str) else v

    @field_validator("shares")
    @classmethod
    def _shares(cls, v):
        if v is not None:
            for x in v.values():
                _to_minor(x)
        return v

    @property
    def amount_minor(self) -> int:
        return _to_minor(self.amount)

    @property
    def shares_minor(self) -> Optional[Dict[str, int]]:
        return None if self.shares is None else {u: _to_minor(a) for u, a in self.shares.items()}


class ShareOut(BaseModel):
    user_id: str
    share_minor: int


class ExpenseOut(BaseModel):
    id: str
    group_id: str
    payer_id: str
    payer_name: str
    amount_minor: int
    description: str
    category: str
    created_at: datetime
    shares: List[ShareOut]


class SettlementCreate(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        _to_minor(v)
        return v

    @property
    def amount_minor(self) -> int:
        return _to_minor(self.amount)


class SettlementOut(BaseModel):
    id: str
    group_id: str
    from_user_id: str
    from_name: str
    to_user_id: str
    to_name: str
    amount_minor: int
    created_at: datetime


class BalancesOut(BaseModel):
    group_id: str
    balances: Dict[str, int]
    names: Dict[str, str]
    is_balanced: bool
    total_spend_minor: int


class TransferOut(BaseModel):
    from_user_id: str
    from_name: str
    to_user_id: str
    to_name: str
    amount_minor: int


class PlanOut(BaseModel):
    group_id: str
    transfers: List[TransferOut]
    original_transactions_count: int
    simplified_transactions_count: int
    transactions_eliminated: int
    efficiency_gain_percent: float


class CategoryTotal(BaseModel):
    category: str
    total_minor: int


class StackFrameOut(BaseModel):
    id: str
    kind: str
    ref_id: str
    created_at: Optional[datetime] = None


class UndoOut(BaseModel):
    success: bool
    undone_kind: Optional[str] = None
    message: str
    remaining_stack_size: int
