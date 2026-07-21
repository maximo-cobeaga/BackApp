"""Tenant-scoped spreadsheet import views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from apps.imports.forms import ImportPreviewForm, LegacyConfigurationReconcileForm
from apps.imports.models import (
    ImportBatch,
    LegacyBackupConfiguration,
    LegacyDailyRecord,
    LegacyImportIssue,
    LegacyTicketReference,
)
from apps.imports.services import (
    confirm_import_batch,
    create_import_preview,
    mark_import_batch_rolled_back,
    reconcile_legacy_configuration,
)
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def import_batch_list(request):
    context = get_tenant_context(request)
    batches = ImportBatch.objects.filter(organization=context.organization)
    return render(request, "imports/batch_list.html", {"batches": batches})


@login_required
def legacy_import_summary(request):
    context = get_tenant_context(request)
    organization = context.organization
    latest_batch = (
        ImportBatch.objects.filter(
            organization=organization,
            source_sha256__gt="",
        )
        .order_by("-created_at")
        .first()
    )
    status_counts = (
        LegacyDailyRecord.objects.filter(organization=organization)
        .values("normalized_status")
        .annotate(total=Count("id"))
        .order_by("normalized_status")
    )
    metrics = {
        "batches": ImportBatch.objects.filter(
            organization=organization,
            source_sha256__gt="",
        ).count(),
        "configurations": LegacyBackupConfiguration.objects.filter(
            organization=organization,
        ).count(),
        "daily_records": LegacyDailyRecord.objects.filter(organization=organization).count(),
        "issues": LegacyImportIssue.objects.filter(organization=organization).count(),
        "tickets": LegacyTicketReference.objects.filter(organization=organization).count(),
    }
    return render(
        request,
        "imports/legacy_summary.html",
        {
            "latest_batch": latest_batch,
            "metrics": metrics,
            "status_counts": status_counts,
        },
    )


@login_required
def legacy_import_configuration_list(request):
    context = get_tenant_context(request)
    configurations = LegacyBackupConfiguration.objects.select_related(
        "managed_customer",
        "import_batch",
    ).filter(organization=context.organization)[:200]
    return render(
        request,
        "imports/legacy_configuration_list.html",
        {"configurations": configurations},
    )


@login_required
def legacy_import_configuration_detail(request, config_id):
    context = get_tenant_context(request)
    configuration = get_object_or_404(
        LegacyBackupConfiguration,
        id=config_id,
        organization=context.organization,
    )
    if request.method == "POST":
        require_admin(request)
        form = LegacyConfigurationReconcileForm(
            request.POST,
            legacy_configuration=configuration,
        )
        if form.is_valid():
            reconcile_legacy_configuration(
                legacy_configuration=configuration,
                site_name=form.cleaned_data["site_name"],
                object_name=form.cleaned_data["object_name"],
                technology_name=form.cleaned_data["technology_name"],
                job_name=form.cleaned_data["job_name"],
                user=request.user,
                note=form.cleaned_data.get("note", ""),
            )
            messages.success(request, "Configuración legacy reconciliada.")
            return redirect("legacy_import_configuration_detail", config_id=configuration.id)
    else:
        form = LegacyConfigurationReconcileForm(legacy_configuration=configuration)

    records = LegacyDailyRecord.objects.filter(
        organization=context.organization,
        backup_configuration=configuration,
    )[:200]
    issues = LegacyImportIssue.objects.filter(
        organization=context.organization,
        source_sha256=configuration.source_sha256,
        source_row=configuration.source_row,
    )[:200]
    status_counts = (
        LegacyDailyRecord.objects.filter(
            organization=context.organization,
            backup_configuration=configuration,
        )
        .values("normalized_status")
        .annotate(total=Count("id"))
        .order_by("normalized_status")
    )
    return render(
        request,
        "imports/legacy_configuration_detail.html",
        {
            "configuration": configuration,
            "records": records,
            "issues": issues,
            "status_counts": status_counts,
            "reconcile_form": form,
        },
    )


@login_required
def legacy_import_daily_record_list(request):
    context = get_tenant_context(request)
    records = LegacyDailyRecord.objects.select_related(
        "backup_configuration",
    ).filter(organization=context.organization)[:200]
    return render(
        request,
        "imports/legacy_daily_record_list.html",
        {"records": records},
    )


@login_required
def legacy_import_issue_list(request):
    context = get_tenant_context(request)
    issues = LegacyImportIssue.objects.filter(organization=context.organization)[:200]
    return render(
        request,
        "imports/legacy_issue_list.html",
        {"issues": issues},
    )


@login_required
def import_preview_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = ImportPreviewForm(request.POST, request.FILES)
        if form.is_valid():
            result = create_import_preview(
                organization=context.organization,
                user=request.user,
                uploaded_file=form.cleaned_data["workbook"],
                original_filename=form.cleaned_data["workbook"].name,
                column_mapping=form.column_mapping(),
            )
            return redirect("import_batch_detail", batch_id=result.batch.id)
    else:
        form = ImportPreviewForm()
    return render(request, "imports/preview_form.html", {"form": form})


@login_required
def import_batch_detail(request, batch_id):
    context = get_tenant_context(request)
    batch = get_object_or_404(ImportBatch, id=batch_id, organization=context.organization)
    rows = batch.rows.all()
    return render(request, "imports/batch_detail.html", {"batch": batch, "rows": rows})


@login_required
def import_batch_confirm(request, batch_id):
    context = require_admin(request)
    batch = get_object_or_404(ImportBatch, id=batch_id, organization=context.organization)
    if request.method == "POST":
        confirm_import_batch(batch=batch, user=request.user)
    return redirect("import_batch_detail", batch_id=batch.id)


@login_required
def import_batch_rollback(request, batch_id):
    context = require_admin(request)
    batch = get_object_or_404(ImportBatch, id=batch_id, organization=context.organization)
    if request.method == "POST":
        mark_import_batch_rolled_back(batch=batch, user=request.user)
    return redirect("import_batch_detail", batch_id=batch.id)
