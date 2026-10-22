"""Social Puls sozlamalari.

Barcha maxfiy va muhitga bog'liq qiymatlar .env faylidan olinadi (.env.example ga qarang).
"""
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, True),
    USE_X_ACCEL_REDIRECT=(bool, False),
    HEMIS_MODE=(str, "live"),
)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY .env faylida ko'rsatilishi shart.")

if not DEBUG and (len(SECRET_KEY) < 40 or SECRET_KEY.lstrip().startswith("#")):
    raise ImproperlyConfigured("SECRET_KEY juda qisqa yoki noto'g'ri (izoh qiymatga qo'shilib ketgan bo'lishi mumkin).")

ALLOWED_HOSTS = env("ALLOWED_HOSTS") or (["localhost", "127.0.0.1"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
# Render o'z domenini (masalan socialpuls.onrender.com) shu o'zgaruvchida beradi.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
# Namoyish sayti: sinov talabalari (HEMIS mock) va demo ma'lumotlarga ruxsat beradi, har sahifada ogohlantirish ko'rinadi.
# Haqiqiy foydalanishda hech qachon yoqilmaydi.
DEMO_SITE = env.bool("DEMO_SITE", default=False)
# Django admin manzili; production'da taxmin qilinmaydigan qiymat bering, masalan "boshqaruv-7f3k/".
ADMIN_URL = (env("ADMIN_URL", default="").strip("/") or "admin") + "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "accounts",
    "structure",
    "achievements",
    "ratings",
    "notifications",
    "audit",
    "hemis",
    "reports",
    "portfolio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "core.middleware.MaintenanceModeMiddleware",
    "core.middleware.IdleTimeoutMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if not DEBUG and not env("DATABASE_URL", default=""):
    # Production'da SQLite ga jimgina o'tib ketmaslik uchun (masalan, hostingda baza ulanmay qolsa).
    raise ImproperlyConfigured("DATABASE_URL ko'rsatilishi shart (DEBUG=False).")
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
# PostgreSQL qayta ishga tushsa, uzilgan doimiy ulanish so'rov boshida aniqlanib qayta ochiladi (500 xato o'rniga).
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.StaffBackend",
    "accounts.backends.HemisStudentBackend",
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Yutuq hujjatlari ochiq MEDIA dan tashqarida saqlanadi va faqat ruxsat tekshiruvidan keyin beriladi.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
USE_X_ACCEL_REDIRECT = env("USE_X_ACCEL_REDIRECT")
X_ACCEL_PREFIX = "/protected/"
UPLOAD_MAX_MB = env.int("UPLOAD_MAX_MB", default=10)
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sessiya va xavfsizlik ---
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    # Preload ro'yxatiga kiritish domen egasining alohida qarori, shuning uchun ogohlantirish o'chirilgan.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Email ---
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
EMAIL_FILE_PATH = env("EMAIL_FILE_PATH", default=str(BASE_DIR / "logs" / "mail"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Ijtimoiy Faollik <noreply@namdu.uz>")
SITE_URL = env("SITE_URL", default=f"https://{RENDER_EXTERNAL_HOSTNAME}" if RENDER_EXTERNAL_HOSTNAME else "http://localhost:8000")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
# Webhook manzilidagi maxfiy qism: https://SAYT/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>/
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")
TELEGRAM_TIMEOUT = env.int("TELEGRAM_TIMEOUT", default=5)

# --- HEMIS ---
# live: haqiqiy API; mock: faqat DEBUG da, internetsiz sinash uchun test talabalar.
HEMIS_MODE = env("HEMIS_MODE")
HEMIS_STUDENT_API_URL = env("HEMIS_STUDENT_API_URL", default="https://student.namdu.uz/rest/v1/")
HEMIS_DATA_API_URL = env("HEMIS_DATA_API_URL", default="https://student.namdu.uz/rest/v1/")
HEMIS_API_TOKEN = env("HEMIS_API_TOKEN", default="")
HEMIS_TIMEOUT = env.int("HEMIS_TIMEOUT", default=15)
if HEMIS_MODE not in ("live", "mock"):
    raise ImproperlyConfigured("HEMIS_MODE faqat 'live' yoki 'mock' bo'lishi mumkin.")
if HEMIS_MODE == "mock" and not (DEBUG or DEMO_SITE):
    raise ImproperlyConfigured("HEMIS_MODE=mock production (DEBUG=False) da ishlatilmaydi (faqat DEMO_SITE=True namoyish saytida).")

# --- Mijoz IP manzili (kirish cheklovi va audit uchun) ---
# x-real-ip: Nginx orqasida (deploy/nginx-socialpuls.conf). x-forwarded-for: Render kabi platformalarda;
# PROXY_COUNT ta ishonchli proksi qo'shgan oxirgi yozuvlardan olinadi, mijoz yozgan boshlang'ich qismi e'tiborga olinmaydi.
CLIENT_IP_SOURCE = env("CLIENT_IP_SOURCE", default="x-real-ip")
PROXY_COUNT = env.int("PROXY_COUNT", default=1)
if CLIENT_IP_SOURCE not in ("x-real-ip", "x-forwarded-for"):
    raise ImproperlyConfigured("CLIENT_IP_SOURCE faqat 'x-real-ip' yoki 'x-forwarded-for' bo'lishi mumkin.")

# --- Kirish urinishlarini cheklash ---
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)

CACHES = {
    "default": env.cache("CACHE_URL", default="locmemcache://socialpuls"),
}

LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "socialpuls.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "plain",
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
    },
}
CSRF_FAILURE_VIEW = "core.views.csrf_failure"
