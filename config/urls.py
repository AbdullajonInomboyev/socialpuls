from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from notifications import views as notif_views

admin.site.site_header = "Social Puls boshqaruvi"
admin.site.site_title = "Social Puls"


def _admin_login(request, extra_context=None):
    # Admin panelga ham faqat asosiy kirish sahifasi orqali (urinishlar cheklovi bilan) kiriladi.
    from django.urls import reverse
    from django.utils.http import urlencode

    return redirect(f"{reverse('accounts:login')}?{urlencode({'xodim': 1, 'next': request.GET.get('next', '/')})}")


admin.site.login = _admin_login

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("eslatmalar/", include("notifications.urls")),
    path("telegram/webhook/<str:secret>/", notif_views.telegram_webhook, name="telegram_webhook"),
    path("", include("achievements.urls")),
    path("", include("ratings.urls")),
    path("", include("portfolio.urls")),
    path("", include("core.urls")),
]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
