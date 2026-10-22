from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.checks import run_checks
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from audit.models import ActionLog

from .factories import make_staff


class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.boss = make_staff("rahbar1", Role.LEADERSHIP)

    def test_admin_login_goes_through_rate_limited_login(self):
        r = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("accounts:login")))
        self.assertIn("xodim=1", r["Location"])
        r = self.client.post("/admin/login/", {"username": "rahbar1", "password": "x"})
        self.assertEqual(r.status_code, 302)  # admin formasi orqali parol tekshirilmaydi

    def test_password_reset_throttled_per_email(self):
        for _ in range(5):
            self.client.post(reverse("accounts:password_reset"), {"email": "rahbar1@namdu.uz"})
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(ActionLog.objects.filter(action="password.reset_throttled").exists())

    def test_students_cannot_reset_password_by_email(self):
        u = User.objects.create(username="s1", role=Role.STUDENT, email="t@mail.uz")
        u.set_password("Kuchli-parol-2026")
        u.save()
        self.client.post(reverse("accounts:password_reset"), {"email": "t@mail.uz"})
        self.assertEqual(len(mail.outbox), 0)

    def test_idle_timeout_next_is_encoded(self):
        from core.models import SiteSettings

        self.client.force_login(self.boss)
        s = self.client.session
        s["last_seen"] = 1
        s.save()
        SiteSettings.load()
        r = self.client.get("/reyting/?a=1&b=2")
        self.assertEqual(r.status_code, 302)
        self.assertIn("next=%2Freyting%2F%3Fa%3D1%26b%3D2", r["Location"])

    @override_settings(DEBUG=False, ADMIN_URL="admin/")
    def test_deploy_checks(self):
        ids = {m.id for m in run_checks(include_deployment_checks=True)}
        self.assertIn("socialpuls.W001", ids)
        self.assertIn("socialpuls.W002", ids)

    def test_create_staff_command(self):
        with mock.patch("getpass.getpass", side_effect=["Rahbar-parol-2026!", "Rahbar-parol-2026!"]):
            call_command("create_staff", "--username", "Bosh", "--email", "b@namdu.uz", "--superuser", stdout=mock.Mock())
        u = User.objects.get(username="bosh")
        self.assertEqual(u.role, Role.LEADERSHIP)
        self.assertTrue(u.is_superuser and u.check_password("Rahbar-parol-2026!"))
        self.assertTrue(self.client.login(username="bosh", password="Rahbar-parol-2026!"))

    def test_security_headers(self):
        self.client.force_login(self.boss)
        r = self.client.get(reverse("core:home"))
        self.assertIn("script-src 'self'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
