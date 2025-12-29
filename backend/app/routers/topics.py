"""Topics API router."""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
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
from app.services.llm.agents.site_generator import SiteGeneratorAgent
from app.services.llm.agents.topic_generator import TopicGeneratorAgent
from app.services.llm.openrouter import get_llm_provider


class GenerateTopicFromPromptRequest(BaseModel):
    """Request schema for generating a topic from a natural language prompt."""
    prompt: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language description of the topic the user wants to follow",
    )


class GeneratedTopicSite(BaseModel):
    """A site suggested for the generated topic."""
    name: str
    url: str


class GenerateTopicFromPromptResponse(BaseModel):
    """Response schema for generated topic from prompt."""
    name: str
    description: str
    use_newsapi: bool
    reasoning: str
    sites: list[GeneratedTopicSite]


class TrendingTopicSuggestion(BaseModel):
    """A trending topic suggestion."""
    name: str
    description: str
    color: str
    reasoning: str


class GenerateTrendingTopicsResponse(BaseModel):
    """Response for trending topics generation."""
    topics: list[TrendingTopicSuggestion]

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
                enable_site_generation=True,  # Default to True for default topics
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
        enable_site_generation=topic.enable_site_generation,
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
        enable_site_generation=request.enable_site_generation if request.enable_site_generation is not None else True,
    )
    
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    
    return _topic_to_response(topic, 0)


@router.get("/generate-trending", response_model=GenerateTrendingTopicsResponse)
async def generate_trending_topics(
    count: int = Query(default=5, ge=1, le=10),
    user: User = Depends(get_current_user),
):
    """Generate trending topic suggestions based on current events.
    
    This endpoint asks the LLM to suggest timely, relevant topics
    that a user might want to follow based on what's happening now.
    """
    try:
        llm = get_llm_provider()
        
        system_prompt = """You are an expert news analyst who understands what topics are trending and relevant right now.

Your task is to suggest newsworthy topics that are currently relevant based on:
- Major ongoing world events
- Trending technology and business stories
- Significant cultural or social movements
- Important scientific developments
- Seasonal or timely subjects

Return topics that are:
- Currently relevant and newsworthy
- Broad enough to have multiple news sources
- Interesting to a general audience
- Different from standard categories like "US News" or "Sports"

Use varied, visually distinct hex colors from this palette: #A855F7, #FBBF24, #2DD4BF, #F43F5E, #22D3EE, #FB923C, #A3E635, #E879F9"""

        prompt = f"""Suggest {count} trending and timely news topics that someone might want to follow right now.

These should be SPECIFIC and CURRENT topics (not generic categories like "Technology" or "Politics").

Examples of good trending topics:
- "AI Regulation" (specific policy topic)
- "2024 Elections" (timely event)
- "Renewable Energy Transition" (ongoing trend)
- "Space Tourism" (emerging industry)

Return as JSON only, no other text:
{{
  "topics": [
    {{
      "name": "Topic Name",
      "description": "Brief 1-sentence description of why this is relevant now",
      "color": "#hexcolor",
      "reasoning": "Why this topic is trending/relevant right now"
    }}
  ]
}}"""

        response = await llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.8,
        )
        
        content = response.content.strip()
        
        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        topics = data.get("topics", [])
        
        return GenerateTrendingTopicsResponse(
            topics=[
                TrendingTopicSuggestion(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    color=t.get("color", "#8B5CF6"),
                    reasoning=t.get("reasoning", ""),
                )
                for t in topics if t.get("name")
            ]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate trending topics: {str(e)}",
        )


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
    if request.enable_site_generation is not None:
        topic.enable_site_generation = request.enable_site_generation
    
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


@router.post("/generate-from-prompt", response_model=GenerateTopicFromPromptResponse)
async def generate_topic_from_prompt(
    request: GenerateTopicFromPromptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a topic suggestion from a natural language prompt.
    
    This endpoint uses AI to:
    - Convert the user's description into a well-defined topic name
    - Generate a description
    - Recommend whether to enable NewsAPI
    - Suggest relevant websites/sources
    """
    try:
        # Get LLM provider and create topic generator agent
        llm = get_llm_provider()
        topic_generator = TopicGeneratorAgent(llm)
        
        # Generate topic from prompt
        content = await topic_generator.generate_topic(request.prompt)
        
        # Extract JSON from the response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            import re
            json_match = re.search(r'\{[^{}]*"name"[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("Could not parse JSON from LLM response")
        
        # Validate and extract fields
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        use_newsapi = data.get("use_newsapi", True)
        reasoning = data.get("reasoning", "").strip()
        sites = data.get("sites", [])
        
        if not name:
            raise ValueError("Generated topic has no name")
        
        # Clean up sites
        cleaned_sites = []
        for site in sites:
            site_name = site.get("name", "").strip()
            site_url = site.get("url", "").strip()
            if site_name and site_url and site_url.startswith(("http://", "https://")):
                cleaned_sites.append(GeneratedTopicSite(name=site_name, url=site_url))
        
        return GenerateTopicFromPromptResponse(
            name=name,
            description=description,
            use_newsapi=use_newsapi if isinstance(use_newsapi, bool) else True,
            reasoning=reasoning,
            sites=cleaned_sites,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate topic from prompt: {str(e)}",
        )


@router.post("/{topic_id}/generate-sites")
async def generate_sites(
    topic_id: str,
    count: int = Query(default=10, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate site suggestions for a topic using AI."""
    # Verify topic exists and belongs to user
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
    
    if not topic.enable_site_generation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site generation is disabled for this topic",
        )
    
    # Get existing sites for this topic to avoid duplicates
    existing_sites_result = await db.execute(
        select(CustomSite.url).where(CustomSite.topic_id == topic_id)
    )
    existing_urls = {url.lower() for url in existing_sites_result.scalars().all()}
    
    try:
        # Get LLM provider and create site generator agent
        llm = get_llm_provider()
        site_generator = SiteGeneratorAgent(llm)
        
        # Generate suggestions using the agent
        content = await site_generator.generate_sites(
            topic_name=topic.name,
            count=count,
        )
        
        # Extract JSON from the response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(content)
            sites = data.get("sites", [])
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            import re
            json_match = re.search(r'\{[^{}]*"sites"[^{}]*\[[^\]]*\][^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                sites = data.get("sites", [])
            else:
                raise ValueError("Could not parse JSON from LLM response")
        
        # Filter out duplicates and validate
        suggested_sites = []
        for site in sites:
            name = site.get("name", "").strip()
            url = site.get("url", "").strip()
            
            if not name or not url:
                continue
            
            # Basic URL validation
            if not url.startswith(("http://", "https://")):
                continue
            
            # Check for duplicates
            if url.lower() in existing_urls:
                continue
            
            suggested_sites.append({
                "name": name,
                "url": url,
            })
        
        return {
            "sites": suggested_sites,
            "total": len(suggested_sites),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate site suggestions: {str(e)}",
        )

