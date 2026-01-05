# Docker Setup for Augustus

This directory contains all Docker-related configuration and documentation for running Augustus.

## Files

- `docker-compose.yml` - Production Docker Compose configuration
- `docker-compose.dev.yml` - Development Docker Compose configuration with hot reload

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- OpenRouter API key ([get one here](https://openrouter.ai/keys))
- (Optional) TTS provider API keys
- (Optional) NewsAPI key
- (Optional) Resend API key for email notifications

### Production Setup

1. **Configure environment**
   ```bash
   # From the project root
   cp .env.example .env
   # Edit .env with your API keys
   # IMPORTANT: Change API_KEY from the default value!
   ```

2. **Start with Docker Compose**
   ```bash
   # From the project root
   docker compose -f docker/docker-compose.yml up -d
   ```

3. **Access the app**
   - Frontend: http://localhost:3000 (or http://YOUR_SERVER_IP:3000)
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Development Setup

For development with hot reload:

```bash
# From the project root
docker compose -f docker/docker-compose.dev.yml up
```

This will start only the backend with hot reload enabled. The frontend should be run locally with `npm run dev` for the best development experience.

## Production Deployment

### Docker Compose Configuration

The `docker-compose.yml` file is configured for production deployment. Here's what you need to know:

1. **Environment Variables**: Copy `.env.example` to `.env` in the project root and configure all required values:
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys and settings
   ```

2. **Required Configuration**:
   - **API_KEY**: Change from default `change-me-in-production` to a secure random string
   - **OPENROUTER_API_KEY**: Your OpenRouter API key (required)

3. **Optional Configuration** (can be set in `.env` or via Settings UI):
   - TTS provider API keys (ElevenLabs, Gemini)
   - NewsAPI key for additional news sources
   - Resend API key for email notifications
   - Timezone, duration, and complexity settings

4. **Data Persistence**: The following directories are mounted as volumes:
   - `../data` - Database and application data
   - `../audio` - Generated audio files
   - `../models` - TTS voice models (for Piper)

5. **Ports**: 
   - Frontend: `3000` (mapped to nginx port 80) - Access at `http://YOUR_SERVER_IP:3000`
   - Backend API: `8000`
   - Consider using a reverse proxy (nginx, Traefik, etc.) for production

6. **Health Checks**: Both services include health checks for monitoring

7. **Start Services**:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

### Production Considerations

- **Reverse Proxy**: For production, set up nginx or Traefik in front of the containers
- **SSL/TLS**: Use Let's Encrypt or similar for HTTPS
- **Database**: For production, consider using PostgreSQL instead of SQLite
- **Backups**: Regularly backup the `../data` and `../audio` directories
- **Resource Limits**: Add resource limits to docker-compose.yml if needed
- **Security**: Ensure `.env` file is not committed to version control

## Database Migrations

When upgrading Augustus, you may need to run database migrations for new features:

```bash
# Run migrations in Docker container
docker exec augustus-backend python -m app.migrations.add_profiles_table
```

Migrations are idempotent and safe to run multiple times.

## Dockerfiles

The Dockerfiles for each service are located in their respective directories:
- `../backend/Dockerfile` - Backend service (Python/FastAPI)
- `../frontend/Dockerfile` - Frontend service (React/Vite with nginx)

### Backend Dockerfile

The backend Dockerfile:
- Uses Python 3.11-slim base image
- Installs system dependencies (ffmpeg, curl)
- Sets up the Python environment
- Includes health checks
- Exposes port 8000

### Frontend Dockerfile

The frontend Dockerfile:
- Uses multi-stage build (Node.js for building, nginx for serving)
- Builds the React application
- Serves static files with nginx
- Includes custom nginx configuration for API proxying
- Exposes port 80

## Troubleshooting

### Container won't start

- Check logs: `docker compose -f docker/docker-compose.yml logs`
- Verify environment variables are set correctly
- Ensure ports 3000 and 8000 are not in use

### Health checks failing

- Check if services are running: `docker ps`
- Inspect container logs: `docker logs augustus-backend` or `docker logs augustus-frontend`
- Verify API key is set correctly

### Volume mount issues

- Ensure directories exist: `../data`, `../audio`, `../models`
- Check file permissions on mounted volumes
- Verify paths are correct relative to the docker-compose.yml location

### Development hot reload not working

- Ensure you're using `docker-compose.dev.yml`
- Check that volumes are mounted correctly
- Verify the backend code is being watched for changes

## Stopping Services

```bash
# Stop services
docker compose -f docker/docker-compose.yml down

# Stop and remove volumes (WARNING: This deletes data!)
docker compose -f docker/docker-compose.yml down -v
```

## Updating

To update Augustus:

1. Pull the latest code
2. Rebuild containers:
   ```bash
   docker compose -f docker/docker-compose.yml build
   docker compose -f docker/docker-compose.yml up -d
   ```
3. Run any necessary migrations (see Database Migrations above)

