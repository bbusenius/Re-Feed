"""Fetch sources and upsert their entries."""

import json
import urllib.request
from dataclasses import asdict, dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import __version__
from .models import Entry, FeedSource
from .parsers import livewhale_next_page, parse_livewhale, parse_rss

UPDATABLE_FIELDS = [
    "title",
    "link",
    "description",
    "location",
    "published",
    "start",
    "end",
    "all_day",
]

# Upper bound on LiveWhale pages read in one poll, in case `links.next` loops.
MAX_PAGES = 50


@dataclass
class PollResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def fetch(url):
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(f"Only http and https URLs can be fetched: {url}")
    timeout = getattr(settings, "REFEED_HTTP_TIMEOUT", 30)
    user_agent = getattr(settings, "REFEED_USER_AGENT", f"django-refeed/{__version__}")
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def read_source(source):
    """Fetch and parse every entry a source currently lists."""
    if source.format == FeedSource.FORMAT_LIVEWHALE:
        entries = {}
        url = source.url
        for _ in range(MAX_PAGES):
            data = json.loads(fetch(url))
            for entry in parse_livewhale(data):
                entries[entry.guid] = entry
            url = livewhale_next_page(data)
            if not url:
                break
        return list(entries.values())
    return parse_rss(fetch(source.url))


def save_entries(source, parsed_entries):
    """Create new entries and update changed ones. Tags are left alone."""
    result = PollResult(fetched=len(parsed_entries))
    existing = {entry.guid: entry for entry in source.entries.all()}
    with transaction.atomic():
        for parsed in parsed_entries:
            values = asdict(parsed)
            guid = values.pop("guid")[:500]
            values["title"] = values["title"][:500]
            values["location"] = values["location"][:500]
            entry = existing.get(guid)
            if entry is None:
                existing[guid] = Entry.objects.create(source=source, guid=guid, **values)
                result.created += 1
                continue
            changed = [name for name in UPDATABLE_FIELDS if getattr(entry, name) != values[name]]
            if changed:
                for name in changed:
                    setattr(entry, name, values[name])
                entry.save(update_fields=[*changed, "updated"])
                result.updated += 1
            else:
                result.unchanged += 1
    return result


def poll_source(source):
    """Poll one source and record the time and any error on it."""
    source.last_polled_at = timezone.now()
    try:
        result = save_entries(source, read_source(source))
    except Exception as exc:
        source.last_error = f"{type(exc).__name__}: {exc}"
        source.save(update_fields=["last_polled_at", "last_error"])
        raise
    source.last_error = ""
    source.save(update_fields=["last_polled_at", "last_error"])
    return result
