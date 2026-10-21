from django.core.management.base import BaseCommand, CommandError

from hemis.sync import SyncBusy, sync_all


class Command(BaseCommand):
    help = "HEMIS dan fakultet, yo'nalish, guruh va talabalarni sinxronlaydi (cron uchun, masalan har kecha)."

    def add_arguments(self, parser):
        parser.add_argument("--faqat-tuzilma", action="store_true", help="Talabalarsiz: faqat fakultet, yo'nalish va guruhlar")

    def handle(self, *args, **opts):
        try:
            run = sync_all(students=not opts["faqat_tuzilma"])
        except SyncBusy as exc:
            raise CommandError(str(exc)) from exc
        if run.status != run.Status.SUCCESS:
            raise CommandError(f"Xatolik: {run.error}")
        self.stdout.write(self.style.SUCCESS(f"Tayyor: {run.created_count} yangi, {run.updated_count} yangilandi."))
