from decimal import Decimal

from django.test import TestCase

from accounts.models import Role
from achievements.models import Achievement, Criterion, ManualScore
from ratings.services import gpa_points, rank_in, recalculate, year_total

from .factories import make_staff, make_structure, make_student


class ScoringTests(TestCase):
    def setUp(self):
        self.s = make_structure()
        self.student = make_student("100", self.s["g1"], gpa="4.20")
        self.dean = make_staff("dekan", Role.FACULTY_ADMIN, faculty=self.s["f1"])
        self.c = {c.code: c for c in Criterion.objects.all()}

    def approve(self, code, points, sem=None):
        return Achievement.objects.create(
            student=self.student, semester=sem or self.s["sem1"], criterion=self.c[code], title="x",
            event_date="2026-10-01", status="approved", points=Decimal(points),
        )

    def test_eleven_criteria_total_100(self):
        self.assertEqual(Criterion.objects.count(), 11)
        self.assertEqual(sum(c.max_points for c in Criterion.objects.all()), 100)

    def test_gpa_formula(self):
        self.assertEqual(gpa_points(Decimal("4.2"), 10), Decimal("8.40"))
        self.assertEqual(gpa_points(Decimal("5"), 10), Decimal("10.00"))
        self.assertEqual(gpa_points(None, 10), Decimal("0"))

    def test_criterion_is_capped_at_max(self):
        self.approve("volontyorlik", 4)
        self.approve("volontyorlik", 3)  # 7 > 5
        score = recalculate(self.student, self.s["sem1"])
        self.assertEqual(score.breakdown["volontyorlik"], "5.00")

    def test_only_approved_counts_and_manual_and_gpa(self):
        self.approve("kitobxonlik", 12)
        Achievement.objects.create(student=self.student, semester=self.s["sem1"], criterion=self.c["sport"], title="y", event_date="2026-10-01", status="pending")
        ManualScore.objects.create(student=self.student, semester=self.s["sem1"], criterion=self.c["odob"], points=Decimal(5), given_by=self.dean)
        score = recalculate(self.student, self.s["sem1"])
        self.assertEqual(score.breakdown["sport"], "0.00")
        self.assertEqual(score.total, Decimal("25.40"))  # 12 + 5 + 8.40
        self.assertEqual(score.faculty, self.s["f1"])

    def test_year_total_is_semester_average(self):
        self.approve("kitobxonlik", 20)
        recalculate(self.student, self.s["sem1"])  # 20 + 8.4 = 28.4
        self.approve("kitobxonlik", 10, sem=self.s["sem2"])
        recalculate(self.student, self.s["sem2"])  # past semester keeps gpa snapshot from profile: 10 + 8.4
        self.assertEqual(year_total(self.student, self.s["year"]), Decimal("23.40"))

    def test_rank(self):
        other = make_student("200", self.s["g1"], gpa="2.00")
        a = recalculate(self.student, self.s["sem1"])
        recalculate(other, self.s["sem1"])
        self.assertEqual(rank_in(self.s["sem1"], a.total), (1, 2))
