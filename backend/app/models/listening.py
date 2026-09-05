"""Persistent, independently verifiable listening coverage for a briefing."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ListeningRecord(Base):
    """Canonical audio-time intervals heard for one briefing."""

    __tablename__ = "listening_records"

    briefing_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("briefings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ranges: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
