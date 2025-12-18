"""FastAPI application entry point."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, close_db, get_db
from app.services.scheduled_briefing import ScheduledBriefingService

settings = get_settings()

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def check_scheduled_briefings():
    """Check for scheduled briefings that should run now."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.database import async_session_maker
    from app.services.briefing_queue import briefing_queue
    
    try:
        async with async_session_maker() as db:
            service = ScheduledBriefingService(db)
            
            # Get user's timezone from settings
            user_timezone = settings.timezone
            
            # Get schedules due now
            due_schedules = await service.get_schedules_due_now(user_timezone)
            
            if due_schedules:
                print(f"[Scheduler] Found {len(due_schedules)} scheduled briefings due now")
                
                for schedule in due_schedules:
                    print(f"[Scheduler] Queueing scheduled briefing: {schedule.name} (ID: {schedule.id})")
                    # Add to queue instead of generating immediately
                    await briefing_queue.enqueue(
                        schedule_id=schedule.id,
                        user_id=schedule.user_id,
                        db_url=settings.database_url,
                    )
            else:
                # Only log occasionally to reduce noise
                pass
    except Exception as e:
        print(f"[Scheduler] Error checking scheduled briefings: {e}")


async def process_briefing_queue():
    """Process the briefing queue, generating briefings one at a time."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.database import async_session_maker
    from app.services.briefing_queue import briefing_queue
    from app.services.scheduled_briefing import ScheduledBriefingService
    
    # Skip if already processing
    if await briefing_queue.is_processing():
        return
    
    # Get next item from queue
    queued = await briefing_queue.dequeue()
    if not queued:
        return
    
    await briefing_queue.set_processing(True)
    
    try:
        print(f"[BriefingQueue] Processing queued briefing: schedule {queued.schedule_id}")
        
        async with async_session_maker() as db:
            service = ScheduledBriefingService(db)
            
            # Trigger briefing generation
            result = await service.trigger_scheduled_briefing(
                schedule_id=queued.schedule_id,
                db_url=queued.db_url,
            )
            
            if result:
                print(f"[BriefingQueue] Completed processing schedule {queued.schedule_id}")
            else:
                print(f"[BriefingQueue] Failed to process schedule {queued.schedule_id} (may have been re-queued)")
    except Exception as e:
        print(f"[BriefingQueue] Error processing queued briefing: {e}")
    finally:
        await briefing_queue.set_processing(False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    
    # Run migrations
    from app.migrations.rename_sendgrid_to_resend import migrate as migrate_sendgrid_to_resend
    try:
        await migrate_sendgrid_to_resend()
    except Exception as e:
        print(f"[Migration] Error running sendgrid to resend migration: {e}")
    
    from app.migrations.create_casts_tables import migrate as migrate_casts
    try:
        await migrate_casts()
    except Exception as e:
        print(f"[Migration] Error running casts migration: {e}")
    
    # Ensure audio storage directory exists
    audio_path = Path(settings.audio_storage_path)
    audio_path.mkdir(parents=True, exist_ok=True)
    
    # Ensure models directory exists for Piper
    models_path = Path("./models")
    models_path.mkdir(parents=True, exist_ok=True)
    
    # Start scheduler
    scheduler.add_job(
        check_scheduled_briefings,
        trigger="cron",
        minute="*",  # Run every minute
        id="check_scheduled_briefings",
        replace_existing=True,
    )
    # Process queue every 10 seconds for faster processing
    scheduler.add_job(
        process_briefing_queue,
        trigger="interval",
        seconds=10,
        id="process_briefing_queue",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Started scheduled briefing checker (runs every minute)")
    print("[Scheduler] Started briefing queue processor (runs every 10 seconds)")
    
    yield
    
    # Shutdown
    scheduler.shutdown(wait=True)
    print("[Scheduler] Stopped scheduled briefing checker")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="OpenHuxe Audio Intelligence Platform - Self-hosted personalized audio briefings",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for audio
if os.path.exists(settings.audio_storage_path):
    app.mount(
        "/audio",
        StaticFiles(directory=settings.audio_storage_path),
        name="audio",
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers after app is created to avoid circular imports
from app.routers import (
    briefings, deepcasts, stations, auth, settings as settings_router,
    topics, custom_sites, scheduled_briefings, casts
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["Briefings"])
app.include_router(deepcasts.router, prefix="/api/deepcasts", tags=["DeepCasts"])
app.include_router(stations.router, prefix="/api/stations", tags=["Stations"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(topics.router, prefix="/api/topics", tags=["Topics"])
app.include_router(custom_sites.router, prefix="/api/custom-sites", tags=["Custom Sites"])
app.include_router(scheduled_briefings.router, prefix="/api/scheduled-briefings", tags=["Scheduled Briefings"])
app.include_router(casts.router, prefix="/api/casts", tags=["Casts"])

