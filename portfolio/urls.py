from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("portfolio/", views.me, name="me"),
    path("portfolio/<int:pk>/", views.detail, name="detail"),
    path("portfolio/<int:pk>/pdf/", views.download, name="pdf"),
]
