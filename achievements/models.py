import uuid
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.functional import LazyObject


class PrivateStorage(LazyObject):
    """Ochiq MEDIA dan tashqaridagi maxfiy papka (URL bermaydi)."""

    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)

    def deconstruct(self):
        return ("achievements.models.PrivateStorage", [], {})


private_storage = PrivateStorage()


class Criterion(models.Model):
    class InputMode(models.TextChoices):
        UPLOAD = "upload", "Talaba hujjat yuklaydi"
        MANUAL = "manual", "Mas'ul o'zi ball qo'yadi"
        AUTO = "auto", "Tizim avtomatik (HEMIS GPA)"

    code = models.SlugField("Kodi", max_length=40, unique=True)
    title = models.CharField("To'liq nomi", max_length=255)
    short_title = models.CharField("Qisqa nomi", max_length=40)
    description = models.TextField("Izoh", blank=True)
    max_points = models.PositiveSmallIntegerField("Maksimal ball", validators=[MinValueValidator(1)])
    input_mode = models.CharField("Baholash usuli", max_length=10, choices=InputMode.choices, default=InputMode.UPLOAD)
    order = models.PositiveSmallIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Mezon"
        verbose_name_plural = "Mezonlar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.short_title


class CriterionLevel(models.Model):
    """Mezon ichidagi tayyor daraja, masalan "Loyiha rahbari" 5 ball."""

    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name="levels", verbose_name="Mezon")
    title = models.CharField("Nomi", max_length=255)
    points = models.DecimalField("Ball", max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Mezon darajasi"
        verbose_name_plural = "Mezon darajalari"
        ordering = ["criterion", "order", "-points"]

    def __str__(self):
        return f"{self.title} ({self.points})"


class Achievement(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        PENDING = "pending", "Tekshiruvda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"
        RETURNED = "returned", "Qayta ishlashga qaytarilgan"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements", verbose_name="Talaba"
    )
    semester = models.ForeignKey(
        "structure.Semester", on_delete=models.PROTECT, related_name="achievements", verbose_name="Semestr"
    )
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT, related_name="achievements", verbose_name="Mezon")
    level = models.ForeignKey(
        CriterionLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Daraja"
    )
    title = models.CharField("Nomi", max_length=200)
    description = models.TextField("Tavsif", max_length=2000, blank=True)
    event_date = models.DateField("Sana")
    status = models.CharField("Holati", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    points = models.DecimalField(
        "Ball", max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_achievements",
        verbose_name="Tekshiruvchi",
    )
    reviewer_comment = models.TextField("Tekshiruvchi izohi", blank=True)
    reviewed_at = models.DateTimeField("Tekshirilgan", null=True, blank=True)
    submitted_at = models.DateTimeField("Yuborilgan", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yutuq"
        verbose_name_plural = "Yutuqlar"
        ordering = ["-submitted_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["student", "semester"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="approved") | Q(points__isnull=False), name="approved_has_points"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_editable_by_student(self):
        return self.status in {self.Status.DRAFT, self.Status.RETURNED} and not self.semester.is_closed


def achievement_upload_to(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"achievements/{instance.achievement.student_id}/{uuid.uuid4().hex}.{ext}"


class AchievementFile(models.Model):
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="files", verbose_name="Yutuq")
    file = models.FileField("Fayl", upload_to=achievement_upload_to, storage=private_storage)
    original_name = models.CharField("Asl nomi", max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField("Hajmi (bayt)")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Yutuq fayli"
        verbose_name_plural = "Yutuq fayllari"

    def __str__(self):
        return self.original_name

    @property
    def is_image(self):
        return self.content_type.startswith("image/")


class ReviewEvent(models.Model):
    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Yuborildi"
        RESUBMITTED = "resubmitted", "Qayta yuborildi"
        APPROVED = "approved", "Tasdiqlandi"
        REJECTED = "rejected", "Rad etildi"
        RETURNED = "returned", "Qayta ishlashga qaytarildi"
        COMMENTED = "commented", "Izoh qoldirildi"
        POINTS_CHANGED = "points_changed", "Ball o'zgartirildi"

    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    action = models.CharField(max_length=20, choices=Action.choices)
    comment = models.TextField(blank=True)
    points = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Tekshiruv tarixi"
        verbose_name_plural = "Tekshiruv tarixi"

    def __str__(self):
        return f"{self.get_action_display()}: {self.achievement}"


class ManualScore(models.Model):
    """Odob-axloq va davomat kabi talaba yuklamaydigan mezonlar uchun mas'ul qo'ygan ball."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="manual_scores")
    semester = models.ForeignKey("structure.Semester", on_delete=models.PROTECT, related_name="manual_scores")
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT, related_name="manual_scores")
    points = models.DecimalField("Ball", max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    comment = models.CharField("Izoh", max_length=500, blank=True)
    given_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Qo'lda qo'yilgan ball"
        verbose_name_plural = "Qo'lda qo'yilgan ballar"
        constraints = [
            models.UniqueConstraint(fields=["student", "semester", "criterion"], name="unique_manual_score"),
        ]

    def __str__(self):
        return f"{self.student} / {self.criterion}: {self.points}"
