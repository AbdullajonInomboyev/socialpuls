import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User
from audit.services import log_action

from . import telegram
from .models import Notification


@login_required
def notification_list(request):
    qs = request.user.notifications.all()
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page})


@login_required
@require_POST
def mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    if n.link and url_has_allowed_host_and_scheme(n.link, allowed_hosts={request.get_host()}):
        return redirect(n.link)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications:list")


@csrf_exempt
@require_POST
def telegram_webhook(request, secret):
    """Bot yangiliklari. Faqat "/start <token>" bilan hisobni ulash qo'llab-quvvatlanadi."""
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not constant_time_compare(secret, expected) or (header and not constant_time_compare(header, expected)):
        raise Http404
    try:
        update = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponse(status=400)
    message = update.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id") or "")
    text = (message.get("text") or "").strip()
    if not chat_id or not text.startswith("/start"):
        return HttpResponse("ok")
    token = text.split(maxsplit=1)[1] if " " in text else ""
    user_id = telegram.user_from_token(token) if token else None
    user = User.objects.filter(pk=user_id, is_active=True).first() if user_id else None
    if user is None:
        telegram.send_message(chat_id, "Hisobni ulash uchun tizimdagi Profil sahifasida “Telegramni ulash” tugmasini bosing.")
        return HttpResponse("ok")
    User.objects.filter(telegram_chat_id=chat_id).exclude(pk=user.pk).update(telegram_chat_id="")
    user.telegram_chat_id = chat_id
    user.notify_telegram = True
    user.save(update_fields=["telegram_chat_id", "notify_telegram"])
    log_action(None, "telegram.link", "Telegram hisobi ulandi", actor=user, obj=user)
    telegram.send_message(chat_id, f"{user.short_name}, Ijtimoiy Faollik bildirishnomalari endi shu yerga keladi.")
    return HttpResponse("ok")


@login_required
@require_POST
def telegram_unlink(request):
    request.user.telegram_chat_id = ""
    request.user.save(update_fields=["telegram_chat_id"])
    log_action(request, "telegram.unlink", "Telegram hisobi uzildi", obj=request.user)
    messages.success(request, "Telegram uzildi.")
    return redirect("accounts:profile")
