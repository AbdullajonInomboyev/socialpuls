from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Namoyish saytida xodimlarga umumiy parol o'rnatadi: tyutorlarga DEMO_TUTOR_PASSWORD, qolganlarga DEMO_STAFF_PASSWORD."

    def handle(self, *args, **opts):
        if not settings.DEMO_SITE:
            raise CommandError("apply_demo_passwords faqat DEMO_SITE=True muhitida ishlaydi.")
        staff = User.objects.exclude(role=Role.STUDENT).filter(is_active=True)
        done = 0
        for password, users in (
            (settings.DEMO_TUTOR_PASSWORD, staff.filter(role=Role.TUTOR)),
            (settings.DEMO_STAFF_PASSWORD, staff.exclude(role=Role.TUTOR)),
        ):
            if password:
                done += users.update(password=make_password(password))
        self.stdout.write(f"Umumiy parol o'rnatilgan xodimlar: {done}.")
