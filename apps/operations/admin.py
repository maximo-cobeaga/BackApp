from django.contrib import admin

from apps.operations.models import DailyControlEntry


@admin.register(DailyControlEntry)
class DailyControlEntryAdmin(admin.ModelAdmin):
    list_display = (
        "control_date",
        "backup_job",
        "protected_object",
        "result",
        "organization",
        "operator",
    )
    list_filter = ("organization", "result", "control_date")
    search_fields = ("backup_job__name", "protected_object__name", "manual_observation")
