from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Faculty(models.Model):
    name = models.CharField("Nomi", max_length=255)
    short_name = models.CharField("Qisqa nomi", max_length=64, blank=True)
    code = models.CharField("Kodi", max_length=32, blank=True)
    hemis_id = models.PositiveIntegerField("HEMIS ID", unique=True, null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Fakultet"
        verbose_name_plural = "Fakultetlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Specialty(models.Model):
    name = models.CharField("Nomi", max_length=255)
    code = models.CharField("Kodi", max_length=32, blank=True)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="specialties", verbose_name="Fakultet")
    hemis_id = models.PositiveIntegerField("HEMIS ID", unique=True, null=True, blank=True)

    class Meta:
        verbose_name = "Yo'nalish"
        verbose_name_plural = "Yo'nalishlar"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} {self.name}".strip()


class Group(models.Model):
    name = models.CharField("Nomi", max_length=64)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="groups", verbose_name="Fakultet")
    specialty = models.ForeignKey(
        Specialty, on_delete=models.SET_NULL, null=True, blank=True, related_name="groups", verbose_name="Yo'nalish"
    )
    education_lang = models.CharField("Ta'lim tili", max_length=64, blank=True)
    hemis_id = models.PositiveIntegerField("HEMIS ID", unique=True, null=True, blank=True)

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicYear(models.Model):
    name = models.CharField("Nomi", max_length=16, unique=True, help_text="Masalan: 2025-2026")
    start_date = models.DateField("Boshlanishi")
    end_date = models.DateField("Tugashi")
    is_current = models.BooleanField("Joriy", default=False)

    class Meta:
        verbose_name = "O'quv yili"
        verbose_name_plural = "O'quv yillari"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["is_current"], condition=Q(is_current=True), name="one_current_year"),
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="year_dates_order"),
        ]

    def __str__(self):
        return self.name


class Semester(models.Model):
    """Baholash davri. Har semestr 100 ballik alohida baholanadi."""

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="semesters", verbose_name="O'quv yili"
    )
    number = models.PositiveSmallIntegerField("Semestr", choices=[(1, "1-semestr"), (2, "2-semestr")])
    start_date = models.DateField("Boshlanishi")
    end_date = models.DateField("Tugashi")
    is_current = models.BooleanField("Joriy", default=False)
    is_closed = models.BooleanField(
        "Yopilgan", default=False, help_text="Yopilgan semestrga yangi yutuq yuklab bo'lmaydi va ballar o'zgarmaydi."
    )

    class Meta:
        verbose_name = "Semestr"
        verbose_name_plural = "Semestrlar"
        ordering = ["-academic_year__start_date", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "number"], name="unique_semester_in_year"),
            models.UniqueConstraint(fields=["is_current"], condition=Q(is_current=True), name="one_current_semester"),
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="semester_dates_order"),
        ]

    def __str__(self):
        return f"{self.academic_year.name}, {self.number}-semestr"

    def clean(self):
        if self.academic_year_id and self.start_date and self.end_date:
            y = self.academic_year
            if self.start_date < y.start_date or self.end_date > y.end_date:
                raise ValidationError("Semestr sanalari o'quv yili oralig'ida bo'lishi kerak.")

    @classmethod
    def current(cls):
        return cls.objects.select_related("academic_year").filter(is_current=True).first()
