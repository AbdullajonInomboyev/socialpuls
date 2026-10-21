from django.core.management.base import BaseCommand

from notifications.reminders import send_monthly

MESSAGES = {
    "disabled": "Oylik eslatma sozlamalarda o'chirilgan.",
    "no-semester": "Joriy ochiq semestr yo'q, eslatma yuborilmadi.",
    "before-semester": "O'tgan oy semestrdan oldin, eslatma yuborilmadi.",
    "already-sent": "Bu oy uchun eslatma allaqachon yuborilgan.",
}


class Command(BaseCommand):
    help = "O'tgan oyda yutuq yubormagan talabalarga eslatma (cron: har oyning 1-kuni)."

    def handle(self, *args, **opts):
        status, n = send_monthly()
        if status == "sent":
            self.stdout.write(self.style.SUCCESS(f"Eslatma {n} talabaga yuborildi."))
        else:
            self.stdout.write(MESSAGES.get(status, status))
