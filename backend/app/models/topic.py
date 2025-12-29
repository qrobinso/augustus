"""Topic model for user-defined news categories."""

import uuid
import re
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.custom_site import CustomSite
    from app.models.article import Article


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


class Topic(Base):
    """User-defined topic/category for organizing news sources."""
    
    __tablename__ = "topics"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
    )
    
    # Topic details
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Display name (e.g., 'Artificial Intelligence')",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="URL-safe key (e.g., 'artificial-intelligence')",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description of the topic",
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        doc="Hex color for UI (e.g., '#3B82F6')",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_newsapi: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="Whether to include NewsAPI results for this topic",
    )
    enable_site_generation: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="Whether to enable AI site generation for this topic",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="topics")
    custom_sites: Mapped[list["CustomSite"]] = relationship(
        "CustomSite",
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, name={self.name}, slug={self.slug})>"


# Default topics to seed for new users
DEFAULT_TOPICS = [
    {"name": "Technology", "slug": "technology", "color": "#3B82F6"},  # Blue
    {"name": "Business", "slug": "business", "color": "#10B981"},  # Green
    {"name": "Science", "slug": "science", "color": "#8B5CF6"},  # Purple
    {"name": "Health", "slug": "health", "color": "#EF4444"},  # Red
    {"name": "Sport", "slug": "sport", "color": "#F97316"},  # Orange
]



