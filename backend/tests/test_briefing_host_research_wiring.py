from app.services.briefing import BriefingService


def test_merge_host_sources_into_briefing_sources():
    svc = BriefingService.__new__(BriefingService)  # no __init__ (no providers needed)
    editor = [{"title": "Editor A", "url": "http://a.com"}]
    host = [{"title": "A dup", "url": "http://a.com", "found_by": ["Alex"]},
            {"title": "Host B", "url": "http://b.com", "found_by": ["Sam"]}]
    merged = svc._merge_sources_for_storage(editor, host)
    by_url = {s["url"]: s for s in merged}
    assert by_url["http://a.com"]["found_by"] == ["Alex"]   # editor source gains attribution
    assert by_url["http://b.com"]["found_by"] == ["Sam"]
    assert len(merged) == 2
