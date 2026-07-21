from django.contrib import admin

from apps.ingestion.models import InboundMessage, MailConnector, MessageAttachment


class MessageAttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0
    readonly_fields = (
        "filename",
        "content_type",
        "size_bytes",
        "sha256",
        "storage_path",
        "extracted_text",
    )


@admin.register(MailConnector)
class MailConnectorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "mailbox_address",
        "read_only",
        "organization",
        "is_active",
    )
    list_filter = ("organization", "provider_type", "is_active")
    search_fields = ("name", "mailbox_address")


@admin.register(InboundMessage)
class InboundMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "connector", "sender", "received_at", "organization")
    list_filter = ("organization", "connector", "parser_status", "has_attachments")
    search_fields = (
        "subject",
        "sender",
        "external_message_id",
        "internet_message_id",
        "text_body",
        "html_as_text",
    )
    inlines = [MessageAttachmentInline]


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "message", "content_type", "size_bytes", "organization")
    list_filter = ("organization", "content_type")
    search_fields = ("filename", "sha256", "extracted_text")
