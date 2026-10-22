"""Kirish urinishlarini cheklash (IP va login bo'yicha)."""
import hashlib

from django.conf import settings
from django.core.cache import cache


def _key(kind, value):
    digest = hashlib.sha256(value.lower().encode()).hexdigest()[:32]
    return f"login-fail:{kind}:{digest}"


def _keys(ip, login):
    keys = [_key("ip", ip or "unknown")]
    if login:
        keys.append(_key("login", login))
    return keys


def is_locked(ip, login):
    limit = settings.LOGIN_MAX_ATTEMPTS
    ip_limit = limit * 4  # bitta IP (masalan, universitet NAT) ortidan ko'p talaba kirishi mumkin
    ip_key, *rest = _keys(ip, login)
    if (cache.get(ip_key) or 0) >= ip_limit:
        return True
    return any((cache.get(k) or 0) >= limit for k in rest)


def register_failure(ip, login):
    for k in _keys(ip, login):
        try:
            cache.incr(k)
        except ValueError:
            cache.set(k, 1, settings.LOGIN_LOCKOUT_SECONDS)


def reset(ip, login):
    cache.delete_many(_keys(ip, login)[1:])


RESET_WINDOW = 60 * 60


def _hit(key, limit):
    if cache.add(key, 1, RESET_WINDOW):
        return True
    try:
        return cache.incr(key) <= limit
    except ValueError:  # kalit shu orada muddati tugab o'chgan
        cache.set(key, 1, RESET_WINDOW)
        return True


def allow_reset(ip, email):
    ip_ok = _hit(_key("reset-ip", ip or "unknown"), 10)
    email_ok = _hit(_key("reset-email", email or ""), 3)
    return ip_ok and email_ok
