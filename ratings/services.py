"""Ball hisoblash qoidalari.

* Har bir semestr alohida 100 ballik baholanadi.
* "upload" mezonlarda tasdiqlangan yutuqlar bali qo'shiladi, lekin mezon maksimumidan oshmaydi.
* "manual" mezonlarda mas'ul qo'ygan ball olinadi.
* "auto" (akademik o'zlashtirish) = GPA / 5 x mezon maksimumi.
* O'quv yili bali = shu yildagi semestrlar ballarining o'rtachasi.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Avg, Count, Sum

from achievements.models import Achievement, Criterion, ManualScore

from .models import StudentScore

TWO = Decimal("0.01")
FIVE = Decimal("5")


def q2(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def gpa_points(gpa, max_points):
    if gpa is None:
        return Decimal("0")
    gpa = max(Decimal("0"), min(FIVE, Decimal(gpa)))
    return q2(gpa / FIVE * Decimal(max_points))


@transaction.atomic
def recalculate(student, semester):
    """Talabaning semestr balini qayta hisoblab saqlaydi va StudentScore qaytaradi."""
    profile = getattr(student, "profile", None)
    criteria = list(Criterion.objects.filter(is_active=True))
    score, _ = StudentScore.objects.select_for_update().get_or_create(student=student, semester=semester)

    approved = dict(
        Achievement.objects.filter(student=student, semester=semester, status=Achievement.Status.APPROVED)
        .values("criterion__code")
        .annotate(s=Sum("points"))
        .values_list("criterion__code", "s")
    )
    manual = dict(
        ManualScore.objects.filter(student=student, semester=semester).values_list("criterion__code", "points")
    )

    if semester.is_current and not semester.is_closed and profile is not None:
        gpa = profile.gpa
    else:
        gpa = score.gpa_snapshot if score.gpa_snapshot is not None else getattr(profile, "gpa", None)

    breakdown = {}
    for c in criteria:
        cap = Decimal(c.max_points)
        if c.input_mode == Criterion.InputMode.AUTO:
            value = gpa_points(gpa, c.max_points)
        elif c.input_mode == Criterion.InputMode.MANUAL:
            value = Decimal(manual.get(c.code) or 0)
        else:
            value = Decimal(approved.get(c.code) or 0)
        breakdown[c.code] = str(q2(min(value, cap)))

    score.breakdown = breakdown
    score.total = q2(sum(Decimal(v) for v in breakdown.values()))
    score.gpa_snapshot = gpa
    score.approved_count = Achievement.objects.filter(
        student=student, semester=semester, status=Achievement.Status.APPROVED
    ).count()
    if profile is not None:
        score.faculty_id = profile.faculty_id
        score.group_id = profile.group_id
    score.save()
    return score


def recalculate_many(students, semester):
    for s in students:
        recalculate(s, semester)


def rank_in(semester, total, **scope):
    """Talabaning o'rni: undan ko'p ball olganlar soni + 1 (teng ball bir xil o'rin)."""
    qs = StudentScore.objects.filter(semester=semester, **scope)
    return qs.filter(total__gt=total).count() + 1, qs.count()


def year_total(student, academic_year):
    agg = StudentScore.objects.filter(student=student, semester__academic_year=academic_year).aggregate(
        avg=Avg("total"), n=Count("id")
    )
    if not agg["n"]:
        return None
    return q2(agg["avg"])


def year_rank(academic_year, total, **scope):
    """O'quv yili bo'yicha o'rin (talabalar semestr o'rtachasi bo'yicha)."""
    rows = (
        StudentScore.objects.filter(semester__academic_year=academic_year, **scope)
        .values("student")
        .annotate(avg=Avg("total"))
    )
    count = rows.count()
    higher = rows.filter(avg__gt=total).count()
    return higher + 1, count


def criterion_rows(breakdown, criteria=None):
    """Shablon uchun: [{criterion, points, max, percent}] ro'yxati."""
    criteria = criteria if criteria is not None else Criterion.objects.filter(is_active=True)
    rows = []
    for c in criteria:
        pts = Decimal(breakdown.get(c.code, "0")) if breakdown else Decimal("0")
        rows.append(
            {
                "criterion": c,
                "points": pts,
                "max": c.max_points,
                "percent": f"{float(pts) / c.max_points * 100:.1f}" if c.max_points else "0",
            }
        )
    return rows


def averaged_breakdown(student, academic_year, criteria):
    scores = list(StudentScore.objects.filter(student=student, semester__academic_year=academic_year))
    if not scores:
        return {}
    out = {}
    for c in criteria:
        vals = [Decimal(s.breakdown.get(c.code, "0")) for s in scores]
        out[c.code] = str(q2(sum(vals) / len(vals)))
    return out

