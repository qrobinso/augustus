"""Article model for storing fetched news articles."""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.topic import Topic


class Article(Base):
    """Stored article from news sources."""
    
    __tablename__ = "articles"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Article content
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Article title",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Article summary/description",
    )
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        unique=True,
        doc="Article URL (unique identifier for deduplication)",
    )
    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Source name (e.g., 'BBC News', 'r/technology')",
    )
    author: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Article author if available",
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Full article content if available",
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        doc="Article image URL if available",
    )
    
    # Topic association
    topic_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("topics.id"),
        nullable=True,
        doc="Topic this article was fetched for",
    )
    
    # Metadata
    published: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        doc="Publication date if available",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        doc="When this article was fetched and stored",
    )
    
    # Relationships
    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic",
        back_populates="articles",
    )
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title[:50]}..., url={self.url[:50]}...)>"













