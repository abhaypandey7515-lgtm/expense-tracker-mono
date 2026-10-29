from typing import List

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUID7PrimaryKeyMixin


class Expense(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_expense_positive"),)

    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    payer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)  # integer paise, never a float
    description: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), default="General")
    voided: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # soft delete (undo)

    shares: Mapped[List["ExpenseShare"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ExpenseShare(Base, UUID7PrimaryKeyMixin):
    __tablename__ = "expense_shares"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_user"),
        CheckConstraint("share_minor >= 0", name="ck_share_nonneg"),
    )

    expense_id: Mapped[str] = mapped_column(String(36), ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    share_minor: Mapped[int] = mapped_column(Integer)
