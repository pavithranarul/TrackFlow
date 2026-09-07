"""Put every project inside an organization.

`Project.organization` is not nullable, but existing rows have no organization
to point at. Adding the column outright would either fail or silently invent a
value, so this runs in three steps: add it nullable, backfill, then tighten.

The backfill puts every pre-existing project into one organization named
"Default Organization" and gives every existing user membership of it, so an
installation that predates this change keeps working exactly as it did. If
there is nothing to migrate, no organization is created.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

DEFAULT_SLUG = "default"

HELP = (
    "The tenant this project belongs to. Nobody outside the organization can "
    "reach it, whatever its visibility."
)


def backfill(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Organization = apps.get_model("organizations", "Organization")
    OrgMember = apps.get_model("organizations", "OrgMember")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    orphans = Project.objects.filter(organization__isnull=True)

    if not orphans.exists():
        return

    organization, _ = Organization.objects.get_or_create(
        slug=DEFAULT_SLUG,
        defaults={
            "name": "Default Organization",
            "description": "Created automatically to hold projects that "
                           "predate organizations.",
        },
    )

    orphans.update(organization=organization)

    # Everyone who already had access keeps it: without a membership row the
    # new outer tenant check would lock people out of their own projects the
    # moment this migration lands.
    for user in User.objects.all():
        OrgMember.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={"role": "ADMIN" if user.is_superuser else "MEMBER"},
        )


def unbackfill(apps, schema_editor):
    """Reverse: detach the projects again. The organization row itself is left
    in place, because by then it may hold projects that were never orphans."""
    Project = apps.get_model("projects", "Project")
    Organization = apps.get_model("organizations", "Organization")

    default = Organization.objects.filter(slug=DEFAULT_SLUG).first()

    if default:
        Project.objects.filter(organization=default).update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0008_project_issue_counter"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="projects",
                to="organizations.organization",
                help_text=HELP,
            ),
        ),
        migrations.RunPython(backfill, unbackfill),
        migrations.AlterField(
            model_name="project",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="projects",
                to="organizations.organization",
                help_text=HELP,
            ),
        ),
    ]
