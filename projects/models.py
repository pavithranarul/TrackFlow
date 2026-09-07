from django.conf import settings
from django.db import models


class Project(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    class Visibility(models.TextChoices):
        PRIVATE = "PRIVATE", "Private"
        PUBLIC = "PUBLIC", "Public"

    name = models.CharField(max_length=200)

    key = models.CharField(
        max_length=10,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
        help_text="The tenant this project belongs to. Nobody outside the "
                  "organization can reach it, whatever its visibility.",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )

    issue_counter = models.PositiveIntegerField(
        default=0,
        help_text="Highest issue number handed out for this project. Bumped "
                  "with an atomic F() update so two concurrent creates can "
                  "never be given the same number.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectMember(models.Model):

    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Manager"
        DEVELOPER = "DEVELOPER", "Developer"
        VIEWER = "VIEWER", "Viewer"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        unique_together = (
            "project",
            "user",
        )

    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.role})"