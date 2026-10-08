"""Convert source documents into `ParsedEntry` values.

Parsers take bytes or decoded JSON and never touch the network or the
database, so tests can feed them fixtures directly.
"""

import calendar
import html
from dataclasses import dataclass
from datetime import datetime, time
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import feedparser
from django.utils.dateparse import parse_date, parse_datetime


@dataclass
class ParsedEntry:
    guid: str
    title: str
    link: str
    description: str = ""
    location: str = ""
    published: datetime | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False


class ParseError(Exception):
    pass


def parse_rss(content):
    """Parse an RSS or Atom document.

    Start and end times come from the RSS event module elements
    `ev:startdate` and `ev:enddate` when present. A date with no time
    marks the entry as all-day.
    """
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise ParseError(f"Not a readable RSS or Atom feed: {feed.bozo_exception}")

    entries = []
    for item in feed.entries:
        link = item.get("link", "")
        guid = item.get("id") or link
        if not guid or not link:
            continue
        start, start_is_date = _parse_iso(item.get("ev_startdate"))
        end, end_is_date = _parse_iso(item.get("ev_enddate"))
        entries.append(
            ParsedEntry(
                guid=guid,
                title=item.get("title", ""),
                link=link,
                description=_rss_description(item),
                published=_struct_to_datetime(
                    item.get("published_parsed") or item.get("updated_parsed")
                ),
                start=start,
                end=end,
                all_day=start_is_date and (end is None or end_is_date),
            )
        )
    return entries


def parse_livewhale(data):
    """Parse one page of a LiveWhale `/live/json/` events response.

    LiveWhale lists a multi-day event once per day as an all-day item. Each
    copy carries the full span in `repeats_start` and `repeats_end`, so every
    copy of one event id parses to the same entry. Times in the `*_utc` and
    `repeats_*` fields are UTC.

    An entry is all-day when LiveWhale flags the item as all-day and the span
    starts and ends at local midnight. All-day `start` and `end` hold the
    first and last local day at midnight UTC.
    """
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ParseError("LiveWhale response has no data list.")

    entries = {}
    for item in items:
        if not item.get("id") or not item.get("url"):
            continue
        if item.get("repeats_start"):
            start = _parse_utc(item["repeats_start"])
            end = _parse_utc(item.get("repeats_end"))
        else:
            start = _parse_utc(item.get("date_utc"))
            end = _parse_utc(item.get("date2_utc"))
        tz = _zone(item.get("timezone"))
        all_day = bool(item.get("is_all_day")) and all(
            _is_local_midnight(value, tz) for value in (start, end) if value
        )
        if all_day:
            start = _utc_midnight(start, tz)
            end = _utc_midnight(end, tz)
        entries[str(item["id"])] = ParsedEntry(
            guid=str(item["id"]),
            title=html.unescape(item.get("title") or ""),
            link=item["url"],
            description=item.get("description") or "",
            location=html.unescape(item.get("location") or ""),
            start=start,
            end=end,
            all_day=all_day,
        )
    return list(entries.values())


def livewhale_next_page(data):
    """Return the URL of the next page, or None on the last page."""
    if isinstance(data, dict):
        return (data.get("links") or {}).get("next")
    return None


def _rss_description(item):
    if item.get("content"):
        return item["content"][0].get("value", "")
    return item.get("summary", "")


def _struct_to_datetime(value):
    if not value:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), tz=dt_timezone.utc)


def _parse_iso(value):
    """Return `(datetime, is_date_only)` for an ISO 8601 date or datetime."""
    if not value:
        return None, False
    value = value.strip()
    try:
        day = parse_date(value)
        parsed = None if day else parse_datetime(value)
    except ValueError:
        return None, False
    if day:
        return datetime.combine(day, time.min, tzinfo=dt_timezone.utc), True
    if parsed is None:
        return None, False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed, False


def _parse_utc(value):
    if not value:
        return None
    try:
        parsed = parse_datetime(value)
    except ValueError:
        return None
    if parsed is None:
        return None
    return parsed.replace(tzinfo=dt_timezone.utc)


def _zone(name):
    try:
        return ZoneInfo(name) if name else dt_timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        return dt_timezone.utc


def _is_local_midnight(value, tz):
    local = value.astimezone(tz)
    return local.time() == time.min


def _utc_midnight(value, tz):
    if value is None:
        return None
    return datetime.combine(value.astimezone(tz).date(), time.min, tzinfo=dt_timezone.utc)
