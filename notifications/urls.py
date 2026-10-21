from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<int:pk>/oqildi/", views.mark_read, name="read"),
    path("hammasi-oqildi/", views.mark_all_read, name="read_all"),
]
