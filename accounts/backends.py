import logging

from django.contrib.auth.backends import ModelBackend

from hemis.client import HemisAuthError, HemisUnavailable, get_student_client
from hemis.services import upsert_student

from .models import Role, User

logger = logging.getLogger("socialpuls.auth")


class StaffBackend(ModelBackend):
    """Xodimlar mahalliy login/parol bilan kiradi. Talabalar bu yo'l bilan kira olmaydi."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None and user.role == Role.STUDENT and not user.is_superuser:
            return None
        return user


class HemisStudentBackend(ModelBackend):
    """Talaba HEMIS login/paroli bilan kiradi. Parol saqlanmaydi, har kirishda HEMIS'da tekshiriladi."""

    def authenticate(self, request, hemis_login=None, hemis_password=None, **kwargs):
        if not hemis_login or not hemis_password:
            return None
        client = get_student_client()
        try:
            token = client.login(hemis_login, hemis_password)
            data = client.me(token)
        except HemisAuthError:
            return None
        except HemisUnavailable:
            if request is not None:
                request.hemis_unavailable = True
            return None
        try:
            user, _ = upsert_student(data)
        except PermissionError:
            logger.warning("HEMIS ID %s xodim hisobiga tegishli, talaba sifatida kirish rad etildi", hemis_login)
            return None
        return user if self.user_can_authenticate(user) else None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
