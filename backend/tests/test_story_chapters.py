from app.services.briefing import BriefingService


def test_numbered_chapters_keep_identity_when_titles_are_rewritten():
    svc = BriefingService.__new__(BriefingService)
    script = 'Alex: Intro.\n[CHAPTER: 2 | Changed plans]\nAlex: The launch moved.\n[CHAPTER: 1 | New chips]\nSam: Chips arrived.'
    chapters = svc._extract_chapters(script)
    assert [ch['article_index'] for ch in chapters] == [1, 0]
    assert [ch['title'] for ch in chapters] == ['Changed plans', 'New chips']
    timings = [
        {'text': 'Intro.', 'start_seconds': 0, 'end_seconds': 10},
        {'text': 'The launch moved.', 'start_seconds': 10, 'end_seconds': 30},
        {'text': 'Chips arrived.', 'start_seconds': 30, 'end_seconds': 50},
    ]
    mapped = svc._map_chapters_to_timestamps(chapters, script, timings, 50)
    assert [(ch['article_index'], ch['start_time'], ch['end_time']) for ch in mapped] == [(1, 10, 30), (0, 30, 50)]


def test_legacy_markers_never_invent_story_association():
    svc = BriefingService.__new__(BriefingService)
    chapters = svc._extract_chapters('[CHAPTER: Intro]\nAlex: Hello.')
    assert 'article_index' not in chapters[0]


def test_marker_inside_a_spoken_turn_does_not_credit_the_whole_turn():
    svc = BriefingService.__new__(BriefingService)
    script = 'Alex: An unrelated introduction.\n[CHAPTER: 1 | Launch]\nThe launch moved.'
    chapters = svc._extract_chapters(script)
    timings = [{'text': 'An unrelated introduction.\n\nThe launch moved.', 'start_seconds': 0, 'end_seconds': 100}]
    mapped = svc._map_chapters_to_timestamps(chapters, script, timings, 100)
    assert 'article_index' not in mapped[0]


def test_estimated_next_boundary_cannot_credit_previous_story():
    svc = BriefingService.__new__(BriefingService)
    script = '[CHAPTER: 1 | First]\nAlex: First story.\n[CHAPTER: 2 | Second]\nSecond story continues at length.'
    chapters = svc._extract_chapters(script)
    timings = [{'text': 'First story.\n\nSecond story continues at length.', 'start_seconds': 0, 'end_seconds': 100}]
    mapped = svc._map_chapters_to_timestamps(chapters, script, timings, 100)
    assert all('article_index' not in chapter for chapter in mapped)
