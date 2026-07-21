from django.contrib import admin

from apps.operations.models import BackupExecution, DailyControlEntry, ExpectedExecution


@admin.register(ExpectedExecution)
class ExpectedExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "service_date",
        "backup_job",
        "status",
        "scheduled_start_at",
        "report_deadline_at",
        "organization",
    )
    list_filter = ("organization", "status", "service_date")
    search_fields = ("backup_job__name", "system_summary")


@admin.register(BackupExecution)
class BackupExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "service_date",
        "backup_job",
        "result",
        "match_status",
        "expected_execution",
        "matched_by",
        "organization",
    )
    list_filter = ("organization", "result", "match_status", "service_date")
    search_fields = (
        "backup_job__name",
        "parser_summary",
        "operator_note",
        "parsed_item__summary",
    )
    autocomplete_fields = ("backup_job", "expected_execution", "parsed_item", "matched_by")


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
