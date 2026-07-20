from django.contrib import admin

from apps.inventory.models import ObjectRelation, ProtectedObject


@admin.register(ProtectedObject)
class ProtectedObjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "object_type",
        "managed_customer",
        "site",
        "organization",
        "is_active",
    )
    list_filter = ("organization", "object_type", "is_active")
    search_fields = ("name", "external_reference", "hostname")


@admin.register(ObjectRelation)
class ObjectRelationAdmin(admin.ModelAdmin):
    list_display = ("source", "relation_type", "target", "organization", "is_active")
    list_filter = ("organization", "relation_type", "is_active")
    search_fields = ("source__name", "target__name")
