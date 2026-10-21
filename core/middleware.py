import time

from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import SiteSettings

CSP = (
    "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "font-src 'self'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class MaintenanceModeMiddleware:
    """Texnik xizmat rejimida faqat rahbariyat va moderator ishlay oladi."""

    EXEMPT = ("/static/", "/admin/", "/kirish/", "/chiqish/", "/api/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.EXEMPT):
            return self.get_response(request)
        if SiteSettings.load().maintenance_mode:
            user = request.user
            if not (user.is_authenticated and (user.is_leadership or user.is_moderator)):
                return render(request, "errors/maintenance.html", status=503)
        return self.get_response(request)


class IdleTimeoutMiddleware:
    """Belgilangan daqiqa harakatsiz qolgan foydalanuvchini tizimdan chiqaradi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            minutes = SiteSettings.load().idle_timeout_minutes
            now = int(time.time())
            last = request.session.get("last_seen")
            if minutes and last and now - last > minutes * 60:
                logout(request)
                messages.info(request, f"{minutes} daqiqa harakatsizlik sababli tizimdan chiqdingiz.")
                return redirect(f"{reverse(settings.LOGIN_URL)}?next={request.path}")
            if not last or now - last > 30:
                request.session["last_seen"] = now
        return self.get_response(request)
