"""Tenant-scoped backup inventory views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.backups.forms import (
    BackupDestinationForm,
    BackupJobForm,
    BackupJobTargetForm,
    BackupScheduleForm,
    BackupTechnologyForm,
    RetentionPolicyForm,
)
from apps.backups.models import (
    BackupDestination,
    BackupJob,
    BackupJobTarget,
    BackupSchedule,
    BackupTechnology,
    RetentionPolicy,
)
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def technology_list(request):
    context = get_tenant_context(request)
    technologies = BackupTechnology.objects.filter(organization=context.organization)
    return render(request, "backups/technology_list.html", {"technologies": technologies})


@login_required
def technology_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = BackupTechnologyForm(request.POST)
        if form.is_valid():
            technology = form.save(commit=False)
            technology.organization = context.organization
            technology.save()
            return redirect("backup_technology_list")
    else:
        form = BackupTechnologyForm()
    return render(request, "backups/form.html", {"form": form, "title": "Crear tecnología"})


@login_required
def job_list(request):
    context = get_tenant_context(request)
    jobs = BackupJob.objects.select_related("managed_customer", "site", "technology").filter(
        organization=context.organization
    )
    return render(request, "backups/job_list.html", {"jobs": jobs})


@login_required
def job_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = BackupJobForm(request.POST, organization=context.organization)
        if form.is_valid():
            job = form.save(commit=False)
            job.organization = context.organization
            job.save()
            return redirect("backup_job_list")
    else:
        form = BackupJobForm(organization=context.organization)
    return render(request, "backups/form.html", {"form": form, "title": "Crear tarea de backup"})


@login_required
def target_list(request):
    context = get_tenant_context(request)
    targets = BackupJobTarget.objects.select_related(
        "backup_job",
        "protected_object",
    ).filter(organization=context.organization)
    return render(request, "backups/target_list.html", {"targets": targets})


@login_required
def target_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = BackupJobTargetForm(request.POST, organization=context.organization)
        if form.is_valid():
            target = form.save(commit=False)
            target.organization = context.organization
            target.save()
            return redirect("backup_target_list")
    else:
        form = BackupJobTargetForm(organization=context.organization)
    return render(request, "backups/form.html", {"form": form, "title": "Agregar objetivo"})


@login_required
def schedule_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = BackupScheduleForm(request.POST, organization=context.organization)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.organization = context.organization
            schedule.save()
            return redirect("backup_job_list")
    else:
        form = BackupScheduleForm(organization=context.organization)
    return render(request, "backups/form.html", {"form": form, "title": "Crear programación"})


@login_required
def destination_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = BackupDestinationForm(request.POST, organization=context.organization)
        if form.is_valid():
            destination = form.save(commit=False)
            destination.organization = context.organization
            destination.save()
            return redirect("backup_job_list")
    else:
        form = BackupDestinationForm(organization=context.organization)
    return render(request, "backups/form.html", {"form": form, "title": "Crear destino"})


@login_required
def retention_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = RetentionPolicyForm(request.POST, organization=context.organization)
        if form.is_valid():
            retention = form.save(commit=False)
            retention.organization = context.organization
            retention.save()
            return redirect("backup_job_list")
    else:
        form = RetentionPolicyForm(organization=context.organization)
    return render(request, "backups/form.html", {"form": form, "title": "Crear retención"})


@login_required
def configuration_summary(request):
    context = get_tenant_context(request)
    return render(
        request,
        "backups/configuration_summary.html",
        {
            "job_count": BackupJob.objects.filter(organization=context.organization).count(),
            "target_count": BackupJobTarget.objects.filter(organization=context.organization).count(),
            "schedule_count": BackupSchedule.objects.filter(organization=context.organization).count(),
            "destination_count": BackupDestination.objects.filter(organization=context.organization).count(),
            "retention_count": RetentionPolicy.objects.filter(organization=context.organization).count(),
        },
    )
