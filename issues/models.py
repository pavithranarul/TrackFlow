from django.conf import settings
from django.db import models

from projects.models import Project


class Issue(models.Model):
    """A unit of work inside a project.

    Identified publicly by ``key`` (``TRK-1``), which is the project's key
    joined to a per-project counter. The counter lives in ``number`` and is
    allocated by ``issue_service.create_issue``; ``unique_together`` below is
    the backstop that makes a double allocation impossible.
    """

    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        TESTING = "TESTING", "Testing"
        DONE = "DONE", "Done"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"
        CRITICAL = "CRITICAL", "Critical"

    class Type(models.TextChoices):
        TASK = "TASK", "Task"
        BUG = "BUG", "Bug"
        FEATURE = "FEATURE", "Feature"
        CHORE = "CHORE", "Chore"

    # Which status changes the service layer will allow. A status may always be
    # set to itself (a no-op transition is not an error).
    ALLOWED_TRANSITIONS = {
        Status.TODO: {Status.IN_PROGRESS},
        Status.IN_PROGRESS: {Status.TODO, Status.TESTING},
        Status.TESTING: {Status.IN_PROGRESS, Status.DONE},
        Status.DONE: {Status.IN_PROGRESS},
    }

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="issues",
    )

    number = models.PositiveIntegerField(
        help_text="Per-project counter. Combined with the project key to form "
                  "the human-readable issue key.",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.TASK,
    )

    # SET_NULL rather than CASCADE: a tracker must not lose the record of work
    # because the person who filed it was deleted. The issue survives with an
    # empty reporter, the same way `assignee` and `IssueActivity.actor` do.
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reported_issues",
        null=True,
        blank=True,
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_issues",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the issue enters DONE, cleared when it leaves.",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("project", "number")
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assignee"]),
        ]

    def __str__(self):
        return f"{self.key} {self.title}"

    @property
    def key(self):
        return f"{self.project.key}-{self.number}"

    def allowed_next_statuses(self):
        """Plain strings, not enum members, so they are safe to put straight
        into an API response or an error message."""
        return sorted(str(s) for s in self.ALLOWED_TRANSITIONS.get(self.status, set()))

    def can_transition_to(self, new_status):
        if new_status == self.status:
            return True

        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())


class Comment(models.Model):
    """A comment on an issue. Editable only by its author."""

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    # Deleting a person must not silently rewrite a discussion thread, so the
    # comment outlives its author with an empty `author`.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="comments",
        null=True,
        blank=True,
    )

    body = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.issue.key}"


class IssueActivity(models.Model):
    """Append-only audit trail for an issue.

    Rows are written by the service layer, never by views or serializers, so
    that every path that mutates an issue is recorded. Nothing updates or
    deletes a row once written.
    """

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        ASSIGNED = "ASSIGNED", "Assigned"
        UNASSIGNED = "UNASSIGNED", "Unassigned"
        PRIORITY_CHANGED = "PRIORITY_CHANGED", "Priority changed"
        UPDATED = "UPDATED", "Updated"
        COMMENTED = "COMMENTED", "Commented"

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="activities",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issue_activities",
        null=True,
    )

    action = models.CharField(
        max_length=30,
        choices=Action.choices,
    )

    field = models.CharField(max_length=50, blank=True)

    old_value = models.CharField(max_length=200, blank=True)

    new_value = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "issue activities"

    def __str__(self):
        return f"{self.action} on {self.issue_id} by {self.actor}"
