from django.core.management.base import BaseCommand, CommandError

from refeed.ingest import poll_source
from refeed.models import FeedSource


class Command(BaseCommand):
    help = "Fetch every active feed source and save new and changed entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=int,
            action="append",
            dest="source_ids",
            metavar="ID",
            help="Poll only this source id. Repeat to poll several.",
        )

    def handle(self, *args, source_ids=None, **options):
        sources = FeedSource.objects.filter(is_active=True)
        if source_ids:
            sources = sources.filter(pk__in=source_ids)

        failed = []
        for source in sources:
            try:
                result = poll_source(source)
            except Exception as exc:
                failed.append(source.name)
                self.stderr.write(f"{source.name}: {type(exc).__name__}: {exc}")
                continue
            self.stdout.write(
                f"{source.name}: {result.fetched} fetched, {result.created} created, "
                f"{result.updated} updated, {result.unchanged} unchanged"
            )

        if failed:
            raise CommandError(f"Polling failed for: {', '.join(failed)}")
