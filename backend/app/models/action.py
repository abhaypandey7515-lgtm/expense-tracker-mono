from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUID7PrimaryKeyMixin


class Action(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Persistent undo stack. UUIDv7 ids are time-ordered, so the largest un-undone id is the top."""

    __tablename__ = "actions"
    __table_args__ = (CheckConstraint("kind IN ('expense','settlement')", name="ck_action_kind"),)

    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    ref_id: Mapped[str] = mapped_column(String(36))
    undone: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
