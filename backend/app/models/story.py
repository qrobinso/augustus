"""Profile-owned developing stories and their completed episode appearances."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Story(Base):
    __tablename__ = 'stories'
    __table_args__ = (Index('ix_stories_owner_updated', 'user_id', 'profile_id', 'updated_at'),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    profile_id: Mapped[Optional[str]] = mapped_column(ForeignKey('profiles.id', ondelete='CASCADE'), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    preference: Mapped[str] = mapped_column(String(16), default='normal')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StoryDevelopment(Base):
    __tablename__ = 'story_developments'
    __table_args__ = (UniqueConstraint('briefing_id', 'article_index'), Index('ix_development_story', 'story_id'))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id: Mapped[str] = mapped_column(ForeignKey('stories.id', ondelete='CASCADE'))
    briefing_id: Mapped[str] = mapped_column(ForeignKey('briefings.id', ondelete='CASCADE'))
    article_index: Mapped[int] = mapped_column(Integer)
    chapter_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(String(16))
    claims: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
