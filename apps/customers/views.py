"""Tenant-scoped customer views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.customers.forms import ManagedCustomerForm, SiteForm
from apps.customers.models import ManagedCustomer, Site
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def customer_list(request):
    context = get_tenant_context(request)
    customers = ManagedCustomer.objects.filter(organization=context.organization)
    return render(request, "customers/customer_list.html", {"customers": customers})


@login_required
def customer_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = ManagedCustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = context.organization
            customer.save()
            return redirect("customer_list")
    else:
        form = ManagedCustomerForm()
    return render(request, "customers/customer_form.html", {"form": form})


@login_required
def site_list(request):
    context = get_tenant_context(request)
    sites = Site.objects.select_related("managed_customer").filter(
        organization=context.organization
    )
    return render(request, "customers/site_list.html", {"sites": sites})


@login_required
def site_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = SiteForm(request.POST, organization=context.organization)
        if form.is_valid():
            site = form.save(commit=False)
            site.organization = context.organization
            site.save()
            return redirect("site_list")
    else:
        form = SiteForm(organization=context.organization)
    return render(request, "customers/site_form.html", {"form": form})
