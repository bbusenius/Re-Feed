import pytest

from refeed.ingest import fetch, poll_source
from refeed.models import Entry, Tag

from .conftest import LIVEWHALE_URL, RSS_URL


def test_livewhale_poll_follows_pages(responses, livewhale_source):
    result = poll_source(livewhale_source)
    assert (result.fetched, result.created, result.updated, result.unchanged) == (5, 5, 0, 0)
    assert set(livewhale_source.entries.values_list("guid", flat=True)) == {
        "1001",
        "1002",
        "1003",
        "1004",
        "1005",
    }
    livewhale_source.refresh_from_db()
    assert livewhale_source.last_polled_at is not None
    assert livewhale_source.last_error == ""


def test_second_poll_changes_nothing(responses, livewhale_source):
    poll_source(livewhale_source)
    result = poll_source(livewhale_source)
    assert (result.created, result.updated, result.unchanged) == (0, 0, 5)
    assert Entry.objects.count() == 5


def test_poll_updates_changed_entries_and_keeps_tags(responses, livewhale_source):
    poll_source(livewhale_source)
    entry = Entry.objects.get(guid="1001")
    tag = Tag.objects.create(name="Kiosk", slug="kiosk")
    entry.tags.add(tag)

    responses[LIVEWHALE_URL] = (
        responses[LIVEWHALE_URL]
        .replace(b'"2026-10-14 20:00:00"', b'"2026-10-14 21:00:00"')
        .replace(b"Workshop: Data &amp; Maps", b"Workshop: Data and Maps")
    )
    result = poll_source(livewhale_source)

    assert (result.created, result.updated) == (0, 1)
    entry.refresh_from_db()
    assert entry.title == "Workshop: Data and Maps"
    assert entry.end.hour == 21
    assert list(entry.tags.all()) == [tag]


def test_same_guid_in_two_sources_is_two_entries(responses, livewhale_source, rss_source):
    responses[RSS_URL] = responses[RSS_URL].replace(b"news-1", b"1001")
    poll_source(livewhale_source)
    poll_source(rss_source)
    assert Entry.objects.filter(guid="1001").count() == 2


def test_failed_poll_records_error_and_keeps_entries(responses, rss_source):
    poll_source(rss_source)
    del responses[RSS_URL]
    with pytest.raises(OSError):
        poll_source(rss_source)
    rss_source.refresh_from_db()
    assert "no fixture" in rss_source.last_error
    assert rss_source.entries.count() == 3


def test_fetch_refuses_non_http_urls():
    with pytest.raises(ValueError):
        fetch("ftp://example.org/feed.xml")
