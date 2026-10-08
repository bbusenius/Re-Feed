from datetime import datetime, timezone

import pytest

from refeed.parsers import ParseError, livewhale_next_page, parse_livewhale, parse_rss

from .conftest import fixture_bytes, fixture_json


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture
def livewhale():
    entries = parse_livewhale(fixture_json("livewhale_page1.json"))
    entries += parse_livewhale(fixture_json("livewhale_page2.json"))
    return {entry.guid: entry for entry in entries}


def test_livewhale_collapses_per_day_copies_to_one_entry():
    entries = parse_livewhale(fixture_json("livewhale_page1.json"))
    assert [entry.guid for entry in entries] == ["1001", "1002", "1003"]


def test_livewhale_timed_event(livewhale):
    entry = livewhale["1001"]
    assert entry.title == "Workshop: Data & Maps"
    assert entry.link == "https://events.example.edu/event/1001-workshop-data-maps"
    assert entry.location == "Main Library, Room 100"
    assert entry.description == "<p>Bring a laptop.</p>"
    assert (entry.start, entry.end, entry.all_day) == (
        utc(2026, 10, 14, 18),
        utc(2026, 10, 14, 20),
        False,
    )


def test_livewhale_multi_day_timed_span_uses_repeats_fields(livewhale):
    entry = livewhale["1002"]
    assert entry.start == utc(2026, 9, 8, 14)
    assert entry.end == utc(2026, 12, 11, 22, 45)
    assert entry.all_day is False


def test_livewhale_multi_day_all_day_span(livewhale):
    entry = livewhale["1003"]
    assert entry.all_day is True
    assert entry.start == utc(2026, 10, 7)
    # The span ends after the clocks change, at 06:00 UTC, still local midnight.
    assert entry.end == utc(2026, 11, 2)


def test_livewhale_single_all_day_without_repeats(livewhale):
    entry = livewhale["1004"]
    assert (entry.start, entry.end, entry.all_day) == (utc(2026, 11, 26), None, True)


def test_livewhale_event_without_end(livewhale):
    entry = livewhale["1005"]
    assert (entry.start, entry.end, entry.all_day) == (utc(2026, 10, 16, 20), None, False)


def test_livewhale_next_page():
    assert livewhale_next_page(fixture_json("livewhale_page1.json")).endswith("?page=2")
    assert livewhale_next_page(fixture_json("livewhale_page2.json")) is None


def test_livewhale_rejects_response_without_data():
    with pytest.raises(ParseError):
        parse_livewhale({"error": "unknown group"})


def test_rss_entries():
    first, second, third = parse_rss(fixture_bytes("rss.xml"))

    assert first.guid == "news-1"
    assert first.title == "Open house & tours"
    assert first.link == "https://news.example.org/open-house"
    assert first.description == "<p>Tours every hour.</p>"
    assert first.published == utc(2026, 10, 5, 15)
    assert (first.start, first.end, first.all_day) == (
        utc(2026, 10, 20, 15),
        utc(2026, 10, 20, 19),
        False,
    )

    assert second.guid == "https://news.example.org/book-sale"
    assert (second.start, second.end, second.all_day) == (
        utc(2026, 10, 24),
        utc(2026, 10, 25),
        True,
    )

    assert (third.start, third.end, third.all_day) == (None, None, False)


def test_atom_entry_prefers_content_over_summary():
    (entry,) = parse_rss(fixture_bytes("atom.xml"))
    assert entry.guid == "urn:example:blog:1"
    assert entry.link == "https://blog.example.org/highlights"
    assert entry.description == "<p>Full text.</p>"
    assert entry.published == utc(2026, 10, 7, 12)


def test_rss_rejects_non_feed():
    with pytest.raises(ParseError):
        parse_rss(b"<html><body>Not found</body></html")
