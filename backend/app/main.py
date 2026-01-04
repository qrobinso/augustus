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
            
            # Get user's timezone from FRESH settings (not cached module-level reference)
            # This ensures timezone changes take effect without server restart
            current_settings = get_settings()
            user_timezone = current_settings.timezone
            
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
                        db_url=current_settings.database_url,
                    )
            else:
                # Only log occasionally to reduce noise
                pass
    except Exception as e:
        print(f"[Scheduler] Error checking scheduled briefings: {e}")


async def process_scheduled_briefing_queue():
    """Process the scheduled briefing queue, generating briefings one at a time."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.database import async_session_maker
    from app.services.briefing_queue import briefing_queue
    from app.services.scheduled_briefing import ScheduledBriefingService
    
    # Skip if any briefing is currently generating globally
    if await briefing_queue.is_global_generating():
        return
    
    # Skip if already processing scheduled queue
    if await briefing_queue.is_processing():
        return
    
    # Get next item from scheduled queue
    queued = await briefing_queue.dequeue()
    if not queued:
        return
    
    await briefing_queue.set_processing(True)
    
    try:
        print(f"[BriefingQueue] Processing queued scheduled briefing: schedule {queued.schedule_id}")
        
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


async def process_ondemand_briefing_queue():
    """Process on-demand queued briefings when no other generation is in progress."""
    from app.database import async_session_maker
    from app.services.briefing_queue import briefing_queue
    from app.services.briefing import BriefingService
    from app.config import get_settings
    
    settings = get_settings()
    
    # Skip if any briefing is currently generating globally
    if await briefing_queue.is_global_generating():
        return
    
    async with async_session_maker() as db:
        service = BriefingService(db)
        
        # Check if any briefing is actually generating
        if await service.has_any_active_briefing():
            return
        
        # Get next queued briefing
        queued_briefing = await service.get_next_queued_briefing()
        if not queued_briefing:
            return
        
        # Update status to pending and start generation
        queued_briefing.status = "pending"
        await db.commit()
        await db.refresh(queued_briefing)
        
        print(f"[BriefingQueue] Starting generation for queued briefing {queued_briefing.id}")
        
        # Get generation parameters from extra_data
        extra_data = queued_briefing.extra_data or {}
        topic_ids = extra_data.get("topic_ids", [])
        profile_name = extra_data.get("profile_name")
        max_duration = extra_data.get("max_duration", settings.briefing_duration_minutes)
        
        # Import and run the generation task
        from app.routers.briefings import generate_briefing_task
        import asyncio
        
        # Run the generation task
        asyncio.create_task(
            generate_briefing_task(
                briefing_id=queued_briefing.id,
                topic_ids=topic_ids if topic_ids else None,
                max_duration=max_duration,
                db_url=settings.database_url,
                profile_name=profile_name,
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    try:
        await init_db()
        
        # Run migrations
        try:
            from app.migrations.add_profiles_table import migrate as migrate_profiles
            await migrate_profiles()
            print("[Startup] Profile migrations completed")
        except Exception as e:
            print(f"[Startup] Warning: Migration error (may already be applied): {e}")
        
        # Ensure audio storage directory exists
        audio_path = Path(settings.audio_storage_path)
        audio_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure models directory exists for Piper
        models_path = Path("./models")
        models_path.mkdir(parents=True, exist_ok=True)
        
        # Start scheduler
        try:
            scheduler.add_job(
                check_scheduled_briefings,
                trigger="cron",
                minute="*",  # Run every minute
                id="check_scheduled_briefings",
                replace_existing=True,
            )
            # Process scheduled briefing queue every 10 seconds
            scheduler.add_job(
                process_scheduled_briefing_queue,
                trigger="interval",
                seconds=10,
                id="process_scheduled_briefing_queue",
                replace_existing=True,
            )
            # Process on-demand queued briefings every 5 seconds
            scheduler.add_job(
                process_ondemand_briefing_queue,
                trigger="interval",
                seconds=5,
                id="process_ondemand_briefing_queue",
                replace_existing=True,
            )
            scheduler.start()
            print("[Scheduler] Started scheduled briefing checker (runs every minute)")
            print("[Scheduler] Started scheduled briefing queue processor (runs every 10 seconds)")
            print("[Scheduler] Started on-demand briefing queue processor (runs every 5 seconds)")
        except Exception as e:
            print(f"[Scheduler] Error starting scheduler: {e}")
            # Continue even if scheduler fails to start
    except Exception as e:
        print(f"[Startup] Error during application startup: {e}")
        raise
    
    try:
        yield
    finally:
        # Shutdown
        try:
            if scheduler.running:
                scheduler.shutdown(wait=True)
                print("[Scheduler] Stopped scheduled briefing checker")
        except Exception as e:
            print(f"[Shutdown] Error shutting down scheduler: {e}")
        
        try:
            await close_db()
        except Exception as e:
            print(f"[Shutdown] Error closing database: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Augustus Audio Intelligence Platform - Self-hosted personalized audio briefings",
        lifespan=lifespan,
    )
    
    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files for audio
    if os.path.exists(settings.audio_storage_path):
        application.mount(
            "/audio",
            StaticFiles(directory=settings.audio_storage_path),
            name="audio",
        )
    
    return application


app = create_app()


@app.get("/")
async def root():
    """Root endpoint."""
    settings = get_settings()
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
    briefings, auth, settings as settings_router,
    topics, custom_sites, scheduled_briefings, casts, profiles
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profiles"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["Briefings"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(topics.router, prefix="/api/topics", tags=["Topics"])
app.include_router(custom_sites.router, prefix="/api/custom-sites", tags=["Custom Sites"])
app.include_router(scheduled_briefings.router, prefix="/api/scheduled-briefings", tags=["Scheduled Briefings"])
app.include_router(casts.router, prefix="/api/casts", tags=["Casts"])

