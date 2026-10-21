from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from audit.models import ActionLog
from hemis.mock import MOCK_PASSWORD

from .factories import PASSWORD, make_staff, make_structure


@override_settings(HEMIS_MODE="mock")
class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.s = make_structure()
        self.dean = make_staff("dekan", Role.FACULTY_ADMIN, faculty=self.s["f1"])

    def test_login_page_renders_both_modes(self):
        self.assertContains(self.client.get(reverse("accounts:login")), "HEMIS login")
        self.assertContains(self.client.get(reverse("accounts:login") + "?xodim=1"), "Parolni unutdingizmi")

    def test_staff_login_and_redirect_to_dashboard(self):
        r = self.client.post(reverse("accounts:login") + "?xodim=1", {"mode": "staff", "username": "dekan", "password": PASSWORD})
        self.assertRedirects(r, reverse("core:home"))
        r = self.client.get(reverse("core:home"))
        self.assertContains(r, "Iqtisodiyot fakulteti")
        self.assertTrue(ActionLog.objects.filter(action="login.success", actor=self.dean).exists())

    def test_staff_wrong_password_shows_error_and_logs(self):
        r = self.client.post(reverse("accounts:login"), {"mode": "staff", "username": "dekan", "password": "xato"})
        self.assertContains(r, "Login yoki parol noto")
        self.assertTrue(ActionLog.objects.filter(action="login.failed").exists())

    def test_student_hemis_login_creates_profile_and_score(self):
        r = self.client.post(reverse("accounts:login"), {"mode": "student", "login": "309251104207", "password": MOCK_PASSWORD})
        self.assertRedirects(r, reverse("core:home"))
        u = User.objects.get(hemis_id="309251104207")
        self.assertEqual(u.role, Role.STUDENT)
        self.assertEqual(u.last_name, "Tog‘ayeva")
        self.assertEqual(u.middle_name, "Rustam qizi")
        self.assertEqual(u.profile.group, self.s["g2"])
        self.assertEqual(str(u.profile.gpa), "4.68")
        self.assertFalse(u.has_usable_password())
        r = self.client.get(reverse("core:home"))
        self.assertContains(r, "Xush kelibsiz, Hilola")
        self.assertContains(r, "9,36")  # GPA 4.68 / 5 x 10

    def test_student_wrong_hemis_password(self):
        r = self.client.post(reverse("accounts:login"), {"mode": "student", "login": "309251104207", "password": "xato"})
        self.assertContains(r, "HEMIS login yoki parol noto")
        self.assertFalse(User.objects.filter(hemis_id="309251104207").exists())

    def test_student_cannot_login_through_staff_form(self):
        self.client.post(reverse("accounts:login"), {"mode": "student", "login": "309251104207", "password": MOCK_PASSWORD})
        self.client.logout()
        u = User.objects.get(hemis_id="309251104207")
        u.set_password(PASSWORD)
        u.save()
        r = self.client.post(reverse("accounts:login"), {"mode": "staff", "username": u.username, "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_ATTEMPTS=3)
    def test_lockout_after_repeated_failures(self):
        for _ in range(3):
            self.client.post(reverse("accounts:login"), {"mode": "staff", "username": "dekan", "password": "xato"})
        r = self.client.post(reverse("accounts:login"), {"mode": "staff", "username": "dekan", "password": PASSWORD})
        self.assertContains(r, "Juda ko")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_open_redirect_is_ignored(self):
        r = self.client.post(
            reverse("accounts:login"), {"mode": "staff", "username": "dekan", "password": PASSWORD, "next": "https://evil.example/"}
        )
        self.assertRedirects(r, reverse("core:home"))

    def test_logout_requires_post(self):
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("accounts:login"))

    def test_password_reset_only_for_staff(self):
        self.client.post(reverse("accounts:login"), {"mode": "student", "login": "309251104207", "password": MOCK_PASSWORD})
        self.client.logout()
        User.objects.filter(hemis_id="309251104207").update(email="talaba@namdu.uz")
        self.client.post(reverse("accounts:password_reset"), {"email": "talaba@namdu.uz"})
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(reverse("accounts:password_reset"), {"email": "dekan@namdu.uz"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/parol/tiklash/", mail.outbox[0].body)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("core:home"))
        self.assertRedirects(r, reverse("accounts:login") + "?next=/")
