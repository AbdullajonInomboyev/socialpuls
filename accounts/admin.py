from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile, User


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    extra = 0
    autocomplete_fields = ["faculty", "specialty", "group"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "full_name", "role", "faculty", "is_active", "last_login"]
    list_filter = ["role", "is_active", "faculty"]
    search_fields = ["username", "first_name", "last_name", "hemis_id", "email"]
    filter_horizontal = ["tutor_groups", "groups", "user_permissions"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Social Puls", {"fields": ("role", "middle_name", "phone", "hemis_id", "faculty", "tutor_groups", "telegram_chat_id")}),
    )
    inlines = [StudentProfileInline]
