"""Tenant-scoped manual daily-control views."""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from apps.operations.forms import DailyControlEntryForm
from apps.operations.models import DailyControlEntry
from apps.operations.services import build_daily_control_workbook
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def daily_control_list(request):
    context = get_tenant_context(request)
    selected_date = parse_date(request.GET.get("date", "")) or date.today()
    entries = DailyControlEntry.objects.select_related(
        "backup_job__managed_customer",
        "backup_job__site",
        "backup_job__technology",
        "protected_object",
    ).filter(organization=context.organization, control_date=selected_date)
    return render(
        request,
        "operations/daily_control_list.html",
        {"entries": entries, "selected_date": selected_date},
    )


@login_required
def daily_control_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = DailyControlEntryForm(request.POST, organization=context.organization)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.organization = context.organization
            entry.operator = request.user
            entry.save()
            return redirect("daily_control_list")
    else:
        form = DailyControlEntryForm(organization=context.organization)
    return render(request, "operations/daily_control_form.html", {"form": form})


@login_required
def daily_control_export(request):
    context = get_tenant_context(request)
    selected_date = parse_date(request.GET.get("date", "")) or date.today()
    output = build_daily_control_workbook(
        organization=context.organization,
        control_date=selected_date,
    )
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="daily-control-{selected_date.isoformat()}.xlsx"'
    )
    return response
