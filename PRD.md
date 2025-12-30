# Product Requirements Document: Augustus

## 1. Executive Summary

**Augustus** is a self-hosted audio intelligence platform that transforms personalized content—news feeds, topics, and queries—into natural, conversational AI-generated podcasts. The platform aggregates content from multiple sources (RSS feeds, custom websites, NewsAPI), uses AI to curate and summarize articles, and generates high-quality audio briefings with multi-voice conversations between customizable AI hosts.

### Key Value Propositions
- **Self-hosted**: Complete data ownership and privacy
- **Personalized**: Custom topics, sources, and AI host personalities
- **Automated**: Scheduled briefings with timezone-aware delivery
- **Flexible**: Multiple LLM and TTS provider support
- **Conversational**: Natural multi-host dialogues with different personalities

## 2. Product Vision

Augustus enables users to consume personalized news and content in an audio format that feels natural and engaging, like listening to a podcast with knowledgeable hosts discussing the topics they care about. The platform gives users complete control over their content sources, delivery schedule, and the personality of their AI hosts.

## 3. Target Users

### Primary Users
- **News Enthusiasts**: Users who want to stay informed but prefer audio consumption
- **Busy Professionals**: People who want to consume news during commutes or workouts
- **Content Curators**: Users who want to aggregate content from specific sources
- **Privacy-Conscious Users**: Individuals who want self-hosted solutions with data ownership

### User Personas
1. **The Commuter**: Wants daily briefings during morning commute, prefers short format (3-5 minutes)
2. **The Deep Diver**: Wants comprehensive briefings (20-25 minutes) on specific topics
3. **The Multi-Topic Enthusiast**: Follows multiple topics and wants organized, scheduled delivery
4. **The Privacy Advocate**: Values self-hosting and data control

## 4. Core Features

### 4.1 Daily Briefings

**Description**: AI-generated audio briefings from aggregated content sources.

**Key Capabilities**:
- Aggregate content from multiple topics and sources
- Configurable duration (Short: 3min, Medium: 7min, Long: 25min)
- Automatic content curation and summarization
- Chapter-based navigation with transcripts
- Playback position tracking and resume functionality
- Listened status tracking and filtering
- Favorite briefings for quick access

**User Stories**:
- As a user, I want to generate a briefing on specific topics so I can get a personalized audio summary
- As a user, I want to resume playback from where I left off so I don't have to re-listen
- As a user, I want to mark briefings as listened so I can track what I've consumed
- As a user, I want to favorite important briefings so I can easily find them later

**Technical Details**:
- Status tracking: `pending`, `generating`, `completed`, `failed`, `cancelled`
- Background task processing with queue system
- Timeout handling for long-running generations
- Chapter extraction from transcript with timestamps
- Audio file storage in configurable directory

### 4.2 Scheduled Briefings

**Description**: Automatically generate briefings on a recurring schedule.

**Key Capabilities**:
- Daily, weekly, or custom schedule patterns (days of week selection)
- Timezone-aware scheduling
- Multiple notification methods (email, webhook)
- Queue-based processing for reliable execution
- Active/inactive toggle for schedules
- Per-schedule topic and cast selection
- Custom duration per schedule

**User Stories**:
- As a user, I want to schedule daily briefings at 7 AM so I can listen during my commute
- As a user, I want to receive email notifications when briefings are ready
- As a user, I want to pause schedules without deleting them
- As a user, I want different schedules for different topics

**Technical Details**:
- Cron-based scheduler (runs every minute to check due schedules)
- Queue system prevents concurrent generation conflicts
- Timezone conversion for accurate scheduling
- Last generation timestamp tracking
- Support for multiple recipients per schedule

### 4.3 Topics Management

**Description**: Organize content by topics with color coding and source management.

**Key Capabilities**:
- Create custom topics for different interests
- Color coding for visual organization
- Enable/disable topics for briefings
- AI-powered site suggestion generation
- NewsAPI integration toggle per topic
- Custom site association

**User Stories**:
- As a user, I want to create topics for different interests so I can organize my content
- As a user, I want AI to suggest relevant sites for my topics
- As a user, I want to temporarily disable topics without deleting them
- As a user, I want to see topics with color coding for quick identification

**Technical Details**:
- Default topics seeded for new users (Technology, Business, Science, Health, Sport)
- Slug generation for URL-safe identifiers
- Topic-to-article and topic-to-custom-site relationships
- Enable/disable flags for content inclusion

### 4.4 Custom Sites

**Description**: Add custom RSS feeds and websites for content aggregation.

**Key Capabilities**:
- Add any RSS feed or website URL
- Automatic article scraping and parsing
- Test site connectivity before adding
- Organize sites by topic
- Error tracking and status monitoring
- Active/inactive toggle

**User Stories**:
- As a user, I want to add my favorite blog's RSS feed
- As a user, I want to test if a site can be scraped before adding it
- As a user, I want to see which sites are failing so I can fix them
- As a user, I want to temporarily disable sites without removing them

**Technical Details**:
- RSS feed parsing
- Web scraping with article extraction
- Last fetch timestamp and error message tracking
- Site-to-topic relationship
- Automatic article creation from fetched content

### 4.5 Casts (AI Hosts)

**Description**: Customizable AI host configurations with multiple personalities and voices.

**Key Capabilities**:
- Create custom host personalities and voices
- Multi-voice conversations between hosts
- Set default cast for all content
- Restore default cast configuration
- Per-host personality selection (15+ personality types)
- Voice selection per host member

**User Stories**:
- As a user, I want to create a cast with two hosts having different personalities
- As a user, I want to set a default cast so all briefings use it automatically
- As a user, I want different voices for each host so I can distinguish them
- As a user, I want to restore the default cast if I make a mistake

**Technical Details**:
- Cast members with order (0, 1, 2, etc.)
- Personality types: Casual, Analytical, Professional, Friendly, Optimist, Realist, Skeptic, Storyteller, Scholar, Businessman, Informative, Upbeat, Provocateur, and more
- Voice ID mapping to TTS provider
- Default cast flag per user
- Cast-to-briefing relationship

### 4.6 Audio Player

**Description**: Advanced audio player with chapter navigation and playback controls.

**Key Capabilities**:
- Chapter-based progress visualization with color-coded segments
- Interactive chapter markers with hover tooltips
- Playback speed control (0.75x - 2.0x)
- Resume from last position
- Auto-mark as listened
- Chapter navigation with active chapter highlighting
- Minimizable player for compact viewing
- Touch-optimized controls for mobile devices

**User Stories**:
- As a user, I want to see which chapter is currently playing
- As a user, I want to jump to specific chapters
- As a user, I want to adjust playback speed
- As a user, I want the player to remember where I left off

**Technical Details**:
- Chapter extraction from transcript with timestamps
- Playback position persistence in database
- Real-time position updates during playback
- Auto-mark as listened at 90% completion threshold

### 4.7 Settings & Personalization

**Description**: Comprehensive configuration interface for all platform settings.

**Key Capabilities**:
- Timezone configuration
- Content duration preferences
- Conversation complexity (Casual to Expert, 1-5 scale)
- Personal name for host addressing
- API key management (OpenRouter, TTS providers, NewsAPI, Resend)
- Model selection with search
- TTS provider configuration

**User Stories**:
- As a user, I want to configure my timezone so schedules run at the right time
- As a user, I want to adjust conversation complexity to match my knowledge level
- As a user, I want to manage my API keys in one place
- As a user, I want to switch between TTS providers easily

**Technical Details**:
- Settings stored in database (User model preferences JSON)
- Environment variable overrides
- Model search and filtering
- Timezone list with IANA format support
- Complexity levels with detailed descriptions

### 4.8 Filtering & Organization

**Description**: Advanced filtering and organization tools for briefings.

**Key Capabilities**:
- Filter by listened status (All, Listened, Not Listened)
- Filter by cast/hosts
- Filter by topics (multi-select with color coding)
- Filter by favorite status
- Collapsible filter panels with state persistence
- Search and pagination
- Featured briefing card for latest content

**User Stories**:
- As a user, I want to see only unlistened briefings
- As a user, I want to filter by specific topics
- As a user, I want to see briefings from a specific cast
- As a user, I want my filter preferences to persist

**Technical Details**:
- Query parameter-based filtering
- Pagination with configurable page size
- LocalStorage persistence for UI state
- Featured briefing selection logic (latest completed)

## 5. Technical Architecture

### 5.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Interfaces                            │
├─────────────────────┬─────────────────────┬─────────────────────┤
│   Web Dashboard     │   REST API          │   Email/Webhooks    │
│   (React/Vite)       │   (FastAPI)         │   (Notifications)   │
└──────────────┬──────┴──────────┬──────────┴──────────┬───────────┘
               │                 │                     │
               └─────────────────┼─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   FastAPI Backend       │
                    │   (REST API + Scheduler)│
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐          ┌──────▼──────┐         ┌─────▼─────┐
   │ Briefing  │          │ Scheduled   │         │  Content  │
   │ Service   │          │ Briefing    │         │  Sources  │
   │           │          │ Service     │         │           │
   └────┬─────┘          └──────────────┘         └─────┬─────┘
        │                                               │
        └────────────────────────┘                       │
                        │                               │
        ┌───────────────▼───────────────┐              │
        │    Content Sources            │              │
        │  (RSS, Custom Sites, NewsAPI) │              │
        └───────────────┬───────────────┘              │
                        │                               │
        ┌───────────────▼───────────────────────────────▼───────┐
        │    LLM / TTS Providers                                │
        │  (OpenRouter, Piper, ElevenLabs, Gemini)              │
        └───────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

**Backend**:
- **Framework**: FastAPI (Python)
- **Database**: SQLite (with async SQLAlchemy)
- **Scheduler**: APScheduler (AsyncIOScheduler)
- **Task Queue**: In-memory queue system
- **ORM**: SQLAlchemy with async support

**Frontend**:
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Routing**: React Router

**AI/ML**:
- **LLM Provider**: OpenRouter (access to 100+ models)
- **TTS Providers**: 
  - Piper (self-hosted, default)
  - ElevenLabs (cloud API)
  - Google Gemini (cloud API)

**Integrations**:
- **News Sources**: NewsAPI, RSS feeds, custom web scraping
- **Email**: Resend API
- **Webhooks**: Custom URL callbacks

### 5.3 Data Models

#### Core Entities

**User**
- ID, email, name
- Preferences (JSON)
- Relationships: briefings, topics, custom_sites, scheduled_briefings, casts

**Topic**
- ID, user_id, name, slug, description, color
- Flags: is_active, use_newsapi, enable_site_generation
- Relationships: custom_sites, articles

**CustomSite**
- ID, user_id, topic_id, name, url
- Status: is_active, last_fetched, last_error
- Relationships: topic, user

**Briefing**
- ID, user_id, title, transcript
- Audio: audio_filename, duration_seconds
- Status: status, error_message
- Tracking: listened, listened_at, playback_position, favorite
- Metadata: extra_data (JSON), sources (JSON)
- Relationships: user, cast

**ScheduledBriefing**
- ID, user_id, name
- Configuration: topic_ids, schedule_time, schedule_days
- Notifications: notification_methods, email_recipients, webhook_url
- Settings: is_active, max_duration_minutes, resend_api_key
- Tracking: last_generated_at
- Relationships: user, cast

**Cast**
- ID, user_id, name, description, is_default
- Relationships: user, members

**CastMember**
- ID, cast_id, name, voice_id, personality, order
- Relationships: cast

**Article**
- ID, topic_id, title, url, content, published_at
- Relationships: topic

### 5.4 Key Services

**BriefingService**
- Creates and generates briefings
- Orchestrates content gathering, LLM processing, and TTS generation
- Handles cancellation and timeout
- Manages briefing status lifecycle

**ScheduledBriefingService**
- Manages scheduled briefing configurations
- Determines which schedules are due
- Triggers briefing generation
- Handles notifications

**CastService**
- Manages cast configurations
- Handles default cast assignment
- Validates cast member configurations

**NewsService**
- Aggregates content from NewsAPI
- Filters and processes news articles

**ScraperService**
- Fetches and parses RSS feeds
- Scrapes custom websites
- Extracts article content

**SearchService**
- Provides search capabilities for content
- Used in content curation

**BriefingQueue**
- Manages background briefing generation
- Prevents concurrent generation conflicts
- Handles queue persistence

### 5.5 LLM Agent Architecture

**Orchestrator Pattern**:
- **FactsGathererAgent**: Collects and summarizes articles
- **StoryAnalyzerAgent**: Analyzes stories and identifies key themes
- **BriefingWriterAgent**: Generates conversational podcast script
- **Orchestrator**: Coordinates agents and manages workflow

**Personality System**:
- 15+ predefined personality types
- Each personality has system prompts and behavior guidelines
- Supports multi-host conversations with different personalities
- Natural conversational dynamics (friction, callbacks, tangents)

## 6. User Flows

### 6.1 Generate a Briefing

1. User navigates to Dashboard → Generate tab
2. User selects topics (optional, defaults to all active topics)
3. User selects cast (optional, defaults to default cast)
4. User clicks "Generate Briefing"
5. System creates briefing record with `pending` status
6. Background task starts generation:
   - Gather articles from selected topics
   - Use FactsGathererAgent to summarize articles
   - Use StoryAnalyzerAgent to identify themes
   - Use BriefingWriterAgent to create script
   - Generate audio using TTS provider
   - Extract chapters from transcript
   - Update briefing status to `completed`
7. User sees briefing appear in Audio Briefs tab
8. User can play, navigate chapters, and manage playback

### 6.2 Schedule a Briefing

1. User navigates to Dashboard → Generate tab
2. User expands "Scheduled Briefings" section
3. User clicks "Create Schedule" or edits existing
4. User configures:
   - Name
   - Topics to include
   - Schedule time (HH:MM in user's timezone)
   - Days of week
   - Duration
   - Cast (optional)
   - Notification methods (email/webhook)
5. User saves schedule
6. System adds schedule to database
7. Scheduler checks every minute for due schedules
8. When schedule is due:
   - System queues briefing generation
   - Queue processor generates briefing
   - System sends notifications (if configured)
   - System updates `last_generated_at`

### 6.3 Add a Custom Site

1. User navigates to Topics page
2. User selects a topic
3. User clicks "Add Custom Site"
4. User enters site name and URL
5. User optionally tests connectivity
6. User saves site
7. System adds site to database
8. During next briefing generation, system fetches articles from site
9. Articles are associated with topic

### 6.4 Create a Cast

1. User navigates to Casts page
2. User clicks "Create Cast"
3. User enters cast name and description
4. User adds cast members:
   - Name
   - Voice selection
   - Personality selection
   - Order
5. User saves cast
6. User optionally sets as default
7. System saves cast configuration
8. Cast is available for briefing generation

## 7. API Specifications

### 7.1 Authentication

All API endpoints require authentication via API key in header:
```
X-API-Key: <api_key>
```

### 7.2 Core Endpoints

**Briefings**
- `GET /api/briefings` - List briefings (with filters)
- `POST /api/briefings/generate` - Generate new briefing
- `GET /api/briefings/{id}` - Get briefing details
- `PATCH /api/briefings/{id}/listened` - Update listened status
- `PATCH /api/briefings/{id}/playback-position` - Update playback position
- `PATCH /api/briefings/{id}/favorite` - Toggle favorite status

**Topics**
- `GET /api/topics` - List all topics
- `POST /api/topics` - Create new topic
- `GET /api/topics/{id}` - Get topic details
- `PUT /api/topics/{id}` - Update topic
- `DELETE /api/topics/{id}` - Delete topic
- `POST /api/topics/{id}/generate-sites` - Generate site suggestions

**Custom Sites**
- `GET /api/custom-sites` - List all custom sites
- `POST /api/custom-sites` - Create new custom site
- `GET /api/custom-sites/{id}` - Get site details
- `PUT /api/custom-sites/{id}` - Update site
- `DELETE /api/custom-sites/{id}` - Delete site
- `POST /api/custom-sites/{id}/test` - Test site connectivity

**Scheduled Briefings**
- `GET /api/scheduled-briefings` - List all scheduled briefings
- `POST /api/scheduled-briefings` - Create new scheduled briefing
- `GET /api/scheduled-briefings/{id}` - Get scheduled briefing details
- `PUT /api/scheduled-briefings/{id}` - Update scheduled briefing
- `DELETE /api/scheduled-briefings/{id}` - Delete scheduled briefing
- `PATCH /api/scheduled-briefings/{id}/toggle` - Toggle active status

**Casts**
- `GET /api/casts` - List all casts
- `POST /api/casts` - Create new cast
- `GET /api/casts/{id}` - Get cast details
- `PUT /api/casts/{id}` - Update cast
- `DELETE /api/casts/{id}` - Delete cast
- `POST /api/casts/{id}/set-default` - Set as default cast
- `POST /api/casts/default/restore` - Restore default cast

**Settings**
- `GET /api/settings` - Get current settings
- `PATCH /api/settings` - Update settings
- `GET /api/settings/models` - Get available LLM models
- `GET /api/settings/timezones` - Get available timezones

### 7.3 Response Formats

All endpoints return JSON. List endpoints support pagination:
```json
{
  "items": [...],
  "total": 100,
  "limit": 10,
  "offset": 0
}
```

Error responses follow standard HTTP status codes with error details:
```json
{
  "detail": "Error message"
}
```

## 8. Integration Points

### 8.1 OpenRouter (LLM)

- **Purpose**: Access to 100+ AI models
- **Features**: Model search, context length awareness, automatic switching
- **Configuration**: API key, base URL, model selection
- **Usage**: All LLM operations (content summarization, script generation)

### 8.2 TTS Providers

**Piper** (Default, Self-hosted)
- No API key required
- Local voice models
- Good quality, free

**ElevenLabs** (Cloud)
- Premium quality voices
- API key required
- Usage-based pricing

**Google Gemini** (Cloud)
- Native TTS with expressiveness
- API key required
- Supports non-speech sounds

### 8.3 NewsAPI

- **Purpose**: Additional news sources
- **Configuration**: API key per topic
- **Usage**: Content aggregation for topics with `use_newsapi` enabled

### 8.4 Resend (Email)

- **Purpose**: Email notifications for scheduled briefings
- **Configuration**: API key, from email address
- **Usage**: Send briefing notifications to configured recipients

### 8.5 Webhooks

- **Purpose**: Custom integrations
- **Configuration**: Webhook URL per scheduled briefing
- **Usage**: POST request when briefing is generated

## 9. Non-Functional Requirements

### 9.1 Performance

- Briefing generation: Target < 5 minutes for short briefings
- API response time: < 200ms for read operations
- Audio playback: Streaming support for large files
- Queue processing: Process one briefing at a time to prevent resource exhaustion

### 9.2 Scalability

- Support for multiple users (single-user focused but multi-user capable)
- Database can be migrated to PostgreSQL for production
- Audio storage can be moved to object storage (S3, etc.)
- Queue system can be replaced with Redis/Celery for distributed processing

### 9.3 Reliability

- Error handling for all external API calls
- Retry logic for transient failures
- Timeout handling for long-running operations
- Status tracking for all operations
- Queue persistence to prevent data loss

### 9.4 Security

- API key authentication
- Input validation on all endpoints
- SQL injection prevention (SQLAlchemy ORM)
- XSS prevention (React sanitization)
- CORS configuration for production

### 9.5 Usability

- Responsive design for mobile and desktop
- Touch-optimized controls
- Clear error messages
- Loading states for all async operations
- Persistent UI state (filters, accordions)

### 9.6 Privacy

- Self-hosted deployment option
- All data stored locally
- No data sent to external services (except configured APIs)
- User controls all API keys

## 10. Deployment

### 10.1 Self-Hosted Deployment

**Docker Compose Setup**:
- Backend service (FastAPI)
- Frontend service (Nginx)
- Volume mounts for data persistence
- Environment variable configuration

**Requirements**:
- Docker and Docker Compose
- OpenRouter API key (required)
- Optional: TTS provider API keys, NewsAPI key, Resend key

**Data Persistence**:
- `./data` - Database and application data
- `./audio` - Generated audio files
- `./models` - TTS voice models (Piper)

### 10.2 Development Setup

**Backend**:
- Python 3.13+ virtual environment
- FastAPI with uvicorn
- SQLite database

**Frontend**:
- Node.js and npm
- React with Vite
- Hot reload for development

## 11. Future Considerations

### 11.1 Potential Enhancements

- **Multi-user Support**: Enhanced user management and permissions
- **Export Features**: Download briefings as MP3, export transcripts
- **Analytics**: Listening statistics, topic popularity
- **Content Discovery**: AI-powered content recommendations
- **Social Features**: Share briefings, community casts
- **Mobile Apps**: Native iOS/Android applications
- **Voice Cloning**: Custom voice creation for casts
- **Real-time Updates**: WebSocket support for live generation progress
- **Advanced Scheduling**: More flexible schedule patterns (monthly, custom cron)
- **Content Caching**: Cache articles to reduce API calls
- **Transcript Search**: Full-text search across all transcripts
- **Playlists**: Organize briefings into playlists
- **Offline Mode**: Download briefings for offline listening

### 11.2 Technical Improvements

- **Database Migration**: PostgreSQL support for production
- **Distributed Queue**: Redis/Celery for multi-instance deployments
- **Object Storage**: S3-compatible storage for audio files
- **CDN Integration**: Serve audio files via CDN
- **Monitoring**: Health checks, metrics, logging
- **Testing**: Comprehensive test suite
- **Documentation**: API documentation, deployment guides
- **Performance Optimization**: Caching, database indexing

## 12. Success Metrics

### 12.1 User Engagement

- Number of briefings generated per user
- Average listening completion rate
- Number of scheduled briefings created
- Topics and custom sites per user

### 12.2 Quality Metrics

- Briefing generation success rate
- Average generation time
- User satisfaction with content quality
- Error rates for content fetching

### 12.3 Technical Metrics

- API response times
- Queue processing time
- Audio generation time
- System uptime

## 13. Glossary

- **Briefing**: An AI-generated audio podcast summarizing content from selected topics
- **Cast**: A configuration of AI hosts with specific personalities and voices
- **Topic**: A category for organizing content sources (e.g., "Technology", "Science")
- **Custom Site**: A user-added RSS feed or website for content aggregation
- **Scheduled Briefing**: An automatically generated briefing on a recurring schedule
- **Chapter**: A segment of a briefing with a specific topic or theme
- **Personality**: A predefined behavior pattern for AI hosts (e.g., "Casual", "Analytical")
- **TTS**: Text-to-Speech, the technology that converts text to audio
- **LLM**: Large Language Model, used for content summarization and script generation

---

**Document Version**: 1.0  
**Last Updated**: Based on current codebase analysis  
**Status**: Current State Documentation

