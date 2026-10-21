"""Telegram bot: xabar yuborish va hisobni ulash (deep link /start <token>)."""
import logging

import requests
from django.conf import settings
from django.core import signing

logger = logging.getLogger("socialpuls.telegram")
SALT = "telegram-link"
LINK_MAX_AGE = 60 * 30


def is_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN)


def link_url(user):
    """Profil sahifasidagi "Telegramni ulash" havolasi. Token 30 daqiqa amal qiladi."""
    if not (is_configured() and settings.TELEGRAM_BOT_USERNAME):
        return ""
    token = signing.dumps(user.pk, salt=SALT, compress=True)
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"


def user_from_token(token):
    try:
        return signing.loads(token, salt=SALT, max_age=LINK_MAX_AGE)
    except signing.BadSignature:
        return None


def send_message(chat_id, text):
    """True/False qaytaradi; xatolik foydalanuvchi amalini to'xtatmaydi, faqat logga yoziladi."""
    if not (is_configured() and chat_id):
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=settings.TELEGRAM_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Telegram xabari yuborilmadi: %s", exc)
        return False
    if resp.status_code != 200:
        logger.warning("Telegram xatolik qaytardi: %s %s", resp.status_code, resp.text[:200])
        return False
    return True
