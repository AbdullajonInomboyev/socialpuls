"""Reyting ro'yxati: davr (semestr yoki o'quv yili), doira va filtrlar bo'yicha tartiblangan qatorlar.

Reyting sahifasi, TOP-10, Excel va PDF eksport bir xil qatorlardan foydalanadi.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from achievements.models import Criterion
from core.permissions import scoped_students
from structure.models import AcademicYear, Semester

from .models import StudentScore
from .services import q2


@dataclass
class Period:
    key: str
    label: str
    semester: Semester | None = None
    year: AcademicYear | None = None


@dataclass
class Row:
    student: object
    total: Decimal
    breakdown: dict
    approved: int
    rank: int = 0
    cells: list = field(default_factory=list)

    @property
    def profile(self):
        return getattr(self.student, "profile", None)


def all_periods():
    """Ballari bor semestrlar va o'quv yillari, yangidan eskiga."""
    sem_ids = set(StudentScore.objects.values_list("semester_id", flat=True).distinct())
    current = Semester.current()
    if current:
        sem_ids.add(current.pk)
    semesters = list(Semester.objects.filter(pk__in=sem_ids).select_related("academic_year"))
    years = sorted({s.academic_year for s in semesters}, key=lambda y: y.start_date, reverse=True)
    out = []
    for y in years:
        for s in sorted((s for s in semesters if s.academic_year_id == y.pk), key=lambda s: -s.number):
            out.append(Period(f"s{s.pk}", f"{y.name}, {s.number}-semestr", semester=s, year=y))
        out.append(Period(f"y{y.pk}", f"{y.name}, butun o‘quv yili", year=y))
    return out


def resolve_period(key, periods=None):
    periods = periods if periods is not None else all_periods()
    found = next((p for p in periods if p.key == key), None)
    if found:
        return found
    current = Semester.current()
    return next((p for p in periods if p.semester and current and p.semester.pk == current.pk), periods[0] if periods else None)


def rating_rows(user, period, faculty=None, group=None, course=None, criteria=None):
    """Doiradagi talabalarning tartiblangan qatorlari. Teng ballilar bir xil o'rinda (1, 1, 3).

    user=None bo'lsa butun universitet olinadi (TOP-10 va ochiq statistika uchun).
    """
    if period is None:
        return []
    criteria = criteria if criteria is not None else list(Criterion.objects.filter(is_active=True))
    if user is None:
        from accounts.models import Role, User

        students = User.objects.filter(role=Role.STUDENT, is_active=True)
    else:
        students = scoped_students(user)
    if faculty:
        students = students.filter(profile__faculty_id=faculty)
    if group:
        students = students.filter(profile__group_id=group)
    if course:
        students = students.filter(profile__course=course)

    related = ("student", "student__profile", "student__profile__faculty", "student__profile__group")
    if period.semester:
        scores = StudentScore.objects.filter(semester=period.semester, student__in=students).select_related(*related)
        rows = [Row(s.student, s.total, s.breakdown, s.approved_count) for s in scores]
    else:
        scores = list(
            StudentScore.objects.filter(semester__academic_year=period.year, student__in=students).select_related(*related)
        )
        grouped = defaultdict(list)
        for s in scores:
            grouped[s.student_id].append(s)
        rows = []
        for items in grouped.values():
            n = len(items)
            breakdown = {
                c.code: str(q2(sum(Decimal(i.breakdown.get(c.code, "0")) for i in items) / n)) for c in criteria
            }
            total = q2(sum(i.total for i in items) / n)
            rows.append(Row(items[0].student, total, breakdown, sum(i.approved_count for i in items)))

    rows.sort(key=lambda r: (-r.total, r.student.last_name, r.student.first_name))
    prev, rank = None, 0
    for i, r in enumerate(rows, start=1):
        if r.total != prev:
            rank, prev = i, r.total
        r.rank = rank
        r.cells = [Decimal(r.breakdown.get(c.code, "0")) for c in criteria]
    return rows


def summary(rows):
    if not rows:
        return {"count": 0, "avg": None, "active": 0, "best": None}
    return {
        "count": len(rows),
        "avg": q2(sum(r.total for r in rows) / len(rows)),
        "active": sum(1 for r in rows if r.approved),
        "best": rows[0].total,
    }

