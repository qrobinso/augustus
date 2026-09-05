# Augustus

**Self-hosted Audio Intelligence Platform**

Augustus transforms your personalized content—news feeds, topics, and queries—into natural, conversational AI-generated podcasts.

## Who is Augustus for?

Augustus is designed for two primary use cases:

- **Self-hosted, home lab setups with one or more people in the household** - Perfect for individuals and families who want complete control over their data and content. With multi-profile support, each household member can have their own personalized briefings, topics, and preferences while sharing the same infrastructure.

- **Enterprises that want to enable daily podcasts for their employees with their own models and data** - Ideal for organizations looking to provide personalized audio content to their teams while maintaining full data sovereignty. Augustus allows enterprises to use their own LLM models, keep all data on-premises, and customize content delivery to match organizational needs.

## Features

### Core Content

- 🎙️ **Daily Briefings** - AI-generated audio briefings from news sources, blogs, and Reddit
  - Configurable duration
  - Automatic content curation and summarization
  - Chapter-based navigation with transcripts
  - Playback position tracking and resume functionality
  - Listened status tracking and filtering

- 📅 **Scheduled Briefings** - Automatically generate briefings on a schedule
  - Daily, weekly, or custom schedule patterns
  - Multiple notification methods (email, webhook)

### Story Memory & Listening

Augustus keeps a separate story history for each profile. The editor connects reports about a developing event across episodes and topic combinations, prioritizing substantive updates over repeated headlines. A generated episode does not count as something you have heard.

- **Listening coverage:** continuous playback is recorded by chapter. Seeking and replaying do not inflate unique coverage. A chapter becomes a listening baseline at 80% coverage; an episode is marked listened at 80% total coverage. Manual listened toggles affect organization, not story knowledge.
- **Follow stories:** new briefing detail pages show story developments with **Follow story** and **Less of this** controls. These preferences influence future editorial selection; they do not trigger notifications or infer preferences from skipped audio.
- **Inspectable evidence:** research findings retain their own source links and matching excerpts. Findings without matching source material remain labeled unverified. A matching excerpt establishes provenance, not an automatic guarantee that a claim is true.
- **Quiet days:** fewer worthwhile stories produce a shorter target duration. When none qualify, Augustus saves a text-only result without generating filler audio.

Restart the backend after updating: startup creates the additional `stories`, `story_developments`, and `listening_records` tables automatically. Existing episodes still play, but their old listened flags are not imported as chapter knowledge. Story memory builds from newly generated episodes, and automatic tracking starts with playback in the updated app.

The editor receives up to 60 recent stories (followed stories first) and the latest five developments per story, within a 32,000-character memory budget. Event matching and update classification depend on the selected language model. Chapter exposure uses the audio provider’s timing information; transitions are tracked conservatively. Listening uploads retry while the app is open, but an unsuccessful upload followed by a hard browser shutdown can lose the pending interval. External podcast-player listening is not tracked.

New API routes (using the existing authentication and `X-Profile-ID` header):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/briefings/{id}/listening` | POST | Merge played intervals: `{"ranges": [[0, 30], [45, 60]]}` |
| `/api/stories/{id}` | GET | Read a story’s current preference |
| `/api/stories/{id}/preference` | PATCH | Set `{"preference": "normal"}`, `"follow"`, or `"less"` |

### Breakout podcasts

Press **Deep dive** in the audio player to create a separate podcast about the chapter playing at that moment—one click, with the same cast and a 10-minute target. It immediately takes the first slot in **Up Next** while your current episode continues. If that episode ends before the deep dive is ready, playback waits and starts it when generation finishes. The queue shows progress or errors; you can remove or reorder it. Removing it from playback does not cancel generation. Accepted generation jobs remain in the queue across reloads; playback still requires your usual play action after a reload. Chapter timing is required to identify the current subject.

Use the MCP/API below for a custom subject, saved topic, source chapter, focus, duration, or cast. These requests use the usual progress, cancellation, transcript and audio controls without automatically joining the browser's playback queue. Source-based breakouts retain a link to the original episode.

Breakouts research one subject across background, mechanisms, evidence, differing views and implications. They bypass daily novelty filtering and quiet-day shortening. Available fetched sources determine what can be supported; insufficient research fails clearly. Breakouts do not mark the source episode listened or add research sections as new story-memory events. Length is a target, not a guaranteed audio runtime.

**API:** `POST /api/briefings/breakout` returns a normal briefing with HTTP **202** and status `queued`. Supply exactly one target:

```json
{"topic": "Atlantic ocean circulation", "focus": "How it works and what changes could mean", "max_duration_minutes": 10}
```

Or use `{"topic_id": "<saved-topic-id>"}`, or `{"source_briefing_id": "<episode-id>", "chapter_index": 1}` (zero-based chapter index from `GET /api/briefings/<id>`). Optional fields are `focus`, `cast_id`, and `max_duration_minutes` (3–30, default 10). A chapter breakout inherits its source cast unless you choose another; otherwise the profile default applies. Source, topic, and cast must belong to the active profile. The selected chapter context is snapshotted when the job is created.

Use `X-Profile-ID` for the local UI/API profile, or an `X-API-Key` generated in the MCP management page for a bound external client. API keys cannot override their bound profile. Allow **generate_breakout_podcast** on restricted keys; also allow **get_briefing** to poll for completion and **cancel_briefing** if cancellation is needed. API-key identity does not replace network access protection for this self-hosted app.

**MCP:** install the backend dependencies (`pip install -r backend/requirements.txt`) in the Python environment used by the MCP server; this includes the supported v1 MCP SDK. Then call `generate_breakout_podcast(topic="Atlantic ocean circulation", max_duration_minutes=10)`, or pass the saved-topic/chapter selectors above. The tool uses the same queue and returns the standard detail/listen links. Poll `get_briefing(briefing_id)` until `completed`, `failed`, or `cancelled`; do not treat HTTP 202 as finished audio. Restart the MCP client/server after updating to refresh its tool catalog.

**Generation queue:** You can submit multiple daily briefings and breakout podcasts for the same profile; every accepted request gets its own episode ID. The shared worker processes episodes one at a time in first-in, first-out order across profiles. Waiting jobs persist in the database and resume after a backend restart. An episode interrupted during generation is marked failed, and legacy pending jobs are returned to the queue. Poll or cancel each episode independently. `GET /api/briefings/queue` returns all active jobs for the current profile, oldest first, as `{briefings: [...], total: ...}`.

### Content Management

- 🏷️ **Topics** - Organize content by topics
  - Create custom topics for different interests
  - Enable/disable topics for briefings
  - AI-powered site suggestion generation
  - NewsAPI integration for additional sources
  - Automatic article scraping and parsing

- 🎭 **Casts** - Customizable AI host configurations
  - Create custom host personalities and voices
  - Multi-voice conversations between hosts
  - Set default cast for all content
  - Restore default cast configuration

- 👥 **Profiles** - Multi-profile support for households
  - Create separate profiles with their own data
  - Each profile has independent briefings, topics, schedules, and casts
  - Admin profile for account management

### Audio & Playback

- 🎵 **Audio Player**
  - Chapter-based progress visualization with color-coded segments
  - Interactive chapter markers with hover tooltips
  - Playback speed control (0.75x - 2.0x)
  - Resume from last position
  - Auto-mark as listened
  - Chapter navigation with active chapter highlighting
  - Minimizable player for compact viewing

### Integrations & Providers

- 🤖 **LLM Providers** - OpenRouter or Codex subscription
  - OpenRouter API access to multiple model providers
  - Codex with ChatGPT sign-in and account model selection
  - Provider selection applies to all text generation; audio is configured separately

- 🔊 **TTS Providers**
  - **Piper** - Self-hosted, free, good quality
  - **ElevenLabs** - Cloud API, premium quality voices
  - **Google Gemini** - Native TTS with expressiveness

- 📰 **News Sources**
  - NewsAPI integration (optional)
  - Custom website scraping
  - Automatic content fetching

- 📧 **Email Notifications** - Resend integration
  - Send briefings via email
  - HTML email templates
  - Multiple recipients
  - Transcript previews

- 🔗 **Webhooks** - For scheduled briefings
  - Custom webhook URLs
  - Notification callbacks
  - Integration with external services

### Technical Features

- 🏠 **Self-hosted** - Full data ownership and privacy
  - All data stored locally
  - No external dependencies required (except API keys)
  - Complete control over your content

- 🔌 **Modular Architecture** - Swap providers easily
  - Pluggable LLM providers
  - Pluggable TTS providers
  - Easy to extend and customize

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenRouter API key ([get one here](https://openrouter.ai/keys)), or a ChatGPT plan with Codex access and the Codex CLI installed on the backend host
- (Optional) TTS provider API key:
  - ElevenLabs API key for premium TTS ([get one here](https://elevenlabs.io))
  - Google Gemini API key for Gemini TTS ([get one here](https://aistudio.google.com))
  - Or use Piper (self-hosted, no API key needed)
- (Optional) NewsAPI key for additional news sources ([get one here](https://newsapi.org))
- (Optional) Resend API key for email notifications ([get one here](https://resend.com))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/qrobinso/augustus.git
   cd augustus
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   # IMPORTANT: Change API_KEY from the default value!
   ```

3. **Start with Docker Compose**
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

4. **Access the app**
   - Frontend: http://localhost:3000 (or http://YOUR_SERVER_IP:3000)
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   
   > **Note:** Replace `YOUR_SERVER_IP` with your server's IP address to access from other devices on your network.

5. **Configure in the UI**
   - Go to Settings
   - Enter your OpenRouter API key (if not set in .env)
   - (Optional) Configure TTS provider (Piper works out of the box)
   - (Optional) Add NewsAPI key for additional news sources
   - (Optional) Add Resend API key for email notifications
   - Configure your timezone and preferences
   - Start generating!

> **For detailed Docker setup instructions, see [docker/README.md](docker/README.md)**


## Production Deployment

For detailed production deployment instructions, including Docker Compose setup, configuration, and best practices, see [docker/README.md](docker/README.md).

## Configuration

### Required Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Authentication key for the API | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM | Only with OpenRouter |

### Codex subscription setup

1. Install the official Codex CLI on the machine running the **backend**: `npm install -g @openai/codex@0.146.0` (Node.js required). This integration is tested with CLI 0.146.0; older versions may lack the tool-isolation protocol fields. Set `CODEX_CLI_PATH` to the executable's absolute path if the backend cannot find it.
2. Restart the backend, open **Settings → LLM Provider → Codex subscription**, and choose **Connect with ChatGPT**. Open the displayed verification link and enter the code. If needed, enable device-code login in your ChatGPT security settings or ask your workspace administrator to allow it.
3. Select an available model, or leave the Codex default selected. Provider and model changes save automatically. Subscription limits and workspace policies apply; an exhausted allowance causes an error instead of switching to paid API billing. TTS still uses your separately selected audio provider.

Augustus uses the [official Codex App Server](https://learn.chatgpt.com/docs/app-server) and [managed ChatGPT authentication](https://learn.chatgpt.com/docs/auth). It keeps a separate login under `backend/data/codex` (override with `AUGUSTUS_CODEX_HOME`); it does not read or copy your desktop Codex credentials. Disconnect affects only this Augustus login. Keep that directory private and persistent. Backend instances should not share a Codex home concurrently. Model requests have no execution environments, filesystem/shell tools, apps, plugins, or native web search; research uses Augustus's search service. Each request uses an ephemeral thread. `temperature` and `max_tokens` from the shared provider interface are not hard controls in the App Server protocol.

For containers, the standard Python backend image does **not** include Codex. Install the CLI and Node.js in a derived backend image, set `CODEX_CLI_PATH`, and persist `/app/data` with `AUGUSTUS_CODEX_HOME=/app/data/codex`. Installing on the Docker host alone will not make it available inside the container. If frontend and backend use separate origins or a reverse proxy, set `FRONTEND_URL` to the exact public Augustus origin so account controls pass the origin check. This remains a trusted, single-household self-hosted app; put remote access behind your own authentication.

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `openrouter` or `codex` | `openrouter` |
| `CODEX_MODEL` | Codex model ID (blank uses account default) | empty |
| `CODEX_CLI_PATH` | Codex executable on the backend | `codex` |
| `AUGUSTUS_CODEX_HOME` | Dedicated Augustus Codex credentials and state | `backend/data/codex` |
| `CODEX_TIMEOUT_SECONDS` | Deadline per model request | `180` |
| `OPENROUTER_MODEL` | LLM model to use | `anthropic/claude-3.5-sonnet` |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | `https://openrouter.ai/api/v1` |

### TTS Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_PROVIDER` | TTS provider (`piper`, `elevenlabs`, or `gemini`) | `piper` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | Optional |
| `ELEVENLABS_MODEL` | ElevenLabs TTS model | `eleven_turbo_v2_5` |
| `GEMINI_API_KEY` | Google Gemini API key | Optional |
| `GEMINI_MODEL` | Gemini TTS model | `gemini-2.5-flash-preview-tts` |
| `PIPER_MODEL_PATH` | Path to Piper voice model | `./models/en_US-lessac-medium.onnx` |

### Content Duration Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `BRIEFING_DURATION_MINUTES` | Daily briefing target duration | `7` |

### Content Quality Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CONVERSATION_COMPLEXITY` | Language complexity (1-5 scale) | `3` |
| `TIMEZONE` | User timezone (IANA format) | `UTC` |

### Integrations

| Variable | Description | Default |
|----------|-------------|---------|
| `NEWS_API_KEY` | NewsAPI key for news sources | Optional |
| `RESEND_API_KEY` | Resend API key for email notifications | Optional |

### Storage & Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./augustus.db` |
| `AUDIO_STORAGE_PATH` | Path to store audio files | `./audio` |

> **Note:** Most settings can be configured via the web UI in Settings, which is the recommended approach. Environment variables are used for initial setup and server-level defaults.

## Capabilities

Augustus provides a comprehensive platform for creating personalized audio content:

- **Content Aggregation**: Collect articles from RSS feeds, custom websites, and news APIs
- **AI-Powered Summarization**: Transform articles into conversational summaries
- **Multi-Host Conversations**: Create natural dialogues between AI hosts with different personalities
- **Automatic Scheduling**: Set up recurring briefings that generate automatically
- **Smart Content Curation**: AI selects and prioritizes the most relevant content
- **Chapter Navigation**: Automatic chapter generation with transcripts
- **Playback Management**: Resume playback, speed control, and listening status tracking
- **Topic Organization**: Organize content by topics with custom sites and sources
- **Custom Site Discovery**: AI suggests relevant sites for topics
- **Email Delivery**: Send briefings directly to email inboxes
- **Webhook Integration**: Integrate with external services and automation
- **Multi-Provider Support**: Choose from multiple LLM and TTS providers
- **Timezone Awareness**: Schedule and deliver content based on your timezone
- **Personalization**: Customize content complexity, duration, and host personalities

## Architecture

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
   ┌────▼─────┐
   │ Briefing  │
   │ Service   │
   └────┬─────┘
        │
        └────────────────────────┘
                        │
        ┌───────────────▼───────────────┐
        │    Content Sources            │
        │  (RSS, Custom Sites, NewsAPI) │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │    LLM / TTS Providers        │
        │  (OpenRouter, Piper, 11Labs,  │
        │   Gemini)                      │
        └───────────────────────────────┘
```

## API Endpoints

### Briefings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefings` | GET | List all briefings (with filters) |
| `/api/briefings/generate` | POST | Queue a new briefing |
| `/api/briefings/queue` | GET | List all active generation jobs for the current profile |
| `/api/briefings/{id}` | GET | Get briefing details |
| `/api/briefings/{id}/listened` | PATCH | Update listened status |
| `/api/briefings/{id}/playback-position` | PATCH | Update playback position |

### Topics
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/topics` | GET | List all topics |
| `/api/topics` | POST | Create new topic |
| `/api/topics/{id}` | GET | Get topic details |
| `/api/topics/{id}` | PUT | Update topic |
| `/api/topics/{id}` | DELETE | Delete topic |
| `/api/topics/{id}/generate-sites` | POST | Generate site suggestions |

### Custom Sites
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/custom-sites` | GET | List all custom sites |
| `/api/custom-sites` | POST | Create new custom site |
| `/api/custom-sites/{id}` | GET | Get site details |
| `/api/custom-sites/{id}` | PUT | Update site |
| `/api/custom-sites/{id}` | DELETE | Delete site |
| `/api/custom-sites/{id}/test` | POST | Test site connectivity |

### Scheduled Briefings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scheduled-briefings` | GET | List all scheduled briefings |
| `/api/scheduled-briefings` | POST | Create new scheduled briefing |
| `/api/scheduled-briefings/{id}` | GET | Get scheduled briefing details |
| `/api/scheduled-briefings/{id}` | PUT | Update scheduled briefing |
| `/api/scheduled-briefings/{id}` | DELETE | Delete scheduled briefing |
| `/api/scheduled-briefings/{id}/toggle` | PATCH | Toggle active status |

### Casts
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/casts` | GET | List all casts |
| `/api/casts` | POST | Create new cast |
| `/api/casts/{id}` | GET | Get cast details |
| `/api/casts/{id}` | PUT | Update cast |
| `/api/casts/{id}` | DELETE | Delete cast |
| `/api/casts/{id}/set-default` | POST | Set as default cast |
| `/api/casts/default/restore` | POST | Restore default cast |

### Profiles
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profiles` | GET | List all profiles |
| `/api/profiles` | POST | Create new profile |
| `/api/profiles/{id}` | GET | Get profile details |
| `/api/profiles/{id}` | PUT | Update profile |
| `/api/profiles/{id}` | DELETE | Delete profile (non-admin only) |

### Settings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | GET | Get current settings |
| `/api/settings` | PATCH | Update settings |
| `/api/settings/models` | GET | Get available LLM models |
| `/api/settings/timezones` | GET | Get available timezones |

## TTS Providers

### Piper (Self-hosted, Default)

Free, local TTS with good quality. No API calls required, completely private.

**Setup:**
```bash
# Download a voice model
mkdir -p models
wget -O models/en_US-lessac-medium.onnx \
  https://github.com/rhasspy/piper/releases/download/v1.2.0/voice-en_US-lessac-medium.onnx
```

**Pros:**
- Free and self-hosted
- No API costs
- Good quality voices
- Complete privacy

**Cons:**
- Requires downloading voice models
- Slightly less natural than premium options

### ElevenLabs (Cloud)

Premium quality TTS with natural-sounding voices. Requires API key.

**Setup:**
1. Get API key from [ElevenLabs](https://elevenlabs.io)
2. Set `TTS_PROVIDER=elevenlabs` in settings
3. Enter API key in Settings UI

**Pros:**
- Premium voice quality
- Very natural sounding
- Fast generation
- Multiple voice options

**Cons:**
- Requires API key
- Usage-based pricing
- Data sent to external service

### Google Gemini (Cloud)

Native TTS with expressiveness and natural prosody. Currently in preview.

**Setup:**
1. Get Gemini 2.0+ API key from [Google AI Studio](https://aistudio.google.com)
2. Set `TTS_PROVIDER=gemini` in settings
3. Enter API key in Settings UI

**Pros:**
- Native TTS integration
- Expressive voices
- Good for conversational content
- Competitive pricing

**Cons:**
- Requires API key
- Preview/beta status
- Data sent to external service

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.




## Acknowledgments

- [OpenRouter](https://openrouter.ai) for multi-model LLM access
- [Piper](https://github.com/rhasspy/piper) for open-source TTS
- [ElevenLabs](https://elevenlabs.io) for premium voice synthesis
- [Google Gemini](https://deepmind.google/technologies/gemini/) for native TTS capabilities
- [Resend](https://resend.com) for email delivery
- [NewsAPI](https://newsapi.org) for news aggregation
- Inspired by [Huxe](https://huxe.com)
