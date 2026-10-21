"""Bildirishnoma yaratish va email/Telegram orqali yetkazish.

Tizim ichidagi xabar har doim yaratiladi. Email va Telegram foydalanuvchi sozlamasi yoqilgan va kanal sozlangan bo'lsa,
tranzaksiya muvaffaqiyatli tugagach yuboriladi; tashqi xizmat xatosi asosiy amalni bekor qilmaydi.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction

from . import telegram
from .models import Notification

logger = logging.getLogger("socialpuls.notify")


def _absolute(link):
    return settings.SITE_URL.rstrip("/") + link if link and link.startswith("/") else link


def _text(n):
    parts = [n.title]
    if n.body:
        parts.append(n.body)
    if n.link:
        parts.append(_absolute(n.link))
    return "\n\n".join(parts)


def _email_ok(user):
    return bool(user.notify_email and user.email)


def _telegram_ok(user):
    return bool(user.notify_telegram and user.telegram_chat_id and telegram.is_configured())


def deliver(notifications, email=True, tg=True):
    """Tayyor Notification yozuvlarini tashqi kanallarga yuboradi. Yuborilganlar soni (email, telegram)."""
    sent_email = sent_tg = 0
    messages = []
    for n in notifications:
        if email and _email_ok(n.recipient):
            messages.append((n, EmailMessage(f"[Ijtimoiy Faollik] {n.title}", _text(n), to=[n.recipient.email])))
    if messages:
        try:
            with get_connection() as conn:
                for n, msg in messages:
                    try:
                        msg.connection = conn
                        msg.send()
                        n.sent_email = True
                        sent_email += 1
                    except Exception as exc:  # noqa: BLE001 - bitta manzil xatosi qolganlarini to'xtatmasin
                        logger.warning("Email yuborilmadi (%s): %s", n.recipient.email, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("SMTP ga ulanib bo'lmadi: %s", exc)
    if tg:
        for n in notifications:
            if _telegram_ok(n.recipient) and telegram.send_message(n.recipient.telegram_chat_id, _text(n)):
                n.sent_telegram = True
                sent_tg += 1
    changed = [n for n in notifications if n.sent_email or n.sent_telegram]
    if changed:
        Notification.objects.bulk_update(changed, ["sent_email", "sent_telegram"])
    return sent_email, sent_tg


def notify(recipient, title, body="", link="", kind=Notification.Kind.SYSTEM, email=True, tg=True):
    n = Notification.objects.create(recipient=recipient, kind=kind, title=title[:200], body=body, link=link)
    transaction.on_commit(lambda: deliver([n], email=email, tg=tg))
    return n


def notify_many(recipients, title, body="", link="", kind=Notification.Kind.MESSAGE, broadcast=None, email=True, tg=True):
    items = Notification.objects.bulk_create(
        [Notification(recipient=r, kind=kind, title=title[:200], body=body, link=link, broadcast=broadcast) for r in recipients],
        batch_size=500,
    )
    # bulk_create recipient obyektini saqlaydi, shuning uchun email/chat_id qayta so'ralmaydi.
    transaction.on_commit(lambda: deliver(items, email=email, tg=tg))
    return items
