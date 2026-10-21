from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        SYSTEM = "system", "Tizim"
        REVIEW = "review", "Tekshiruv natijasi"
        REMINDER = "reminder", "Eslatma"
        MESSAGE = "message", "Xabar"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    broadcast = models.ForeignKey("Broadcast", on_delete=models.SET_NULL, null=True, blank=True, related_name="items")
    sent_email = models.BooleanField(default=False)
    sent_telegram = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"])]
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"

    def __str__(self):
        return self.title


class Broadcast(models.Model):
    """Fakultet mas'uli yoki tyutor tanlangan talabalarga yuborgan xabar."""

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="broadcasts")
    title = models.CharField("Mavzu", max_length=200)
    body = models.TextField("Matn", max_length=4000)
    via_email = models.BooleanField("Email", default=False)
    via_telegram = models.BooleanField("Telegram", default=False)
    recipient_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ommaviy xabar"
        verbose_name_plural = "Ommaviy xabarlar"

    def __str__(self):
        return self.title


class ReminderRun(models.Model):
    """Oylik eslatma bir oyda ikki marta yuborilmasligi uchun."""

    month = models.DateField(unique=True, help_text="Oyning birinchi kuni")
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month"]
