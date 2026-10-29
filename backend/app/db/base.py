"""
SQLAlchemy Declarative Base and Common Column Mixins.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String
from app.core.uuid7 import uuid7_str


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class UUID7PrimaryKeyMixin:
    """Provides time-ordered UUIDv7 as primary key."""
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=uuid7_str,
        index=True,
        doc="RFC 9562 UUIDv7 Primary Key string"
    )


class TimestampMixin:
    """Provides created_at timestamp in UTC."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        doc="Record creation timestamp in UTC"
    )
