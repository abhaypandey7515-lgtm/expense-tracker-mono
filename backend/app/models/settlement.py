from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUID7PrimaryKeyMixin


class Settlement(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A recorded payment from one member to another."""

    __tablename__ = "settlements"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_settlement_positive"),)

    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    from_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    voided: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
