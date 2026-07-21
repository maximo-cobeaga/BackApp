"""Forms for spreadsheet import mapping."""
from django import forms

from apps.imports.models import LegacyBackupConfiguration


class LegacyConfigurationReconcileForm(forms.Form):
    site_name = forms.CharField(label="Sede operativa")
    object_name = forms.CharField(label="Objeto protegido")
    technology_name = forms.CharField(label="Tecnología")
    job_name = forms.CharField(label="Tarea de backup")
    note = forms.CharField(label="Nota de reconciliación", required=False, widget=forms.Textarea)

    def __init__(self, *args, legacy_configuration: LegacyBackupConfiguration, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            site_label = legacy_configuration.legacy_site_label.strip()
            if site_label.casefold() in {"", "n/a", "na"}:
                site_label = ""
            technology = (
                legacy_configuration.provider
                or legacy_configuration.legacy_method
                or ""
            )
            self.fields["site_name"].initial = site_label
            self.fields["object_name"].initial = legacy_configuration.source_asset_label
            self.fields["technology_name"].initial = technology
            self.fields["job_name"].initial = legacy_configuration.legacy_backup_name


class ImportPreviewForm(forms.Form):
    workbook = forms.FileField(label="Archivo Excel")
    customer_column = forms.CharField(label="Columna cliente", initial="Cliente")
    site_column = forms.CharField(label="Columna sede", initial="Sede")
    reference_column = forms.CharField(label="Columna referencia", initial="Referencia", required=False)
    object_name_column = forms.CharField(label="Columna objeto", initial="Objeto")
    object_type_column = forms.CharField(label="Columna tipo de objeto", required=False)
    technology_column = forms.CharField(label="Columna tecnología", initial="Tecnología")
    job_name_column = forms.CharField(label="Columna tarea", initial="Tarea")
    status_column = forms.CharField(label="Columna estado", required=False)
    observation_column = forms.CharField(label="Columna observación", required=False)

    def column_mapping(self) -> dict[str, str]:
        return {
            "customer": self.cleaned_data["customer_column"],
            "site": self.cleaned_data["site_column"],
            "reference": self.cleaned_data.get("reference_column", ""),
            "object_name": self.cleaned_data["object_name_column"],
            "object_type": self.cleaned_data.get("object_type_column", ""),
            "technology": self.cleaned_data["technology_column"],
            "job_name": self.cleaned_data["job_name_column"],
            "status": self.cleaned_data.get("status_column", ""),
            "observation": self.cleaned_data.get("observation_column", ""),
        }
