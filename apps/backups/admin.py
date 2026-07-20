from django.contrib import admin

from apps.backups.models import (
    BackupConfigurationChange,
    BackupDestination,
    BackupJob,
    BackupJobTarget,
    BackupSchedule,
    BackupTechnology,
    RetentionPolicy,
)


@admin.register(BackupTechnology)
class BackupTechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "organization", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("name", "vendor")


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = ("name", "technology", "managed_customer", "site", "status", "organization")
    list_filter = ("organization", "technology", "status", "criticality")
    search_fields = ("name", "external_identifier", "matching_aliases")


@admin.register(BackupJobTarget)
class BackupJobTargetAdmin(admin.ModelAdmin):
    list_display = ("backup_job", "protected_object", "role", "organization", "is_active")
    list_filter = ("organization", "role", "is_active")
    search_fields = ("backup_job__name", "protected_object__name")


@admin.register(BackupSchedule)
class BackupScheduleAdmin(admin.ModelAdmin):
    list_display = ("backup_job", "frequency", "scheduled_time", "report_deadline_time", "mode", "is_active")
    list_filter = ("organization", "frequency", "mode", "is_active")


@admin.register(BackupDestination)
class BackupDestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "backup_job", "repository_type", "is_offsite", "organization")
    list_filter = ("organization", "repository_type", "is_offsite")


@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ("backup_job", "daily_copies", "weekly_copies", "monthly_copies", "uses_gfs", "organization")
    list_filter = ("organization", "uses_gfs")


@admin.register(BackupConfigurationChange)
class BackupConfigurationChangeAdmin(admin.ModelAdmin):
    list_display = ("backup_job", "summary", "changed_by", "organization", "created_at")
    list_filter = ("organization", "created_at")
    search_fields = ("backup_job__name", "summary", "reason")
