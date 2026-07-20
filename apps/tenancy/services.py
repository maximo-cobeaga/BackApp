"""Tenant resolution and authorization services."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.tenancy.models import Membership, Organization


ACTIVE_ORGANIZATION_SESSION_KEY = "active_organization_id"


@dataclass(frozen=True)
class TenantContext:
    organization: Organization
    membership: Membership


def resolve_active_membership(request: HttpRequest) -> Membership:
    user = request.user
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")

    memberships = Membership.objects.select_related("organization").filter(
        user=user,
        is_active=True,
        organization__is_active=True,
    )

    active_id = request.session.get(ACTIVE_ORGANIZATION_SESSION_KEY)
    if active_id:
        membership = memberships.filter(organization_id=active_id).first()
        if membership is not None:
            return membership
        raise PermissionDenied("Active organization is not available for this user.")

    membership_count = memberships.count()
    if membership_count == 1:
        membership = memberships.get()
        request.session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(membership.organization_id)
        return membership

    if membership_count == 0:
        raise PermissionDenied("User has no active organization membership.")

    raise PermissionDenied("Select an active organization before continuing.")


def get_tenant_context(request: HttpRequest) -> TenantContext:
    membership = resolve_active_membership(request)
    return TenantContext(organization=membership.organization, membership=membership)


def require_admin(request: HttpRequest) -> TenantContext:
    context = get_tenant_context(request)
    if context.membership.role != Membership.Role.ADMIN:
        raise PermissionDenied("Administrator role is required.")
    return context


def scoped_to_organization(queryset, organization: Organization):
    return queryset.filter(organization=organization)
