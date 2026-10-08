from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .ingest import poll_source
from .models import Entry, FeedSource, Tag


@admin.register(FeedSource)
class FeedSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "format", "is_active", "entry_count", "last_polled_at", "last_error"]
    list_filter = ["format", "is_active"]
    search_fields = ["name", "url"]
    readonly_fields = ["last_polled_at", "last_error"]
    actions = ["poll_now"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_entries=Count("entries"))

    @admin.display(description="Entries", ordering="num_entries")
    def entry_count(self, source):
        return source.num_entries

    @admin.action(description="Poll selected sources now", permissions=["change"])
    def poll_now(self, request, queryset):
        for source in queryset:
            try:
                result = poll_source(source)
            except Exception as exc:
                self.message_user(request, f"{source}: {exc}", messages.ERROR)
            else:
                self.message_user(
                    request,
                    f"{source}: {result.fetched} fetched, {result.created} created, "
                    f"{result.updated} updated.",
                )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "entry_count", "feed_links"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_entries=Count("entries"))

    @admin.display(description="Entries", ordering="num_entries")
    def entry_count(self, tag):
        return tag.num_entries

    @admin.display(description="Feeds")
    def feed_links(self, tag):
        return format_html(
            '<a href="{}">RSS</a> | <a href="{}">Atom</a> | <a href="{}">JSON</a>',
            reverse("refeed:tag-rss", args=[tag.slug]),
            reverse("refeed:tag-atom", args=[tag.slug]),
            reverse("refeed:tag-json", args=[tag.slug]),
        )


class TagActionForm(ActionForm):
    tag = forms.ModelChoiceField(Tag.objects.all(), required=False)


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ["title", "source", "start", "end", "all_day", "tag_names"]
    list_filter = ["source", "tags", "all_day"]
    search_fields = ["title", "description", "location"]
    date_hierarchy = "start"
    filter_horizontal = ["tags"]
    action_form = TagActionForm
    actions = ["add_tag", "remove_tag"]
    fields = [
        "tags",
        "title",
        "link",
        "source",
        "guid",
        "start",
        "end",
        "all_day",
        "location",
        "published",
        "description",
    ]
    # Polling overwrites these fields, so editors change only the tags.
    readonly_fields = [name for name in fields if name != "tags"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("source").prefetch_related("tags")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Tags")
    def tag_names(self, entry):
        return ", ".join(tag.name for tag in entry.tags.all())

    def _selected_tag(self, request):
        try:
            tag = TagActionForm.base_fields["tag"].clean(request.POST.get("tag"))
        except ValidationError:
            tag = None
        if tag is None:
            self.message_user(request, "Choose a tag first.", messages.WARNING)
        return tag

    @admin.action(description="Add the chosen tag to selected entries", permissions=["change"])
    def add_tag(self, request, queryset):
        tag = self._selected_tag(request)
        if tag:
            tag.entries.add(*queryset)
            self.message_user(request, f"Tagged {queryset.count()} entries with {tag}.")

    @admin.action(description="Remove the chosen tag from selected entries", permissions=["change"])
    def remove_tag(self, request, queryset):
        tag = self._selected_tag(request)
        if tag:
            tag.entries.remove(*queryset)
            self.message_user(request, f"Removed {tag} from {queryset.count()} entries.")
