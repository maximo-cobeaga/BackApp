"""Forms for customer setup."""
from django import forms

from apps.customers.models import ManagedCustomer, Site


class ManagedCustomerForm(forms.ModelForm):
    class Meta:
        model = ManagedCustomer
        fields = ["name", "internal_code", "notes", "is_active"]
        labels = {
            "name": "Nombre",
            "internal_code": "Código interno",
            "notes": "Observaciones",
            "is_active": "Activo",
        }


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ["managed_customer", "name", "code", "site_type", "timezone", "notes", "is_active"]
        labels = {
            "managed_customer": "Cliente gestionado",
            "name": "Nombre",
            "code": "Código",
            "site_type": "Tipo",
            "timezone": "Zona horaria",
            "notes": "Observaciones",
            "is_active": "Activo",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["managed_customer"].queryset = ManagedCustomer.objects.filter(
                organization=organization
            )
