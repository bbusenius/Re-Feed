"""Register Re-Feed models as Wagtail snippets.

Add `refeed.contrib.wagtail` to `INSTALLED_APPS` after `refeed` to get a
"Re-Feed" menu in the Wagtail admin. Wagtail's snippet permissions apply,
so editors need the matching `refeed` model permissions.
"""

from wagtail.admin.panels import FieldPanel
from wagtail.permission_policies import ModelPermissionPolicy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from refeed.models import Entry, FeedSource, Tag


class FeedSourceViewSet(SnippetViewSet):
    model = FeedSource
    icon = "link"
    list_display = ["name", "format", "is_active", "last_polled_at", "last_error"]
    list_filter = ["format", "is_active"]
    search_fields = ["name", "url"]
    panels = [
        FieldPanel("name"),
        FieldPanel("url"),
        FieldPanel("format"),
        FieldPanel("is_active"),
    ]


class TagViewSet(SnippetViewSet):
    model = Tag
    icon = "tag"
    list_display = ["name", "slug"]
    search_fields = ["name"]
    panels = [FieldPanel("name"), FieldPanel("slug")]


class EntryPermissionPolicy(ModelPermissionPolicy):
    """Entries come only from polling, so nobody can add one by hand."""

    def user_has_permission(self, user, action):
        return action != "add" and super().user_has_permission(user, action)


class EntryViewSet(SnippetViewSet):
    model = Entry
    icon = "list-ul"
    list_display = ["title", "source", "start", "end", "all_day"]
    list_filter = ["source", "tags", "all_day"]
    search_fields = ["title"]
    # Polling overwrites every field except tags.
    panels = [
        FieldPanel("tags"),
        FieldPanel("title", read_only=True),
        FieldPanel("link", read_only=True),
        FieldPanel("source", read_only=True),
        FieldPanel("start", read_only=True),
        FieldPanel("end", read_only=True),
        FieldPanel("all_day", read_only=True),
        FieldPanel("location", read_only=True),
    ]


class RefeedViewSetGroup(SnippetViewSetGroup):
    menu_label = "Re-Feed"
    menu_icon = "list-ul"
    items = [EntryViewSet, TagViewSet, FeedSourceViewSet]


try:
    from wagtail.permissions import register_permission_policy
except ImportError:
    # Wagtail before 7.1 reads the policy from the viewset.
    EntryViewSet.permission_policy = EntryPermissionPolicy(Entry)
else:
    register_permission_policy(Entry, EntryPermissionPolicy(Entry))

register_snippet(RefeedViewSetGroup)
