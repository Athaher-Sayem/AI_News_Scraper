"""Delete old ArticleView rows so the trending table does not grow forever."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import ArticleView


class Command(BaseCommand):
    help = "Delete ArticleView rows older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=settings.VIEW_RETENTION_DAYS,
            help="Keep views newer than this many days (default: VIEW_RETENTION_DAYS).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be a positive integer")
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = ArticleView.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} article view(s) older than {days} days")
        )
