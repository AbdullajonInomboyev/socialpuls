from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render

from accounts.models import Role
from achievements.models import Achievement, Criterion
from ratings.models import StudentScore
from ratings.services import averaged_breakdown, criterion_rows, rank_in, recalculate, year_rank, year_total
from structure.models import Semester

from .permissions import scope_filter, scoped_students, staff_required, student_required


@login_required
def home(request):
    if request.user.role == Role.STUDENT:
        return student_dashboard(request)
    return staff_dashboard(request)


def _periods(student):
    """Talaba tanlay oladigan davrlar: ballari bor semestrlar, joriy semestr va o'quv yillari."""
    sem_ids = set(StudentScore.objects.filter(student=student).values_list("semester_id", flat=True))
    current = Semester.current()
    if current:
        sem_ids.add(current.pk)
    semesters = list(Semester.objects.filter(pk__in=sem_ids).select_related("academic_year"))
    years = sorted({s.academic_year for s in semesters}, key=lambda y: y.start_date, reverse=True)
    periods = []
    for y in years:
        for s in sorted((s for s in semesters if s.academic_year_id == y.pk), key=lambda s: s.number):
            periods.append({"key": f"s{s.pk}", "label": f"{s.number}-semestr", "semester": s, "year": y})
        periods.append({"key": f"y{y.pk}", "label": f"{y.name} o'quv yili", "semester": None, "year": y})
    return periods, current


@student_required
def student_dashboard(request):
    user = request.user
    profile = getattr(user, "profile", None)
    criteria = list(Criterion.objects.filter(is_active=True))
    periods, current = _periods(user)
    wanted = request.GET.get("davr")
    selected = next((p for p in periods if p["key"] == wanted), None)
    if selected is None:
        selected = next((p for p in periods if p["semester"] and p["semester"] == current), periods[0] if periods else None)

    total = None
    breakdown = {}
    faculty_rank = uni_rank = None
    if selected and selected["semester"]:
        sem = selected["semester"]
        score = StudentScore.objects.filter(student=user, semester=sem).first()
        if score is None and sem.is_current:
            score = recalculate(user, sem)
        if score:
            total, breakdown = score.total, score.breakdown
            uni_rank = rank_in(sem, total)
            if profile and profile.faculty_id:
                faculty_rank = rank_in(sem, total, faculty_id=profile.faculty_id)
    elif selected:
        year = selected["year"]
        total = year_total(user, year)
        if total is not None:
            breakdown = averaged_breakdown(user, year, criteria)
            uni_rank = year_rank(year, total)
            if profile and profile.faculty_id:
                faculty_rank = year_rank(year, total, faculty_id=profile.faculty_id)

    rows = criterion_rows(breakdown, criteria)
    ach_qs = Achievement.objects.filter(student=user).select_related("criterion", "semester")
    if selected and selected["semester"]:
        ach_qs = ach_qs.filter(semester=selected["semester"])
    elif selected:
        ach_qs = ach_qs.filter(semester__academic_year=selected["year"])
    counts = ach_qs.aggregate(
        pending=Count("id", filter=Q(status=Achievement.Status.PENDING)),
        returned=Count("id", filter=Q(status=Achievement.Status.RETURNED)),
    )

    return render(
        request,
        "core/student_dashboard.html",
        {
            "profile": profile,
            "periods": periods,
            "selected": selected,
            "total": total if total is not None else Decimal("0"),
            "has_score": total is not None,
            "rows": rows,
            "faculty_rank": faculty_rank,
            "uni_rank": uni_rank,
            "recent": ach_qs[:6],
            "counts": counts,
            "notifications": user.notifications.all()[:4],
        },
    )


@staff_required
def staff_dashboard(request):
    user = request.user
    semester = Semester.current()
    students = scoped_students(user)
    scope = scope_filter(user)
    pending = Achievement.objects.filter(status=Achievement.Status.PENDING, **scope)
    scores = StudentScore.objects.none()
    if semester:
        scores = StudentScore.objects.filter(semester=semester, student__in=students)
    agg = scores.aggregate(avg=Avg("total"), active=Count("id", filter=Q(approved_count__gt=0)))
    top = scores.select_related("student", "student__profile__group", "faculty").order_by("-total")[:8]
    criteria = list(Criterion.objects.filter(is_active=True))
    top_rows = [{"score": s, "rows": criterion_rows(s.breakdown, criteria)} for s in top]
    return render(
        request,
        "core/staff_dashboard.html",
        {
            "semester": semester,
            "student_count": students.count(),
            "pending_count": pending.count(),
            "avg_score": agg["avg"],
            "active_count": agg["active"] or 0,
            "top_rows": top_rows,
            "scope_label": _scope_label(user),
        },
    )


def _scope_label(user):
    if user.role == Role.FACULTY_ADMIN and user.faculty:
        return user.faculty.name
    if user.role == Role.TUTOR:
        names = list(user.tutor_groups.values_list("name", flat=True)[:4])
        return ", ".join(names) + ("..." if user.tutor_groups.count() > 4 else "") if names else "Guruh biriktirilmagan"
    return "Butun universitet"


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def csrf_failure(request, reason=""):
    return render(request, "errors/403_csrf.html", status=403)
