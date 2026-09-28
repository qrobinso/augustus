"""CastService respects the provider a cast belongs to."""
import pytest

from app.models.cast import Cast
from app.schemas.cast import CastCreate, CastMemberBase, CastUpdate
from app.services.cast import (
    CastProviderMismatchError, CastService, NoCastForProviderError, provider_mismatch_message,
)


def _cast(name, voice="Kore"):
    return CastCreate(name=name, members=[CastMemberBase(name="Alex", voice_id=voice, personality="Casual", order=0)])


@pytest.mark.asyncio
async def test_first_cast_per_provider_becomes_default_and_later_ones_do_not(db_session):
    service = CastService(db_session)
    first = await service.create_cast("u", _cast("One"), profile_id="p", provider="gemini")
    second = await service.create_cast("u", _cast("Two"), profile_id="p", provider="gemini")
    other = await service.create_cast("u", _cast("Kokoro", "am_eric"), profile_id="p", provider="piper")
    assert (first.is_default, second.is_default, other.is_default) == (True, False, True)
    assert first.tts_provider == "gemini" and other.tts_provider == "piper"
    # Regression: creating a cast must not clear the existing default.
    assert (await service.get_default_cast("u", "p", "gemini")).id == first.id


@pytest.mark.asyncio
async def test_listing_is_scoped_by_provider(db_session):
    service = CastService(db_session)
    await service.create_cast("u", _cast("G"), profile_id="p", provider="gemini")
    await service.create_cast("u", _cast("P", "am_eric"), profile_id="p", provider="piper")
    assert [c.name for c in await service.get_user_casts("u", "p", provider="piper")] == ["P"]
    assert {c.name for c in await service.get_user_casts("u", "p")} == {"G", "P"}
    assert await service.count_by_provider("u", "p") == {"gemini": 1, "piper": 1}


@pytest.mark.asyncio
async def test_default_missing_raises_with_user_facing_message(db_session):
    service = CastService(db_session)
    await service.create_cast("u", _cast("G"), profile_id="p", provider="gemini")
    with pytest.raises(NoCastForProviderError, match="^No Piper cast yet. Create one on the Casts page.$"):
        await service.get_default_cast("u", "p", "piper")


@pytest.mark.asyncio
async def test_default_promotes_oldest_when_none_marked(db_session):
    from datetime import datetime

    db_session.add_all([
        Cast(id="old", user_id="u", profile_id="p", name="Old", tts_provider="piper", is_default=False,
             created_at=datetime(2026, 1, 1)),
        Cast(id="new", user_id="u", profile_id="p", name="New", tts_provider="piper", is_default=False,
             created_at=datetime(2026, 1, 2)),
    ])
    await db_session.commit()
    default = await CastService(db_session).get_default_cast("u", "p", "piper")
    assert default.id == "old" and default.is_default is True


@pytest.mark.asyncio
async def test_set_default_switches_within_provider_and_rejects_other_providers(db_session):
    service = CastService(db_session)
    a = await service.create_cast("u", _cast("A"), profile_id="p", provider="gemini")
    b = await service.create_cast("u", _cast("B"), profile_id="p", provider="gemini")
    v = await service.create_cast("u", _cast("V", "am_eric"), profile_id="p", provider="piper")
    assert (await service.set_default_cast(b.id, "u", "p", "gemini")).is_default is True
    await db_session.refresh(a)
    assert a.is_default is False
    with pytest.raises(CastProviderMismatchError, match="'V' is a Piper cast; your voice provider is Google Gemini."):
        await service.set_default_cast(v.id, "u", "p", "gemini")


@pytest.mark.asyncio
async def test_update_rejects_casts_of_another_provider(db_session):
    service = CastService(db_session)
    v = await service.create_cast("u", _cast("V", "am_eric"), profile_id="p", provider="piper")
    with pytest.raises(CastProviderMismatchError):
        await service.update_cast(v.id, "u", CastUpdate(name="Renamed"), "p", "gemini")


@pytest.mark.asyncio
async def test_restore_default_is_gemini_only(db_session):
    service = CastService(db_session)
    with pytest.raises(CastProviderMismatchError, match="only available for Google Gemini"):
        await service.restore_default_cast("u", "p", "piper")
    restored = await service.restore_default_cast("u", "p", "gemini")
    assert restored.tts_provider == "gemini" and restored.is_default is True
    assert [m.voice_id for m in restored.members] == ["Kore", "Puck"]


def test_mismatch_message_copy():
    assert provider_mismatch_message("Gemini Pro Cast", "gemini", "piper") == (
        "'Gemini Pro Cast' is a Google Gemini cast; your voice provider is Piper."
    )
