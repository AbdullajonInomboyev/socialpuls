"""Yutuq ish jarayoni: yuborish, tekshirish, qo'lda ball qo'yish. Hamma holat o'zgarishi shu yerdan o'tadi."""
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import REVIEWER_ROLES, Role
from audit.services import log_action
from core.permissions import scoped_students
from notifications.delivery import notify
from notifications.models import Notification
from ratings.services import recalculate
from structure.models import Group

from .models import Achievement, AchievementFile, ManualScore, ReviewEvent
from .validators import clean_filename

Status = Achievement.Status
Action = ReviewEvent.Action


class WorkflowError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato (noto'g'ri holat, yopilgan semestr va h.k.)."""


def can_view(user, achievement):
    if achievement.student_id == user.pk:
        return True
    if user.role == Role.STUDENT:
        return False
    return scoped_students(user).filter(pk=achievement.student_id).exists()


def can_review(user, achievement):
    return (
        user.role in REVIEWER_ROLES
        and achievement.student_id != user.pk
        and not achievement.semester.is_closed
        and achievement.status != Status.DRAFT
        and scoped_students(user).filter(pk=achievement.student_id).exists()
    )


def reviewable_groups(user):
    if user.role == Role.FACULTY_ADMIN and user.faculty_id:
        return Group.objects.filter(faculty_id=user.faculty_id)
    if user.role == Role.TUTOR:
        return user.tutor_groups.all()
    return Group.objects.none()


def attach_files(achievement, file_types):
    for f, content_type in file_types:
        AchievementFile.objects.create(
            achievement=achievement, file=f, original_name=clean_filename(f.name), content_type=content_type, size=f.size
        )


@transaction.atomic
def save_student_achievement(request, form, semester, submit):
    """Yangi yoki tahrirlangan yutuqni saqlaydi. submit=True bo'lsa tekshiruvga yuboriladi."""
    user = request.user
    is_new = form.instance.pk is None
    achievement = form.save(commit=False)
    previous = None if is_new else Achievement.objects.select_for_update().get(pk=achievement.pk).status
    if not is_new and previous not in (Status.DRAFT, Status.RETURNED):
        raise WorkflowError("Bu yutuq tekshiruvda yoki baholangan, uni tahrirlab bo‘lmaydi.")
    if submit and form.total_files == 0:
        raise WorkflowError("Tekshiruvga yuborish uchun kamida bitta tasdiqlovchi hujjat biriktiring.")

    if is_new:
        achievement.student = user
        achievement.semester = semester
    if submit:
        achievement.status = Status.PENDING
        achievement.submitted_at = timezone.now()
    elif is_new:
        achievement.status = Status.DRAFT
    achievement.save()

    removing = set(form.cleaned_data.get("remove_files") or [])
    if removing:
        for f in achievement.files.filter(pk__in=removing):
            f.delete()
    attach_files(achievement, getattr(form, "file_types", []))

    if submit:
        action = Action.RESUBMITTED if previous == Status.RETURNED else Action.SUBMITTED
        ReviewEvent.objects.create(achievement=achievement, actor=user, action=action)
    verb = "yubordi" if submit else "qoralama saqladi"
    log_action(request, "achievement.submit" if submit else "achievement.save", f"Yutuq {verb}: {achievement.title}", obj=achievement)
    return achievement


@transaction.atomic
def delete_student_achievement(request, achievement):
    locked = Achievement.objects.select_for_update().get(pk=achievement.pk)
    if locked.status not in (Status.DRAFT, Status.PENDING) or locked.semester.is_closed:
        raise WorkflowError("Faqat qoralama yoki hali tekshirilmagan yutuqni o‘chirish mumkin.")
    log_action(request, "achievement.delete", f"Yutuq o‘chirildi: {locked.title}", obj=locked)
    for f in locked.files.all():
        f.delete()
    locked.delete()


NOTICE = {
    Action.APPROVED: ("Yutug‘ingiz tasdiqlandi", "“{title}” uchun {points} ball qo‘shildi."),
    Action.REJECTED: ("Yutug‘ingiz rad etildi", "“{title}”. Izoh: {comment}"),
    Action.RETURNED: ("Yutug‘ingiz qayta ishlashga qaytarildi", "“{title}”. Izoh: {comment}"),
    Action.POINTS_CHANGED: ("Yutug‘ingiz bali o‘zgartirildi", "“{title}” uchun ball endi {points}."),
    Action.COMMENTED: ("Yutug‘ingizga izoh qoldirildi", "“{title}”: {comment}"),
}


def _fmt(points):
    return f"{points:.2f}".rstrip("0").rstrip(".").replace(".", ",") if points is not None else ""


@transaction.atomic
def review(request, achievement_id, action, points=None, comment="", version=None):
    """Mas'ul qarori. Ruxsat, holat va bir vaqtdagi tahrir shu yerda qulf ostida tekshiriladi."""
    from .forms import version_of

    reviewer = request.user
    a = (
        Achievement.objects.select_for_update(of=("self",))
        .select_related("criterion", "semester", "student")
        .get(pk=achievement_id)
    )
    if not can_review(reviewer, a):
        raise WorkflowError("Bu yutuqni baholashga ruxsatingiz yo‘q yoki semestr yopilgan.")
    if version and version != version_of(a):
        raise WorkflowError("Bu yutuq boshqa mas’ul tomonidan o‘zgartirildi. Sahifani yangilang.")

    was_approved = a.status == Status.APPROVED
    now = timezone.now()
    if action == "approve":
        points = Decimal(points)
        if points <= 0 or points > a.criterion.max_points:
            raise WorkflowError(f"Ball 0 dan katta va {a.criterion.max_points} dan oshmasligi kerak.")
        event = Action.POINTS_CHANGED if was_approved else Action.APPROVED
        if was_approved and a.points == points and not comment:
            raise WorkflowError("Ball o‘zgarmadi.")
        a.status, a.points = Status.APPROVED, points
    elif action == "reject":
        event = Action.REJECTED
        a.status, a.points = Status.REJECTED, None
    elif action == "return":
        if a.status not in (Status.PENDING, Status.APPROVED):
            raise WorkflowError("Faqat tekshiruvdagi yoki tasdiqlangan yutuqni qaytarish mumkin.")
        event = Action.RETURNED
        a.status, a.points = Status.RETURNED, None
    elif action == "comment":
        event = Action.COMMENTED
    else:
        raise WorkflowError("Noma’lum amal.")

    if event != Action.COMMENTED:
        a.reviewer = reviewer
        a.reviewed_at = now
        a.reviewer_comment = comment
    a.save()
    ReviewEvent.objects.create(
        achievement=a, actor=reviewer, action=event, comment=comment, points=a.points if action == "approve" else None
    )

    if was_approved or a.status == Status.APPROVED:
        recalculate(a.student, a.semester)

    title, body = NOTICE[event]
    notify(
        a.student, title, body.format(title=a.title, points=_fmt(a.points), comment=comment),
        link=reverse("achievements:detail", args=[a.pk]), kind=Notification.Kind.REVIEW,
    )
    log_action(
        request, f"achievement.{action}", f"{a.student.full_name}: “{a.title}” ({ReviewEvent.Action(event).label})",
        obj=a, points=_fmt(a.points), comment=comment[:200],
    )
    return a


def next_pending(user, exclude_pk=None):
    from core.permissions import scope_filter

    qs = Achievement.objects.filter(status=Status.PENDING, semester__is_closed=False, **scope_filter(user))
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.order_by("submitted_at", "pk").first()


@transaction.atomic
def save_manual_scores(request, semester, criteria, students, values):
    """values: {(student_id, criterion_id): Decimal | None}. None = ballni olib tashlash.

    Faqat o'zgargan qiymatlar yoziladi, keyin tegishli talabalar bali qayta hisoblanadi.
    """
    if semester.is_closed:
        raise WorkflowError("Semestr yopilgan, ballarni o‘zgartirib bo‘lmaydi.")
    existing = {
        (m.student_id, m.criterion_id): m
        for m in ManualScore.objects.select_for_update().filter(semester=semester, student__in=students, criterion__in=criteria)
    }
    by_id = {s.pk: s for s in students}
    changed_students = set()
    changes = 0
    for (sid, cid), value in values.items():
        current = existing.get((sid, cid))
        if value is None:
            if current:
                current.delete()
                changed_students.add(sid)
                changes += 1
            continue
        if current and current.points == value:
            continue
        ManualScore.objects.update_or_create(
            student_id=sid, semester=semester, criterion_id=cid, defaults={"points": value, "given_by": request.user}
        )
        changed_students.add(sid)
        changes += 1
    for sid in changed_students:
        recalculate(by_id[sid], semester)
    if changes:
        log_action(request, "manual_score.save", f"Qo‘lda ball: {changes} ta o‘zgarish, {len(changed_students)} talaba", semester=str(semester))
    return changes
