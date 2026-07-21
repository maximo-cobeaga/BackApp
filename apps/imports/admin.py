from django.contrib import admin

from apps.imports.models import (
    ImportBatch,
    ImportRow,
    LegacyBackupConfiguration,
    LegacyDailyRecord,
    LegacyImportIssue,
    LegacyTicketReference,
)


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    readonly_fields = ("row_number", "status", "raw_data", "normalized_data", "messages")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "organization", "status", "row_count", "created_at")
    list_filter = ("organization", "status", "created_at")
    search_fields = ("original_filename",)
    inlines = [ImportRowInline]


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ("batch", "row_number", "status", "organization")
    list_filter = ("organization", "status")
    search_fields = ("batch__original_filename",)


@admin.register(LegacyBackupConfiguration)
class LegacyBackupConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "legacy_customer_name",
        "legacy_site_label",
        "legacy_backup_name",
        "legacy_method",
        "provider",
        "source_row",
        "organization",
    )
    list_filter = ("organization", "provider", "provider_requires_confirmation")
    search_fields = (
        "legacy_customer_name",
        "legacy_site_label",
        "source_asset_label",
        "legacy_backup_name",
        "legacy_method",
    )
    readonly_fields = ("source_sha256", "legacy_fingerprint", "source_row")


@admin.register(LegacyDailyRecord)
class LegacyDailyRecordAdmin(admin.ModelAdmin):
    list_display = (
        "source_date",
        "source_row",
        "normalized_status",
        "raw_ticket",
        "organization",
    )
    list_filter = ("organization", "normalized_status", "source_date")
    search_fields = ("raw_status", "raw_ticket", "raw_observation")
    readonly_fields = ("source_sha256", "source_row", "source_date")


@admin.register(LegacyImportIssue)
class LegacyImportIssueAdmin(admin.ModelAdmin):
    list_display = ("issue_code", "severity", "source_row", "source_date", "organization")
    list_filter = ("organization", "issue_code", "severity")
    search_fields = ("issue_code", "details")


@admin.register(LegacyTicketReference)
class LegacyTicketReferenceAdmin(admin.ModelAdmin):
    list_display = ("external_system", "external_id", "organization")
    list_filter = ("organization", "external_system")
    search_fields = ("external_id",)
