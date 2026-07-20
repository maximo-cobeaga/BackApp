"""Forms for expected executions and manual daily control."""
from django import forms

from apps.backups.models import BackupJob, BackupJobTarget
from apps.operations.models import DailyControlEntry, ExpectedExecution


class ExpectedExecutionGenerateForm(forms.Form):
    service_date = forms.DateField(
        label="Fecha de servicio",
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class DailyControlEntryForm(forms.ModelForm):
    class Meta:
        model = DailyControlEntry
        fields = [
            "control_date",
            "expected_execution",
            "backup_job",
            "backup_job_target",
            "result",
            "observed_at",
            "manual_observation",
            "ticket_reference",
        ]
        widgets = {
            "control_date": forms.DateInput(attrs={"type": "date"}),
            "observed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "control_date": "Fecha de control",
            "expected_execution": "Ejecución esperada",
            "backup_job": "Tarea de backup",
            "backup_job_target": "Objeto protegido",
            "result": "Resultado",
            "observed_at": "Hora observada",
            "manual_observation": "Observación manual",
            "ticket_reference": "Ticket",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["expected_execution"].queryset = ExpectedExecution.objects.filter(
                organization=organization
            )
            self.fields["backup_job"].queryset = BackupJob.objects.filter(
                organization=organization
            )
            self.fields["backup_job_target"].queryset = BackupJobTarget.objects.filter(
                organization=organization
            ).select_related("backup_job", "protected_object")
