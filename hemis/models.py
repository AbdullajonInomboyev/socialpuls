from django.conf import settings
from django.db import models


class HemisSyncRun(models.Model):
    class Kind(models.TextChoices):
        FACULTIES = "faculties", "Fakultetlar"
        SPECIALTIES = "specialties", "Yo'nalishlar"
        GROUPS = "groups", "Guruhlar"
        STUDENTS = "students", "Talabalar"
        EXCEL = "excel", "Excel import"

    class Status(models.TextChoices):
        RUNNING = "running", "Bajarilmoqda"
        SUCCESS = "success", "Muvaffaqiyatli"
        FAILED = "failed", "Xatolik"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "HEMIS sinxronizatsiya"
        verbose_name_plural = "HEMIS sinxronizatsiyalar"

    def __str__(self):
        return f"{self.get_kind_display()} {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self):
        if self.finished_at:
            return self.finished_at - self.started_at
        return None
