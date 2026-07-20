from django.contrib import admin

from apps.customers.models import ManagedCustomer, Site


@admin.register(ManagedCustomer)
class ManagedCustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "internal_code", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("name", "internal_code")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "managed_customer", "organization", "site_type", "is_active")
    list_filter = ("organization", "site_type", "is_active")
    search_fields = ("name", "code", "managed_customer__name")
