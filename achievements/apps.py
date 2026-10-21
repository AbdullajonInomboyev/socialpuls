from django.apps import AppConfig


class AchievementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "achievements"
    verbose_name = "Yutuqlar"

    def ready(self):
        from . import signals  # noqa: F401  (qabul qiluvchilarni ro‘yxatdan o‘tkazadi)
