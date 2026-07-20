"""Template context helpers for tenant-aware pages."""
from django.core.exceptions import PermissionDenied

from apps.tenancy.services import get_tenant_context


def active_organization(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"active_organization": None}
    try:
        context = get_tenant_context(request)
    except PermissionDenied:
        return {"active_organization": None}
    return {"active_organization": context.organization}
