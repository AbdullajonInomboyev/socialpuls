from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm

from .models import Role, User


class StudentLoginForm(forms.Form):
    login = forms.CharField(
        label="HEMIS login (talaba ID)",
        max_length=32,
        widget=forms.TextInput(
            attrs={"autocomplete": "username", "inputmode": "numeric", "autofocus": True, "placeholder": "HEMIS login (talaba ID)"}
        ),
    )
    password = forms.CharField(
        label="HEMIS paroli",
        strip=False,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Parol"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        login, password = cleaned.get("login"), cleaned.get("password")
        if login and password:
            self.user = authenticate(self.request, hemis_login=login.strip(), hemis_password=password)
            if self.user is None:
                if getattr(self.request, "hemis_unavailable", False):
                    raise forms.ValidationError(
                        "HEMIS tizimi hozir javob bermayapti. Bir necha daqiqadan keyin qayta urinib ko'ring.",
                        code="unavailable",
                    )
                raise forms.ValidationError(
                    "HEMIS login yoki parol noto'g'ri. HEMIS'ga qanday kirsangiz, shu ma'lumotlarni kiriting.",
                    code="invalid",
                )
        return cleaned


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        label="Login",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True, "placeholder": "Login"}),
    )
    password = forms.CharField(
        label="Parol", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Parol"})
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        username, password = cleaned.get("username"), cleaned.get("password")
        if username and password:
            self.user = authenticate(self.request, username=username.strip(), password=password)
            if self.user is None:
                raise forms.ValidationError("Login yoki parol noto'g'ri.", code="invalid")
            if not self.user.is_active:
                raise forms.ValidationError("Hisobingiz faol emas. Moderatorga murojaat qiling.", code="inactive")
        return cleaned


class StaffPasswordResetForm(PasswordResetForm):
    """Parolni tiklash faqat xodimlar uchun: talabalar parolini HEMIS'da tiklaydi."""

    def get_users(self, email):
        for user in super().get_users(email):
            if user.role != Role.STUDENT:
                yield user


class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "notify_email", "notify_telegram"]
        labels = {"email": "Email manzil"}
