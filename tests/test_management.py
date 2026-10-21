import io
import json
import tempfile
from datetime import date, datetime
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from accounts.models import Role, User
from achievements.models import Achievement, Criterion
from audit.models import ActionLog
from core.models import SiteSettings
from hemis.models import HemisSyncRun
from hemis.sync import EXCEL_COLUMNS
from notifications import telegram
from notifications.delivery import notify, notify_many
from notifications.models import Broadcast, Notification, ReminderRun
from notifications.reminders import send_monthly
from structure.models import AcademicYear, Semester

from .factories import PASSWORD, make_staff, make_structure, make_student

TG = {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_BOT_USERNAME": "puls_bot", "TELEGRAM_WEBHOOK_SECRET": "s3cret-hook"}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.s = make_structure()
        self.sem = self.s["sem1"]
        self.boss = make_staff("rahbar1", Role.LEADERSHIP)
        self.mod = make_staff("moder1", Role.MODERATOR)
        self.dean = make_staff("dekan1", Role.FACULTY_ADMIN, faculty=self.s["f1"])
        self.tutor = make_staff("tyutor1", Role.TUTOR, groups=[self.s["g2"]])
        self.a = make_student("309251100011", self.s["g1"])
        self.b = make_student("309251100012", self.s["g2"])
        self.a.email, self.a.notify_email = "a@mail.uz", True
        self.a.save()


class DeliveryTests(Base):
    @override_settings(**TG)
    def test_notify_sends_email_and_telegram_after_commit(self):
        self.a.telegram_chat_id, self.a.notify_telegram = "777", True
        self.a.save()
        with mock.patch("notifications.telegram.requests.post") as post:
            post.return_value.status_code = 200
            with self.captureOnCommitCallbacks(execute=True):
                n = notify(self.a, "Yutuq tasdiqlandi", "Sport", link="/yutuqlar/1/")
        n.refresh_from_db()
        self.assertTrue(n.sent_email and n.sent_telegram)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/yutuqlar/1/", mail.outbox[0].body)
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], "777")

    def test_respects_user_preferences(self):
        self.a.notify_email = False
        self.a.save()
        with self.captureOnCommitCallbacks(execute=True):
            n = notify(self.a, "X")
        n.refresh_from_db()
        self.assertFalse(n.sent_email)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(**TG)
    def test_telegram_failure_does_not_break(self):
        import requests

        self.a.telegram_chat_id = "777"
        self.a.save()
        with mock.patch("notifications.telegram.requests.post", side_effect=requests.ConnectionError):
            with self.captureOnCommitCallbacks(execute=True):
                n = notify(self.a, "X", email=False)
        n.refresh_from_db()
        self.assertFalse(n.sent_telegram)


@override_settings(**TG)
class TelegramWebhookTests(Base):
    def url(self, secret="s3cret-hook"):
        return reverse("telegram_webhook", args=[secret])

    def post(self, text, secret="s3cret-hook", header="s3cret-hook"):
        body = {"message": {"chat": {"id": 555}, "text": text}}
        return self.client.post(self.url(secret), json.dumps(body), content_type="application/json",
                                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=header)

    def test_wrong_secret_is_404(self):
        self.assertEqual(self.post("/start x", secret="nope").status_code, 404)
        self.assertEqual(self.post("/start x", header="bad").status_code, 404)

    def test_start_with_valid_token_links_account(self):
        token = telegram.link_url(self.a).split("start=")[1]
        with mock.patch("notifications.telegram.requests.post") as post:
            post.return_value.status_code = 200
            r = self.post(f"/start {token}")
        self.assertEqual(r.status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual(self.a.telegram_chat_id, "555")
        self.assertTrue(ActionLog.objects.filter(action="telegram.link", actor=self.a).exists())

    def test_forged_token_does_not_link(self):
        with mock.patch("notifications.telegram.requests.post"):
            self.post("/start 12345")
        self.a.refresh_from_db()
        self.assertEqual(self.a.telegram_chat_id, "")

    def test_unlink(self):
        self.a.telegram_chat_id = "555"
        self.a.save()
        self.client.force_login(self.a)
        self.client.post(reverse("notifications:telegram_unlink"))
        self.a.refresh_from_db()
        self.assertEqual(self.a.telegram_chat_id, "")


class ReminderTests(Base):
    def test_monthly_reminder_once_per_month(self):
        Achievement.objects.create(student=self.a, semester=self.sem, criterion=Criterion.objects.get(code="sport"), title="T",
                                   event_date=date(2026, 10, 2), status=Achievement.Status.PENDING,
                                   submitted_at=timezone.make_aware(datetime(2026, 10, 3, 12)))
        status, n = send_monthly(today=date(2026, 11, 1))
        self.assertEqual((status, n), ("sent", 1))
        self.assertTrue(Notification.objects.filter(recipient=self.b, kind=Notification.Kind.REMINDER).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.a, kind=Notification.Kind.REMINDER).exists())
        self.assertEqual(send_monthly(today=date(2026, 11, 1)), ("already-sent", 0))
        self.assertEqual(ReminderRun.objects.count(), 1)

    def test_disabled_and_before_semester(self):
        st = SiteSettings.load()
        st.monthly_reminder_enabled = False
        st.save()
        cache.clear()
        self.assertEqual(send_monthly(today=date(2026, 11, 1))[0], "disabled")
        self.assertEqual(send_monthly(today=date(2026, 9, 1), force=True)[0], "before-semester")


@override_settings(HEMIS_MODE="mock")
class HemisPageTests(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def xlsx(self, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(EXCEL_COLUMNS)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return SimpleUploadedFile("talabalar.xlsx", buf.getvalue())

    def test_only_moderator_or_leadership(self):
        for u in (self.dean, self.tutor, self.a):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("core:manage_hemis")).status_code, 403)
        self.client.force_login(self.mod)
        self.assertEqual(self.client.get(reverse("core:manage_hemis")).status_code, 200)

    def test_sync_in_mock_mode(self):
        self.client.force_login(self.mod)
        self.client.post(reverse("core:manage_hemis"), {"op": "sync"})
        run = HemisSyncRun.objects.get()
        self.assertEqual(run.status, HemisSyncRun.Status.SUCCESS, run.error)
        self.assertGreater(run.created_count + run.updated_count, 0)

    def test_sync_lock(self):
        cache.add("hemis-sync-lock", 1)
        from hemis.sync import LOCK_KEY

        cache.add(LOCK_KEY, 1)
        self.client.force_login(self.mod)
        r = self.client.post(reverse("core:manage_hemis"), {"op": "sync"}, follow=True)
        self.assertContains(r, "allaqachon bajarilmoqda")
        self.assertFalse(HemisSyncRun.objects.exists())

    def test_excel_preview_then_apply(self):
        self.client.force_login(self.mod)
        f = self.xlsx([["309251100099", "Karimov", "Bobur", "", "Iqtisodiyot fakulteti", "Iqtisodiyot", "IQT-AU-25", 2, "4,2"],
                       ["309251100011", "Valiyev", "Ali", "", "Iqtisodiyot fakulteti", "", "IQT-AU-25", 1, ""]])
        r = self.client.post(reverse("core:manage_hemis"), {"op": "excel", "file": f})
        self.assertContains(r, "2 talabani import qilish")
        self.assertFalse(User.objects.filter(hemis_id="309251100099").exists())  # ko'rib chiqishda hech narsa yozilmaydi
        r = self.client.post(reverse("core:manage_hemis"), {"op": "apply"}, follow=True)
        self.assertContains(r, "1 yangi, 1 yangilandi")
        new = User.objects.get(hemis_id="309251100099")
        self.assertEqual(new.profile.group, self.s["g1"])
        self.assertEqual(str(new.profile.gpa), "4.20")
        self.assertEqual(self.client.post(reverse("core:manage_hemis"), {"op": "apply"}, follow=True).status_code, 200)
        self.assertEqual(HemisSyncRun.objects.filter(kind=HemisSyncRun.Kind.EXCEL).count(), 1)  # takroriy tasdiq ishlamaydi

    def test_excel_with_errors_is_not_applicable(self):
        self.client.force_login(self.mod)
        f = self.xlsx([["abc", "", "Bobur", "", "", "", "", 9, "7"]])
        r = self.client.post(reverse("core:manage_hemis"), {"op": "excel", "file": f})
        self.assertContains(r, "2-qator")
        self.assertNotContains(r, "talabani import qilish")
        r = self.client.post(reverse("core:manage_hemis"), {"op": "apply"}, follow=True)
        self.assertContains(r, "Tekshirilgan fayl topilmadi")

    def test_wrong_header(self):
        self.client.force_login(self.mod)
        wb = Workbook()
        wb.active.append(["a", "b"])
        buf = io.BytesIO()
        wb.save(buf)
        r = self.client.post(reverse("core:manage_hemis"), {"op": "excel", "file": SimpleUploadedFile("x.xlsx", buf.getvalue())})
        self.assertContains(r, "shablonga mos emas")

    def test_template_download(self):
        self.client.force_login(self.mod)
        r = self.client.get(reverse("core:manage_hemis_template"))
        self.assertTrue(r.content.startswith(b"PK"))


class StaffTests(Base):
    def data(self, **kw):
        d = {"username": "yangi.tyutor", "last_name": "Aliyev", "first_name": "Vali", "middle_name": "", "email": "v@namdu.uz",
             "phone": "", "role": Role.TUTOR, "tutor_groups": [self.s["g1"].pk], "is_active": "on", "password": ""}
        d.update(kw)
        return d

    def test_create_tutor_sends_set_password_link(self):
        self.client.force_login(self.mod)
        r = self.client.post(reverse("core:manage_staff_new"), self.data())
        self.assertRedirects(r, reverse("core:manage_staff"))
        u = User.objects.get(username="yangi.tyutor")
        self.assertFalse(u.has_usable_password())
        self.assertEqual(list(u.tutor_groups.all()), [self.s["g1"]])
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(ActionLog.objects.filter(action="staff.create").exists())

    def test_role_scope_validation(self):
        self.client.force_login(self.mod)
        r = self.client.post(reverse("core:manage_staff_new"), self.data(tutor_groups=[]))
        self.assertContains(r, "kamida bitta guruh")
        r = self.client.post(reverse("core:manage_staff_new"), self.data(role=Role.FACULTY_ADMIN, tutor_groups=[]))
        self.assertContains(r, "fakultet tanlang")

    def test_student_like_login_rejected(self):
        self.client.force_login(self.mod)
        r = self.client.post(reverse("core:manage_staff_new"), self.data(username="s12345"))
        self.assertContains(r, "talabalar uchun band")

    def test_moderator_cannot_create_or_edit_leadership(self):
        self.client.force_login(self.mod)
        r = self.client.post(reverse("core:manage_staff_new"), self.data(role=Role.LEADERSHIP, tutor_groups=[]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="yangi.tyutor").exists())
        r = self.client.post(reverse("core:manage_staff_edit", args=[self.boss.pk]), self.data(username="rahbar1", role=Role.TUTOR))
        self.assertRedirects(r, reverse("core:manage_staff"))
        self.boss.refresh_from_db()
        self.assertEqual(self.boss.role, Role.LEADERSHIP)

    def test_leadership_can_set_password(self):
        self.client.force_login(self.boss)
        self.client.post(reverse("core:manage_staff_edit", args=[self.tutor.pk]),
                         self.data(username="tyutor1", password="Yangi-parol-2026!", tutor_groups=[self.s["g2"].pk]))
        self.assertTrue(self.client.login(username="tyutor1", password="Yangi-parol-2026!"))

    def test_cannot_edit_self(self):
        self.client.force_login(self.mod)
        r = self.client.get(reverse("core:manage_staff_edit", args=[self.mod.pk]))
        self.assertRedirects(r, reverse("core:manage_staff"))

    def test_reset_link(self):
        self.client.force_login(self.mod)
        self.client.post(reverse("core:manage_staff_reset", args=[self.dean.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["dekan1@namdu.uz"])
        self.assertEqual(self.client.get(reverse("core:manage_staff_reset", args=[self.dean.pk])).status_code, 405)

    def test_staff_list_filters(self):
        self.client.force_login(self.mod)
        r = self.client.get(reverse("core:manage_staff"), {"rol": Role.TUTOR})
        self.assertContains(r, "tyutor1")
        self.assertNotContains(r, "dekan1@")
        self.assertNotContains(r, "309251100011")


class SettingsTests(Base):
    def test_update_settings_logged(self):
        self.client.force_login(self.boss)
        data = {"op": "settings", "system_name": "Ijtimoiy Faollik", "university_name": "NamDU", "university_short": "NamDU",
                "contact_email": "", "idle_timeout_minutes": 30, "student_upload_enabled": "on"}
        r = self.client.post(reverse("core:manage_settings"), data)
        self.assertRedirects(r, reverse("core:manage_settings"))
        self.assertFalse(SiteSettings.load().public_stats_enabled)
        self.assertTrue(ActionLog.objects.filter(action="settings.update").exists())

    def test_idle_timeout_bounds(self):
        self.client.force_login(self.boss)
        data = {"op": "settings", "system_name": "X", "university_name": "U", "university_short": "U", "idle_timeout_minutes": 2}
        self.assertContains(self.client.post(reverse("core:manage_settings"), data), "5 dan 480")

    def test_create_year(self):
        self.client.force_login(self.mod)
        data = {"op": "year", "y-name": "2027-2028", "y-sem1_start": "2027-09-01", "y-sem1_end": "2028-01-31",
                "y-sem2_start": "2028-02-01", "y-sem2_end": "2028-06-30"}
        self.client.post(reverse("core:manage_settings"), data)
        y = AcademicYear.objects.get(name="2027-2028")
        self.assertEqual(y.semesters.count(), 2)
        self.assertFalse(y.is_current)

    def test_create_year_validation(self):
        self.client.force_login(self.mod)
        data = {"op": "year", "y-name": "2027-2029", "y-sem1_start": "2027-09-01", "y-sem1_end": "2027-08-01",
                "y-sem2_start": "2028-02-01", "y-sem2_end": "2028-06-30"}
        r = self.client.post(reverse("core:manage_settings"), data)
        self.assertContains(r, "ketma-ket")
        self.assertContains(r, "Sanalar tartibi")

    def test_switch_current_semester(self):
        self.client.force_login(self.mod)
        sem2 = self.s["sem2"]
        self.client.post(reverse("core:manage_semester", args=[sem2.pk, "joriy"]))
        self.assertEqual(Semester.current(), sem2)
        self.assertEqual(Semester.objects.filter(is_current=True).count(), 1)

    def test_close_requires_force_when_pending(self):
        Achievement.objects.create(student=self.a, semester=self.sem, criterion=Criterion.objects.get(code="sport"), title="T",
                                   event_date=date(2026, 10, 2), status=Achievement.Status.PENDING, submitted_at=timezone.now())
        self.client.force_login(self.mod)
        url = reverse("core:manage_semester", args=[self.sem.pk, "yopish"])
        r = self.client.post(url, follow=True)
        self.assertContains(r, "1 ta tekshirilmagan")
        self.sem.refresh_from_db()
        self.assertFalse(self.sem.is_closed)
        self.client.post(url, {"force": "1"})
        self.sem.refresh_from_db()
        self.assertTrue(self.sem.is_closed and not self.sem.is_current)
        self.assertTrue(ActionLog.objects.filter(action="semester.yopish").exists())
        # Yopilgan semestrni qayta joriy qilib bo'lmaydi
        self.client.post(reverse("core:manage_semester", args=[self.sem.pk, "joriy"]))
        self.sem.refresh_from_db()
        self.assertFalse(self.sem.is_current)

    def test_semester_actions_need_post_and_role(self):
        self.client.force_login(self.dean)
        self.assertEqual(self.client.post(reverse("core:manage_semester", args=[self.sem.pk, "yopish"])).status_code, 403)
        self.client.force_login(self.mod)
        self.assertEqual(self.client.get(reverse("core:manage_semester", args=[self.sem.pk, "yopish"])).status_code, 405)


class AuditTests(Base):
    def setUp(self):
        super().setUp()
        ActionLog.objects.create(actor=self.boss, action="rating.export", description="Reyting eksport qilindi", ip_address="10.0.0.5")
        ActionLog.objects.create(actor=self.mod, action="staff.create", description="Xodim yaratildi: x")
        ActionLog.objects.create(actor=None, action="login.failed", description="Muvaffaqiyatsiz kirish")

    def test_filters(self):
        self.client.force_login(self.mod)
        url = reverse("core:manage_audit")
        r = self.client.get(url, {"amal": "rating"})
        self.assertContains(r, "Reyting eksport")
        self.assertNotContains(r, "Xodim yaratildi")
        r = self.client.get(url, {"q": "10.0.0.5"})
        self.assertContains(r, "Reyting eksport")
        self.assertNotContains(r, "Muvaffaqiyatsiz")  # IP qidiruvi IP'si yo'q yozuvlarni qaytarmaydi
        r = self.client.get(url, {"dan": "2099-01-01"})
        self.assertContains(r, "Yozuv topilmadi")
        self.assertEqual(self.client.get(url, {"gacha": "noto'g'ri"}).status_code, 200)

    def test_forbidden_for_reviewers(self):
        self.client.force_login(self.dean)
        self.assertEqual(self.client.get(reverse("core:manage_audit")).status_code, 403)


class BroadcastTests(Base):
    def send(self, user, **kw):
        data = {"title": "Tanlov", "body": "Ertaga soat 10:00 da", "via_telegram": "on"}
        data.update(kw)
        self.client.force_login(user)
        return self.client.post(reverse("core:manage_broadcasts"), data)

    def test_two_step_confirm(self):
        r = self.send(self.boss)
        self.assertContains(r, "Xabar 2 talabaga yuboriladi")
        self.assertFalse(Broadcast.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            r = self.send(self.boss, confirm="on")
        self.assertRedirects(r, reverse("core:manage_broadcasts"))
        b = Broadcast.objects.get()
        self.assertEqual(b.recipient_count, 2)
        self.assertEqual(Notification.objects.filter(broadcast=b).count(), 2)

    def test_tutor_reaches_only_assigned_groups(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.tutor, confirm="on")
        b = Broadcast.objects.get()
        self.assertEqual(set(Notification.objects.filter(broadcast=b).values_list("recipient", flat=True)), {self.b.pk})

    def test_tutor_cannot_pick_foreign_group(self):
        r = self.send(self.tutor, groups=[self.s["g1"].pk], confirm="on")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Broadcast.objects.exists())

    def test_dean_scope(self):
        self.send(self.dean, confirm="on")
        b = Broadcast.objects.get()
        self.assertEqual(list(Notification.objects.filter(broadcast=b).values_list("recipient", flat=True)), [self.a.pk])

    def test_daily_limit(self):
        for _ in range(10):
            Broadcast.objects.create(sender=self.dean, title="x", body="y")
        r = self.send(self.dean, confirm="on")
        self.assertContains(r, "ko‘pi bilan 10")

    def test_student_forbidden(self):
        r = self.send(self.a, confirm="on")
        self.assertEqual(r.status_code, 403)

    def test_email_option(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.boss, confirm="on", via_email="on")
        self.assertEqual([m.to for m in mail.outbox], [["a@mail.uz"]])

    def test_notify_many_helper(self):
        with self.captureOnCommitCallbacks(execute=True):
            items = notify_many([self.a, self.b], "Salom", email=False, tg=False)
        self.assertEqual(len(items), 2)


class NavTests(Base):
    def test_management_menu_visibility(self):
        self.client.force_login(self.mod)
        r = self.client.get(reverse("core:home"))
        self.assertContains(r, reverse("core:manage_audit"))
        self.assertNotContains(r, reverse("achievements:criteria"))
        self.client.force_login(self.tutor)
        r = self.client.get(reverse("core:home"))
        self.assertNotContains(r, reverse("core:manage_audit"))
        self.assertContains(r, reverse("core:manage_broadcasts"))

    def test_password_login_for_created_staff(self):
        self.assertTrue(self.client.login(username="moder1", password=PASSWORD))
