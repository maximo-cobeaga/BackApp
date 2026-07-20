from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase

from apps.customers.forms import SiteForm
from apps.customers.models import ManagedCustomer, Site
from apps.inventory.forms import ObjectRelationForm, ProtectedObjectForm
from apps.inventory.models import ObjectRelation, ProtectedObject
from apps.tenancy.models import Membership, Organization
from apps.tenancy.services import get_tenant_context, require_admin


class TenantBoundaryTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="admin_a", password="pass")
        self.user_b = User.objects.create_user(username="admin_b", password="pass")
        self.viewer = User.objects.create_user(username="viewer", password="pass")
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")
        Membership.objects.create(
            organization=self.org_a,
            user=self.user_a,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.org_b,
            user=self.user_b,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.org_a,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.customer_a = ManagedCustomer.objects.create(
            organization=self.org_a,
            name="Cliente A",
        )
        self.customer_b = ManagedCustomer.objects.create(
            organization=self.org_b,
            name="Cliente B",
        )
        self.site_a = Site.objects.create(
            organization=self.org_a,
            managed_customer=self.customer_a,
            name="MDP",
        )
        self.site_b = Site.objects.create(
            organization=self.org_b,
            managed_customer=self.customer_b,
            name="BA",
        )
        self.server_a = ProtectedObject.objects.create(
            organization=self.org_a,
            managed_customer=self.customer_a,
            site=self.site_a,
            name="YAPP",
            object_type=ProtectedObject.ObjectType.PHYSICAL_SERVER,
            hostname="YAPP",
        )
        self.app_a = ProtectedObject.objects.create(
            organization=self.org_a,
            managed_customer=self.customer_a,
            site=self.site_a,
            name="ERP",
            object_type=ProtectedObject.ObjectType.APPLICATION,
        )
        self.server_b = ProtectedObject.objects.create(
            organization=self.org_b,
            managed_customer=self.customer_b,
            site=self.site_b,
            name="OTHER",
            object_type=ProtectedObject.ObjectType.PHYSICAL_SERVER,
        )

    def _request_for(self, user, organization_id=None):
        request = RequestFactory().get("/")
        request.user = user
        request.session = {}
        if organization_id is not None:
            request.session["active_organization_id"] = str(organization_id)
        return request

    def test_single_membership_resolves_active_organization(self):
        request = self._request_for(self.user_a)
        context = get_tenant_context(request)
        assert context.organization == self.org_a
        assert request.session["active_organization_id"] == str(self.org_a.id)

    def test_user_cannot_select_foreign_organization(self):
        request = self._request_for(self.user_a, organization_id=self.org_b.id)
        with self.assertRaises(PermissionDenied):
            get_tenant_context(request)

    def test_admin_role_is_required_for_writes(self):
        request = self._request_for(self.viewer)
        with self.assertRaises(PermissionDenied):
            require_admin(request)

    def test_customer_queries_are_scoped_by_organization(self):
        visible = ManagedCustomer.objects.filter(organization=self.org_a)
        assert list(visible) == [self.customer_a]

    def test_site_form_only_exposes_active_organization_customers(self):
        form = SiteForm(organization=self.org_a)
        assert list(form.fields["managed_customer"].queryset) == [self.customer_a]

    def test_protected_object_form_only_exposes_active_organization_sites(self):
        form = ProtectedObjectForm(organization=self.org_a)
        assert list(form.fields["site"].queryset) == [self.site_a]

    def test_relation_form_only_exposes_active_organization_objects(self):
        form = ObjectRelationForm(organization=self.org_a)
        assert set(form.fields["source"].queryset) == {self.server_a, self.app_a}
        assert self.server_b not in form.fields["target"].queryset

    def test_object_relation_cannot_cross_organizations(self):
        relation = ObjectRelation(
            organization=self.org_a,
            source=self.server_a,
            target=self.server_b,
            relation_type=ObjectRelation.RelationType.DEPENDS_ON,
        )
        with self.assertRaises(ValidationError):
            relation.clean()

    def test_application_can_be_marked_as_hosted_by_server(self):
        relation = ObjectRelation.objects.create(
            organization=self.org_a,
            source=self.server_a,
            target=self.app_a,
            relation_type=ObjectRelation.RelationType.HOSTS,
        )
        assert relation.organization == self.org_a
        assert relation.source == self.server_a
        assert relation.target == self.app_a
