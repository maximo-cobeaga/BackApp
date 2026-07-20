"""Tenant-scoped mailbox connector views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.ingestion.forms import MailConnectorForm
from apps.ingestion.models import InboundMessage, MailConnector
from apps.ingestion.providers.base import MailProviderError
from apps.ingestion.services import sync_mailbox
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def connector_list(request):
    context = get_tenant_context(request)
    connectors = MailConnector.objects.filter(organization=context.organization)
    return render(request, "ingestion/connector_list.html", {"connectors": connectors})


@login_required
def connector_create(request):
    context = require_admin(request)
    if request.method == "POST":
        form = MailConnectorForm(request.POST)
        if form.is_valid():
            connector = form.save(commit=False)
            connector.organization = context.organization
            connector.created_by = request.user
            connector.save()
            return redirect("mail_connector_list")
    else:
        form = MailConnectorForm(
            initial={
                "provider_type": MailConnector.ProviderType.MICROSOFT_GRAPH,
                "auth_mode": MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
                "folder": "Inbox",
            }
        )
    return render(request, "ingestion/connector_form.html", {"form": form})


@login_required
def connector_sync(request, connector_id):
    context = require_admin(request)
    connector = get_object_or_404(
        MailConnector,
        id=connector_id,
        organization=context.organization,
    )
    if request.method == "POST":
        try:
            result = sync_mailbox(connector=connector)
            messages.success(
                request,
                f"Sincronización completa: {result.created} nuevos, {result.skipped} omitidos.",
            )
        except MailProviderError as exc:
            messages.error(request, f"No se pudo sincronizar la casilla: {exc}")
    return redirect("mail_connector_list")


@login_required
def message_list(request):
    context = get_tenant_context(request)
    inbound_messages = InboundMessage.objects.select_related("connector").filter(
        organization=context.organization
    )
    return render(
        request,
        "ingestion/message_list.html",
        {"inbound_messages": inbound_messages},
    )
