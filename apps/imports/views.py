"""Tenant-scoped spreadsheet import views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.imports.forms import ImportPreviewForm
from apps.imports.models import ImportBatch
from apps.imports.services import confirm_import_batch, create_import_preview, mark_import_batch_rolled_back
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def import_batch_list(request):
    context = get_tenant_context(request)
    batches = ImportBatch.objects.filter(organization=context.organization)
    return render(request, "imports/batch_list.html", {"batches": batches})


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
