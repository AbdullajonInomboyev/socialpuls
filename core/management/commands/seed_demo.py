"""Faqat ishlab chiqish uchun demo ma'lumotlar (DEBUG=True bo'lganda ishlaydi)."""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, StudentProfile, User
from achievements.models import Achievement, Criterion, ManualScore, ReviewEvent
from notifications.models import Notification
from hemis.mock import MOCK_STUDENTS
from hemis.services import upsert_student
from ratings.services import recalculate
from structure.models import AcademicYear, Faculty, Group, Semester, Specialty

DEMO_PASSWORD = "Puls-demo-2026"

FACULTIES = [
    ("Iqtisodiyot fakulteti", "IQT", [("60310100", "Iqtisodiyot", ["IQT-AU-25", "IQT-AU-24"])]),
    ("Filologiya fakulteti", "FIL", [("60230100", "Filologiya va tillarni o‘qitish (o‘zbek tili)", ["UZB-DU-24", "UZB-DU-23"])]),
    ("Fizika-matematika fakulteti", "FM", [("60540100", "Matematika", ["MAT-21-25", "MAT-21-24"])]),
    ("Tibbiyot fakulteti", "TIB", [("60910200", "Davolash ishi", ["DAV-DR-25", "DAV-GU-25"])]),
    ("Ijtimoiy fanlar fakulteti", "IJF", [("60220300", "Falsafa", ["FAL-AU-25", "FAL-AU-24"])]),
]
MALE = ["Ulug‘bek", "Behruzbek", "Jasurbek", "Sardor", "Asadbek", "Otabek", "Doniyor", "Javohir", "Shohruh", "Abdulaziz", "Bekzod", "Islom"]
FEMALE = ["Hilola", "Madinabonu", "Mohinur", "Sevara", "Dilnoza", "Gulnoza", "Maftuna", "Shahzoda", "Nilufar", "Zarina", "Kamola", "Muslima"]
LAST = ["Mirzaxalilov", "Ibroximov", "Tojiboyev", "Tog‘ayev", "Qodirov", "Rahimov", "Yusupov", "Karimov", "Ergashev", "Nazarov", "Sobirov", "Xolmatov"]
TITLES = {
    "kitobxonlik": ["“Yosh kitobxon” tanlovi fakultet bosqichi", "Oyning eng faol kitobxoni", "Kitob taqdimoti: “O‘tkan kunlar”"],
    "tashabbus": ["“Zakovat” to‘garagi mashg‘ulotlari", "IT to‘garagida loyiha", "Musiqa to‘garagi konserti"],
    "tanlov": ["Fan olimpiadasi, viloyat bosqichi", "“Talabalar bahori” festivali", "Respublika matematika olimpiadasi"],
    "marifat": ["Ma’rifat darsida ma’ruza", "Ma’rifat darsi: ekologiya mavzusi"],
    "volontyorlik": ["Mehribonlik uyiga yordam aksiyasi", "“Yashil makon” ko‘chat ekish", "Qon topshirish aksiyasi"],
    "madaniyat": ["Namangan viloyat teatriga tashrif", "Tarix muzeyiga ekskursiya", "Bobur nomidagi bog‘ga sayr"],
    "sport": ["Universitet mini-futbol turniri", "Yugurish marafoni 5 km", "Stol tennisi musobaqasi"],
    "boshqa": ["Talabalar gazetasi uchun maqola", "Ma’naviyat haftaligida chiqish"],
}


class Command(BaseCommand):
    help = "Demo ma'lumotlar yaratadi (faqat DEBUG=True)."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=72)

    @transaction.atomic
    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("seed_demo faqat DEBUG=True muhitida ishlaydi.")
        rnd = random.Random(2026)

        y1, _ = AcademicYear.objects.get_or_create(name="2025-2026", defaults={"start_date": date(2025, 9, 1), "end_date": date(2026, 6, 30)})
        y2, _ = AcademicYear.objects.get_or_create(name="2026-2027", defaults={"start_date": date(2026, 9, 1), "end_date": date(2027, 6, 30)})
        AcademicYear.objects.exclude(pk=y2.pk).update(is_current=False)
        y2.is_current = True
        y2.save()
        Semester.objects.update(is_current=False)
        s11, _ = Semester.objects.get_or_create(academic_year=y1, number=1, defaults={"start_date": date(2025, 9, 1), "end_date": date(2026, 1, 31), "is_closed": True})
        s12, _ = Semester.objects.get_or_create(academic_year=y1, number=2, defaults={"start_date": date(2026, 2, 1), "end_date": date(2026, 6, 30), "is_closed": True})
        s21, _ = Semester.objects.get_or_create(academic_year=y2, number=1, defaults={"start_date": date(2026, 9, 1), "end_date": date(2027, 1, 31)})
        Semester.objects.get_or_create(academic_year=y2, number=2, defaults={"start_date": date(2027, 2, 1), "end_date": date(2027, 6, 30)})
        s21.is_current = True
        s21.save()

        groups = []
        faculties = []
        for i, (fname, code, specs) in enumerate(FACULTIES, start=1):
            # HEMIS ID lar hemis.mock dagi test talabalar bilan mos keladi (1, 2, ...).
            fac, _ = Faculty.objects.get_or_create(name=fname, defaults={"code": code, "short_name": code, "hemis_id": i})
            faculties.append(fac)
            for scode, sname, gnames in specs:
                sp, _ = Specialty.objects.get_or_create(code=scode, faculty=fac, defaults={"name": sname, "hemis_id": i * 10 + 1})
                for j, g in enumerate(gnames, start=1):
                    grp, _ = Group.objects.get_or_create(
                        name=g, faculty=fac, defaults={"specialty": sp, "education_lang": "O‘zbek", "hemis_id": i * 100 + j}
                    )
                    groups.append(grp)

        def staff(username, first, last, role, faculty=None):
            u, created = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last, "role": role, "faculty": faculty, "email": f"{username}@namdu.uz"})
            if created:
                u.set_password(DEMO_PASSWORD)
                u.save()
            return u

        staff("rahbar", "Abdulhafiz", "Davlatov", Role.LEADERSHIP)
        staff("moderator", "Sherzod", "Aliyev", Role.MODERATOR)
        dean = staff("dekan_iqt", "Nodira", "Usmonova", Role.FACULTY_ADMIN, faculties[0])
        for fac in faculties[1:]:
            staff(f"dekan_{fac.code.lower()}", "Mas’ul", fac.code, Role.FACULTY_ADMIN, fac)
        tutor = staff("tyutor", "Akmal", "Tursunov", Role.TUTOR)
        tutor.tutor_groups.set([g for g in groups if g.name.startswith("IQT")])

        criteria = {c.code: c for c in Criterion.objects.all()}
        upload_codes = [c.code for c in criteria.values() if c.input_mode == "upload"]
        existing = StudentProfile.objects.count()
        now = timezone.now()

        def populate(user, activity):
            for sem in (s11, s12, s21):
                k = int(activity * 9) if sem != s21 else int(activity * 6)
                for _ in range(k):
                    code = rnd.choice(upload_codes)
                    c = criteria[code]
                    status = rnd.choices(["approved", "pending", "rejected", "returned"], [7, 2 if sem == s21 else 0, 1, 1 if sem == s21 else 0])[0]
                    ev = min(sem.start_date + timedelta(days=rnd.randint(3, 100)), date.today() - timedelta(days=1))
                    pts = Decimal(rnd.randint(1, max(1, c.max_points // 2))) if status == "approved" else None
                    a = Achievement.objects.create(
                        student=user, semester=sem, criterion=c, title=rnd.choice(TITLES[code]), event_date=ev, status=status,
                        points=pts, submitted_at=timezone.make_aware(timezone.datetime.combine(ev + timedelta(days=1), timezone.datetime.min.time())),
                        reviewer=dean if status != "pending" else None,
                        reviewer_comment="Sertifikat aniq ko‘rinmayapti, sifatli nusxa yuklang." if status == "returned" else "",
                    )
                    ReviewEvent.objects.create(achievement=a, actor=user, action="submitted")
                    if status != "pending":
                        ReviewEvent.objects.create(achievement=a, actor=dean, action=status, points=pts, comment=a.reviewer_comment)
                for code in ("odob", "davomat"):
                    ManualScore.objects.update_or_create(student=user, semester=sem, criterion=criteria[code], defaults={"points": Decimal(rnd.choice([3, 4, 4, 5, 5])), "given_by": dean})
                recalculate(user, sem)
            if activity > 0.5:
                Notification.objects.create(recipient=user, kind="review", title="Yutug‘ingiz tasdiqlandi", body="“Universitet mini-futbol turniri” uchun 3 ball qo‘shildi.")
            if activity < 0.25:
                Notification.objects.create(recipient=user, kind="reminder", title="Sentyabr oyida yutuq yuklamadingiz", body="Reytingda ishtirokingiz past bo‘lishi mumkin. Yutuqlaringizni yuklashni unutmang.")

        for n in range(existing, existing + opts["students"]):
            gender = rnd.choice("mf")
            first = rnd.choice(MALE if gender == "m" else FEMALE)
            last = rnd.choice(LAST)
            if gender == "f" and last.endswith("v"):
                last += "a"
            grp = groups[n % len(groups)]
            sid = f"30925110{4300 + n:04d}"
            user = User.objects.create(username=f"s{sid}", hemis_id=sid, role=Role.STUDENT, first_name=first, last_name=last)
            user.set_unusable_password()
            user.save()
            activity = rnd.random()
            StudentProfile.objects.create(
                user=user, student_id_number=sid, faculty=grp.faculty, specialty=grp.specialty, group=grp,
                course=27 - int(grp.name[-2:]),  # 2026-2027 o'quv yili: 25-qabul = 2-kurs education_form="Kunduzgi",
                education_type="Bakalavr", payment_form=rnd.choice(["To‘lov-shartnoma", "Davlat granti"]), gender=gender,
                gpa=Decimal(str(round(rnd.uniform(2.9, 5.0), 2))), gpa_synced_at=now, hemis_synced_at=now,
            )
            populate(user, activity)

        for sid, activity in (("309251104207", 0.92), ("309251104208", 0.55)):
            user, _ = upsert_student(MOCK_STUDENTS[sid])
            populate(user, activity)

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor. Xodimlar paroli: {DEMO_PASSWORD} (rahbar, moderator, dekan_iqt, tyutor). "
            "HEMIS test talabalari: 309251104208 / 309251104207, parol: hemis-demo"
        ))
