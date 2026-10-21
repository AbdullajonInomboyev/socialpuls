"""Rol va doira (fakultet / guruh) bo'yicha ruxsatlar. Har bir view server tomonda shu yerdan tekshiradi."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import Role, User


def role_required(*roles):
    allowed = {str(r) for r in roles}

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if user.role in allowed or (user.is_superuser and Role.STUDENT not in allowed):
                return view(request, *args, **kwargs)
            raise PermissionDenied
        return wrapper

    return decorator


student_required = role_required(Role.STUDENT)
staff_required = role_required(Role.FACULTY_ADMIN, Role.TUTOR, Role.LEADERSHIP, Role.MODERATOR)
reviewer_required = role_required(Role.FACULTY_ADMIN, Role.TUTOR)
leadership_required = role_required(Role.LEADERSHIP)
moderator_required = role_required(Role.MODERATOR, Role.LEADERSHIP)


def scoped_students(user):
    """Foydalanuvchi ko'ra oladigan talabalar."""
    qs = User.objects.filter(role=Role.STUDENT, is_active=True)
    if user.is_superuser or user.role in (Role.LEADERSHIP, Role.MODERATOR):
        return qs
    if user.role == Role.FACULTY_ADMIN and user.faculty_id:
        return qs.filter(profile__faculty_id=user.faculty_id)
    if user.role == Role.TUTOR:
        return qs.filter(profile__group__in=user.tutor_groups.all())
    return qs.none()


def scope_filter(user, prefix="student__profile__"):
    """Boshqa modellarni (yutuq, ball) doira bo'yicha filtrlash uchun kwargs."""
    if user.is_superuser or user.role in (Role.LEADERSHIP, Role.MODERATOR):
        return {}
    if user.role == Role.FACULTY_ADMIN and user.faculty_id:
        return {f"{prefix}faculty_id": user.faculty_id}
    if user.role == Role.TUTOR:
        return {f"{prefix}group__in": user.tutor_groups.all()}
    return {"pk__in": []}
