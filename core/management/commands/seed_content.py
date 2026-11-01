from django.core.management.base import BaseCommand

from core.content import ensure_pages


class Command(BaseCommand):
    help = "Create the About Us and policy pages with starting text (existing pages are never changed)."

    def handle(self, *args, **options):
        created = ensure_pages()
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created: {', '.join(created)}"))
        else:
            self.stdout.write("All pages already exist - nothing changed.")
