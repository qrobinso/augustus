"""Custom Sites API router."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.topic import Topic
from app.models.custom_site import CustomSite
from app.routers.auth import get_current_user
from app.schemas.custom_site import (
    CustomSiteCreate,
    CustomSiteUpdate,
    CustomSiteResponse,
    CustomSiteListResponse,
)
from app.services.scraper import get_scraper_service

router = APIRouter()


def _site_to_response(site: CustomSite) -> CustomSiteResponse:
    """Convert CustomSite model to response with topic info."""
    return CustomSiteResponse(
        id=site.id,
        user_id=site.user_id,
        name=site.name,
        url=site.url,
        topic_id=site.topic_id,
        topic_name=site.topic.name if site.topic else None,
        topic_color=site.topic.color if site.topic else None,
        is_active=site.is_active,
        last_fetched=site.last_fetched,
        last_error=site.last_error,
        created_at=site.created_at,
    )


@router.get("", response_model=CustomSiteListResponse)
async def list_custom_sites(
    topic_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all custom sites for the current user."""
    query = (
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.user_id == user.id)
    )
    
    if topic_id:
        query = query.where(CustomSite.topic_id == topic_id)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Get paginated results
    result = await db.execute(
        query
        .order_by(CustomSite.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sites = result.scalars().all()
    
    return CustomSiteListResponse(
        sites=[_site_to_response(site) for site in sites],
        total=total,
    )


@router.post("", response_model=CustomSiteResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_site(
    request: CustomSiteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom site."""
    # Verify topic exists and belongs to user
    topic_result = await db.execute(
        select(Topic).where(Topic.id == request.topic_id)
    )
    topic = topic_result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    if topic.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this topic",
        )
    
    # Check for duplicate URL for this user
    existing = await db.execute(
        select(CustomSite).where(
            CustomSite.user_id == user.id,
            CustomSite.url == request.url,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A site with this URL already exists",
        )
    
    site = CustomSite(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=request.name,
        url=request.url,
        topic_id=request.topic_id,
        is_active=True,
    )
    
    db.add(site)
    await db.commit()
    
    # Reload with topic relationship
    result = await db.execute(
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.id == site.id)
    )
    site = result.scalar_one()
    
    return _site_to_response(site)


@router.get("/{site_id}", response_model=CustomSiteResponse)
async def get_custom_site(
    site_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific custom site by ID."""
    result = await db.execute(
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.id == site_id)
    )
    site = result.scalar_one_or_none()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom site not found",
        )
    
    if site.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return _site_to_response(site)


@router.put("/{site_id}", response_model=CustomSiteResponse)
async def update_custom_site(
    site_id: str,
    request: CustomSiteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a custom site."""
    result = await db.execute(
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.id == site_id)
    )
    site = result.scalar_one_or_none()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom site not found",
        )
    
    if site.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Update fields
    if request.name is not None:
        site.name = request.name
    if request.url is not None:
        site.url = request.url
    if request.topic_id is not None:
        # Verify topic exists and belongs to user
        topic_result = await db.execute(
            select(Topic).where(Topic.id == request.topic_id)
        )
        topic = topic_result.scalar_one_or_none()
        
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found",
            )
        
        if topic.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this topic",
            )
        
        site.topic_id = request.topic_id
    if request.is_active is not None:
        site.is_active = request.is_active
    
    await db.commit()
    
    # Reload with topic relationship
    result = await db.execute(
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.id == site.id)
    )
    site = result.scalar_one()
    
    return _site_to_response(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_site(
    site_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom site."""
    result = await db.execute(
        select(CustomSite).where(CustomSite.id == site_id)
    )
    site = result.scalar_one_or_none()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom site not found",
        )
    
    if site.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await db.delete(site)
    await db.commit()


@router.post("/{site_id}/test", response_model=dict)
async def test_custom_site(
    site_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test fetching articles from a custom site."""
    result = await db.execute(
        select(CustomSite)
        .options(selectinload(CustomSite.topic))
        .where(CustomSite.id == site_id)
    )
    site = result.scalar_one_or_none()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom site not found",
        )
    
    if site.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    from app.services.news import get_news_service
    
    news_service = get_news_service()
    scraper = get_scraper_service()
    
    try:
        # Check if this is a Reddit URL
        if news_service.is_reddit_url(site.url):
            # Extract subreddit name and fetch using Reddit API
            subreddit = news_service.extract_subreddit_name(site.url)
            if subreddit:
                articles = await news_service.fetch_reddit_subreddit(
                    subreddit=subreddit,
                    max_age_days=3,
                    limit=25,
                )
                # Limit to 5 articles for testing (same as scraper)
                articles = articles[:5]
            else:
                return {
                    "success": False,
                    "error": f"Could not extract subreddit name from URL: {site.url}",
                    "articles_found": 0,
                    "articles": [],
                }
        else:
            # Use topic name as category for scraper
            topic_name = site.topic.name if site.topic else "general"
            articles = await scraper.fetch_site_articles(
                url=site.url,
                site_name=site.name,
                category=topic_name.lower(),
                max_articles=5,
            )
        
        # Update last_fetched and clear error
        site.last_fetched = datetime.utcnow()
        site.last_error = None
        await db.commit()
        
        return {
            "success": True,
            "articles_found": len(articles),
            "articles": [
                {
                    "title": a.title,
                    "url": a.url,
                    "summary": a.summary[:200] if a.summary else None,
                }
                for a in articles
            ],
        }
        
    except Exception as e:
        # Update error status
        site.last_error = str(e)[:500]
        await db.commit()
        
        return {
            "success": False,
            "error": str(e),
            "articles_found": 0,
            "articles": [],
        }

