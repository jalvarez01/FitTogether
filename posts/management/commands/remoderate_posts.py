import logging

from django.core.management.base import BaseCommand

from posts.services.moderation_queue import reprocess_posts

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Reprocess post moderation queue. By default processes only pending posts. "
        "Use --all to remoderate all existing posts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            dest="include_all",
            help="Re-moderate all posts (approved/rejected/pending), not only pending.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="How many posts to fetch per DB iterator batch.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional max number of posts to process in this run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Run moderation checks without persisting status changes.",
        )

    def handle(self, *args, **options):
        include_all = bool(options.get("include_all"))
        batch_size = int(options.get("batch_size") or 100)
        limit = options.get("limit")
        dry_run = bool(options.get("dry_run"))

        scope = "all posts" if include_all else "pending posts"
        self.stdout.write(self.style.NOTICE(f"Starting moderation reprocessing for {scope}..."))

        stats = reprocess_posts(
            include_all_statuses=include_all,
            batch_size=batch_size,
            limit=limit,
            dry_run=dry_run,
        )

        summary = (
            f"Done. scanned={stats.scanned} changed={stats.changed} unchanged={stats.unchanged} "
            f"still_pending={stats.still_pending} failures={stats.failures}"
        )

        if stats.failures:
            logger.error("Moderation reprocessing completed with failures: %s", summary)
            self.stdout.write(self.style.WARNING(summary))
            return

        self.stdout.write(self.style.SUCCESS(summary))
