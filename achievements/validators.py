"""Yuklanadigan hujjatlarni tekshirish.

Fayl turi kengaytmaga emas, faylning birinchi baytlariga qarab aniqlanadi. Rasm Pillow bilan ochib ko'riladi,
PDF ichida avtomatik ishga tushadigan skript bo'lsa rad etiladi.
"""
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
ACCEPT_ATTR = ".pdf,.jpg,.jpeg,.png,.webp"
MAX_FILES = 5
PDF_DANGEROUS = (b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/EmbeddedFile")


def max_bytes():
    return settings.UPLOAD_MAX_MB * 1024 * 1024


def sniff(head):
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def clean_filename(name):
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = "".join(ch for ch in base if ch.isprintable())
    return (base or "hujjat")[:200]


def validate_upload(f):
    """Faylni tekshiradi va haqiqiy MIME turini qaytaradi. Xato bo'lsa ValidationError."""
    name = clean_filename(f.name)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"“{name}”: faqat PDF, JPG, PNG yoki WEBP fayl yuklash mumkin.")
    if f.size > max_bytes():
        raise ValidationError(f"“{name}”: fayl hajmi {settings.UPLOAD_MAX_MB} MB dan oshmasligi kerak.")
    if f.size == 0:
        raise ValidationError(f"“{name}”: fayl bo'sh.")

    f.seek(0)
    head = f.read(16)
    f.seek(0)
    real = sniff(head)
    if real is None or real != ALLOWED_EXTENSIONS[ext]:
        raise ValidationError(f"“{name}”: fayl mazmuni kengaytmasiga mos emas yoki buzilgan.")

    if real == "application/pdf":
        data = f.read()
        f.seek(0)
        if any(marker in data for marker in PDF_DANGEROUS):
            raise ValidationError(f"“{name}”: PDF ichida skript yoki biriktirilgan fayl bor. Oddiy PDF yuklang.")
        if b"%%EOF" not in data[-2048:]:
            raise ValidationError(f"“{name}”: PDF to'liq yuklanmagan yoki buzilgan.")
    else:
        try:
            with Image.open(f) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValidationError(f"“{name}”: rasmni ochib bo'lmadi.") from exc
        finally:
            f.seek(0)
    return real
