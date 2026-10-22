"""Birinchi rahbariyat yoki moderator hisobini yaratish (keyingilari "Boshqaruv → Xodimlar" sahifasida)."""
import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from audit.services import log_action


class Command(BaseCommand):
    help = "Xodim hisobini yaratadi: manage.py create_staff --username rahbar --email r@namdu.uz --role leadership --superuser"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--last-name", default="")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--role", choices=[Role.LEADERSHIP, Role.MODERATOR], default=Role.LEADERSHIP)
        parser.add_argument("--superuser", action="store_true", help="Django admin panelga ham kirish huquqi")

    def handle(self, *args, **opts):
        username = opts["username"].strip().lower()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"“{username}” logini band.")
        user = User(username=username, email=opts["email"], last_name=opts["last_name"], first_name=opts["first_name"],
                    role=opts["role"], is_staff=opts["superuser"], is_superuser=opts["superuser"])
        for _ in range(3):
            pw = getpass.getpass("Parol: ")
            if pw != getpass.getpass("Parolni takrorlang: "):
                self.stderr.write("Parollar mos emas.")
                continue
            try:
                validate_password(pw, user)
            except ValidationError as e:
                self.stderr.write(" ".join(e.messages))
                continue
            break
        else:
            raise CommandError("Parol o‘rnatilmadi.")
        with transaction.atomic():
            user.set_password(pw)
            user.save()
            log_action(None, "staff.create", f"Xodim buyruq orqali yaratildi: {username} ({user.get_role_display()})", actor=user, obj=user)
        self.stdout.write(self.style.SUCCESS(f"{user.get_role_display()} hisobi yaratildi: {username}"))
