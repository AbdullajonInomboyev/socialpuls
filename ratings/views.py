from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.models import Role
from achievements.models import Achievement, Criterion, ManualScore
from audit.services import log_action
from core.models import SiteSettings
from core.permissions import scope_filter, scoped_students, staff_required
from reports.exports import build_excel, build_pdf
from structure.models import Faculty, Group

from .selection import all_periods, rating_rows, resolve_period, summary
from .services import criterion_rows, q2

UNIVERSITY_ROLES = (Role.LEADERSHIP, Role.MODERATOR)


def _is_university(user):
    return user.is_superuser or user.role in UNIVERSITY_ROLES


def _scope_label(user):
    if _is_university(user):
        return "Butun universitet"
    if user.role == Role.FACULTY_ADMIN and user.faculty:
        return user.faculty.name
    if user.role == Role.TUTOR:
        return "Biriktirilgan guruhlar: " + (", ".join(user.tutor_groups.values_list("name", flat=True)) or "yo‘q")
    return ""


def _int(value):
    return int(value) if value and str(value).isdigit() else None


def _filters(request):
    """So'rovdan filtrlar. Doiradan tashqaridagi fakultet/guruh tanlansa ham natija bo'sh chiqadi (scoped_students)."""
    user = request.user
    periods = all_periods()
    period = resolve_period(request.GET.get("davr"), periods)
    faculties = list(Faculty.objects.filter(is_active=True)) if _is_university(user) else []
    faculty = _int(request.GET.get("fakultet")) if faculties else None
    if _is_university(user):
        groups = Group.objects.filter(faculty_id=faculty) if faculty else Group.objects.none()
    elif user.role == Role.FACULTY_ADMIN:
        groups = Group.objects.filter(faculty_id=user.faculty_id)
    else:
        groups = user.tutor_groups.all()
    groups = list(groups.order_by("name"))
    group = _int(request.GET.get("guruh"))
    if group and group not in {g.pk for g in groups}:
        group = None
    course = _int(request.GET.get("kurs"))
    if course and not 1 <= course <= 7:
        course = None
    return {
        "periods": periods, "period": period, "faculties": faculties, "faculty": faculty, "groups": groups,
        "group": group, "course": course, "q": request.GET.get("q", "").strip()[:80],
    }


def _selection_label(f):
    parts = []
    if f["faculty"]:
        parts.append(next((x.name for x in f["faculties"] if x.pk == f["faculty"]), ""))
    if f["group"]:
        parts.append(next((g.name for g in f["groups"] if g.pk == f["group"]), ""))
    if f["course"]:
        parts.append(f"{f['course']}-kurs")
    return ", ".join(p for p in parts if p)


def _search(rows, q):
    if not q:
        return rows
    ql = q.lower()
    return [r for r in rows if ql in r.student.full_name.lower() or ql == (r.student.hemis_id or "")]


@staff_required
def rating(request):
    f = _filters(request)
    criteria = list(Criterion.objects.filter(is_active=True))
    rows = rating_rows(request.user, f["period"], f["faculty"], f["group"], f["course"], criteria)
    stats = summary(rows)
    shown = _search(rows, f["q"])
    page = Paginator(shown, 50).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(
        request,
        "ratings/rating.html",
        {**f, "criteria": criteria, "page": page, "stats": stats, "keep": keep.urlencode(),
         "scope_label": _scope_label(request.user), "selection": _selection_label(f)},
    )


@staff_required
def export(request, fmt):
    if fmt not in ("excel", "pdf"):
        raise Http404
    f = _filters(request)
    criteria = list(Criterion.objects.filter(is_active=True))
    rows = _search(rating_rows(request.user, f["period"], f["faculty"], f["group"], f["course"], criteria), f["q"])
    site = SiteSettings.load()
    scope = _selection_label(f) or _scope_label(request.user)
    meta = {"title": f"{site.university_name}: ijtimoiy faollik reytingi", "period": f["period"].label if f["period"] else "",
            "scope": scope, "university": site.university_short}
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    if fmt == "excel":
        data = build_excel(rows, criteria, meta)
        resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        name = f"reyting-{stamp}.xlsx"
    else:
        data = build_pdf(rows, criteria, meta)
        resp = HttpResponse(data, content_type="application/pdf")
        name = f"reyting-{stamp}.pdf"
    resp["Content-Disposition"] = f'attachment; filename="{name}"'
    log_action(request, f"rating.export_{fmt}", f"Reyting yuklab olindi ({fmt}): {meta['period']}, {scope}, {len(rows)} qator")
    return resp


@login_required
def top10(request):
    """TOP-10: butun universitet va (talaba yoki mas'ul uchun) o'z fakulteti."""
    user = request.user
    periods = all_periods()
    period = resolve_period(request.GET.get("davr"), periods)
    criteria = list(Criterion.objects.filter(is_active=True))
    uni = rating_rows(None, period, criteria=criteria)
    faculty = None
    if user.role == Role.STUDENT:
        faculty = getattr(getattr(user, "profile", None), "faculty", None)
    elif user.role == Role.FACULTY_ADMIN:
        faculty = user.faculty
    fac_rows = rating_rows(None, period, faculty=faculty.pk, criteria=criteria)[:10] if faculty else []
    me = next((r for r in uni if r.student.pk == user.pk), None) if user.role == Role.STUDENT else None
    gap = (uni[9].total - me.total + Decimal("0.01")) if me and me.rank > 10 and len(uni) >= 10 else None
    return render(
        request,
        "ratings/top10.html",
        {"periods": periods, "period": period, "podium": uni[:3], "uni": uni[:10], "faculty": faculty,
         "fac_rows": fac_rows, "me": me, "gap": gap, "total_count": len(uni)},
    )


@staff_required
def student_card(request, pk):
    student = get_object_or_404(scoped_students(request.user).select_related("profile__faculty", "profile__group"), pk=pk)
    periods = all_periods()
    period = resolve_period(request.GET.get("davr"), periods)
    criteria = list(Criterion.objects.filter(is_active=True))
    rows = rating_rows(None, period, faculty=getattr(student.profile, "faculty_id", None), criteria=criteria)
    mine = next((r for r in rows if r.student.pk == student.pk), None)
    ach = Achievement.objects.filter(student=student).exclude(status=Achievement.Status.DRAFT).select_related("criterion")
    manual = ManualScore.objects.filter(student=student).select_related("criterion", "given_by")
    if period and period.semester:
        ach, manual = ach.filter(semester=period.semester), manual.filter(semester=period.semester)
    elif period:
        ach, manual = ach.filter(semester__academic_year=period.year), manual.filter(semester__academic_year=period.year)
    return render(
        request,
        "ratings/student_card.html",
        {"student": student, "profile": getattr(student, "profile", None), "periods": periods, "period": period,
         "row": mine, "faculty_size": len(rows), "bars": criterion_rows(mine.breakdown if mine else {}, criteria),
         "achievements": ach.order_by("-created_at")[:50], "manual": manual},
    )


@staff_required
def analytics(request):
    user = request.user
    periods = all_periods()
    period = resolve_period(request.GET.get("davr"), periods)
    criteria = list(Criterion.objects.filter(is_active=True))
    rows = rating_rows(user, period, criteria=criteria)
    stats = summary(rows)
    students_total = scoped_students(user).count()

    # Kesim: universitet darajasida fakultetlar, aks holda guruhlar.
    by_faculty = _is_university(user)
    buckets = defaultdict(list)
    for r in rows:
        p = r.profile
        key = (p.faculty.short_name or p.faculty.name) if by_faculty and p and p.faculty else (p.group.name if p and p.group else "—")
        buckets[key].append(r.total)
    compare = sorted(({"label": k, "avg": q2(sum(v) / len(v)), "n": len(v)} for k, v in buckets.items()), key=lambda x: -x["avg"])

    crit = []
    for i, c in enumerate(criteria):
        avg = q2(sum(r.cells[i] for r in rows) / len(rows)) if rows else Decimal("0")
        crit.append({"c": c, "avg": avg, "pct": f"{float(avg) / c.max_points * 100:.1f}" if c.max_points else "0"})
    weakest = min(crit, key=lambda x: float(x["pct"])) if rows else None

    hist = Counter(min(int(r.total // 10), 9) for r in rows)
    hist_max = max(hist.values(), default=0)
    histogram = [{"label": f"{b * 10}–{b * 10 + 10}", "n": hist.get(b, 0),
                  "pct": f"{hist.get(b, 0) / hist_max * 100:.1f}" if hist_max else "0"} for b in range(10)]

    ach = Achievement.objects.filter(**scope_filter(user)).exclude(status=Achievement.Status.DRAFT)
    if period and period.semester:
        ach = ach.filter(semester=period.semester)
        start, end = period.semester.start_date, period.semester.end_date
    elif period:
        ach = ach.filter(semester__academic_year=period.year)
        start, end = period.year.start_date, period.year.end_date
    else:
        ach, start, end = ach.none(), date.today(), date.today()
    status_counts = dict(ach.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    monthly_raw = Counter(
        (d.year, d.month) for d in ach.filter(status=Achievement.Status.APPROVED).values_list("event_date", flat=True)
    )
    end = min(end, timezone.localdate())
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month) and len(months) < 12:
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    month_max = max((monthly_raw.get(k, 0) for k in months), default=0)
    month_names = ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"]
    monthly = [{"label": month_names[mm - 1], "full": f"{month_names[mm - 1]} {yy}", "n": monthly_raw.get((yy, mm), 0),
                "pct": f"{monthly_raw.get((yy, mm), 0) / month_max * 100:.1f}" if month_max else "0"} for yy, mm in months]

    statuses = [(s, Achievement.Status(s).label, status_counts.get(s, 0)) for s in ("approved", "pending", "returned", "rejected")]
    status_total = sum(n for _, _, n in statuses)
    return render(
        request,
        "ratings/analytics.html",
        {"periods": periods, "period": period, "stats": stats, "students_total": students_total,
         "active_pct": f"{stats['active'] / students_total * 100:.0f}" if students_total else "0",
         "compare": compare, "compare_title": "Fakultetlar kesimida" if by_faculty else "Guruhlar kesimida",
         "crit": crit, "weakest": weakest, "histogram": histogram, "monthly": monthly,
         "statuses": [{"key": k, "label": lbl, "n": n, "pct": f"{n / status_total * 100:.1f}" if status_total else "0"} for k, lbl, n in statuses],
         "status_total": status_total, "scope_label": _scope_label(user)},
    )


@require_GET
def public_stats(request):
    """OTM sayti uchun ochiq statistika (JSON). Shaxsiy ma'lumot: faqat TOP-10 familiya va ism bosh harfi."""
    site = SiteSettings.load()
    if not site.public_stats_enabled:
        return JsonResponse({"detail": "Ochiq statistika o‘chirilgan."}, status=404)
    data = cache.get("public-stats")
    if data is None:
        period = resolve_period(None)
        criteria = list(Criterion.objects.filter(is_active=True))
        rows = rating_rows(None, period, criteria=criteria)
        faculties = defaultdict(list)
        for r in rows:
            if r.profile and r.profile.faculty:
                faculties[r.profile.faculty.name].append(r.total)
        stats = summary(rows)
        data = {
            "university": site.university_name,
            "period": period.label if period else None,
            "updated_at": timezone.now().isoformat(),
            "students_rated": stats["count"],
            "active_students": stats["active"],
            "average_score": float(stats["avg"]) if stats["avg"] is not None else None,
            "faculties": sorted(
                ({"name": k, "students": len(v), "average_score": float(q2(sum(v) / len(v)))} for k, v in faculties.items()),
                key=lambda x: -x["average_score"],
            ),
            "top10": [
                {"rank": r.rank, "name": _public_name(r.student), "faculty": r.profile.faculty.name if r.profile and r.profile.faculty else None,
                 "course": r.profile.course if r.profile else None, "score": float(r.total)}
                for r in rows[:10]
            ],
            "criteria": [{"code": c.code, "title": c.short_title, "max_points": c.max_points} for c in criteria],
        }
        cache.set("public-stats", data, 600)
    resp = JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Cache-Control"] = "public, max-age=600"
    return resp


def _public_name(user):
    initial = f" {user.first_name[:1]}." if user.first_name else ""
    return f"{user.last_name}{initial}".strip() or "—"
