import pytest
from django.conf import settings

from refeed.ingest import poll_source
from refeed.models import Entry, Tag

pytestmark = pytest.mark.skipif(not settings.WAGTAIL_INSTALLED, reason="Wagtail is not installed")


@pytest.fixture
def entry(responses, livewhale_source):
    poll_source(livewhale_source)
    return Entry.objects.get(guid="1002")


def edit_url(entry):
    return f"/cms/snippets/refeed/entry/edit/{entry.pk}/"


def test_snippets_are_registered():
    from wagtail.snippets.models import get_snippet_models

    assert {Entry, Tag} <= set(get_snippet_models())


def test_editor_tags_an_entry(client, admin_user, entry):
    tag = Tag.objects.create(name="Kiosk", slug="kiosk")
    client.force_login(admin_user)
    assert client.get(edit_url(entry)).status_code == 200

    response = client.post(edit_url(entry), {"tags": [tag.pk], "title": "Edited"})
    assert response.status_code == 302
    entry.refresh_from_db()
    assert list(entry.tags.all()) == [tag]
    assert entry.title == "Exhibition: Paper Trails"


def test_anonymous_edit_is_redirected_to_login(client, entry):
    tag = Tag.objects.create(name="Kiosk", slug="kiosk")
    response = client.post(edit_url(entry), {"tags": [tag.pk]})
    assert response.status_code == 302
    assert "/login/" in response["Location"]
    assert entry.tags.count() == 0


def test_entries_cannot_be_added(client, admin_user, db):
    client.force_login(admin_user)
    response = client.get("/cms/snippets/refeed/entry/add/")
    assert response.status_code in (302, 403)
