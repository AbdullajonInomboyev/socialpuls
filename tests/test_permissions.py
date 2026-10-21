from django.test import TestCase
from django.urls import reverse

from accounts.models import Role
from core.permissions import scoped_students

from .factories import make_staff, make_structure, make_student


class ScopeTests(TestCase):
    def setUp(self):
        self.s = make_structure()
        self.a = make_student("1", self.s["g1"])
        self.b = make_student("2", self.s["g2"])

    def test_faculty_admin_sees_own_faculty(self):
        dean = make_staff("dekan", Role.FACULTY_ADMIN, faculty=self.s["f1"])
        self.assertEqual(list(scoped_students(dean)), [self.a])

    def test_tutor_sees_only_assigned_groups(self):
        tutor = make_staff("tyutor", Role.TUTOR, groups=[self.s["g2"]])
        self.assertEqual(list(scoped_students(tutor)), [self.b])
        lonely = make_staff("tyutor2", Role.TUTOR)
        self.assertEqual(list(scoped_students(lonely)), [])

    def test_leadership_sees_all(self):
        boss = make_staff("rahbar", Role.LEADERSHIP)
        self.assertEqual(scoped_students(boss).count(), 2)

    def test_dashboards_render_per_role(self):
        for user in (self.a, make_staff("rahbar", Role.LEADERSHIP), make_staff("mod", Role.MODERATOR),
                     make_staff("t", Role.TUTOR, groups=[self.s["g1"]])):
            self.client.force_login(user)
            r = self.client.get(reverse("core:home"))
            self.assertEqual(r.status_code, 200, user)

    def test_student_dashboard_period_switch_and_pages(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse("core:home") + f"?davr=y{self.s['year'].pk}")
        self.assertContains(r, "Semestrlar o‘rtachasi")
        for name in ("accounts:profile", "notifications:list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_student_cannot_change_password_page(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse("accounts:password_change"))
        self.assertRedirects(r, reverse("accounts:profile"))

    def test_security_headers(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertIn("script-src 'self'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
