"""Topics API router."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.topic import Topic, slugify, DEFAULT_TOPICS
from app.models.custom_site import CustomSite
from app.routers.auth import get_current_user
from app.schemas.topic import (
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    TopicListResponse,
)

router = APIRouter()


async def ensure_default_topics(user_id: str, db: AsyncSession) -> None:
    """Ensure user has default topics if they have none."""
    result = await db.execute(
        select(func.count(Topic.id)).where(Topic.user_id == user_id)
    )
    count = result.scalar()
    
    if count == 0:
        for topic_data in DEFAULT_TOPICS:
            topic = Topic(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=topic_data["name"],
                slug=topic_data["slug"],
                color=topic_data["color"],
                is_active=True,
                use_newsapi=True,  # Default to True for default topics
            )
            db.add(topic)
        await db.commit()


def _topic_to_response(topic: Topic, site_count: int = 0) -> TopicResponse:
    """Convert Topic model to response with site count."""
    return TopicResponse(
        id=topic.id,
        user_id=topic.user_id,
        name=topic.name,
        slug=topic.slug,
        description=topic.description,
        color=topic.color,
        is_active=topic.is_active,
        use_newsapi=topic.use_newsapi,
        created_at=topic.created_at,
        site_count=site_count,
    )


@router.get("", response_model=TopicListResponse)
async def list_topics(
    include_inactive: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all topics for the current user."""
    # Ensure default topics exist
    await ensure_default_topics(user.id, db)
    
    query = select(Topic).where(Topic.user_id == user.id)
    
    if not include_inactive:
        query = query.where(Topic.is_active == True)
    
    result = await db.execute(query.order_by(Topic.created_at.asc()))
    topics = result.scalars().all()
    
    # Get site counts for each topic
    topic_responses = []
    for topic in topics:
        count_result = await db.execute(
            select(func.count(CustomSite.id)).where(CustomSite.topic_id == topic.id)
        )
        site_count = count_result.scalar() or 0
        topic_responses.append(_topic_to_response(topic, site_count))
    
    return TopicListResponse(
        topics=topic_responses,
        total=len(topic_responses),
    )


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    request: TopicCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic."""
    slug = slugify(request.name)
    
    # Check for duplicate slug for this user
    existing = await db.execute(
        select(Topic).where(
            Topic.user_id == user.id,
            Topic.slug == slug,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A topic with this name already exists",
        )
    
    topic = Topic(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=request.name,
        slug=slug,
        description=request.description,
        color=request.color,
        is_active=True,
        use_newsapi=request.use_newsapi if request.use_newsapi is not None else True,
    )
    
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    
    return _topic_to_response(topic, 0)


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific topic by ID."""
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    if topic.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Get site count
    count_result = await db.execute(
        select(func.count(CustomSite.id)).where(CustomSite.topic_id == topic.id)
    )
    site_count = count_result.scalar() or 0
    
    return _topic_to_response(topic, site_count)


@router.put("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    request: TopicUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a topic."""
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    if topic.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Update fields
    if request.name is not None:
        new_slug = slugify(request.name)
        # Check for duplicate slug
        existing = await db.execute(
            select(Topic).where(
                Topic.user_id == user.id,
                Topic.slug == new_slug,
                Topic.id != topic_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A topic with this name already exists",
            )
        topic.name = request.name
        topic.slug = new_slug
    
    if request.description is not None:
        topic.description = request.description
    if request.color is not None:
        topic.color = request.color
    if request.is_active is not None:
        topic.is_active = request.is_active
    if request.use_newsapi is not None:
        topic.use_newsapi = request.use_newsapi
    
    await db.commit()
    await db.refresh(topic)
    
    # Get site count
    count_result = await db.execute(
        select(func.count(CustomSite.id)).where(CustomSite.topic_id == topic.id)
    )
    site_count = count_result.scalar() or 0
    
    return _topic_to_response(topic, site_count)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a topic. Custom sites linked to this topic will also be deleted."""
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    if topic.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await db.delete(topic)
    await db.commit()

