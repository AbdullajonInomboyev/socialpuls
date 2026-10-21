from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kirish/", views.login_view, name="login"),
    path("chiqish/", views.logout_view, name="logout"),
    path("profil/", views.profile_view, name="profile"),
    path("parol/ozgartirish/", views.PasswordChangeView.as_view(), name="password_change"),
    path("parol/tiklash/", views.PasswordResetView.as_view(), name="password_reset"),
    path("parol/tiklash/yuborildi/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("parol/tiklash/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("parol/tiklash/tayyor/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
