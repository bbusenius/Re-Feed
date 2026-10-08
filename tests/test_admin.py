import pytest
from django.contrib.auth.models import Permission, User

from refeed.ingest import poll_source
from refeed.models import Entry, FeedSource, Tag

CHANGELIST = "/admin/refeed/entry/"


@pytest.fixture
def entries(responses, livewhale_source):
    poll_source(livewhale_source)
    return Entry.objects.order_by("guid")


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="Kiosk", slug="kiosk")


def tag_action(client, entries, tag):
    return client.post(
        CHANGELIST,
        {
            "action": "add_tag",
            "tag": tag.pk,
            "_selected_action": [entry.pk for entry in entries[:2]],
        },
    )


def make_staff(*codenames):
    user = User.objects.create_user("editor", password="pw", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    return user


def test_anonymous_tagging_is_redirected_to_login(client, entries, tag):
    response = tag_action(client, entries, tag)
    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")
    assert tag.entries.count() == 0


def test_staff_without_permission_cannot_tag(client, entries, tag):
    client.force_login(make_staff())
    response = tag_action(client, entries, tag)
    assert response.status_code == 403
    assert tag.entries.count() == 0


def test_view_permission_does_not_allow_tagging(client, entries, tag):
    client.force_login(make_staff("view_entry"))
    tag_action(client, entries, tag)
    assert tag.entries.count() == 0


def test_editor_with_change_permission_can_tag(client, entries, tag):
    client.force_login(make_staff("view_entry", "change_entry"))
    response = tag_action(client, entries, tag)
    assert response.status_code == 302
    assert set(tag.entries.values_list("guid", flat=True)) == {"1001", "1002"}


def test_change_form_edits_only_tags(client, entries, tag, admin_user):
    client.force_login(admin_user)
    entry = entries[0]
    response = client.post(
        f"/admin/refeed/entry/{entry.pk}/change/",
        {"tags": [tag.pk], "title": "Edited"},
    )
    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.title != "Edited"
    assert list(entry.tags.all()) == [tag]


def test_entries_cannot_be_added_by_hand(client, admin_user, db):
    client.force_login(admin_user)
    assert client.get("/admin/refeed/entry/add/").status_code == 403


def test_poll_action_requires_change_permission(client, responses, livewhale_source):
    client.force_login(make_staff("view_feedsource"))
    client.post(
        "/admin/refeed/feedsource/",
        {"action": "poll_now", "_selected_action": [livewhale_source.pk]},
    )
    assert Entry.objects.count() == 0

    client.force_login(make_staff_with_change())
    client.post(
        "/admin/refeed/feedsource/",
        {"action": "poll_now", "_selected_action": [livewhale_source.pk]},
    )
    assert Entry.objects.count() == 5


def make_staff_with_change():
    user = User.objects.create_user("manager", password="pw", is_staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(codename__in=["view_feedsource", "change_feedsource"])
    )
    return user


def test_no_source_is_created_by_anonymous_post(client, db):
    response = client.post(
        "/admin/refeed/feedsource/add/",
        {"name": "x", "url": "https://example.org/feed", "format": "rss", "is_active": "on"},
    )
    assert response.status_code == 302
    assert FeedSource.objects.count() == 0
