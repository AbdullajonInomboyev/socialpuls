from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from accounts.models import Role
from core.models import SiteSettings
from core.permissions import reviewer_required, scope_filter, scoped_students, staff_required, student_required
from structure.models import Semester

from . import services
from .forms import AchievementForm, ReviewForm
from .models import Achievement, AchievementFile, Criterion, ManualScore
from .validators import ACCEPT_ATTR, MAX_FILES

Status = Achievement.Status
DAILY_LIMIT = 20


# ---------- Talaba ----------

STATUS_TABS = [
    ("", "Hammasi"),
    (Status.PENDING, "Tekshiruvda"),
    (Status.RETURNED, "Qaytarilgan"),
    (Status.APPROVED, "Tasdiqlangan"),
    (Status.REJECTED, "Rad etilgan"),
    (Status.DRAFT, "Qoralama"),
]


@student_required
def my_list(request):
    user = request.user
    base = Achievement.objects.filter(student=user)
    semesters = list(
        Semester.objects.filter(Q(achievements__student=user) | Q(is_current=True)).distinct().select_related("academic_year")
    )
    current = next((s for s in semesters if s.is_current), None)
    sem_param = request.GET.get("semestr")
    semester = next((s for s in semesters if str(s.pk) == sem_param), current if sem_param is None else None)
    if semester:
        base = base.filter(semester=semester)

    counts = dict(base.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    status = request.GET.get("holat", "")
    if status not in dict(STATUS_TABS):
        status = ""
    qs = base.filter(status=status) if status else base
    qs = qs.select_related("criterion", "semester", "level").annotate(file_count=Count("files"))
    page = Paginator(qs.order_by("-created_at"), 15).get_page(request.GET.get("page"))
    tabs = [
        {"key": k, "label": label, "count": sum(counts.values()) if not k else counts.get(k, 0), "active": k == status}
        for k, label in STATUS_TABS
    ]
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(
        request,
        "achievements/my_list.html",
        {
            "page": page,
            "tabs": tabs,
            "semesters": semesters,
            "semester": semester,
            "status": status,
            "keep": keep.urlencode(),
            "can_upload": _upload_block_reason(user, current) is None,
            "upload_block": _upload_block_reason(user, current),
        },
    )


def _upload_block_reason(user, semester):
    if not SiteSettings.load().student_upload_enabled:
        return "Yutuq yuklash vaqtincha yopilgan. Keyinroq urinib ko‘ring."
    if semester is None:
        return "Joriy semestr belgilanmagan. Mas’ullar sozlagandan keyin yuklash ochiladi."
    if semester.is_closed:
        return "Joriy semestr yopilgan, yangi yutuq qabul qilinmaydi."
    return None


def _criteria_context(user, semester, form):
    """Mezon kartalari: har biri uchun maksimum, shu semestrda tasdiqlangan ball va darajalar."""
    approved = dict(
        Achievement.objects.filter(student=user, semester=semester, status=Status.APPROVED)
        .values("criterion_id")
        .annotate(s=Sum("points"))
        .values_list("criterion_id", "s")
    )
    cards = []
    for c in form.fields["criterion"].queryset.prefetch_related("levels"):
        got = approved.get(c.pk) or Decimal("0")
        cards.append({"c": c, "got": min(got, Decimal(c.max_points)), "full": got >= c.max_points, "levels": list(c.levels.all())})
    levels = {str(card["c"].pk): [[str(lv.pk), lv.title, str(lv.points)] for lv in card["levels"]] for card in cards}
    return {"criteria_cards": cards, "levels_json": levels}


@student_required
def create(request):
    user = request.user
    semester = Semester.current()
    reason = _upload_block_reason(user, semester)
    if reason:
        messages.error(request, reason)
        return redirect("achievements:my_list")

    since = timezone.now() - timedelta(days=1)
    if request.method == "POST" and Achievement.objects.filter(student=user, created_at__gte=since).count() >= DAILY_LIMIT:
        messages.error(request, f"Bir kunda ko‘pi bilan {DAILY_LIMIT} ta yutuq qo‘shish mumkin. Ertaga davom eting.")
        return redirect("achievements:my_list")

    form = AchievementForm(request.POST or None, request.FILES or None, semester=semester)
    if request.method == "GET" and request.GET.get("mezon"):
        form.initial["criterion"] = request.GET["mezon"]
    if request.method == "POST" and form.is_valid():
        submit = request.POST.get("intent") != "draft"
        try:
            a = services.save_student_achievement(request, form, semester, submit=submit)
        except services.WorkflowError as e:
            form.add_error(None, str(e))
        else:
            messages.success(request, "Yutuq tekshiruvga yuborildi." if submit else "Qoralama saqlandi.")
            return redirect("achievements:detail", pk=a.pk)
    return render(request, "achievements/form.html", _form_context(user, semester, form, None))


def _form_context(user, semester, form, achievement):
    ctx = {"form": form, "semester": semester, "achievement": achievement, "accept": ACCEPT_ATTR,
           "max_files": MAX_FILES, "max_mb": settings.UPLOAD_MAX_MB}
    ctx.update(_criteria_context(user, semester, form))
    return ctx


@student_required
def edit(request, pk):
    user = request.user
    a = get_object_or_404(Achievement.objects.select_related("semester", "criterion"), pk=pk, student=user)
    if not a.is_editable_by_student:
        messages.error(request, "Bu yutuqni hozir tahrirlab bo‘lmaydi.")
        return redirect("achievements:detail", pk=a.pk)
    reason = _upload_block_reason(user, a.semester) if a.semester.is_current else None
    if reason:
        messages.error(request, reason)
        return redirect("achievements:detail", pk=a.pk)

    form = AchievementForm(request.POST or None, request.FILES or None, instance=a, semester=a.semester)
    if request.method == "POST" and form.is_valid():
        submit = request.POST.get("intent") != "draft"
        try:
            services.save_student_achievement(request, form, a.semester, submit=submit)
        except services.WorkflowError as e:
            form.add_error(None, str(e))
        else:
            messages.success(request, "Yutuq qayta yuborildi." if submit else "O‘zgarishlar saqlandi.")
            return redirect("achievements:detail", pk=a.pk)
    return render(request, "achievements/form.html", _form_context(user, a.semester, form, a))


@student_required
@require_POST
def delete(request, pk):
    a = get_object_or_404(Achievement, pk=pk, student=request.user)
    try:
        services.delete_student_achievement(request, a)
    except services.WorkflowError as e:
        messages.error(request, str(e))
        return redirect("achievements:detail", pk=pk)
    messages.success(request, "Yutuq o‘chirildi.")
    return redirect("achievements:my_list")


# ---------- Umumiy: ko'rish va fayl ----------

@login_required
def detail(request, pk):
    a = get_object_or_404(
        Achievement.objects.select_related("criterion", "semester__academic_year", "level", "reviewer", "student__profile__group", "student__profile__faculty"),
        pk=pk,
    )
    user = request.user
    # Ruxsatsiz foydalanuvchiga yutuq borligi ham bildirilmaydi.
    if not services.can_view(user, a) or (a.status == Status.DRAFT and a.student_id != user.pk):
        raise Http404
    if user.role in (Role.FACULTY_ADMIN, Role.TUTOR) and services.can_review(user, a):
        return review(request, a)
    return render(
        request,
        "achievements/detail.html",
        {
            "a": a,
            "files": list(a.files.all()),
            "events": a.events.select_related("actor"),
            "is_owner": a.student_id == user.pk,
            "can_delete": a.student_id == user.pk and a.status in (Status.DRAFT, Status.PENDING) and not a.semester.is_closed,
        },
    )


@login_required
@xframe_options_sameorigin
def file_view(request, pk):
    f = get_object_or_404(AchievementFile.objects.select_related("achievement__semester"), pk=pk)
    a = f.achievement
    if not services.can_view(request.user, a) or (a.status == Status.DRAFT and a.student_id != request.user.pk):
        raise Http404
    download = request.GET.get("yuklab") == "1"
    if settings.USE_X_ACCEL_REDIRECT:
        response = HttpResponse(content_type=f.content_type)
        response["X-Accel-Redirect"] = settings.X_ACCEL_PREFIX + f.file.name
        response["Content-Disposition"] = content_disposition_header(download, f.original_name)
    else:
        try:
            handle = f.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(handle, as_attachment=download, filename=f.original_name, content_type=f.content_type)
    response["Cache-Control"] = "private, max-age=600"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'self'"
    return response


# ---------- Mas'ul: tekshiruv ----------

REVIEW_TABS = [
    (Status.PENDING, "Kutilmoqda"),
    (Status.RETURNED, "Qaytarilgan"),
    (Status.APPROVED, "Tasdiqlangan"),
    (Status.REJECTED, "Rad etilgan"),
]


@staff_required
def queue(request):
    user = request.user
    scope = scope_filter(user)
    base = Achievement.objects.exclude(status=Status.DRAFT).filter(**scope)
    current = Semester.current()
    sem_id = request.GET.get("semestr")
    semesters = list(Semester.objects.select_related("academic_year").order_by("-academic_year__start_date", "-number")[:6])
    semester = next((s for s in semesters if str(s.pk) == sem_id), current if not sem_id else None)
    if semester:
        base = base.filter(semester=semester)

    groups = services.reviewable_groups(user) if user.role in (Role.FACULTY_ADMIN, Role.TUTOR) else None
    criteria = Criterion.objects.filter(input_mode=Criterion.InputMode.UPLOAD)
    filters = {"q": request.GET.get("q", "").strip()[:80], "mezon": request.GET.get("mezon", ""), "guruh": request.GET.get("guruh", "")}
    if filters["q"]:
        q = filters["q"]
        base = base.filter(
            Q(title__icontains=q) | Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q) | Q(student__hemis_id=q)
        )
    if filters["mezon"].isdigit():
        base = base.filter(criterion_id=filters["mezon"])
    if filters["guruh"].isdigit():
        base = base.filter(student__profile__group_id=filters["guruh"])

    counts = dict(base.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    status = request.GET.get("holat", Status.PENDING)
    if status not in dict(REVIEW_TABS):
        status = Status.PENDING
    qs = base.filter(status=status).select_related("criterion", "student__profile__group", "student__profile__faculty", "reviewer")
    qs = qs.annotate(file_count=Count("files"))
    qs = qs.order_by("submitted_at", "pk") if status == Status.PENDING else qs.order_by("-reviewed_at", "-pk")
    page = Paginator(qs, 20).get_page(request.GET.get("page"))

    keep = request.GET.copy()
    keep.pop("page", None)
    keep.pop("holat", None)
    tabs = [{"key": k, "label": label, "count": counts.get(k, 0), "active": k == status} for k, label in REVIEW_TABS]
    return render(
        request,
        "achievements/queue.html",
        {
            "page": page,
            "tabs": tabs,
            "status": status,
            "filters": filters,
            "criteria": criteria,
            "groups": groups,
            "semesters": semesters,
            "semester": semester,
            "keep": keep.urlencode(),
            "is_reviewer": user.role in (Role.FACULTY_ADMIN, Role.TUTOR),
        },
    )


@reviewer_required
def review(request, a):
    """Mas'ul uchun yutuq sahifasi: hujjat ko'rish va qaror. detail() dan chaqiriladi."""
    form = ReviewForm(request.POST or None, achievement=a)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        try:
            services.review(request, a.pk, cd["action"], points=cd.get("points"), comment=cd["comment"], version=cd["version"])
        except services.WorkflowError as e:
            form.add_error(None, str(e))
        else:
            label = {"approve": "Tasdiqlandi", "reject": "Rad etildi", "return": "Talabaga qaytarildi", "comment": "Izoh yuborildi"}
            messages.success(request, f"{label[cd['action']]}: {a.title}")
            nxt = services.next_pending(request.user, exclude_pk=a.pk) if cd["action"] != "comment" else None
            if nxt and request.POST.get("then") == "next":
                return redirect("achievements:detail", pk=nxt.pk)
            if cd["action"] == "comment":
                return redirect("achievements:detail", pk=a.pk)
            return redirect(reverse("achievements:queue"))

    student = a.student
    in_criterion = (
        Achievement.objects.filter(student=student, semester=a.semester, criterion=a.criterion, status=Status.APPROVED)
        .exclude(pk=a.pk)
        .aggregate(s=Sum("points"))["s"]
        or Decimal("0")
    )
    others = (
        Achievement.objects.filter(student=student, semester=a.semester)
        .exclude(pk=a.pk)
        .exclude(status=Status.DRAFT)
        .select_related("criterion")
        .order_by("-created_at")[:6]
    )
    return render(
        request,
        "achievements/review.html",
        {
            "a": a,
            "form": form,
            "files": list(a.files.all()),
            "events": a.events.select_related("actor"),
            "levels": list(a.criterion.levels.all()),
            "in_criterion": in_criterion,
            "room": max(Decimal("0"), Decimal(a.criterion.max_points) - in_criterion),
            "others": others,
            "pending_left": Achievement.objects.filter(status=Status.PENDING, **scope_filter(request.user)).exclude(pk=a.pk).count(),
        },
    )


# ---------- Mas'ul: qo'lda baholanadigan mezonlar ----------

@reviewer_required
def manual_scores(request):
    user = request.user
    semester = Semester.current()
    groups = list(services.reviewable_groups(user).select_related("faculty"))
    criteria = list(Criterion.objects.filter(is_active=True, input_mode=Criterion.InputMode.MANUAL))
    group = next((g for g in groups if str(g.pk) == request.GET.get("guruh")), groups[0] if groups else None)
    ctx = {"semester": semester, "groups": groups, "group": group, "criteria": criteria, "rows": [], "errors": {}}
    if not (semester and group and criteria):
        return render(request, "achievements/manual.html", ctx)

    students = list(
        scoped_students(user).filter(profile__group=group).order_by("last_name", "first_name").select_related("profile")
    )
    scores = {
        (m.student_id, m.criterion_id): m
        for m in ManualScore.objects.filter(semester=semester, student__in=students, criterion__in=criteria)
    }
    errors, values, raw = {}, {}, {}
    if request.method == "POST":
        for s in students:
            for c in criteria:
                key = f"s{s.pk}_c{c.pk}"
                text = request.POST.get(key, "").strip().replace(",", ".")
                raw[key] = text
                if text == "":
                    values[(s.pk, c.pk)] = None
                    continue
                try:
                    val = Decimal(text)
                except InvalidOperation:
                    errors[key] = "Son kiriting"
                    continue
                if not val.is_finite() or val < 0 or val > c.max_points:
                    errors[key] = f"0 dan {c.max_points} gacha"
                elif val != val.quantize(Decimal("0.01")):
                    errors[key] = "Ko‘pi bilan 2 xona"
                else:
                    values[(s.pk, c.pk)] = val
        if errors:
            messages.error(request, "Ba’zi qiymatlar noto‘g‘ri. Qizil bilan belgilangan kataklarni tuzating.")
        else:
            try:
                n = services.save_manual_scores(request, semester, criteria, students, values)
            except services.WorkflowError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"Saqlandi: {n} ta o‘zgarish." if n else "O‘zgarish yo‘q.")
                return redirect(f"{reverse('achievements:manual')}?guruh={group.pk}")

    rows = []
    for s in students:
        cells = []
        for c in criteria:
            key = f"s{s.pk}_c{c.pk}"
            m = scores.get((s.pk, c.pk))
            value = raw[key] if key in raw else ("" if m is None else f"{m.points.normalize():f}")
            cells.append({"key": key, "value": value, "error": errors.get(key), "c": c, "given_by": m.given_by if m else None})
        rows.append({"s": s, "cells": cells})
    ctx.update(rows=rows, errors=errors, filled=sum(1 for v in scores.values()), total_cells=len(students) * len(criteria))
    return render(request, "achievements/manual.html", ctx)
