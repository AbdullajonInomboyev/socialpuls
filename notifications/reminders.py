"""Oylik eslatma: o'tgan oyda bitta ham yutuq yubormagan talabalarga xabar."""
from datetime import date, datetime, time

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from achievements.models import Achievement
from core.models import SiteSettings
from structure.models import Semester

from .delivery import notify_many
from .models import Notification, ReminderRun

MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]


def previous_month(today):
    first = today.replace(day=1)
    return date(first.year - 1, 12, 1) if first.month == 1 else date(first.year, first.month - 1, 1)


def inactive_students(month_start):
    month_end = date(month_start.year + (month_start.month == 12), month_start.month % 12 + 1, 1)
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(month_start, time.min), tz)
    end = timezone.make_aware(datetime.combine(month_end, time.min), tz)
    active_ids = Achievement.objects.filter(submitted_at__gte=start, submitted_at__lt=end).values("student_id")
    return User.objects.filter(role=Role.STUDENT, is_active=True).exclude(pk__in=active_ids)


def send_monthly(today=None, force=False):
    """(holat, soni). Har oy uchun faqat bir marta; force=True takroriy yuborishga ruxsat bermaydi, faqat sozlamani chetlaydi."""
    today = today or timezone.localdate()
    if not force and not SiteSettings.load().monthly_reminder_enabled:
        return "disabled", 0
    sem = Semester.current()
    if sem is None or sem.is_closed:
        return "no-semester", 0
    month = previous_month(today)
    if month < sem.start_date.replace(day=1):
        return "before-semester", 0
    try:
        with transaction.atomic():
            run = ReminderRun.objects.create(month=month)
            students = list(inactive_students(month))
            name = MONTHS[month.month - 1]
            notify_many(
                students,
                f"{name.capitalize()} oyida yutuq yuklamadingiz",
                "Reytingdagi o‘rningiz pasayishi mumkin. Tanlov, to‘garak, volontyorlik yoki kitobxonlikdagi ishtirokingizni "
                "hujjat bilan yuklashni unutmang.",
                link=reverse("achievements:create"),
                kind=Notification.Kind.REMINDER,
            )
            run.sent_count = len(students)
            run.save(update_fields=["sent_count"])
    except IntegrityError:
        return "already-sent", 0
    return "sent", len(students)
