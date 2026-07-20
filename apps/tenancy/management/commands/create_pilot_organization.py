"""Create the default pilot organization and optional admin membership."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.tenancy.models import Membership, Organization


class Command(BaseCommand):
    help = "Create the pilot organization and optionally attach an admin user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default=getattr(settings, "DEFAULT_ORGANIZATION_NAME", "Organizacion Piloto"),
            help="Pilot organization name.",
        )
        parser.add_argument(
            "--admin-username",
            help="Existing username to assign as organization administrator.",
        )

    def handle(self, *args, **options):
        name = options["name"]
        organization, created = Organization.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created organization: {organization}"))
        else:
            self.stdout.write(f"Organization already exists: {organization}")

        username = options.get("admin_username")
        if username:
            User = get_user_model()
            user = User.objects.get(username=username)
            Membership.objects.update_or_create(
                organization=organization,
                user=user,
                defaults={"role": Membership.Role.ADMIN, "is_active": True},
            )
            self.stdout.write(
                self.style.SUCCESS(f"Assigned ADMIN membership to {username}")
            )
