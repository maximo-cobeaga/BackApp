"""Forms for mailbox connectors."""
from django import forms

from apps.ingestion.models import MailConnector


class MailConnectorForm(forms.ModelForm):
    tenant_id_env = forms.CharField(
        label="Variable de entorno Tenant ID",
        required=False,
        initial="M365_TENANT_ID",
    )
    client_id_env = forms.CharField(
        label="Variable de entorno Client ID",
        required=False,
        initial="M365_CLIENT_ID",
    )
    client_secret_env = forms.CharField(
        label="Variable de entorno Client Secret",
        required=False,
        initial="M365_CLIENT_SECRET",
    )

    class Meta:
        model = MailConnector
        fields = [
            "name",
            "provider_type",
            "auth_mode",
            "mailbox_address",
            "folder",
            "poll_interval_seconds",
            "is_active",
            "notes",
        ]
        labels = {
            "name": "Nombre",
            "provider_type": "Proveedor",
            "auth_mode": "Autenticación",
            "mailbox_address": "Casilla",
            "folder": "Carpeta",
            "poll_interval_seconds": "Intervalo sugerido en segundos",
            "is_active": "Activo",
            "notes": "Observaciones",
        }

    def clean(self):
        cleaned = super().clean()
        provider_type = cleaned.get("provider_type")
        auth_mode = cleaned.get("auth_mode")
        if provider_type == MailConnector.ProviderType.MICROSOFT_GRAPH:
            if auth_mode != MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS:
                raise forms.ValidationError(
                    "Microsoft 365 requiere OAuth client credentials en esta fase."
                )
            for field_name in ("tenant_id_env", "client_id_env", "client_secret_env"):
                if not cleaned.get(field_name):
                    raise forms.ValidationError(
                        "Microsoft 365 requiere referencias a variables de entorno."
                    )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.read_only = True
        instance.config = {
            "tenant_id_env": self.cleaned_data.get("tenant_id_env", ""),
            "client_id_env": self.cleaned_data.get("client_id_env", ""),
            "client_secret_env": self.cleaned_data.get("client_secret_env", ""),
        }
        if commit:
            instance.save()
        return instance
