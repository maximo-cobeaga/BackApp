"""Forms for backup inventory configuration."""
from django import forms

from apps.backups.models import (
    BackupDestination,
    BackupJob,
    BackupJobTarget,
    BackupSchedule,
    BackupTechnology,
    RetentionPolicy,
)
from apps.customers.models import Site
from apps.inventory.models import ProtectedObject


class BackupTechnologyForm(forms.ModelForm):
    class Meta:
        model = BackupTechnology
        fields = ["name", "vendor", "notes", "is_active"]
        labels = {
            "name": "Nombre",
            "vendor": "Proveedor",
            "notes": "Observaciones",
            "is_active": "Activa",
        }


class BackupJobForm(forms.ModelForm):
    class Meta:
        model = BackupJob
        fields = [
            "site",
            "technology",
            "name",
            "external_identifier",
            "matching_aliases",
            "status",
            "criticality",
            "internal_owner",
            "notes",
        ]
        labels = {
            "site": "Sede o entorno",
            "technology": "Tecnología",
            "name": "Nombre de tarea",
            "external_identifier": "Identificador externo",
            "matching_aliases": "Alias de matching",
            "status": "Estado",
            "criticality": "Criticidad",
            "internal_owner": "Responsable interno",
            "notes": "Observaciones",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["site"].queryset = Site.objects.filter(organization=organization)
            self.fields["technology"].queryset = BackupTechnology.objects.filter(
                organization=organization,
                is_active=True,
            )


class BackupJobTargetForm(forms.ModelForm):
    class Meta:
        model = BackupJobTarget
        fields = ["backup_job", "protected_object", "role", "inclusions", "exclusions", "notes", "is_active"]
        labels = {
            "backup_job": "Tarea de backup",
            "protected_object": "Objeto protegido",
            "role": "Rol",
            "inclusions": "Inclusiones",
            "exclusions": "Exclusiones",
            "notes": "Observaciones",
            "is_active": "Activo",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["backup_job"].queryset = BackupJob.objects.filter(
                organization=organization
            )
            self.fields["protected_object"].queryset = ProtectedObject.objects.filter(
                organization=organization
            )


class BackupScheduleForm(forms.ModelForm):
    class Meta:
        model = BackupSchedule
        fields = [
            "backup_job",
            "frequency",
            "weekdays",
            "scheduled_time",
            "timezone",
            "cron_expression",
            "expected_duration_minutes",
            "report_deadline_time",
            "report_deadline_offset_days",
            "mode",
            "notes",
            "is_active",
        ]
        labels = {
            "backup_job": "Tarea de backup",
            "frequency": "Frecuencia",
            "weekdays": "Días",
            "scheduled_time": "Hora programada",
            "timezone": "Zona horaria",
            "cron_expression": "Expresión cron opcional",
            "expected_duration_minutes": "Duración esperada en minutos",
            "report_deadline_time": "Hora límite de reporte",
            "report_deadline_offset_days": "Días de margen para reporte",
            "mode": "Modalidad",
            "notes": "Observaciones",
            "is_active": "Activa",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["backup_job"].queryset = BackupJob.objects.filter(
                organization=organization
            )


class BackupDestinationForm(forms.ModelForm):
    class Meta:
        model = BackupDestination
        fields = [
            "backup_job",
            "repository_type",
            "name",
            "location",
            "capacity_gb",
            "free_space_threshold_gb",
            "is_offsite",
            "notes",
        ]
        labels = {
            "backup_job": "Tarea de backup",
            "repository_type": "Tipo de repositorio",
            "name": "Nombre",
            "location": "Ubicación",
            "capacity_gb": "Capacidad GB",
            "free_space_threshold_gb": "Umbral libre GB",
            "is_offsite": "Offsite",
            "notes": "Observaciones",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["backup_job"].queryset = BackupJob.objects.filter(
                organization=organization
            )


class RetentionPolicyForm(forms.ModelForm):
    class Meta:
        model = RetentionPolicy
        fields = [
            "backup_job",
            "daily_copies",
            "weekly_copies",
            "monthly_copies",
            "annual_copies",
            "total_days",
            "uses_gfs",
            "deleted_item_retention_days",
            "notes",
        ]
        labels = {
            "backup_job": "Tarea de backup",
            "daily_copies": "Copias diarias",
            "weekly_copies": "Copias semanales",
            "monthly_copies": "Copias mensuales",
            "annual_copies": "Copias anuales",
            "total_days": "Días totales",
            "uses_gfs": "Usa GFS",
            "deleted_item_retention_days": "Retención de eliminados",
            "notes": "Observaciones",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["backup_job"].queryset = BackupJob.objects.filter(
                organization=organization
            )
