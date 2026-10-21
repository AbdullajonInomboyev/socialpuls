from django.contrib import admin

from .models import Achievement, AchievementFile, Criterion, CriterionLevel, ManualScore, ReviewEvent


class LevelInline(admin.TabularInline):
    model = CriterionLevel
    extra = 0


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ["order", "short_title", "max_points", "input_mode", "is_active"]
    list_display_links = ["short_title"]
    inlines = [LevelInline]


class FileInline(admin.TabularInline):
    model = AchievementFile
    extra = 0
    readonly_fields = ["original_name", "content_type", "size", "uploaded_at"]
    exclude = ["file"]


class EventInline(admin.TabularInline):
    model = ReviewEvent
    extra = 0
    readonly_fields = ["actor", "action", "comment", "points", "created_at"]


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ["title", "student", "criterion", "status", "points", "submitted_at"]
    list_filter = ["status", "criterion", "semester"]
    search_fields = ["title", "student__last_name", "student__hemis_id"]
    raw_id_fields = ["student", "reviewer"]
    inlines = [FileInline, EventInline]


@admin.register(ManualScore)
class ManualScoreAdmin(admin.ModelAdmin):
    list_display = ["student", "criterion", "semester", "points", "given_by"]
    raw_id_fields = ["student", "given_by"]
