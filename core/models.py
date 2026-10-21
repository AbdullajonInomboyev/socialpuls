from django.core.cache import cache
from django.db import models


class SiteSettings(models.Model):
    """Yagona yozuv: tizim sozlamalari (moderator tahrirlaydi)."""

    system_name = models.CharField("Tizim nomi", max_length=100, default="Ijtimoiy Faollik")
    university_name = models.CharField("Universitet", max_length=255, default="Namangan davlat universiteti")
    university_short = models.CharField("Qisqa nomi", max_length=32, default="NamDU")
    contact_email = models.EmailField("Aloqa email", blank=True)
    idle_timeout_minutes = models.PositiveSmallIntegerField(
        "Harakatsizlikda chiqish (daqiqa)", default=30, help_text="0 = o'chirilgan"
    )
    maintenance_mode = models.BooleanField(
        "Texnik xizmat rejimi", default=False, help_text="Yoqilsa faqat moderator va rahbariyat kira oladi."
    )
    monthly_reminder_enabled = models.BooleanField("Oylik eslatma", default=True)
    student_upload_enabled = models.BooleanField("Talabalar yutuq yuklashi mumkin", default=True)
    public_stats_enabled = models.BooleanField("OTM sayti uchun ochiq statistika", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    CACHE_KEY = "site-settings"

    class Meta:
        verbose_name = "Tizim sozlamalari"
        verbose_name_plural = "Tizim sozlamalari"

    def __str__(self):
        return "Tizim sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj
