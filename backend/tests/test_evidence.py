import json
import pytest
from app.services.evidence import attribute_claims, collect_claims
from app.services.llm.agents.host_research import HostResearchAgent
from app.services.llm.base import LLMResponse
from tests.conftest import FakeLLM

SOURCES = [{'url': 'https://source.test/report', 'title': 'Report', 'snippet': 'The launch moved from June to July.', 'story_index': 0}]


def test_invented_urls_and_quotes_do_not_become_support():
    claims = attribute_claims([
        {'answer': 'Launch moved.', 'evidence': [{'url': 'https://invented.test', 'excerpt': 'The launch moved from June to July.'}]},
        {'answer': 'Launch cancelled.', 'evidence': [{'url': 'https://source.test/report', 'excerpt': 'The launch was cancelled.'}]},
        {'answer': 'Launch moved to July.', 'evidence': [{'url': 'https://source.test/report', 'excerpt': 'The launch moved from June to July.'}]},
    ], SOURCES, 'Alex')
    assert [c['attribution'] for c in claims] == ['unverified', 'unverified', 'supported']
    assert claims[0]['sources'] == []
    assert claims[2]['sources'][0]['url'] == 'https://source.test/report'
    assert claims[2]['found_by'] == ['Alex']


def test_legacy_facts_remain_explicitly_unverified():
    claims = attribute_claims([{'answer': 'A number without a citation'}], SOURCES, 'Sam')
    assert claims[0]['attribution'] == 'unverified'


@pytest.mark.asyncio
async def test_online_claim_retains_its_own_source_not_every_host_source():
    response = LLMResponse(content=json.dumps({'questions_and_answers': [
        {'question': 'When?', 'answer': 'July', 'evidence': [
            {'url': 'https://source.test/report', 'excerpt': 'The launch moved from June to July.'}]}]}),
        model='fake', usage={}, annotations=[{'url_citation': {'url': 'https://source.test/report',
            'title': 'Report', 'content': 'The launch moved from June to July.'}}])
    research = await HostResearchAgent(FakeLLM(response), use_web_plugin=True).research(
        [{'title': 'Launch', 'url': 'https://news.test', 'summary': 'Date moved'}], 'Alex', 'Analytical')
    claims = collect_claims([research])
    assert claims[0][0]['sources'][0]['excerpt'] == 'The launch moved from June to July.'
    assert claims[0][0]['text'] == 'July'


def test_writer_receives_evidence_and_marks_unattributed_notes():
    from app.services.llm.agents.host_research import HostResearch
    from app.services.llm.agents.briefing_writer import build_host_research_section
    research = HostResearch('Alex', 'Analytical', 'Data', {0: ['Question: When?\nAnswer: July']}, SOURCES,
        {0: attribute_claims([{'answer': 'July', 'evidence': [{'url': 'https://source.test/report',
           'excerpt': 'The launch moved from June to July.'}]}], SOURCES, 'Alex')})
    prompt = build_host_research_section([research], [{'title': 'Launch'}])
    assert 'https://source.test/report' in prompt
    assert 'The launch moved from June to July.' in prompt
    legacy = HostResearch('Sam', 'Casual', 'Casual', {0: ['Question: How much?\nAnswer: 999']})
    assert 'unverified' in build_host_research_section([legacy], []).lower()
