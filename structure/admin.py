from django.contrib import admin

from .models import AcademicYear, Faculty, Group, Semester, Specialty


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "hemis_id", "is_active"]
    search_fields = ["name", "code"]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "faculty"]
    list_filter = ["faculty"]
    search_fields = ["name", "code"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "faculty", "specialty"]
    list_filter = ["faculty"]
    search_fields = ["name"]


class SemesterInline(admin.TabularInline):
    model = Semester
    extra = 0


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_current"]
    inlines = [SemesterInline]
