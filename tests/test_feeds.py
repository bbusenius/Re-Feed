import json
import xml.etree.ElementTree as ET

import pytest

from refeed.ingest import poll_source
from refeed.models import Entry, Tag

ATOM = "{http://www.w3.org/2005/Atom}"
EV = "{http://purl.org/rss/1.0/modules/event/}"

TAGGED_GUIDS = ["1001", "1002", "1003"]


@pytest.fixture
def kiosk_tag(responses, livewhale_source):
    poll_source(livewhale_source)
    tag = Tag.objects.create(name="Kiosk", slug="kiosk")
    tag.entries.add(*Entry.objects.filter(guid__in=TAGGED_GUIDS))
    return tag


def tagged_links():
    return {entry.link for entry in Entry.objects.filter(guid__in=TAGGED_GUIDS)}


def test_rss_feed(client, kiosk_tag):
    response = client.get("/feeds/tags/kiosk/rss/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/rss+xml")
    items = ET.fromstring(response.content).find("channel").findall("item")
    assert {item.findtext("link") for item in items} == tagged_links()
    assert {item.findtext("guid") for item in items} == tagged_links()

    span = next(
        item
        for item in items
        if item.findtext("link").startswith("https://events.example.edu/event/1002")
    )
    assert span.findtext(f"{EV}startdate") == "2026-09-08T14:00:00+00:00"
    assert span.findtext(f"{EV}enddate") == "2026-12-11T22:45:00+00:00"


def test_atom_feed_first_link_is_event_url(client, kiosk_tag):
    response = client.get("/feeds/tags/kiosk/atom/")
    assert response.status_code == 200
    root = ET.fromstring(response.content)
    # Same lookup a link matcher does: the first link element of each entry.
    links = {entry.find(f"{ATOM}link").get("href") for entry in root.findall(f"{ATOM}entry")}
    assert links == tagged_links()

    all_day = next(
        entry
        for entry in root.findall(f"{ATOM}entry")
        if entry.find(f"{ATOM}link").get("href").endswith("1003-reading-week")
    )
    assert all_day.findtext(f"{EV}startdate") == "2026-10-07"
    assert all_day.findtext(f"{EV}enddate") == "2026-11-02"


def test_json_feed(client, kiosk_tag):
    response = client.get("/feeds/tags/kiosk/json/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/feed+json"
    feed = json.loads(response.content)
    assert feed["version"] == "https://jsonfeed.org/version/1.1"
    assert feed["title"] == "Re-Feed: Kiosk"
    assert {item["url"] for item in feed["items"]} == tagged_links()
    by_url = {item["url"]: item["_refeed"] for item in feed["items"]}
    assert by_url["https://events.example.edu/event/1003-reading-week"] == {
        "source": "Events",
        "start": "2026-10-07",
        "end": "2026-11-02",
        "all_day": True,
        "location": "",
    }


def test_feed_is_newest_first(client, kiosk_tag):
    feed = json.loads(client.get("/feeds/tags/kiosk/json/").content)
    starts = [item["_refeed"]["start"] for item in feed["items"]]
    assert starts == ["2026-10-14T18:00:00+00:00", "2026-10-07", "2026-09-08T14:00:00+00:00"]


def test_feed_limit(client, kiosk_tag, settings):
    settings.REFEED_FEED_LIMIT = 1
    feed = json.loads(client.get("/feeds/tags/kiosk/json/").content)
    assert len(feed["items"]) == 1


@pytest.mark.parametrize("kind", ["rss", "atom", "json"])
def test_unknown_tag_is_404(client, db, kind):
    assert client.get(f"/feeds/tags/missing/{kind}/").status_code == 404


@pytest.mark.parametrize("kind", ["rss", "atom", "json"])
def test_feeds_reject_writes(client, kiosk_tag, kind):
    assert client.post(f"/feeds/tags/kiosk/{kind}/").status_code == 405
