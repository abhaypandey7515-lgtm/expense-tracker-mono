from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUID7PrimaryKeyMixin


class Group(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(100))
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)


class GroupMember(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Membership row. Every group endpoint authorizes against this table."""

    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_user"),)

    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
