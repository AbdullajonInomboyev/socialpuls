import logging

from .models import ActionLog

logger = logging.getLogger("socialpuls.audit")


def client_ip(request):
    if request is None:
        return None
    # Nginx orqasida X-Real-IP ishonchli; X-Forwarded-For ni mijoz soxtalashtirishi mumkin.
    ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")
    return ip or None


def log_action(request, action, description, obj=None, actor=None, **extra):
    """Har bir muhim amalni bazaga va log faylga yozadi."""
    if actor is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        actor = request.user
    entry = ActionLog.objects.create(
        actor=actor,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        description=description[:500],
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request is not None else ""),
        extra=extra,
    )
    logger.info("%s actor=%s %s", action, getattr(actor, "pk", None), description)
    return entry
