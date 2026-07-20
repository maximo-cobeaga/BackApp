from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import ManagedCustomer, Site
from apps.inventory.models import ObjectRelation, ProtectedObject
from apps.tenancy.models import Membership, Organization


class PhaseOneViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin", password="pass")
        self.other_user = User.objects.create_user(username="other", password="pass")
        self.org = Organization.objects.create(name="Org", slug="org")
        self.other_org = Organization.objects.create(name="Other", slug="other")
        Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.other_org,
            user=self.other_user,
            role=Membership.Role.ADMIN,
        )
        self.other_customer = ManagedCustomer.objects.create(
            organization=self.other_org,
            name="Cliente ajeno",
        )
        self.client.force_login(self.user)

    def test_admin_can_create_customer_site_object_and_relation(self):
        customer_response = self.client.post(
            reverse("customer_create"),
            {"name": "Cliente", "internal_code": "CLI", "notes": "", "is_active": "on"},
        )
        assert customer_response.status_code == 302
        customer = ManagedCustomer.objects.get(organization=self.org, name="Cliente")

        site_response = self.client.post(
            reverse("site_create"),
            {
                "managed_customer": str(customer.id),
                "name": "MDP",
                "code": "MDP",
                "site_type": Site.SiteType.OFFICE,
                "timezone": "America/Argentina/Buenos_Aires",
                "notes": "",
                "is_active": "on",
            },
        )
        assert site_response.status_code == 302
        site = Site.objects.get(organization=self.org, name="MDP")

        server_response = self.client.post(
            reverse("protected_object_create"),
            {
                "site": str(site.id),
                "name": "YAPP",
                "external_reference": "YA01",
                "object_type": ProtectedObject.ObjectType.PHYSICAL_SERVER,
                "hostname": "YAPP",
                "platform": "Windows Server",
                "criticality": "Alta",
                "notes": "",
                "is_active": "on",
            },
        )
        assert server_response.status_code == 302
        server = ProtectedObject.objects.get(organization=self.org, name="YAPP")

        app_response = self.client.post(
            reverse("protected_object_create"),
            {
                "site": str(site.id),
                "name": "ERP",
                "external_reference": "APP-ERP",
                "object_type": ProtectedObject.ObjectType.APPLICATION,
                "hostname": "",
                "platform": "",
                "criticality": "Alta",
                "notes": "",
                "is_active": "on",
            },
        )
        assert app_response.status_code == 302
        app = ProtectedObject.objects.get(organization=self.org, name="ERP")

        relation_response = self.client.post(
            reverse("object_relation_create"),
            {
                "source": str(server.id),
                "relation_type": ObjectRelation.RelationType.HOSTS,
                "target": str(app.id),
                "notes": "",
                "is_active": "on",
            },
        )
        assert relation_response.status_code == 302
        assert ObjectRelation.objects.filter(
            organization=self.org,
            source=server,
            target=app,
            relation_type=ObjectRelation.RelationType.HOSTS,
        ).exists()

    def test_customer_list_hides_other_organization_records(self):
        ManagedCustomer.objects.create(organization=self.org, name="Visible")
        response = self.client.get(reverse("customer_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Visible" in content
        assert "Cliente ajeno" not in content
