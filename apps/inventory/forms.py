"""Forms for protected inventory."""
from django import forms

from apps.customers.models import Site
from apps.inventory.models import ObjectRelation, ProtectedObject


class ProtectedObjectForm(forms.ModelForm):
    class Meta:
        model = ProtectedObject
        fields = [
            "site",
            "name",
            "external_reference",
            "object_type",
            "hostname",
            "platform",
            "criticality",
            "notes",
            "is_active",
        ]
        labels = {
            "site": "Sede o entorno",
            "name": "Nombre",
            "external_reference": "Referencia externa",
            "object_type": "Tipo",
            "hostname": "Hostname opcional",
            "platform": "Plataforma",
            "criticality": "Criticidad",
            "notes": "Observaciones",
            "is_active": "Activo",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["site"].queryset = Site.objects.filter(organization=organization)


class ObjectRelationForm(forms.ModelForm):
    class Meta:
        model = ObjectRelation
        fields = ["source", "relation_type", "target", "notes", "is_active"]
        labels = {
            "source": "Objeto origen",
            "relation_type": "Relación",
            "target": "Objeto destino",
            "notes": "Observaciones",
            "is_active": "Activa",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            scoped_objects = ProtectedObject.objects.filter(organization=organization)
            self.fields["source"].queryset = scoped_objects
            self.fields["target"].queryset = scoped_objects
