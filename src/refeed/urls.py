from django.urls import path

from . import feeds

app_name = "refeed"

urlpatterns = [
    path("tags/<slug:slug>/rss/", feeds.tag_rss_feed, name="tag-rss"),
    path("tags/<slug:slug>/atom/", feeds.tag_atom_feed, name="tag-atom"),
    path("tags/<slug:slug>/json/", feeds.tag_json_feed, name="tag-json"),
]
