from django.conf import settings
from django.db import models


class StudentScore(models.Model):
    """Talabaning semestr bo'yicha hisoblangan bali (reyting tez ishlashi uchun saqlanadi).

    `breakdown` = {mezon_kodi: ball}. Har tasdiqlash, qo'lda ball yoki GPA yangilanishidan keyin
    `ratings.services.recalculate` orqali qayta hisoblanadi.
    """

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scores")
    semester = models.ForeignKey("structure.Semester", on_delete=models.CASCADE, related_name="scores")
    faculty = models.ForeignKey("structure.Faculty", on_delete=models.SET_NULL, null=True, related_name="+")
    group = models.ForeignKey("structure.Group", on_delete=models.SET_NULL, null=True, related_name="+")
    total = models.DecimalField(max_digits=6, decimal_places=2, default=0, db_index=True)
    breakdown = models.JSONField(default=dict)
    gpa_snapshot = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    approved_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Talaba bali"
        verbose_name_plural = "Talaba ballari"
        ordering = ["-total"]
        constraints = [models.UniqueConstraint(fields=["student", "semester"], name="unique_score_per_semester")]
        indexes = [models.Index(fields=["semester", "-total"]), models.Index(fields=["semester", "faculty", "-total"])]

    def __str__(self):
        return f"{self.student}: {self.total}"
