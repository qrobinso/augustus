# Augustus (OpenHuxe)

**Self-hosted Audio Intelligence Platform**

Augustus transforms your personalized content—news feeds, topics, and queries—into natural, conversational AI-generated podcasts.

![Augustus Dashboard](docs/screenshot.png)

## Features

- 🎙️ **Daily Briefings** - AI-generated audio briefings from RSS feeds
- 🔍 **DeepCasts** - On-demand podcasts from any topic or question
- 📻 **Live Stations** - Subscribe to topics with automatic updates
- 🗣️ **Multi-voice** - Natural conversations between AI hosts
- 🏠 **Self-hosted** - Full data ownership and privacy
- 🔌 **Modular** - Swap LLM and TTS providers easily

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenRouter API key ([get one here](https://openrouter.ai/keys))
- (Optional) ElevenLabs API key for premium TTS

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/augustus.git
   cd augustus
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the app**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

5. **Configure in the UI**
   - Go to Settings
   - Enter your API key (the one you set in `.env`)
   - Start generating!

## Development Setup

### Backend (Python/FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend (React/Vite)

```bash
cd frontend
npm install
npm run dev
```

### Development with Docker

```bash
# Start backend only (frontend runs locally for hot reload)
docker-compose -f docker-compose.dev.yml up
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Authentication key for the API | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM | Required |
| `OPENROUTER_MODEL` | LLM model to use | `anthropic/claude-3.5-sonnet` |
| `TTS_PROVIDER` | TTS provider (`piper` or `elevenlabs`) | `piper` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | Optional |
| `RSS_FEEDS` | Comma-separated RSS feed URLs | BBC Tech, NYT Tech |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Interfaces                            │
├─────────────────────┬─────────────────────┬─────────────────────┤
│   Web Dashboard     │   Mobile (PWA)      │   REST API          │
└──────────────┬──────┴──────────┬──────────┴──────────┬───────────┘
               │                 │                     │
               └─────────────────┼─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   FastAPI Backend       │
                    │   (REST API)            │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐          ┌──────▼──────┐        ┌────────▼────────┐
   │ Briefing  │          │  DeepCast   │        │  Station        │
   │ Service   │          │  Service    │        │  Service        │
   └────┬─────┘          └──────┬──────┘        └────────┬────────┘
        │                       │                        │
        └───────────────┬───────┴────────────────────────┘
                        │
        ┌───────────────▼───────────────┐
        │    LLM / TTS Providers        │
        │  (OpenRouter, Piper, 11Labs)  │
        └───────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefings` | GET | List all briefings |
| `/api/briefings/generate` | POST | Generate new briefing |
| `/api/briefings/{id}` | GET | Get briefing details |
| `/api/deepcasts` | GET | List all DeepCasts |
| `/api/deepcasts` | POST | Create new DeepCast |
| `/api/deepcasts/{id}` | GET | Get DeepCast details |
| `/api/stations` | GET | List all stations |
| `/api/stations` | POST | Create new station |
| `/api/stations/{id}` | GET | Get station with episodes |
| `/api/stations/{id}/episodes` | POST | Generate new episode |

## TTS Providers

### Piper (Self-hosted, Default)

Free, local TTS with good quality. Requires downloading voice models.

```bash
# Download a voice model
mkdir -p models
wget -O models/en_US-lessac-medium.onnx \
  https://github.com/rhasspy/piper/releases/download/v1.2.0/voice-en_US-lessac-medium.onnx
```

### ElevenLabs (Cloud)

Premium quality TTS. Set `TTS_PROVIDER=elevenlabs` and provide your API key.

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
- Inspired by [Huxe](https://huxe.com)

---

**Augustus** - *Audio Intelligence for Everyone* 🎙️

