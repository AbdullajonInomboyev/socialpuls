"""Production uchun qo'shimcha tekshiruvlar (`manage.py check --deploy`)."""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def shared_cache_check(app_configs, **kwargs):
    backend = settings.CACHES["default"]["BACKEND"]
    if backend.endswith("LocMemCache"):
        return [Warning(
            "Kesh har bir gunicorn jarayonida alohida (LocMemCache).",
            hint="Kirish urinishlari cheklovi va HEMIS sinxron qulfi barcha jarayonlarda ishlashi uchun CACHE_URL ni "
                 "dbcache://socialpuls_cache (keyin `manage.py createcachetable`) yoki Redis ga o'rnating.",
            id="socialpuls.W001",
        )]
    return []


@register(Tags.security, deploy=True)
def admin_url_check(app_configs, **kwargs):
    if settings.ADMIN_URL == "admin/":
        return [Warning("Django admin standart /admin/ manzilida.", hint="ADMIN_URL ni taxmin qilinmaydigan qiymatga o'zgartiring.",
                        id="socialpuls.W002")]
    return []


@register(Tags.security, deploy=True)
def hemis_token_check(app_configs, **kwargs):
    if settings.HEMIS_MODE == "live" and not settings.HEMIS_API_TOKEN:
        return [Warning("HEMIS_API_TOKEN o'rnatilmagan.", hint="Talabalar ro'yxatini sinxronlash uchun HEMIS ma'lumot API tokeni kerak.",
                        id="socialpuls.W003")]
    return []
