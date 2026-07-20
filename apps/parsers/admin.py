from django.contrib import admin

from apps.parsers.models import ParsedReportItem


@admin.register(ParsedReportItem)
class ParsedReportItemAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "parser_name",
        "parser_status",
        "review_status",
        "confidence",
        "organization",
    )
    list_filter = ("organization", "parser_name", "parser_status", "review_status")
    search_fields = ("message__subject", "summary", "error_code")
