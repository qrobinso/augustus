"""VoiceboxClient against a fake Voicebox server (httpx.MockTransport)."""
import json

import httpx
import pytest

from app.services.tts import voicebox_client as vc
from app.services.tts.voicebox_client import VoiceboxClient, VoiceboxError


PROFILES = [
    {"id": "p-halie", "name": "Halie ", "language": "en", "voice_type": "cloned", "preset_engine": None},
    {"id": "p-heart", "name": "Heart (kokoro)", "language": "en", "voice_type": "preset", "preset_engine": "kokoro"},
]
MODELS = {"models": [
    {"model_name": "chatterbox-turbo", "display_name": "Chatterbox Turbo", "downloaded": True},
    {"model_name": "qwen-tts-1.7B", "display_name": "Qwen TTS 1.7B", "downloaded": True},
    {"model_name": "qwen-tts-0.6B", "display_name": "Qwen TTS 0.6B", "downloaded": False},
    {"model_name": "whisper-base", "display_name": "Whisper Base", "downloaded": True},
    {"model_name": "future-tts-9", "display_name": "Future", "downloaded": True},
]}


class FakeVoicebox:
    """Routes requests like Voicebox 0.5.0 and records them."""

    def __init__(self, status="completed", error=None):
        self.requests: list[httpx.Request] = []
        self.status, self.error = status, error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, method = request.url.path, request.method
        if path == "/openapi.json":
            return httpx.Response(200, json={"info": {"version": "0.5.0"}})
        if path == "/profiles":
            return httpx.Response(200, json=PROFILES)
        if path == "/models/status":
            return httpx.Response(200, json=MODELS)
        if path == "/generate" and method == "POST":
            return httpx.Response(200, json={"id": "gen-1", "status": "generating"})
        if path == "/generate/gen-1/status":
            event = {"id": "gen-1", "status": "generating"}
            done = {"id": "gen-1", "status": self.status, "error": self.error}
            body = f"data: {json.dumps(event)}\n\ndata: {json.dumps(done)}\n\n"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        if path == "/audio/gen-1":
            return httpx.Response(200, content=b"RIFFfake", headers={"content-type": "audio/x-wav"})
        if path in ("/history/gen-1", "/generate/gen-1/cancel"):
            return httpx.Response(200, json={"message": "ok"})
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def _clear_profile_cache():
    vc._profile_cache.clear()


def client_for(fake):
    return VoiceboxClient("http://vb.local:17493/", transport=httpx.MockTransport(fake))


@pytest.mark.asyncio
async def test_version_profiles_and_cache():
    fake = FakeVoicebox()
    client = client_for(fake)
    assert await client.version() == "0.5.0"
    profiles = await client.list_profiles()
    assert profiles[0].name == "Halie " and profiles[1].preset_engine == "kokoro"
    await client.list_profiles()
    assert sum(r.url.path == "/profiles" for r in fake.requests) == 1  # cached
    await client.close()


@pytest.mark.asyncio
async def test_models_are_downloaded_known_tts_only():
    client = client_for(FakeVoicebox())
    models = await client.list_tts_models()
    assert [(m.name, m.engine, m.model_size) for m in models] == [
        ("chatterbox-turbo", "chatterbox_turbo", None),
        ("qwen-tts-1.7B", "qwen", "1.7B"),
    ]
    await client.close()


@pytest.mark.asyncio
async def test_generate_wait_download_delete(tmp_path):
    fake = FakeVoicebox()
    client = client_for(fake)
    gen = await client.generate("p-halie", "Hello", "en", "qwen", "1.7B")
    assert gen == "gen-1"
    body = json.loads(fake.requests[-1].content)
    assert body == {"profile_id": "p-halie", "text": "Hello", "language": "en", "engine": "qwen", "model_size": "1.7B"}
    await client.wait_until_done(gen, timeout=5)
    dest = tmp_path / "line.wav"
    await client.download_audio(gen, dest)
    assert dest.read_bytes() == b"RIFFfake"
    await client.delete_generation(gen)
    assert fake.requests[-1].method == "DELETE"
    await client.close()


@pytest.mark.asyncio
async def test_failed_generation_raises_with_voicebox_error_and_id():
    client = client_for(FakeVoicebox(status="failed", error="CUDA OOM"))
    with pytest.raises(VoiceboxError, match="gen-1.*CUDA OOM"):
        await client.wait_until_done("gen-1", timeout=5)
    await client.close()


@pytest.mark.asyncio
async def test_unreachable_server_has_readable_error():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)
    client = VoiceboxClient("http://vb.local:17493", transport=httpx.MockTransport(boom))
    with pytest.raises(VoiceboxError, match=r"^Can't reach Voicebox at http://vb.local:17493\.$"):
        await client.list_profiles()
    await client.close()


def test_model_table_matches_spec():
    assert vc.VOICEBOX_MODELS["tada-3b-ml"] == ("tada", "3B")
    assert vc.VOICEBOX_MODELS["qwen-custom-voice-0.6B"] == ("qwen_custom_voice", "0.6B")
    assert vc.VOICEBOX_MODELS["breeze-tts-2"] == ("breeze", None)


def test_briefing_timeout_budget(monkeypatch):
    from app.config import get_settings
    from app.services.tts.registry import briefing_timeout_minutes
    monkeypatch.setenv("BRIEFING_TIMEOUT_MINUTES", "15")
    monkeypatch.setenv("VOICEBOX_BRIEFING_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()
    assert briefing_timeout_minutes("gemini") == 15
    assert briefing_timeout_minutes("voicebox") == 60


def test_parse_version():
    assert vc.parse_version("0.5.0") == (0, 5, 0)
    assert vc.parse_version("1.2.3rc1") == (1, 2, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("body, calls", [
    ({"text": "<!doctype html><html></html>"}, ("version", "profiles", "models", "generate")),
    ({"json": ["not", "an", "object"]}, ("version", "profiles", "models", "generate")),
    ({"json": {"unexpected": True}}, ("profiles", "generate")),
])
async def test_unexpected_responses_become_voicebox_errors(body, calls):
    handler = lambda request: httpx.Response(200, **body)
    client = VoiceboxClient("http://elsewhere:5173", transport=httpx.MockTransport(handler))
    make = {
        "version": client.version,
        "profiles": lambda: client.list_profiles(max_age=0),
        "models": client.list_tts_models,
        "generate": lambda: client.generate("p", "hi", "en", "kokoro", None),
    }
    for name in calls:
        with pytest.raises(VoiceboxError) as err:
            await make[name]()
        assert str(err.value) == "http://elsewhere:5173 doesn't look like a Voicebox server.", name
    await client.close()
