from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Social Puls boshqaruvi"
admin.site.site_title = "Social Puls"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("eslatmalar/", include("notifications.urls")),
    path("", include("achievements.urls")),
    path("", include("ratings.urls")),
    path("", include("core.urls")),
]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
