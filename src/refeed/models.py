from django.db import models
from django.db.models.functions import Coalesce
from django.urls import reverse


class FeedSource(models.Model):
    """A remote feed that `refeed_poll` reads entries from."""

    FORMAT_RSS = "rss"
    FORMAT_LIVEWHALE = "livewhale"
    FORMAT_CHOICES = [
        (FORMAT_RSS, "RSS or Atom"),
        (FORMAT_LIVEWHALE, "LiveWhale JSON"),
    ]

    name = models.CharField(max_length=200)
    url = models.URLField(
        max_length=1000,
        help_text=(
            "For LiveWhale, use a /live/json/ URL. Add /hide_repeats/true for "
            "one item per event, /response_fields/description,location for "
            "those fields, and /start_date/-60%20days to include multi-day "
            "events that are already running."
        ),
    )
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default=FORMAT_RSS)
    is_active = models.BooleanField(default=True, help_text="Only active sources are polled.")
    last_polled_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_error = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    """A label that groups entries into an output feed."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("refeed:tag-rss", args=[self.slug])


class EntryQuerySet(models.QuerySet):
    def newest_first(self):
        """Order by start time, falling back to published time."""
        return self.annotate(sort_date=Coalesce("start", "published", "created")).order_by(
            "-sort_date", "-id"
        )


class Entry(models.Model):
    """One item from a source feed.

    `refeed_poll` overwrites the source fields on every poll. Polling never
    changes tags.
    """

    source = models.ForeignKey(FeedSource, on_delete=models.CASCADE, related_name="entries")
    guid = models.CharField(max_length=500)
    title = models.CharField(max_length=500)
    link = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=500, blank=True)
    published = models.DateTimeField(null=True, blank=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="entries")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = EntryQuerySet.as_manager()

    class Meta:
        ordering = ["-start", "-id"]
        verbose_name_plural = "entries"
        constraints = [
            models.UniqueConstraint(fields=["source", "guid"], name="refeed_entry_source_guid")
        ]

    def __str__(self):
        return self.title
