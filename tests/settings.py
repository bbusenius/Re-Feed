import importlib.util

from django.core.management.utils import get_random_secret_key

SECRET_KEY = get_random_secret_key()
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
USE_TZ = True
TIME_ZONE = "UTC"
ROOT_URLCONF = "tests.urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "refeed",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

STATIC_URL = "/static/"

WAGTAIL_INSTALLED = importlib.util.find_spec("wagtail") is not None

if WAGTAIL_INSTALLED:
    INSTALLED_APPS += [
        "refeed.contrib.wagtail",
        "wagtail.snippets",
        "wagtail.documents",
        "wagtail.images",
        "wagtail.users",
        "wagtail.admin",
        "wagtail",
        "modelcluster",
        "taggit",
    ]
    WAGTAIL_SITE_NAME = "Test"
    WAGTAILADMIN_BASE_URL = "http://testserver"
