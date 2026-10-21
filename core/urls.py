from django.urls import path

from . import manage_views as m
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/ping/", views.ping, name="ping"),
    path("boshqaruv/hemis/", m.hemis_page, name="manage_hemis"),
    path("boshqaruv/hemis/shablon/", m.hemis_template, name="manage_hemis_template"),
    path("boshqaruv/xodimlar/", m.staff_list, name="manage_staff"),
    path("boshqaruv/xodimlar/yangi/", m.staff_edit, name="manage_staff_new"),
    path("boshqaruv/xodimlar/<int:pk>/", m.staff_edit, name="manage_staff_edit"),
    path("boshqaruv/xodimlar/<int:pk>/parol/", m.staff_reset, name="manage_staff_reset"),
    path("boshqaruv/sozlamalar/", m.settings_page, name="manage_settings"),
    path("boshqaruv/semestr/<int:pk>/<str:action>/", m.semester_action, name="manage_semester"),
    path("boshqaruv/audit/", m.audit_log, name="manage_audit"),
    path("xabarlar/", m.broadcasts, name="manage_broadcasts"),
]
