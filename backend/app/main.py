"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, close_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    
    # Ensure audio storage directory exists
    audio_path = Path(settings.audio_storage_path)
    audio_path.mkdir(parents=True, exist_ok=True)
    
    # Ensure models directory exists for Piper
    models_path = Path("./models")
    models_path.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
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
from app.routers import briefings, deepcasts, stations, auth, settings as settings_router

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["Briefings"])
app.include_router(deepcasts.router, prefix="/api/deepcasts", tags=["DeepCasts"])
app.include_router(stations.router, prefix="/api/stations", tags=["Stations"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])

