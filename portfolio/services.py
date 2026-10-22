"""Talaba portfoliosi: tasdiqlangan yutuqlar va ballardan avtomatik yig'iladi, alohida saqlanmaydi.

Har ochilganda bazadagi joriy holatdan tuziladi, shuning uchun yangi tasdiqlangan yutuq darhol ko'rinadi.
Qoralama, tekshiruvdagi, rad etilgan va qaytarilgan yutuqlar portfolioga kirmaydi.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from accounts.models import Role
from achievements.models import Achievement, Criterion
from ratings.models import StudentScore
from ratings.services import criterion_rows
from structure.models import Semester


@dataclass
class SemesterLine:
    semester: Semester
    total: Decimal
    approved: int
    faculty_rank: int | None
    faculty_size: int
    university_rank: int
    university_size: int


@dataclass
class CriterionGroup:
    criterion: Criterion
    items: list
    points: Decimal = Decimal("0")


@dataclass
class Portfolio:
    student: object
    profile: object
    groups: list
    semesters: list
    current: SemesterLine | None
    bars: list
    total_approved: int
    criteria_covered: int
    total_points: Decimal
    generated_at: object = field(default_factory=timezone.now)

    @property
    def is_empty(self):
        return not self.total_approved and not self.semesters


def _ranked(score):
    """Semestr ichida fakultet va universitet bo'yicha o'rin (teng ballilar bir xil o'rinda, reyting bilan bir xil)."""
    same = StudentScore.objects.filter(semester_id=score.semester_id, student__is_active=True, student__role=Role.STUDENT)
    uni_rank = same.filter(total__gt=score.total).count() + 1
    uni_size = same.count()
    fac_rank = fac_size = None
    if score.faculty_id:
        fac = same.filter(faculty_id=score.faculty_id)
        fac_rank, fac_size = fac.filter(total__gt=score.total).count() + 1, fac.count()
    return SemesterLine(score.semester, score.total, score.approved_count, fac_rank, fac_size or 0, uni_rank, uni_size)


def build(student):
    approved = list(
        Achievement.objects.filter(student=student, status=Achievement.Status.APPROVED)
        .select_related("criterion", "level", "semester__academic_year", "reviewer")
        .prefetch_related("files")
        .order_by("criterion__order", "criterion_id", "-event_date")
    )
    groups, by_code = [], {}
    for a in approved:
        g = by_code.get(a.criterion_id)
        if g is None:
            g = by_code[a.criterion_id] = CriterionGroup(a.criterion, [])
            groups.append(g)
        g.items.append(a)
        g.points += a.points or 0

    scores = list(
        StudentScore.objects.filter(student=student)
        .select_related("semester__academic_year")
        .order_by("-semester__start_date")
    )
    semesters = [_ranked(s) for s in scores]
    current_sem = Semester.current()
    current = next((line for line in semesters if current_sem and line.semester.pk == current_sem.pk), None)
    if current is None and semesters:
        current = semesters[0]
    current_score = next((s for s in scores if current and s.semester_id == current.semester.pk), None)
    bars = criterion_rows(current_score.breakdown if current_score else {}, list(Criterion.objects.filter(is_active=True)))

    return Portfolio(
        student=student,
        profile=getattr(student, "profile", None),
        groups=groups,
        semesters=semesters,
        current=current,
        bars=bars,
        total_approved=len(approved),
        criteria_covered=len(groups),
        total_points=sum((a.points or 0 for a in approved), Decimal("0")),
    )
