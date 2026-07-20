"""Forms for manual parser review."""
from django import forms


class ParsedItemReviewForm(forms.Form):
    review_note = forms.CharField(
        label="Nota de revisión",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
