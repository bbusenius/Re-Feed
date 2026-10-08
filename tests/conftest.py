import json
from pathlib import Path

import pytest

from refeed.models import FeedSource

FIXTURES = Path(__file__).parent / "fixtures"

LIVEWHALE_URL = "https://events.example.edu/live/json/events/group/Example/hide_repeats/true"
RSS_URL = "https://news.example.org/feed.xml"


def fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


def fixture_json(name):
    return json.loads(fixture_bytes(name))


@pytest.fixture
def responses(monkeypatch):
    """Serve fixture files in place of HTTP. Tests may edit the mapping."""
    pages = {
        LIVEWHALE_URL: fixture_bytes("livewhale_page1.json"),
        LIVEWHALE_URL + "?page=2": fixture_bytes("livewhale_page2.json"),
        RSS_URL: fixture_bytes("rss.xml"),
    }

    def fake_fetch(url):
        if url not in pages:
            raise OSError(f"no fixture for {url}")
        return pages[url]

    monkeypatch.setattr("refeed.ingest.fetch", fake_fetch)
    return pages


@pytest.fixture
def livewhale_source(db):
    return FeedSource.objects.create(
        name="Events", url=LIVEWHALE_URL, format=FeedSource.FORMAT_LIVEWHALE
    )


@pytest.fixture
def rss_source(db):
    return FeedSource.objects.create(name="News", url=RSS_URL, format=FeedSource.FORMAT_RSS)
