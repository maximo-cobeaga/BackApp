"""Spreadsheet import preview and confirmation services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import IO, Any

from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.backups.models import BackupJob, BackupJobTarget, BackupTechnology
from apps.customers.models import ManagedCustomer, Site
from apps.imports.models import ImportBatch, ImportRow
from apps.inventory.models import ProtectedObject
from apps.tenancy.models import Organization


REQUIRED_FIELDS = ("customer", "site", "object_name", "job_name", "technology")
OPTIONAL_FIELDS = ("reference", "object_type", "status", "observation")


@dataclass(frozen=True)
class ImportPreviewResult:
    batch: ImportBatch
    rows: list[ImportRow]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _header_map(headers: list[str]) -> dict[str, int]:
    return {header: index for index, header in enumerate(headers) if header}


def _cell(row: tuple[Any, ...], headers: dict[str, int], column_name: str) -> str:
    index = headers.get(column_name)
    if index is None or index >= len(row):
        return ""
    return _clean(row[index])


def _status_for_row(organization: Organization, normalized: dict[str, str]) -> tuple[str, list[str]]:
    messages: list[str] = []
    missing = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
    if missing:
        messages.append(f"Missing required fields: {', '.join(missing)}")
        return ImportRow.Status.INCOMPLETE, messages

    customer = ManagedCustomer.objects.filter(
        organization=organization,
        name=normalized["customer"],
    ).first()
    if not customer:
        messages.append("Managed customer will be created.")
        return ImportRow.Status.NEW, messages

    site = Site.objects.filter(
        organization=organization,
        managed_customer=customer,
        name=normalized["site"],
    ).first()
    if not site:
        messages.append("Site will be created.")
        return ImportRow.Status.NEW, messages

    protected_object = ProtectedObject.objects.filter(
        organization=organization,
        managed_customer=customer,
        site=site,
        name=normalized["object_name"],
    ).first()
    technology = BackupTechnology.objects.filter(
        organization=organization,
        name=normalized["technology"],
    ).first()
    job = None
    if technology:
        job = BackupJob.objects.filter(
            organization=organization,
            managed_customer=customer,
            site=site,
            technology=technology,
            name=normalized["job_name"],
        ).first()

    if protected_object and technology and job:
        messages.append("Existing customer, site, object, technology, and job found.")
        return ImportRow.Status.MATCHED, messages

    messages.append("One or more domain records will be created.")
    return ImportRow.Status.NEW, messages


@transaction.atomic
def create_import_preview(
    *,
    organization: Organization,
    user,
    uploaded_file: IO[bytes],
    original_filename: str,
    column_mapping: dict[str, str],
) -> ImportPreviewResult:
    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    headers = [_clean(value) for value in next(rows_iter, ())]
    header_indexes = _header_map(headers)

    batch = ImportBatch.objects.create(
        organization=organization,
        original_filename=original_filename,
        column_mapping=column_mapping,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )

    preview_rows: list[ImportRow] = []
    last_customer = ""
    for row_number, row in enumerate(rows_iter, start=2):
        raw_data = {header: _clean(row[index]) if index < len(row) else "" for header, index in header_indexes.items()}
        normalized: dict[str, str] = {}
        for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
            mapped_column = column_mapping.get(field, "")
            normalized[field] = _cell(row, header_indexes, mapped_column) if mapped_column else ""

        if normalized.get("customer"):
            last_customer = normalized["customer"]
        else:
            normalized["customer"] = last_customer

        if not normalized.get("object_type"):
            normalized["object_type"] = ProtectedObject.ObjectType.OTHER

        status, messages = _status_for_row(organization, normalized)
        preview_rows.append(
            ImportRow(
                organization=organization,
                batch=batch,
                row_number=row_number,
                raw_data=raw_data,
                normalized_data=normalized,
                status=status,
                messages=messages,
            )
        )

    ImportRow.objects.bulk_create(preview_rows)
    batch.row_count = len(preview_rows)
    batch.save(update_fields=["row_count", "updated_at"])
    return ImportPreviewResult(batch=batch, rows=list(batch.rows.all()))


@transaction.atomic
def confirm_import_batch(*, batch: ImportBatch, user) -> ImportBatch:
    if batch.status != ImportBatch.Status.PREVIEW:
        raise ValueError("Only preview batches can be confirmed.")

    imported_customer_ids: list[str] = []
    imported_site_ids: list[str] = []
    imported_object_ids: list[str] = []
    imported_technology_ids: list[str] = []
    imported_job_ids: list[str] = []
    imported_target_ids: list[str] = []

    for row in batch.rows.select_for_update().all():
        if row.status == ImportRow.Status.INCOMPLETE:
            row.status = ImportRow.Status.SKIPPED
            row.messages = [*row.messages, "Skipped because required fields are missing."]
            row.save(update_fields=["status", "messages", "updated_at"])
            continue

        data = row.normalized_data
        customer, customer_created = ManagedCustomer.objects.get_or_create(
            organization=batch.organization,
            name=data["customer"],
        )
        if customer_created:
            imported_customer_ids.append(str(customer.id))

        site, site_created = Site.objects.get_or_create(
            organization=batch.organization,
            managed_customer=customer,
            name=data["site"],
        )
        if site_created:
            imported_site_ids.append(str(site.id))

        technology, technology_created = BackupTechnology.objects.get_or_create(
            organization=batch.organization,
            name=data["technology"],
        )
        if technology_created:
            imported_technology_ids.append(str(technology.id))

        protected_object, object_created = ProtectedObject.objects.get_or_create(
            organization=batch.organization,
            managed_customer=customer,
            site=site,
            name=data["object_name"],
            defaults={
                "external_reference": data.get("reference", ""),
                "object_type": data.get("object_type") or ProtectedObject.ObjectType.OTHER,
            },
        )
        if object_created:
            imported_object_ids.append(str(protected_object.id))

        job, job_created = BackupJob.objects.get_or_create(
            organization=batch.organization,
            managed_customer=customer,
            site=site,
            technology=technology,
            name=data["job_name"],
        )
        if job_created:
            imported_job_ids.append(str(job.id))

        target, target_created = BackupJobTarget.objects.get_or_create(
            organization=batch.organization,
            backup_job=job,
            protected_object=protected_object,
        )
        if target_created:
            imported_target_ids.append(str(target.id))

        row.status = ImportRow.Status.IMPORTED
        row.messages = [*row.messages, "Imported or matched successfully."]
        row.save(update_fields=["status", "messages", "updated_at"])

    batch.imported_customer_ids = imported_customer_ids
    batch.imported_site_ids = imported_site_ids
    batch.imported_object_ids = imported_object_ids
    batch.imported_technology_ids = imported_technology_ids
    batch.imported_job_ids = imported_job_ids
    batch.imported_target_ids = imported_target_ids
    batch.status = ImportBatch.Status.IMPORTED
    batch.confirmed_by = user if getattr(user, "is_authenticated", False) else None
    batch.confirmed_at = timezone.now()
    batch.save()
    return batch


@transaction.atomic
def mark_import_batch_rolled_back(*, batch: ImportBatch, user) -> ImportBatch:
    if batch.status != ImportBatch.Status.IMPORTED:
        raise ValueError("Only imported batches can be marked as rolled back.")
    batch.status = ImportBatch.Status.ROLLED_BACK
    batch.rolled_back_by = user if getattr(user, "is_authenticated", False) else None
    batch.rolled_back_at = timezone.now()
    batch.notes = (batch.notes + "\n" if batch.notes else "") + "Rollback metadata recorded."
    batch.save()
    return batch
