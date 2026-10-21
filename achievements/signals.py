from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import AchievementFile


@receiver(post_delete, sender=AchievementFile)
def remove_stored_file(sender, instance, **kwargs):
    """Yozuv o'chirilsa, diskdagi fayl ham tranzaksiya muvaffaqiyatli tugagach o'chiriladi."""
    name, storage = instance.file.name, instance.file.storage
    if name:
        transaction.on_commit(lambda: storage.delete(name))
