import io
import os
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import Role
from achievements.forms import version_of
from achievements.models import Achievement, AchievementFile, Criterion, ManualScore, ReviewEvent
from core.models import SiteSettings
from notifications.models import Notification
from ratings.models import StudentScore

from .factories import PASSWORD, make_staff, make_structure, make_student

def png_file(name="sertifikat.png"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "orange").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def pdf_file(name="diplom.pdf", body=b"1 0 obj << /Type /Catalog >> endobj"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + body + b"\ntrailer\n%%EOF\n", content_type="application/pdf")


class Base(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.mkdtemp()
        cls._override = override_settings(PRIVATE_MEDIA_ROOT=cls._media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()  # SiteSettings keshda saqlanadi, testlar bir-biriga ta'sir qilmasin
        self.s = make_structure()
        self.student = make_student("309251100001", self.s["g1"])
        self.other = make_student("309251100002", self.s["g2"])
        self.dean = make_staff("dekan1", Role.FACULTY_ADMIN, faculty=self.s["f1"])
        self.dean2 = make_staff("dekan2", Role.FACULTY_ADMIN, faculty=self.s["f2"])
        self.tutor_other = make_staff("tyutor2", Role.TUTOR, groups=[self.s["g2"]])
        self.sport = Criterion.objects.get(code="sport")
        self.tanlov = Criterion.objects.get(code="tanlov")

    def login_staff(self, user):
        self.client.force_login(user)

    def make_achievement(self, student=None, status=Achievement.Status.PENDING, criterion=None, **kw):
        a = Achievement.objects.create(
            student=student or self.student, semester=self.s["sem1"], criterion=criterion or self.sport,
            title="Mini-futbol turniri", event_date=date(2026, 10, 1), status=status, **kw,
        )
        AchievementFile.objects.create(achievement=a, file=png_file(), original_name="s.png", content_type="image/png", size=100)
        return a

    def post_create(self, **extra):
        data = {"criterion": self.sport.pk, "title": "Yugurish marafoni", "event_date": "2026-10-05", "description": "", "files": [png_file()]}
        data.update(extra)
        return self.client.post(reverse("achievements:create"), data)


class StudentUploadTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_create_and_submit(self):
        r = self.post_create()
        a = Achievement.objects.get(student=self.student)
        self.assertRedirects(r, reverse("achievements:detail", args=[a.pk]))
        self.assertEqual(a.status, Achievement.Status.PENDING)
        self.assertEqual(a.semester, self.s["sem1"])
        self.assertEqual(a.files.count(), 1)
        self.assertEqual(a.files.get().content_type, "image/png")
        self.assertTrue(ReviewEvent.objects.filter(achievement=a, action="submitted").exists())

    def test_draft_without_files(self):
        self.post_create(intent="draft", files=[])
        a = Achievement.objects.get(student=self.student)
        self.assertEqual(a.status, Achievement.Status.DRAFT)

    def test_submit_requires_file(self):
        r = self.post_create(files=[])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "kamida bitta tasdiqlovchi hujjat")
        self.assertFalse(Achievement.objects.exists())

    def test_fake_extension_rejected(self):
        fake = SimpleUploadedFile("virus.pdf", b"MZ\x90\x00 this is an exe", content_type="application/pdf")
        r = self.post_create(files=[fake])
        self.assertContains(r, "mos emas")
        self.assertFalse(Achievement.objects.exists())

    def test_wrong_extension_rejected(self):
        r = self.post_create(files=[SimpleUploadedFile("a.exe", b"%PDF-1.4 %%EOF")])
        self.assertContains(r, "faqat PDF")

    def test_pdf_with_javascript_rejected(self):
        r = self.post_create(files=[pdf_file(body=b"<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>")])
        self.assertContains(r, "skript")
        self.assertFalse(Achievement.objects.exists())

    @override_settings(UPLOAD_MAX_MB=1)
    def test_size_limit(self):
        big = pdf_file(body=b"0" * (1024 * 1024 + 10))
        r = self.post_create(files=[big])
        self.assertContains(r, "1 MB")

    def test_max_files(self):
        r = self.post_create(files=[png_file(f"{i}.png") for i in range(6)])
        self.assertContains(r, "5 ta fayl")

    def test_future_date_rejected(self):
        r = self.post_create(event_date="2099-01-01")
        self.assertContains(r, "kelajakda")

    def test_date_outside_semester_rejected(self):
        r = self.post_create(event_date="2026-08-01")
        self.assertContains(r, "semestr oralig")

    def test_manual_criterion_not_uploadable(self):
        odob = Criterion.objects.get(code="odob")
        r = self.post_create(criterion=odob.pk)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Achievement.objects.exists())

    def test_level_must_match_criterion(self):
        lvl = self.tanlov.levels.first()
        r = self.post_create(level=lvl.pk)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Achievement.objects.exists())

    def test_upload_disabled(self):
        st = SiteSettings.load()
        st.student_upload_enabled = False
        st.save()
        r = self.post_create()
        self.assertRedirects(r, reverse("achievements:my_list"))
        self.assertFalse(Achievement.objects.exists())

    def test_returned_edit_resubmit(self):
        a = self.make_achievement(status=Achievement.Status.RETURNED, reviewer_comment="Sifatsiz")
        r = self.client.post(reverse("achievements:edit", args=[a.pk]), {
            "criterion": self.sport.pk, "title": "Tuzatilgan", "event_date": "2026-10-01", "files": [pdf_file()],
        })
        self.assertRedirects(r, reverse("achievements:detail", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)
        self.assertEqual(a.files.count(), 2)
        self.assertTrue(a.events.filter(action="resubmitted").exists())

    def test_cannot_edit_pending_or_approved(self):
        a = self.make_achievement(status=Achievement.Status.APPROVED, points=Decimal("3"))
        r = self.client.post(reverse("achievements:edit", args=[a.pk]), {"criterion": self.sport.pk, "title": "X", "event_date": "2026-10-01"})
        self.assertRedirects(r, reverse("achievements:detail", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.title, "Mini-futbol turniri")

    def test_closed_semester_not_editable(self):
        a = self.make_achievement(status=Achievement.Status.RETURNED)
        self.s["sem1"].is_closed = True
        self.s["sem1"].save()
        r = self.client.get(reverse("achievements:edit", args=[a.pk]))
        self.assertRedirects(r, reverse("achievements:detail", args=[a.pk]))

    def test_delete_pending_removes_file(self):
        a = self.make_achievement()
        stored = a.files.get().file
        path = stored.path
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse("achievements:delete", args=[a.pk]))
        self.assertRedirects(r, reverse("achievements:my_list"))
        self.assertFalse(Achievement.objects.filter(pk=a.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_cannot_delete_approved(self):
        a = self.make_achievement(status=Achievement.Status.APPROVED, points=Decimal("2"))
        self.client.post(reverse("achievements:delete", args=[a.pk]))
        self.assertTrue(Achievement.objects.filter(pk=a.pk).exists())

    def test_cannot_see_other_students_achievement_or_file(self):
        a = self.make_achievement(student=self.other)
        self.assertEqual(self.client.get(reverse("achievements:detail", args=[a.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("achievements:file", args=[a.files.get().pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("achievements:edit", args=[a.pk])).status_code, 404)

    def test_own_file_served_with_safe_headers(self):
        a = self.make_achievement()
        r = self.client.get(reverse("achievements:file", args=[a.files.get().pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", r["Content-Security-Policy"])

    def test_student_cannot_open_queue_or_manual(self):
        self.assertEqual(self.client.get(reverse("achievements:queue")).status_code, 403)
        self.assertEqual(self.client.get(reverse("achievements:manual")).status_code, 403)

    def test_list_page(self):
        self.make_achievement()
        r = self.client.get(reverse("achievements:my_list"))
        self.assertContains(r, "Mini-futbol turniri")


class ReviewTests(Base):
    def review(self, a, user, **data):
        self.client.force_login(user)
        a.refresh_from_db()
        payload = {"version": version_of(a), "comment": ""}
        payload.update(data)
        return self.client.post(reverse("achievements:detail", args=[a.pk]), payload)

    def test_approve_updates_score_and_notifies(self):
        a = self.make_achievement()
        r = self.review(a, self.dean, action="approve", points="4")
        self.assertRedirects(r, reverse("achievements:queue"))
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.APPROVED)
        self.assertEqual(a.points, Decimal("4"))
        self.assertEqual(a.reviewer, self.dean)
        score = StudentScore.objects.get(student=self.student, semester=self.s["sem1"])
        self.assertEqual(Decimal(score.breakdown["sport"]), Decimal("4"))
        self.assertTrue(Notification.objects.filter(recipient=self.student, title__contains="tasdiqlandi").exists())

    def test_points_cannot_exceed_criterion_max(self):
        a = self.make_achievement()
        r = self.review(a, self.dean, action="approve", points="6")
        self.assertEqual(r.status_code, 200)
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_reject_and_return_require_comment(self):
        a = self.make_achievement()
        for action in ("reject", "return"):
            r = self.review(a, self.dean, action=action)
            self.assertContains(r, "Izoh yozing")
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_return_with_comment(self):
        a = self.make_achievement()
        self.review(a, self.dean, action="return", comment="Sertifikat o‘qilmaydi")
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.RETURNED)
        self.assertEqual(a.reviewer_comment, "Sertifikat o‘qilmaydi")

    def test_revoking_approval_recalculates(self):
        a = self.make_achievement()
        self.review(a, self.dean, action="approve", points="5")
        self.review(a, self.dean, action="reject", comment="Soxta hujjat")
        score = StudentScore.objects.get(student=self.student, semester=self.s["sem1"])
        self.assertEqual(Decimal(score.breakdown["sport"]), Decimal("0"))

    def test_out_of_scope_reviewers_get_404(self):
        a = self.make_achievement()
        for user in (self.dean2, self.tutor_other):
            r = self.review(a, user, action="approve", points="3")
            self.assertEqual(r.status_code, 404)
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_stale_version_rejected(self):
        a = self.make_achievement()
        self.client.force_login(self.dean)
        r = self.client.post(reverse("achievements:detail", args=[a.pk]), {"action": "approve", "points": "3", "version": "1.0"})
        self.assertContains(r, "o‘zgartirilgan")
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_draft_hidden_from_reviewer(self):
        a = self.make_achievement(status=Achievement.Status.DRAFT)
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(reverse("achievements:detail", args=[a.pk])).status_code, 404)

    def test_closed_semester_read_only(self):
        a = self.make_achievement()
        self.s["sem1"].is_closed = True
        self.s["sem1"].save()
        r = self.review(a, self.dean, action="approve", points="3")
        self.assertEqual(r.status_code, 200)  # faqat ko'rish sahifasi
        self.assertNotContains(r, 'value="approve"')
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_queue_is_scoped(self):
        mine = self.make_achievement(student=self.student)
        theirs = self.make_achievement(student=self.other)
        theirs.title = "Boshqa fakultet yutug‘i"
        theirs.save()
        self.client.force_login(self.dean)
        r = self.client.get(reverse("achievements:queue"))
        self.assertContains(r, mine.title)
        self.assertNotContains(r, theirs.title)

    def test_leadership_views_read_only(self):
        a = self.make_achievement()
        boss = make_staff("rahbar1", Role.LEADERSHIP)
        self.client.force_login(boss)
        r = self.client.get(reverse("achievements:detail", args=[a.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'value="approve"')
        r = self.client.post(reverse("achievements:detail", args=[a.pk]), {"action": "approve", "points": "3", "version": version_of(a)})
        a.refresh_from_db()
        self.assertEqual(a.status, Achievement.Status.PENDING)

    def test_reviewer_can_open_file_in_scope_only(self):
        a = self.make_achievement()
        fpk = a.files.get().pk
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(reverse("achievements:file", args=[fpk])).status_code, 200)
        self.client.force_login(self.dean2)
        self.assertEqual(self.client.get(reverse("achievements:file", args=[fpk])).status_code, 404)


class ManualScoreTests(Base):
    def test_save_scores_recalculates(self):
        odob = Criterion.objects.get(code="odob")
        davomat = Criterion.objects.get(code="davomat")
        self.client.force_login(self.dean)
        url = reverse("achievements:manual") + f"?guruh={self.s['g1'].pk}"
        r = self.client.get(url)
        self.assertContains(r, self.student.full_name)
        r = self.client.post(url, {f"s{self.student.pk}_c{odob.pk}": "4,5", f"s{self.student.pk}_c{davomat.pk}": "5"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ManualScore.objects.get(student=self.student, criterion=odob).points, Decimal("4.5"))
        score = StudentScore.objects.get(student=self.student, semester=self.s["sem1"])
        self.assertEqual(Decimal(score.breakdown["odob"]), Decimal("4.5"))
        # Bo'sh qoldirilsa ball olib tashlanadi
        self.client.post(url, {f"s{self.student.pk}_c{odob.pk}": "", f"s{self.student.pk}_c{davomat.pk}": "5"})
        self.assertFalse(ManualScore.objects.filter(student=self.student, criterion=odob).exists())

    def test_value_above_max_rejected(self):
        odob = Criterion.objects.get(code="odob")
        self.client.force_login(self.dean)
        url = reverse("achievements:manual") + f"?guruh={self.s['g1'].pk}"
        r = self.client.post(url, {f"s{self.student.pk}_c{odob.pk}": "7"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ManualScore.objects.exists())

    def test_cannot_score_foreign_group(self):
        odob = Criterion.objects.get(code="odob")
        self.client.force_login(self.dean)
        # g2 boshqa fakultetga tegishli: ro'yxatda yo'q, o'rniga o'z guruhi ochiladi
        url = reverse("achievements:manual") + f"?guruh={self.s['g2'].pk}"
        self.client.post(url, {f"s{self.other.pk}_c{odob.pk}": "5"})
        self.assertFalse(ManualScore.objects.filter(student=self.other).exists())

    def test_password_constant_used(self):
        self.assertTrue(self.client.login(username="dekan1", password=PASSWORD))
