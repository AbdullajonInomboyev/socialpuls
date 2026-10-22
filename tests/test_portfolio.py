from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role
from achievements.models import Achievement, Criterion
from audit.models import ActionLog
from ratings.services import recalculate

from .factories import make_staff, make_structure, make_student


class PortfolioTests(TestCase):
    def setUp(self):
        cache.clear()
        self.s = make_structure()
        self.sem = self.s["sem1"]
        self.a = make_student("309251100011", self.s["g1"])
        self.b = make_student("309251100012", self.s["g2"])
        self.dean = make_staff("dekan1", Role.FACULTY_ADMIN, faculty=self.s["f1"])
        self.tutor = make_staff("tyutor1", Role.TUTOR, groups=[self.s["g2"]])
        self.boss = make_staff("rahbar1", Role.LEADERSHIP)
        sport = Criterion.objects.get(code="sport")
        for title, status, pts in (("Futbol turniri", "approved", "3"), ("Kutilayotgan yutuq", "pending", None),
                                   ("Rad etilgan yutuq", "rejected", None)):
            Achievement.objects.create(student=self.a, semester=self.sem, criterion=sport, title=title,
                                       event_date=date(2026, 10, 1), status=status, points=Decimal(pts) if pts else None)
        recalculate(self.a, self.sem)
        recalculate(self.b, self.sem)

    def url(self, student, pdf=False):
        return reverse("portfolio:pdf" if pdf else "portfolio:detail", args=[student.pk])

    def test_student_sees_only_approved(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse("portfolio:me"))
        self.assertContains(r, "Futbol turniri")
        self.assertNotContains(r, "Kutilayotgan yutuq")
        self.assertNotContains(r, "Rad etilgan yutuq")
        self.assertContains(r, "1 / 1")  # fakultetdagi o'rin

    def test_student_cannot_open_other_portfolio(self):
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.url(self.a)).status_code, 404)
        self.assertEqual(self.client.get(self.url(self.a, pdf=True)).status_code, 404)

    def test_staff_scope(self):
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(self.url(self.a)).status_code, 200)
        self.assertEqual(self.client.get(self.url(self.b)).status_code, 404)
        self.client.force_login(self.tutor)
        self.assertEqual(self.client.get(self.url(self.a)).status_code, 404)
        self.assertEqual(self.client.get(self.url(self.b)).status_code, 200)
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get(self.url(self.a)).status_code, 200)
        self.assertRedirects(self.client.get(reverse("portfolio:me")), reverse("ratings:rating"))

    def test_pdf_download(self):
        self.client.force_login(self.a)
        r = self.client.get(self.url(self.a, pdf=True))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertFalse(ActionLog.objects.filter(action="portfolio.download").exists())
        self.client.force_login(self.dean)
        r = self.client.get(self.url(self.a, pdf=True) + "?ochish=1")
        self.assertIn("inline", r["Content-Disposition"])
        self.assertTrue(ActionLog.objects.filter(action="portfolio.download", actor=self.dean).exists())

    def test_empty_portfolio(self):
        self.client.force_login(self.b)
        r = self.client.get(reverse("portfolio:me"))
        self.assertContains(r, "Portfolio hali bo‘sh")
        self.assertTrue(self.client.get(self.url(self.b, pdf=True)).content.startswith(b"%PDF"))

    def test_student_menu_has_portfolio_not_add_button(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse("core:home"))
        nav = r.content.decode().split("<main", 1)[0]
        self.assertIn(reverse("portfolio:me"), nav)
        self.assertNotIn(reverse("achievements:create"), nav)
        self.assertContains(self.client.get(reverse("achievements:my_list")), reverse("achievements:create"))

    def test_student_card_links_portfolio(self):
        self.client.force_login(self.dean)
        self.assertContains(self.client.get(reverse("ratings:student", args=[self.a.pk])), self.url(self.a))
