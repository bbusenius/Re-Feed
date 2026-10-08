from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("feeds/", include("refeed.urls")),
]

if settings.WAGTAIL_INSTALLED:
    from wagtail.admin import urls as wagtailadmin_urls

    urlpatterns.append(path("cms/", include(wagtailadmin_urls)))
