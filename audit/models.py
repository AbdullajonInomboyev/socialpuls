from django.conf import settings
from django.db import models


class ActionLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="action_logs"
    )
    action = models.CharField("Amal", max_length=50, db_index=True)
    object_type = models.CharField("Obyekt turi", max_length=50, blank=True)
    object_id = models.CharField("Obyekt ID", max_length=64, blank=True)
    description = models.CharField("Tavsif", max_length=500)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Amal jurnali"
        verbose_name_plural = "Amallar jurnali"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
