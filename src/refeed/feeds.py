"""Per-tag RSS, Atom, and JSON Feed output.

Item links are the source entry links, unchanged, so a consumer can match
items back to the source feed by URL. Start and end times use the RSS event
module (`ev:startdate`, `ev:enddate`) in RSS and Atom, and a `_refeed`
extension object in JSON Feed.
"""

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from django.views.decorators.http import require_safe

from .models import Tag

EVENT_NS = "http://purl.org/rss/1.0/modules/event/"


def feed_limit():
    return getattr(settings, "REFEED_FEED_LIMIT", 100)


def feed_title(tag):
    prefix = getattr(settings, "REFEED_FEED_TITLE", "Re-Feed")
    return f"{prefix}: {tag.name}"


def tag_entries(tag):
    return tag.entries.select_related("source").newest_first()[: feed_limit()]


def event_value(value, all_day):
    if value is None:
        return None
    return value.date().isoformat() if all_day else value.isoformat()


class EventFeedMixin:
    def add_event_elements(self, handler, item):
        for name in ("startdate", "enddate"):
            if item.get(name):
                handler.addQuickElement(f"ev:{name}", item[name])


class EventRssFeed(EventFeedMixin, Rss201rev2Feed):
    def rss_attributes(self):
        return {**super().rss_attributes(), "xmlns:ev": EVENT_NS}

    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        self.add_event_elements(handler, item)


class EventAtomFeed(EventFeedMixin, Atom1Feed):
    def root_attributes(self):
        return {**super().root_attributes(), "xmlns:ev": EVENT_NS}

    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        self.add_event_elements(handler, item)


class TagRssFeed(Feed):
    feed_type = EventRssFeed

    def get_object(self, request, slug):
        return get_object_or_404(Tag, slug=slug)

    def title(self, tag):
        return feed_title(tag)

    def link(self, tag):
        return reverse("refeed:tag-rss", args=[tag.slug])

    def description(self, tag):
        return feed_title(tag)

    def items(self, tag):
        return tag_entries(tag)

    def item_title(self, entry):
        return entry.title

    def item_description(self, entry):
        return entry.description

    def item_link(self, entry):
        return entry.link

    def item_guid(self, entry):
        return entry.link

    item_guid_is_permalink = True

    def item_pubdate(self, entry):
        return entry.published

    def item_updateddate(self, entry):
        return entry.updated

    def item_extra_kwargs(self, entry):
        return {
            "startdate": event_value(entry.start, entry.all_day),
            "enddate": event_value(entry.end, entry.all_day),
        }


class TagAtomFeed(TagRssFeed):
    feed_type = EventAtomFeed

    def subtitle(self, tag):
        return feed_title(tag)

    def link(self, tag):
        return reverse("refeed:tag-atom", args=[tag.slug])


@require_safe
def tag_json_feed(request, slug):
    """Serve a tag as JSON Feed 1.1 (https://jsonfeed.org/version/1.1)."""
    tag = get_object_or_404(Tag, slug=slug)
    items = []
    for entry in tag_entries(tag):
        item = {
            "id": entry.link,
            "url": entry.link,
            "title": entry.title,
            "content_html": entry.description,
            "_refeed": {
                "source": entry.source.name,
                "start": event_value(entry.start, entry.all_day),
                "end": event_value(entry.end, entry.all_day),
                "all_day": entry.all_day,
                "location": entry.location,
            },
        }
        if entry.published:
            item["date_published"] = entry.published.isoformat()
        items.append(item)
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": feed_title(tag),
        "feed_url": request.build_absolute_uri(),
        "items": items,
    }
    return JsonResponse(feed, content_type="application/feed+json")


tag_rss_feed = require_safe(TagRssFeed())
tag_atom_feed = require_safe(TagAtomFeed())
