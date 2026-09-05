"""Explicit interest controls for profile-owned story memory."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.story import Story
from app.models.user import User
from app.models.profile import Profile
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.services.story_memory import StoryMemoryService

router = APIRouter()


class StoryPreference(BaseModel):
    preference: Literal['normal', 'follow', 'less']


class StoryResponse(StoryPreference):
    id: str
    title: str
    model_config = {'from_attributes': True}


@router.get('/{story_id}', response_model=StoryResponse)
async def get_story(story_id: str, user: User = Depends(get_current_user),
                    profile: Profile = Depends(get_current_profile), db: AsyncSession = Depends(get_db)):
    story = (await db.execute(select(Story).where(
        Story.id == story_id, Story.user_id == user.id, Story.profile_id == profile.id
    ))).scalar_one_or_none()
    if story is None:
        raise HTTPException(404, 'Story not found')
    return story


@router.patch('/{story_id}/preference', response_model=StoryPreference)
async def set_preference(story_id: str, update: StoryPreference, user: User = Depends(get_current_user),
                         profile: Profile = Depends(get_current_profile), db: AsyncSession = Depends(get_db)):
    preference = await StoryMemoryService(db).set_preference(user.id, profile.id, story_id, update.preference)
    if preference is None:
        raise HTTPException(404, 'Story not found')
    return {'preference': preference}
