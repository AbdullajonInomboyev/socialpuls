"""Boshqaruv bo'limi: HEMIS, xodimlar, sozlamalar, semestrlar, audit jurnali va ommaviy xabarlar."""
import uuid
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from accounts.models import STAFF_ROLES, Role, User
from achievements.models import Achievement, PrivateStorage
from audit.models import ActionLog
from audit.services import log_action
from hemis.models import HemisSyncRun
from hemis.sync import SyncBusy, excel_template, import_rows, parse_excel, sync_all
from notifications.delivery import notify_many
from notifications.models import Broadcast
from ratings.services import recalculate_semester
from structure.models import AcademicYear, Semester

from .manage_forms import AcademicYearForm, BroadcastForm, SiteSettingsForm, StaffForm
from .models import SiteSettings
from .permissions import moderator_required, scoped_students, staff_required

BROADCAST_DAILY_LIMIT = 10
IMPORT_SESSION_KEY = "pending_student_import"


# ---------- HEMIS ----------

@moderator_required
def hemis_page(request):
    from django.conf import settings

    preview = None
    if request.method == "POST" and request.POST.get("op") == "sync":
        try:
            run = sync_all(user=request.user, request=request)
        except SyncBusy as e:
            messages.error(request, str(e))
        else:
            if run.status == HemisSyncRun.Status.SUCCESS:
                messages.success(request, f"Sinxronizatsiya tugadi: {run.created_count} yangi, {run.updated_count} yangilandi.")
            else:
                messages.error(request, f"Sinxronizatsiya xatosi: {run.error}")
        return redirect("core:manage_hemis")
    if request.method == "POST" and request.POST.get("op") == "excel":
        f = request.FILES.get("file")
        if not f or not f.name.lower().endswith(".xlsx") or f.size > 15 * 1024 * 1024:
            messages.error(request, ".xlsx fayl tanlang (15 MB gacha).")
            return redirect("core:manage_hemis")
        rows, errors = parse_excel(f)
        _drop_pending_import(request)
        if rows and not errors:
            # Tasdiqlashgacha fayl maxfiy papkada turadi; qayta yuklash shart emas.
            f.seek(0)
            request.session[IMPORT_SESSION_KEY] = PrivateStorage().save(f"imports/{uuid.uuid4().hex}.xlsx", f)
        preview = {"rows": rows[:15], "count": len(rows), "errors": errors[:50], "error_count": len(errors), "name": f.name}
    if request.method == "POST" and request.POST.get("op") == "apply":
        name = request.session.get(IMPORT_SESSION_KEY)
        storage = PrivateStorage()
        if not name or not storage.exists(name):
            messages.error(request, "Tekshirilgan fayl topilmadi. Faylni qayta yuklang.")
            return redirect("core:manage_hemis")
        with storage.open(name) as fh:
            rows, errors = parse_excel(fh)
        _drop_pending_import(request)
        if errors or not rows:
            messages.error(request, "Faylda xatolar bor, hech narsa yozilmadi.")
        else:
            run = import_rows(rows, user=request.user, request=request)
            messages.success(request, f"Import tugadi: {run.created_count} yangi, {run.updated_count} yangilandi.")
        return redirect("core:manage_hemis")
    runs = HemisSyncRun.objects.select_related("triggered_by")[:20]
    return render(request, "manage/hemis.html", {"runs": runs, "preview": preview, "mode": settings.HEMIS_MODE,
                                                 "token_set": bool(settings.HEMIS_API_TOKEN), "api_url": settings.HEMIS_DATA_API_URL})


def _drop_pending_import(request):
    name = request.session.pop(IMPORT_SESSION_KEY, None)
    if name:
        PrivateStorage().delete(name)


@moderator_required
def hemis_template(request):
    resp = HttpResponse(excel_template(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="talabalar-shablon.xlsx"'
    return resp


# ---------- Xodimlar ----------

@moderator_required
def staff_list(request):
    qs = User.objects.filter(role__in=STAFF_ROLES).select_related("faculty").prefetch_related("tutor_groups").order_by("role", "last_name")
    q = request.GET.get("q", "").strip()[:60]
    role = request.GET.get("rol", "")
    if q:
        qs = qs.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q))
    if role in {r.value for r in Role if r != Role.STUDENT}:
        qs = qs.filter(role=role)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    roles = [(r.value, r.label) for r in Role if r != Role.STUDENT]
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(request, "manage/staff_list.html", {"page": page, "q": q, "role": role, "roles": roles, "keep": keep.urlencode()})


def _can_edit_staff(actor, target):
    if actor.is_superuser:
        return True
    if target.is_superuser or target.pk == actor.pk:
        return False
    return not (actor.role == Role.MODERATOR and target.role == Role.LEADERSHIP)


def _send_set_password(request, user):
    # PasswordResetForm.get_users() parolsiz (yangi) hisoblarni o'tkazib yuboradi, shuning uchun xat to'g'ridan-to'g'ri yuboriladi.
    context = {
        "email": user.email, "user": user, "domain": request.get_host(), "site_name": "Ijtimoiy Faollik",
        "uid": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user),
        "protocol": "https" if request.is_secure() else "http",
    }
    PasswordResetForm().send_mail("accounts/email/password_reset_subject.txt", "accounts/email/password_reset.txt",
                                  context, None, user.email)


@moderator_required
def staff_edit(request, pk=None):
    target = get_object_or_404(User, pk=pk, role__in=STAFF_ROLES) if pk else None
    if target and not _can_edit_staff(request.user, target):
        messages.error(request, "Bu hisobni tahrirlashga ruxsatingiz yo‘q.")
        return redirect("core:manage_staff")
    form = StaffForm(request.POST or None, instance=target, actor=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            pw = form.cleaned_data.get("password")
            if pw:
                user.set_password(pw)
            elif user.pk is None:
                user.set_unusable_password()
            user.save()
            form.save_m2m()
        is_new = target is None
        if is_new and not pw:
            _send_set_password(request, user)
        log_action(request, "staff.create" if is_new else "staff.update",
                   f"Xodim {'yaratildi' if is_new else 'tahrirlandi'}: {user.username} ({user.get_role_display()})", obj=user)
        messages.success(request, "Xodim saqlandi." + (" Parol o‘rnatish havolasi emailga yuborildi." if is_new and not pw else ""))
        return redirect("core:manage_staff")
    return render(request, "manage/staff_form.html", {"form": form, "target": target})


@moderator_required
@require_POST
def staff_reset(request, pk):
    target = get_object_or_404(User, pk=pk, role__in=STAFF_ROLES, is_active=True)
    if not _can_edit_staff(request.user, target) or not target.email:
        messages.error(request, "Havola yuborib bo‘lmadi: ruxsat yo‘q yoki email ko‘rsatilmagan.")
    else:
        _send_set_password(request, target)
        log_action(request, "staff.reset_link", f"Parol tiklash havolasi yuborildi: {target.username}", obj=target)
        messages.success(request, f"{target.email} manziliga parol tiklash havolasi yuborildi.")
    return redirect("core:manage_staff")


# ---------- Sozlamalar va semestrlar ----------

@moderator_required
def settings_page(request):
    site = SiteSettings.load()
    form = SiteSettingsForm(request.POST or None, instance=SiteSettings.objects.get(pk=site.pk))
    year_form = AcademicYearForm(request.POST or None, prefix="y") if request.POST.get("op") == "year" else AcademicYearForm(prefix="y")
    if request.method == "POST" and request.POST.get("op") == "settings":
        if form.is_valid():
            form.save()
            log_action(request, "settings.update", "Tizim sozlamalari o‘zgartirildi: " + ", ".join(form.changed_data))
            messages.success(request, "Sozlamalar saqlandi.")
            return redirect("core:manage_settings")
    elif request.method == "POST" and request.POST.get("op") == "year":
        form = SiteSettingsForm(instance=SiteSettings.objects.get(pk=site.pk))
        if year_form.is_valid():
            c = year_form.cleaned_data
            with transaction.atomic():
                y = AcademicYear.objects.create(name=c["name"], start_date=c["sem1_start"], end_date=c["sem2_end"])
                Semester.objects.create(academic_year=y, number=1, start_date=c["sem1_start"], end_date=c["sem1_end"])
                Semester.objects.create(academic_year=y, number=2, start_date=c["sem2_start"], end_date=c["sem2_end"])
            log_action(request, "semester.create_year", f"O‘quv yili yaratildi: {y.name}", obj=y)
            messages.success(request, f"{y.name} o‘quv yili yaratildi.")
            return redirect("core:manage_settings")
    years = list(AcademicYear.objects.prefetch_related("semesters").order_by("-start_date"))
    pending = dict(Achievement.objects.filter(status=Achievement.Status.PENDING).values_list("semester_id").annotate(n=Count("id")))
    for y in years:
        for sem in y.semesters.all():
            sem.pending = pending.get(sem.pk, 0)
    return render(request, "manage/settings.html", {"form": form, "year_form": year_form, "years": years})


@moderator_required
@require_POST
def semester_action(request, pk, action):
    sem = get_object_or_404(Semester.objects.select_related("academic_year"), pk=pk)
    with transaction.atomic():
        if action == "joriy":
            if sem.is_closed:
                messages.error(request, "Yopilgan semestrni joriy qilib bo‘lmaydi.")
                return redirect("core:manage_settings")
            Semester.objects.filter(is_current=True).update(is_current=False)
            AcademicYear.objects.filter(is_current=True).exclude(pk=sem.academic_year_id).update(is_current=False)
            sem.is_current = True
            sem.save(update_fields=["is_current"])
            AcademicYear.objects.filter(pk=sem.academic_year_id).update(is_current=True)
            recalculate_semester(sem)
            text = f"Joriy semestr: {sem}"
        elif action == "yopish":
            if sem.is_closed:
                return redirect("core:manage_settings")
            pending = Achievement.objects.filter(semester=sem, status=Achievement.Status.PENDING).count()
            if pending and request.POST.get("force") != "1":
                messages.error(request, f"Semestrda {pending} ta tekshirilmagan yutuq bor. Avval ularni ko‘rib chiqing yoki baribir yoping.")
                return redirect("core:manage_settings")
            recalculate_semester(sem)  # GPA shu paytdagi qiymatda muzlatiladi
            sem.is_closed, sem.is_current = True, False
            sem.save(update_fields=["is_closed", "is_current"])
            text = f"Semestr yopildi: {sem}"
        else:
            messages.error(request, "Noma’lum amal.")
            return redirect("core:manage_settings")
    log_action(request, f"semester.{action}", text, obj=sem)
    messages.success(request, text)
    return redirect("core:manage_settings")


# ---------- Audit jurnali ----------

@moderator_required
def audit_log(request):
    qs = ActionLog.objects.select_related("actor")
    f = {"q": request.GET.get("q", "").strip()[:80], "amal": request.GET.get("amal", ""), "dan": request.GET.get("dan", ""), "gacha": request.GET.get("gacha", "")}
    if f["q"]:
        cond = Q(description__icontains=f["q"]) | Q(actor__username__icontains=f["q"]) | Q(actor__last_name__icontains=f["q"])
        if _is_ip(f["q"]):
            cond |= Q(ip_address=f["q"])
        qs = qs.filter(cond)
    if f["amal"]:
        qs = qs.filter(action__startswith=f["amal"])
    tz = timezone.get_current_timezone()
    for key, op in (("dan", "gte"), ("gacha", "lt")):
        try:
            d = datetime.strptime(f[key], "%Y-%m-%d").date()
        except ValueError:
            f[key] = ""
            continue
        if key == "gacha":
            d += timedelta(days=1)
        qs = qs.filter(**{f"created_at__{op}": timezone.make_aware(datetime.combine(d, time.min), tz)})
    groups = [("login", "Kirish"), ("achievement", "Yutuqlar"), ("manual_score", "Qo‘lda ball"), ("rating", "Eksport"),
              ("criteria", "Mezonlar"), ("staff", "Xodimlar"), ("settings", "Sozlamalar"), ("semester", "Semestrlar"),
              ("hemis", "HEMIS"), ("students", "Import"), ("broadcast", "Xabarlar"), ("password", "Parol"), ("telegram", "Telegram")]
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(request, "manage/audit.html", {"page": page, "f": f, "groups": groups, "keep": keep.urlencode()})


def _is_ip(value):
    import ipaddress

    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


# ---------- Ommaviy xabarlar ----------

def _recipients(user, cd):
    qs = scoped_students(user)
    if cd.get("faculty"):
        qs = qs.filter(profile__faculty=cd["faculty"])
    if cd.get("groups"):
        qs = qs.filter(profile__group__in=cd["groups"])
    if cd.get("course"):
        qs = qs.filter(profile__course=cd["course"])
    if cd.get("only_inactive"):
        sem = Semester.current()
        if sem:
            active = Achievement.objects.filter(semester=sem, status=Achievement.Status.APPROVED).values("student_id")
            qs = qs.exclude(pk__in=active)
    return qs


@staff_required
def broadcasts(request):
    user = request.user
    form = BroadcastForm(request.POST or None, user=user)
    confirm_count = None
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        recipients = _recipients(user, cd)
        count = recipients.count()
        since = timezone.now() - timedelta(days=1)
        if Broadcast.objects.filter(sender=user, created_at__gte=since).count() >= BROADCAST_DAILY_LIMIT:
            form.add_error(None, f"Bir kunda ko‘pi bilan {BROADCAST_DAILY_LIMIT} ta ommaviy xabar yuborish mumkin.")
        elif count == 0:
            form.add_error(None, "Tanlangan shartlarga mos talaba topilmadi.")
        elif not cd.get("confirm"):
            confirm_count = count
            data = request.POST.copy()
            data["confirm"] = "on"
            form = BroadcastForm(data, user=user)
            form.is_valid()
        else:
            with transaction.atomic():
                b = Broadcast.objects.create(sender=user, title=cd["title"], body=cd["body"], via_email=cd["via_email"],
                                             via_telegram=cd["via_telegram"], recipient_count=count)
                notify_many(list(recipients.only("pk", "email", "telegram_chat_id", "notify_email", "notify_telegram")),
                            cd["title"], cd["body"], broadcast=b, email=cd["via_email"], tg=cd["via_telegram"])
            log_action(request, "broadcast.send", f"Ommaviy xabar: “{b.title}”, {count} talaba", obj=b)
            messages.success(request, f"Xabar {count} talabaga yuborildi.")
            return redirect("core:manage_broadcasts")
    history = Broadcast.objects.select_related("sender")
    if not (user.is_superuser or user.role in (Role.LEADERSHIP, Role.MODERATOR)):
        history = history.filter(sender=user)
    return render(request, "manage/broadcasts.html", {"form": form, "confirm_count": confirm_count, "history": history[:20]})
