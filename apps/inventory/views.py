"""Tenant-scoped protected inventory views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.inventory.forms import ObjectRelationForm, ProtectedObjectForm
from apps.inventory.models import ObjectRelation, ProtectedObject
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def protected_object_list(request):
    context = get_tenant_context(request)
    objects = ProtectedObject.objects.select_related("managed_customer", "site").filter(
        organization=context.organization
    )
    return render(request, "inventory/object_list.html", {"objects": objects})


@login_required
def protected_object_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = ProtectedObjectForm(request.POST, organization=context.organization)
        if form.is_valid():
            protected_object = form.save(commit=False)
            protected_object.organization = context.organization
            protected_object.save()
            return redirect("protected_object_list")
    else:
        form = ProtectedObjectForm(organization=context.organization)
    return render(request, "inventory/object_form.html", {"form": form})


@login_required
def object_relation_list(request):
    context = get_tenant_context(request)
    relations = ObjectRelation.objects.select_related("source", "target").filter(
        organization=context.organization
    )
    return render(request, "inventory/relation_list.html", {"relations": relations})


@login_required
def object_relation_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = ObjectRelationForm(request.POST, organization=context.organization)
        if form.is_valid():
            relation = form.save(commit=False)
            relation.organization = context.organization
            relation.save()
            return redirect("object_relation_list")
    else:
        form = ObjectRelationForm(organization=context.organization)
    return render(request, "inventory/relation_form.html", {"form": form})
