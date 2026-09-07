from django.conf import settings
from django.db import models


class Organization(models.Model):
    """A tenant. Every project belongs to exactly one.

    Organizations are the outer boundary of the permission system: a user can
    only reach a project if they are a member of the project's organization,
    *and* the project's own rules admit them. The two checks are independent
    and both must pass — see `projects.selectors.project_selector`.

    Only a super admin (`User.is_superuser`) can create or delete one.
    """

    name = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-safe identifier, e.g. 'acme-corp'.",
    )

    description = models.TextField(blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text="Deactivating hides the organization and its projects from "
                  "everyone except super admins, without deleting anything.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrgMember(models.Model):
    """Someone's place in an organization.

    Deliberately only two roles. Fine-grained permissions live at the project
    level (`ProjectMember.Role`); this layer answers one question — may you
    see anything in this organization at all — plus who administers the roster.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MEMBER = "MEMBER", "Member"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="org_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        unique_together = ("organization", "user")

    def __str__(self):
        return f"{self.user} in {self.organization} ({self.role})"
