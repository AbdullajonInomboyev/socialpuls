from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q


class Role(models.TextChoices):
    STUDENT = "student", "Talaba"
    FACULTY_ADMIN = "faculty_admin", "Fakultet mas'uli"
    TUTOR = "tutor", "Tyutor"
    LEADERSHIP = "leadership", "Rahbariyat"
    MODERATOR = "moderator", "Moderator"


REVIEWER_ROLES = {Role.FACULTY_ADMIN, Role.TUTOR}
STAFF_ROLES = {Role.FACULTY_ADMIN, Role.TUTOR, Role.LEADERSHIP, Role.MODERATOR}


class User(AbstractUser):
    role = models.CharField("Rol", max_length=20, choices=Role.choices, default=Role.STUDENT, db_index=True)
    middle_name = models.CharField("Otasining ismi", max_length=150, blank=True)
    phone = models.CharField("Telefon", max_length=32, blank=True)
    hemis_id = models.CharField("HEMIS ID", max_length=32, unique=True, null=True, blank=True)
    faculty = models.ForeignKey(
        "structure.Faculty",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff",
        verbose_name="Fakultet (mas'ul uchun)",
    )
    tutor_groups = models.ManyToManyField(
        "structure.Group", blank=True, related_name="tutors", verbose_name="Biriktirilgan guruhlar (tyutor uchun)"
    )
    telegram_chat_id = models.CharField("Telegram chat ID", max_length=32, blank=True)
    notify_email = models.BooleanField("Email orqali xabar", default=True)
    notify_telegram = models.BooleanField("Telegram orqali xabar", default=True)

    objects = UserManager()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        constraints = [
            models.CheckConstraint(
                condition=~Q(role="faculty_admin") | Q(faculty__isnull=False),
                name="faculty_admin_has_faculty",
            ),
        ]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self):
        return " ".join(p for p in [self.last_name, self.first_name, self.middle_name] if p).strip()

    @property
    def short_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.full_name or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        return "".join(p[0] for p in parts).upper()[:2] or self.username[:2].upper()

    @property
    def is_student(self):
        return self.role == Role.STUDENT

    @property
    def is_reviewer(self):
        return self.role in REVIEWER_ROLES

    @property
    def is_leadership(self):
        return self.role == Role.LEADERSHIP or self.is_superuser

    @property
    def is_moderator(self):
        return self.role == Role.MODERATOR or self.is_superuser

    @property
    def is_staff_member(self):
        return self.role in STAFF_ROLES or self.is_superuser


class StudentProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "m", "Erkak"
        FEMALE = "f", "Ayol"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile", verbose_name="Foydalanuvchi")
    student_id_number = models.CharField("Talaba ID (HEMIS)", max_length=32, unique=True)
    faculty = models.ForeignKey(
        "structure.Faculty", on_delete=models.PROTECT, null=True, blank=True, related_name="students"
    )
    specialty = models.ForeignKey(
        "structure.Specialty", on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    group = models.ForeignKey("structure.Group", on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    course = models.PositiveSmallIntegerField("Kurs", null=True, blank=True)
    education_form = models.CharField("Ta'lim shakli", max_length=64, blank=True)
    education_type = models.CharField("Ta'lim turi", max_length=64, blank=True)
    payment_form = models.CharField("To'lov shakli", max_length=64, blank=True)
    gender = models.CharField("Jinsi", max_length=1, choices=Gender.choices, blank=True)
    gpa = models.DecimalField("GPA", max_digits=4, decimal_places=2, null=True, blank=True)
    gpa_synced_at = models.DateTimeField("GPA yangilangan", null=True, blank=True)
    image_url = models.URLField("Rasm (HEMIS)", max_length=500, blank=True)
    hemis_synced_at = models.DateTimeField("HEMIS dan yangilangan", null=True, blank=True)

    class Meta:
        verbose_name = "Talaba profili"
        verbose_name_plural = "Talaba profillari"
        indexes = [models.Index(fields=["faculty", "course"])]
        constraints = [
            models.CheckConstraint(condition=Q(gpa__gte=0) & Q(gpa__lte=5) | Q(gpa__isnull=True), name="gpa_range"),
        ]

    def __str__(self):
        return f"{self.user} ({self.student_id_number})"
