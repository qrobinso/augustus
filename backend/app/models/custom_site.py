"""CustomSite model for user-defined news sources."""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.topic import Topic


class CustomSite(Base):
    """User-defined website/blog to scrape for news articles."""
    
    __tablename__ = "custom_sites"
    
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
    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id"),
        nullable=False,
        doc="Reference to the topic this site belongs to",
    )
    
    # Site configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="custom_sites")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="custom_sites")
    
    def __repr__(self) -> str:
        return f"<CustomSite(id={self.id}, name={self.name}, url={self.url})>"

