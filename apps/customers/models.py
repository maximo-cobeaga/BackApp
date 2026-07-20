"""Managed customer and site models."""
from django.db import models

from apps.tenancy.models import OrganizationOwnedModel


class ManagedCustomer(OrganizationOwnedModel):
    name = models.CharField(max_length=255)
    internal_code = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uq_managed_customer_name_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "internal_code"],
                condition=~models.Q(internal_code=""),
                name="uq_managed_customer_code_per_organization",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Site(OrganizationOwnedModel):
    class SiteType(models.TextChoices):
        OFFICE = "OFFICE", "Oficina"
        DATACENTER = "DATACENTER", "Datacenter"
        CLOUD = "CLOUD", "Cloud"
        SAAS = "SAAS", "SaaS"
        OTHER = "OTHER", "Otro"

    managed_customer = models.ForeignKey(
        ManagedCustomer,
        on_delete=models.PROTECT,
        related_name="sites",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    site_type = models.CharField(
        max_length=20,
        choices=SiteType.choices,
        default=SiteType.OTHER,
    )
    timezone = models.CharField(max_length=64, default="America/Argentina/Buenos_Aires")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["managed_customer__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "managed_customer", "name"],
                name="uq_site_name_per_customer_organization",
            )
        ]

    def clean(self):
        if self.managed_customer_id:
            self.organization = self.managed_customer.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.managed_customer} - {self.name}"
