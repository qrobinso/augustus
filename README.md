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

- 🤖 **LLM Provider** - OpenRouter integration
  - Access to 100+ AI models
  - Model search and selection
  - Context length awareness
  - Automatic model switching

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
- OpenRouter API key ([get one here](https://openrouter.ai/keys))
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
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM | Required |

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
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
| `/api/briefings/generate` | POST | Generate new briefing |
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

