import pytest
from django.core.management import CommandError, call_command

from refeed.models import Entry, FeedSource

from .conftest import RSS_URL


def test_poll_command_polls_all_active_sources(responses, livewhale_source, rss_source, capsys):
    FeedSource.objects.create(name="Paused", url="https://example.org/off", is_active=False)
    call_command("refeed_poll")
    out = capsys.readouterr().out
    assert "Events: 5 fetched, 5 created, 0 updated, 0 unchanged" in out
    assert "News: 3 fetched, 3 created, 0 updated, 0 unchanged" in out
    assert "Paused" not in out
    assert Entry.objects.count() == 8


def test_poll_command_second_run_reports_unchanged(responses, livewhale_source, capsys):
    call_command("refeed_poll")
    call_command("refeed_poll")
    assert "Events: 5 fetched, 0 created, 0 updated, 5 unchanged" in capsys.readouterr().out


def test_poll_command_single_source(responses, livewhale_source, rss_source):
    call_command("refeed_poll", "--source", str(rss_source.pk))
    assert set(Entry.objects.values_list("source__name", flat=True)) == {"News"}


def test_poll_command_continues_after_failure_and_exits_nonzero(
    responses, livewhale_source, rss_source
):
    del responses[RSS_URL]
    with pytest.raises(CommandError, match="News"):
        call_command("refeed_poll")
    assert Entry.objects.filter(source=livewhale_source).count() == 5
