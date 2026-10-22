import tempfile
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import StudentProfile
from achievements.models import AchievementFile
from audit.services import client_ip


class ClientIpTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_x_real_ip_default(self):
        r = self.rf.get("/", HTTP_X_REAL_IP="203.0.113.5", HTTP_X_FORWARDED_FOR="1.1.1.1")
        self.assertEqual(client_ip(r), "203.0.113.5")

    @override_settings(CLIENT_IP_SOURCE="x-forwarded-for", PROXY_COUNT=1)
    def test_forwarded_for_ignores_client_supplied_prefix(self):
        r = self.rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7")
        self.assertEqual(client_ip(r), "203.0.113.7")
        r = self.rf.get("/", HTTP_X_REAL_IP="6.6.6.6")
        self.assertEqual(client_ip(r), "127.0.0.1")

    @override_settings(CLIENT_IP_SOURCE="x-forwarded-for", PROXY_COUNT=2)
    def test_forwarded_for_two_proxies(self):
        r = self.rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7, 10.0.0.2")
        self.assertEqual(client_ip(r), "203.0.113.7")


class DemoSiteTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_shows_demo_logins_only_on_demo_site(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertNotContains(r, "Namoyish versiyasi")
        with override_settings(DEMO_SITE=True):
            r = self.client.get(reverse("accounts:login"))
            self.assertContains(r, "Namoyish versiyasi")
            self.assertContains(r, "hemis-demo")
            self.assertContains(self.client.get(reverse("accounts:login") + "?xodim=1"), "Puls-demo-2026")

    @override_settings(DEBUG=False, DEMO_SITE=False)
    def test_seed_refused_outside_demo(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--students", "1", stdout=StringIO())

    def test_seed_if_empty_restores_lost_files(self):
        with tempfile.TemporaryDirectory() as media, override_settings(DEBUG=False, DEMO_SITE=True, PRIVATE_MEDIA_ROOT=media):
            call_command("seed_demo", "--students", "2", "--if-empty", stdout=StringIO())
            students = StudentProfile.objects.count()
            f = AchievementFile.objects.first()
            self.assertIsNotNone(f)
            f.file.storage.delete(f.file.name)
            out = StringIO()
            call_command("seed_demo", "--students", "2", "--if-empty", stdout=out)
            self.assertEqual(StudentProfile.objects.count(), students)
            self.assertIn("tiklangan fayllar: 1", out.getvalue())
            self.assertTrue(f.file.storage.exists(f.file.name))
