from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUID7PrimaryKeyMixin


class User(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # NOCASE: "Asha" and "asha" are the same account.
    username: Mapped[str] = mapped_column(String(64, collation="NOCASE"), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    pw_hash: Mapped[bytes] = mapped_column(LargeBinary)
    salt: Mapped[bytes] = mapped_column(LargeBinary)
