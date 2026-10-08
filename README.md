# Re-Feed

Re-Feed is a Django app that reads RSS, Atom, and LiveWhale event feeds into your database. Editors tag entries, and Re-Feed publishes each tag as an RSS, Atom, and JSON feed. Item links in the output point at the original source items, so a consumer can match a tagged item back to its source by URL.

Re-Feed runs inside your Django project. It has no server, database, or login of its own. It works with the Django admin, and it has an optional Wagtail admin integration.

## Requirements

- Python 3.10 or later
- Django 4.2 or later, with `USE_TZ = True`
- Wagtail 6.3 or later, only for the Wagtail integration

## Install the app

1. From a clone of this repository, install the package into your project's environment:

	```sh
	pip install .
	```

	To include the Wagtail integration, install the `wagtail` extra with `pip install ".[wagtail]"`.

2. Add `refeed` to `INSTALLED_APPS`. The Django admin needs `django.contrib.admin` and its usual dependencies.

	```python
	INSTALLED_APPS = [
		# ...
		"refeed",
	]
	```

3. Add the feed URLs to your root URLconf:

	```python
	from django.urls import include, path

	urlpatterns = [
		# ...
		path("refeed/", include("refeed.urls")),
	]
	```

4. Create the tables:

	```sh
	python manage.py migrate refeed
	```

Re-Feed does not set `SECRET_KEY` or any other project setting. Your project supplies them.

## Add a feed source

In the Django admin, open **Re-Feed > Feed sources** and add a source with a name, a URL, and a format.

- **RSS or Atom** reads any feed that feedparser can parse.
- **LiveWhale JSON** reads a LiveWhale `/live/json/events/...` URL.

For a LiveWhale group, build the URL from these path segments:

- `/hide_repeats/true` returns one item per event instead of one item per day.
- `/response_fields/description,location` adds the description and location. LiveWhale leaves them out by default.
- `/start_date/-60 days` includes multi-day events that started before today. Without it, LiveWhale returns only events from today onward. Encode the space as `%20`.

For example, this URL reads the Library group from the University of Chicago calendar:

```
https://events.uchicago.edu/live/json/events/group/Library/hide_repeats/true/response_fields/description,location/start_date/-60%20days
```

Re-Feed follows `links.next` when a LiveWhale response has more than one page.

## Poll the sources from cron

The `refeed_poll` management command fetches every active source and saves new and changed entries:

```sh
python manage.py refeed_poll
```

It prints one line per source, for example `Events: 41 fetched, 0 created, 2 updated, 39 unchanged`. If a source fails, the command records the error on the source, polls the remaining sources, and exits with status 1. To poll specific sources, pass `--source ID` once for each source.

This crontab line polls every 15 minutes. Replace `<project-dir>` and `<venv>` with your project directory and virtual environment.

```
*/15 * * * * cd <project-dir> && <venv>/bin/python manage.py refeed_poll
```

Each poll updates the title, link, description, location, published time, start, end, and all-day flag of existing entries. Polling never changes tags. Entries that disappear from a source stay in the database.

To poll a source from the admin, select it in **Feed sources** and run **Poll selected sources now**.

## Tag entries

Create tags in **Re-Feed > Tags**. A tag's slug is the last part of its feed URLs.

To tag entries in bulk, open **Re-Feed > Entries**, select the entries, choose a tag in the action bar, and run **Add the chosen tag to selected entries**. To tag one entry, open it and edit its tags. The other entry fields are read-only, because polling overwrites them.

Tagging needs the `refeed.change_entry` permission. Adding and changing sources needs the `refeed` feed source permissions.

## Read the tag feeds

Each tag has three public, read-only feeds. With the URLconf above and a tag with the slug `kiosk`:

| Format | URL |
| --- | --- |
| RSS 2.0 | `/refeed/tags/kiosk/rss/` |
| Atom | `/refeed/tags/kiosk/atom/` |
| JSON Feed 1.1 | `/refeed/tags/kiosk/json/` |

In every format, the item link is the source item's link. In Atom, the link is the first `<link href>` of each `<entry>`. RSS `<guid>` and Atom `<id>` are the same link.

RSS and Atom items carry the start and end as `ev:startdate` and `ev:enddate` from the RSS event module (`http://purl.org/rss/1.0/modules/event/`). JSON Feed items carry them in a `_refeed` object with `start`, `end`, `all_day`, `location`, and `source`. All-day values are dates, such as `2026-10-07`. Other values are ISO 8601 datetimes in UTC.

Feeds list entries by start time, newest first. Entries without a start time sort by their published time.

The feed views accept only GET and HEAD.

## Use the Wagtail admin

To manage Re-Feed in the Wagtail admin, add `refeed.contrib.wagtail` after `refeed`:

```python
INSTALLED_APPS = [
	# ...
	"refeed",
	"refeed.contrib.wagtail",
]
```

A **Re-Feed** menu appears with entries, tags, and feed sources as snippets. Wagtail checks the same `refeed` model permissions as the Django admin. Neither admin lets anyone add entries by hand.

The `refeed` app itself never imports Wagtail.

## Settings

All settings are optional.

| Setting | Default | Meaning |
| --- | --- | --- |
| `REFEED_FEED_LIMIT` | `100` | Maximum number of items in each tag feed. |
| `REFEED_FEED_TITLE` | `"Re-Feed"` | Prefix of each feed title. A tag named Kiosk gets the title `Re-Feed: Kiosk`. |
| `REFEED_HTTP_TIMEOUT` | `30` | Seconds to wait for a source to respond. |
| `REFEED_USER_AGENT` | `"django-refeed/<version>"` | `User-Agent` header sent to sources. |

## How LiveWhale items become entries

- The entry guid is the LiveWhale event id. The entry link is the item `url`.
- LiveWhale lists a multi-day event once per day as an all-day item. Every copy holds the full span in `repeats_start` and `repeats_end`, so Re-Feed saves one entry with that span.
- When `repeats_start` is empty, the span comes from `date_utc` and `date2_utc`.
- An entry is all-day when LiveWhale marks the item all-day and the span starts and ends at midnight in the event's time zone. For all-day entries, `start` and `end` hold the first and last day.
- HTML entities in titles and locations are decoded.

For RSS and Atom sources, the guid is the item id, or the link when the item has no id. Start and end come from `ev:startdate` and `ev:enddate` when present. A date with no time marks the entry as all-day.

## Run the tests

```sh
pip install -e ".[test]"
pytest
```

The tests read fixture files and make no network requests. With Wagtail installed, the suite also tests the Wagtail integration.
