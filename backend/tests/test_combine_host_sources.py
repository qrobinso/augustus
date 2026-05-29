from app.services.web_research import combine_host_sources


def test_combine_dedupes_by_url_and_unions_found_by():
    a = [{"title": "X", "url": "http://x.com", "found_by": ["Alex"]}]
    b = [
        {"title": "X dup", "url": "http://x.com", "found_by": ["Sam"]},
        {"title": "Y", "url": "http://y.com", "found_by": ["Sam"]},
    ]
    merged = combine_host_sources([a, b])
    by_url = {s["url"]: s for s in merged}
    assert sorted(by_url["http://x.com"]["found_by"]) == ["Alex", "Sam"]
    assert by_url["http://y.com"]["found_by"] == ["Sam"]
    assert len(merged) == 2


def test_combine_preserves_order_first_seen():
    a = [{"title": "A", "url": "http://a.com", "found_by": ["Alex"]}]
    b = [{"title": "B", "url": "http://b.com", "found_by": ["Sam"]}]
    merged = combine_host_sources([a, b])
    assert [s["url"] for s in merged] == ["http://a.com", "http://b.com"]
