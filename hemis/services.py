"""HEMIS ma'lumotlarini lokal modellarga yozish."""
import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from accounts.models import Role, StudentProfile, User
from structure.models import Faculty, Group, Semester, Specialty


def _cap(value):
    """Har so'zning birinchi harfini katta qiladi ("TOG‘AYEVA" -> "Tog‘ayeva"; .title() "Tog‘Ayeva" qilardi)."""
    lower = {"o‘g‘li", "og'li", "o'g'li", "qizi", "ugli", "kizi"}
    words = []
    for w in (value or "").split():
        w = w.lower()
        words.append(w if w in lower else w[:1].upper() + w[1:])
    return " ".join(words)


def _name(obj):
    return (obj or {}).get("name", "") if isinstance(obj, dict) else ""


def _parse_course(level):
    m = re.search(r"\d+", _name(level) or "")
    if m:
        return int(m.group())
    code = (level or {}).get("code") if isinstance(level, dict) else None
    if code and str(code).isdigit() and int(code) > 10:
        return int(code) - 10
    return None


def _parse_gpa(value):
    if value in (None, ""):
        return None
    try:
        gpa = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None
    if gpa < 0 or gpa > 5:
        return None
    return gpa.quantize(Decimal("0.01"))


def upsert_faculty(data):
    if not isinstance(data, dict) or not data.get("id"):
        return None
    fac, _ = Faculty.objects.update_or_create(
        hemis_id=data["id"], defaults={"name": data.get("name") or "Noma'lum fakultet", "code": data.get("code") or ""}
    )
    return fac


def upsert_specialty(data, faculty):
    if not isinstance(data, dict) or not data.get("id") or faculty is None:
        return None
    sp, _ = Specialty.objects.update_or_create(
        hemis_id=data["id"],
        defaults={"name": data.get("name") or "", "code": data.get("code") or "", "faculty": faculty},
    )
    return sp


def upsert_group(data, faculty, specialty):
    if not isinstance(data, dict) or not data.get("id") or faculty is None:
        return None
    grp, _ = Group.objects.update_or_create(
        hemis_id=data["id"],
        defaults={
            "name": data.get("name") or "",
            "faculty": faculty,
            "specialty": specialty,
            "education_lang": _name(data.get("educationLang")),
        },
    )
    return grp


@transaction.atomic
def upsert_student(data, recalc=True):
    """HEMIS talaba obyektidan User + StudentProfile yaratadi yoki yangilaydi. (user, created) qaytaradi."""
    sid = str(data.get("student_id_number") or "").strip()
    if not sid:
        raise ValueError("HEMIS javobida student_id_number yo'q.")

    faculty = upsert_faculty(data.get("faculty") or data.get("department"))
    specialty = upsert_specialty(data.get("specialty"), faculty)
    group = upsert_group(data.get("group"), faculty, specialty)

    user = User.objects.filter(hemis_id=sid).first()
    created = user is None
    if created:
        user = User(username=f"s{sid}", hemis_id=sid, role=Role.STUDENT)
        user.set_unusable_password()
    elif user.role != Role.STUDENT:
        raise PermissionError("Bu HEMIS ID xodim hisobiga biriktirilgan.")

    user.first_name = _cap(data.get("first_name"))
    user.last_name = _cap(data.get("second_name"))
    user.middle_name = _cap(data.get("third_name"))
    if data.get("email") and not user.email:
        user.email = data["email"]
    if data.get("phone"):
        user.phone = str(data["phone"])[:32]
    user.save()

    gender_code = str((data.get("gender") or {}).get("code") or "")
    now = timezone.now()
    defaults = {
        "student_id_number": sid,
        "faculty": faculty,
        "specialty": specialty,
        "group": group,
        "course": _parse_course(data.get("level")),
        "education_form": _name(data.get("educationForm")),
        "education_type": _name(data.get("educationType")),
        "payment_form": _name(data.get("paymentForm")),
        "gender": {"11": "m", "12": "f"}.get(gender_code, ""),
        "image_url": data.get("image") or "",
        "hemis_synced_at": now,
    }
    gpa = _parse_gpa(data.get("avg_gpa") if "avg_gpa" in data else data.get("gpa"))
    if gpa is not None:
        defaults["gpa"] = gpa
        defaults["gpa_synced_at"] = now
    StudentProfile.objects.update_or_create(user=user, defaults=defaults)

    semester = Semester.current() if recalc else None
    if semester is not None:
        from ratings.services import recalculate

        user.refresh_from_db()
        recalculate(user, semester)
    return user, created
