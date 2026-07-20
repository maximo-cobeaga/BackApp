"""Protected inventory models."""
from django.core.exceptions import ValidationError
from django.db import models

from apps.customers.models import ManagedCustomer, Site
from apps.tenancy.models import OrganizationOwnedModel


class ProtectedObject(OrganizationOwnedModel):
    class ObjectType(models.TextChoices):
        PHYSICAL_SERVER = "PHYSICAL_SERVER", "Servidor físico"
        VIRTUAL_SERVER = "VIRTUAL_SERVER", "Servidor virtual"
        VIRTUAL_MACHINE = "VIRTUAL_MACHINE", "Máquina virtual"
        APPLICATION = "APPLICATION", "Aplicación"
        DATABASE = "DATABASE", "Base de datos"
        FILE_SET = "FILE_SET", "Archivos o carpetas"
        NAS = "NAS", "NAS"
        MICROSOFT_365_TENANT = "MICROSOFT_365_TENANT", "Tenant Microsoft 365"
        MAILBOX = "MAILBOX", "Buzón"
        CLOUD_RESOURCE = "CLOUD_RESOURCE", "Recurso cloud"
        SNAPSHOT = "SNAPSHOT", "Snapshot"
        OTHER = "OTHER", "Otro"

    managed_customer = models.ForeignKey(
        ManagedCustomer,
        on_delete=models.PROTECT,
        related_name="protected_objects",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="protected_objects",
    )
    name = models.CharField(max_length=255)
    external_reference = models.CharField(max_length=120, blank=True)
    object_type = models.CharField(max_length=40, choices=ObjectType.choices)
    hostname = models.CharField(max_length=255, blank=True)
    platform = models.CharField(max_length=120, blank=True)
    criticality = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["managed_customer__name", "site__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "managed_customer", "site", "name"],
                name="uq_protected_object_name_per_site_organization",
            ),
        ]

    def clean(self):
        if self.site_id:
            self.organization = self.site.organization
            self.managed_customer = self.site.managed_customer
        if self.managed_customer_id and self.site_id:
            if self.managed_customer.organization_id != self.site.organization_id:
                raise ValidationError("Customer and site must belong to the same organization.")
            if self.site.managed_customer_id != self.managed_customer_id:
                raise ValidationError("Site must belong to the selected customer.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ObjectRelation(OrganizationOwnedModel):
    class RelationType(models.TextChoices):
        HOSTS = "HOSTS", "Aloja"
        RUNS_ON = "RUNS_ON", "Corre sobre"
        PART_OF = "PART_OF", "Parte de"
        DEPENDS_ON = "DEPENDS_ON", "Depende de"
        OTHER = "OTHER", "Otra"

    source = models.ForeignKey(
        ProtectedObject,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
    )
    target = models.ForeignKey(
        ProtectedObject,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
    )
    relation_type = models.CharField(max_length=20, choices=RelationType.choices)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["source__name", "relation_type", "target__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source", "target", "relation_type"],
                name="uq_object_relation_per_organization",
            ),
            models.CheckConstraint(
                condition=~models.Q(source=models.F("target")),
                name="ck_object_relation_no_self_link",
            ),
        ]

    def clean(self):
        if self.source_id:
            self.organization = self.source.organization
        if self.source_id and self.target_id:
            if self.source.organization_id != self.target.organization_id:
                raise ValidationError("Related objects must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.source} {self.relation_type} {self.target}"
