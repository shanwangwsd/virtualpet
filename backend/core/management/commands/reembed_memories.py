from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import ai
from core.models import Memory


class Command(BaseCommand):
    help = "Re-embed existing memories for the configured provider. Live mode requires --live and incurs API costs."

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true")
        parser.add_argument("--user-id", type=int)

    def handle(self, *args, **options):
        if settings.AI_MODE == "live" and not options["live"]:
            raise CommandError(
                "Live embeddings cost money. Re-run with --live after checking provider budget."
            )
        queryset = Memory.objects.all()
        if options["user_id"]:
            queryset = queryset.filter(user_id=options["user_id"])
        count = 0
        for memory in queryset.exclude(embedding_model=ai.embedding_identity()).iterator():
            vector = ai.embed(memory.content)
            # A concurrent deletion must not recreate a forgotten memory.
            count += Memory.objects.filter(pk=memory.pk).update(
                embedding=vector, embedding_model=ai.embedding_identity()
            )
        self.stdout.write(f"Re-embedded {count} memories.")
