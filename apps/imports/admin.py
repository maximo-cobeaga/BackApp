from django.contrib import admin

from apps.imports.models import ImportBatch, ImportRow


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
