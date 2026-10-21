from django.urls import path

from . import views

app_name = "ratings"

urlpatterns = [
    path("reyting/", views.rating, name="rating"),
    path("reyting/yuklab/<str:fmt>/", views.export, name="export"),
    path("reyting/talaba/<int:pk>/", views.student_card, name="student"),
    path("top-10/", views.top10, name="top10"),
    path("tahlil/", views.analytics, name="analytics"),
    path("api/ochiq/statistika/", views.public_stats, name="public_stats"),
]
