"""Forms for manual parser review."""
from django import forms

from apps.operations.models import BackupExecution, ExpectedExecution
from apps.operations.services import BackupExecutionCandidate


class ParsedItemReviewForm(forms.Form):
    expected_execution = forms.ModelChoiceField(
        label="Ejecución esperada",
        queryset=ExpectedExecution.objects.none(),
        required=False,
        help_text="Asociá el reporte recibido con la ejecución que debía llegar.",
    )
    result = forms.ChoiceField(
        label="Resultado real",
        choices=BackupExecution.Result.choices,
        required=False,
        help_text="Usá Desconocido si el formato todavía no permite confirmar el resultado.",
    )
    review_note = forms.CharField(
        label="Nota de revisión",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(
        self,
        *args,
        organization=None,
        initial_result=None,
        matching_candidates: list[BackupExecutionCandidate] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.matching_candidates = matching_candidates or []
        self.candidate_by_id = {
            candidate.expected_execution.id: candidate
            for candidate in self.matching_candidates
        }
        if organization is not None:
            self.fields["expected_execution"].queryset = (
                ExpectedExecution.objects.filter(organization=organization)
                .select_related("backup_job__managed_customer", "backup_job__site")
                .order_by("-service_date", "backup_job__name")
            )
        self.fields["expected_execution"].label_from_instance = self._expected_label
        if self._has_single_strong_candidate():
            self.fields["expected_execution"].initial = (
                self.matching_candidates[0].expected_execution
            )
        if initial_result is not None:
            self.fields["result"].initial = initial_result

    def _expected_label(self, expected_execution: ExpectedExecution) -> str:
        label = str(expected_execution)
        candidate = self.candidate_by_id.get(expected_execution.id)
        if candidate:
            percent = int(candidate.confidence * 100)
            return f"Sugerida {percent}% · {label}"
        return label

    def _has_single_strong_candidate(self) -> bool:
        if not self.matching_candidates:
            return False
        first = self.matching_candidates[0]
        if first.confidence < 0.75:
            return False
        if len(self.matching_candidates) == 1:
            return True
        return first.confidence > self.matching_candidates[1].confidence

    def clean(self):
        cleaned = super().clean()
        expected_execution = cleaned.get("expected_execution")
        result = cleaned.get("result")
        if expected_execution and not result:
            raise forms.ValidationError(
                "Seleccioná el resultado real para asociar la ejecución."
            )
        return cleaned
