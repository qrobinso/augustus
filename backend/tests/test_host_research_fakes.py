import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch


@pytest.mark.asyncio
async def test_fakellm_returns_responses_in_sequence():
    fake = FakeLLM(response_content=["first", "second"])
    r1 = await fake.generate(prompt="a")
    r2 = await fake.generate(prompt="b")
    r3 = await fake.generate(prompt="c")  # exhausted -> repeats last
    assert (r1.content, r2.content, r3.content) == ("first", "second", "second")


@pytest.mark.asyncio
async def test_fakesearch_records_queries_and_returns_results():
    fake = FakeSearch(results=[SearchResult("T", "http://x.com", "s")])
    res = await fake.search("query one", num_results=3)
    content = await fake.fetch_page_content("http://x.com")
    assert fake.queries == ["query one"]
    assert res[0].url == "http://x.com"
    assert len(content) > 200
