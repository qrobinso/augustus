"""Memory follows actual exposure and stays inside a profile."""
import pytest
from sqlalchemy import select
from app.models.briefing import Briefing
from app.services.news import NewsItem
from app.services.story_memory import StoryMemoryService, select_story_updates
from app.models.story import Story, StoryDevelopment


def item(title='Launch scheduled', key='Acme launch', development='Acme will launch in June', change='new'):
    news = NewsItem(title=title, summary=development, url='https://example.com/launch', source='Example')
    news.story_key, news.development, news.change_type = key, development, change
    return news


async def briefing(db, profile='p1', topics=None, status='completed'):
    b = Briefing(user_id='u', profile_id=profile, title='Daily', transcript='Host: News.',
                 status=status, duration_seconds=100,
                 extra_data={'topic_ids': topics or ['a'], 'chapters': [
                     {'title': 'Launch', 'article_index': 0, 'start_time': 0, 'end_time': 100}]})
    db.add(b)
    await db.commit()
    return b


@pytest.mark.asyncio
async def test_memory_persists_across_topic_combinations_but_not_profiles(db_session):
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session, topics=['a', 'b'])
    saved = await svc.save(b, [item()], b.extra_data['chapters'], {})
    await db_session.commit()
    assert saved['0']['development'] == 'Acme will launch in June'
    context = await svc.context('u', 'p1')
    assert len(context) == 1
    assert context[0]['developments'][0]['heard'] is False
    assert await svc.context('u', 'p2') == []
    assert await svc.context('another-user', 'p1') == []
    b2 = await briefing(db_session, topics=['b', 'c'])
    await svc.save(b2, [item(key=context[0]['id'], development='Acme delayed launch to July', change='update')],
                   b2.extra_data['chapters'], {})
    await db_session.commit()
    context = await svc.context('u', 'p1')
    assert len(context) == 1
    assert len(context[0]['developments']) == 2


@pytest.mark.asyncio
async def test_failed_briefing_cannot_create_memory(db_session):
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session, status='failed')
    assert await svc.save(b, [item()], b.extra_data['chapters'], {}) == {}
    assert (await db_session.execute(select(Story))).scalars().all() == []


@pytest.mark.asyncio
async def test_save_is_idempotent_and_unknown_chapter_does_not_imply_exposure(db_session):
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session)
    chapters = [{'title': 'Renamed', 'start_time': 0, 'end_time': 100}]
    await svc.save(b, [item()], chapters, {})
    await svc.save(b, [item()], chapters, {})
    await db_session.commit()
    rows = (await db_session.execute(select(StoryDevelopment))).scalars().all()
    assert len(rows) == 1
    assert rows[0].chapter_index is None
    assert (await svc.context('u', 'p1'))[0]['developments'][0]['heard'] is False


@pytest.mark.asyncio
async def test_preferences_require_exact_ownership(db_session):
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session)
    saved = await svc.save(b, [item()], b.extra_data['chapters'], {})
    await db_session.commit()
    sid = saved['0']['story_id']
    assert await svc.set_preference('u', 'p2', sid, 'follow') is None
    assert await svc.set_preference('other', 'p1', sid, 'follow') is None
    assert await svc.set_preference('u', 'p1', sid, 'follow') == 'follow'
    with pytest.raises(ValueError):
        await svc.set_preference('u', 'p1', sid, 'bogus')
    assert (await svc.context('u', 'p1'))[0]['preference'] == 'follow'


def history(heard):
    return [{'id': 'known', 'title': 'Acme launch', 'preference': 'normal', 'developments': [
        {'summary': 'Acme will launch in June', 'heard': heard}]}]


def selection(change='unchanged', key='known', development='Acme will launch in June', number=1):
    return {'article_num': number, 'priority': 8, 'reason': 'Relevant', 'story_key': key,
            'development': development, 'change_type': change}


def test_heard_rehash_removed_but_unheard_and_new_development_kept():
    assert select_story_updates([selection()], [item()], history(True), 3) == []
    assert len(select_story_updates([selection()], [item()], history(False), 3)) == 1
    updated = select_story_updates([selection('update', development='Launch delayed to July')], [item()], history(True), 3)
    assert updated[0].change_type == 'update'
    assert updated[0].heard_context == ['Acme will launch in June']


def test_same_event_cannot_occupy_two_slots_and_invented_id_is_rejected():
    selected = select_story_updates([selection('new', 'Acme launch'), selection('new', 'acme  launch', number=2)],
                                    [item(), item()], [], 3)
    assert len(selected) == 1
    assert select_story_updates([selection('update', '9c157ed1-a605-499f-83c8-c90945d27922')], [item()], [], 3) == []


def test_malformed_ranking_cannot_silently_become_empty_day():
    with pytest.raises(ValueError):
        select_story_updates([{'article_num': 'oops'}], [item()], [], 3)


@pytest.mark.asyncio
async def test_only_covered_chapter_enters_heard_context(db_session):
    from app.services.listening import ListeningService
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session)
    b.listened = True  # Existing five-second/manual flag is not knowledge.
    b.extra_data = {'chapters': [
        {'title': 'First', 'article_index': 0, 'start_time': 0, 'end_time': 50},
        {'title': 'Second', 'article_index': 1, 'start_time': 50, 'end_time': 100}]}
    await svc.save(b, [item(), item(key='Other event', development='Other news')], b.extra_data['chapters'], {})
    await db_session.commit()
    assert all(not s['developments'][0]['heard'] for s in await svc.context('u', 'p1'))
    await ListeningService(db_session).record(b, [[0, 40], [80, 85]])
    contexts = {s['title']: s for s in await svc.context('u', 'p1')}
    assert contexts['Acme launch']['developments'][0]['heard'] is True
    assert contexts['Other event']['developments'][0]['heard'] is False


@pytest.mark.asyncio
async def test_editor_context_bounds_large_evidence_without_losing_recent_summary(db_session):
    import json
    svc = StoryMemoryService(db_session)
    b = await briefing(db_session)
    claims = [{'text': 'A finding ' * 400, 'sources': [
        {'url': 'https://example.com/report', 'title': 'Report', 'excerpt': 'A passage ' * 150} for _ in range(8)]} for _ in range(10)]
    await svc.save(b, [item()], b.extra_data['chapters'], {0: claims})
    await db_session.commit()
    context = await svc.context('u', 'p1')
    assert context[0]['developments'][0]['summary'] == 'Acme will launch in June'
    assert len(json.dumps(context, ensure_ascii=False)) < 32000
