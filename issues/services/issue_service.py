from django.db import transaction
from django.db.models import F
from django.utils import timezone

from issues.models import Comment, Issue, IssueActivity
from projects.models import Project


class TransitionNotAllowed(Exception):
    """Raised when a status change is not permitted from the current status."""


def _log(*, issue, actor, action, field="", old_value="", new_value=""):
    """Append one row to the audit trail.

    Values are stringified and truncated to the column width so that logging
    can never be the thing that fails a write.
    """
    return IssueActivity.objects.create(
        issue=issue,
        actor=actor,
        action=action,
        field=field[:50],
        old_value=str(old_value or "")[:200],
        new_value=str(new_value or "")[:200],
    )


def _allocate_number(project):
    """Hand out the next issue number for a project.

    The increment happens in the database with an F() expression rather than
    in Python, so two concurrent creates cannot read the same value and collide
    on the (project, number) unique constraint.
    """
    Project.objects.filter(pk=project.pk).update(
        issue_counter=F("issue_counter") + 1
    )

    return Project.objects.values_list("issue_counter", flat=True).get(pk=project.pk)


@transaction.atomic
def create_issue(*, project, reporter, validated_data):
    issue = Issue.objects.create(
        project=project,
        reporter=reporter,
        number=_allocate_number(project),
        **validated_data,
    )

    if issue.status == Issue.Status.DONE:
        issue.closed_at = timezone.now()
        issue.save(update_fields=["closed_at"])

    _log(
        issue=issue,
        actor=reporter,
        action=IssueActivity.Action.CREATED,
        new_value=issue.title,
    )

    if issue.assignee_id:
        _log(
            issue=issue,
            actor=reporter,
            action=IssueActivity.Action.ASSIGNED,
            field="assignee",
            new_value=issue.assignee.username,
        )

    return issue


@transaction.atomic
def update_issue(*, issue, actor, validated_data):
    """Apply a partial update, logging each meaningful field change.

    Status is deliberately rejected here: it has transition rules, so it goes
    through `transition_issue` instead.
    """
    validated_data.pop("status", None)

    tracked = {
        "assignee": IssueActivity.Action.ASSIGNED,
        "priority": IssueActivity.Action.PRIORITY_CHANGED,
    }

    for field, value in validated_data.items():
        old = getattr(issue, field)

        if old == value:
            continue

        setattr(issue, field, value)

        if field in tracked:
            if field == "assignee" and value is None:
                _log(
                    issue=issue,
                    actor=actor,
                    action=IssueActivity.Action.UNASSIGNED,
                    field="assignee",
                    old_value=getattr(old, "username", ""),
                )
            else:
                _log(
                    issue=issue,
                    actor=actor,
                    action=tracked[field],
                    field=field,
                    old_value=getattr(old, "username", old),
                    new_value=getattr(value, "username", value),
                )
        else:
            _log(
                issue=issue,
                actor=actor,
                action=IssueActivity.Action.UPDATED,
                field=field,
                old_value=old,
                new_value=value,
            )

    issue.save()

    return issue


@transaction.atomic
def transition_issue(*, issue, actor, new_status):
    """Move an issue to a new status, enforcing the transition graph.

    `closed_at` is maintained here rather than in a signal so that the whole
    state change — timestamp, audit row, saved row — is one transaction.
    """
    if not issue.can_transition_to(new_status):
        allowed = sorted(
            str(s) for s in issue.ALLOWED_TRANSITIONS.get(issue.status, set())
        )

        raise TransitionNotAllowed(
            f"Cannot move an issue from {issue.status} to {new_status}. "
            f"Allowed from {issue.status}: {allowed or 'nothing'}."
        )

    old_status = issue.status

    if new_status == old_status:
        return issue

    issue.status = new_status

    if new_status == Issue.Status.DONE:
        issue.closed_at = timezone.now()
    elif old_status == Issue.Status.DONE:
        issue.closed_at = None

    issue.save(update_fields=["status", "closed_at", "updated_at"])

    _log(
        issue=issue,
        actor=actor,
        action=IssueActivity.Action.STATUS_CHANGED,
        field="status",
        old_value=old_status,
        new_value=new_status,
    )

    return issue


@transaction.atomic
def assign_issue(*, issue, actor, assignee):
    """Set or clear an issue's assignee."""
    old = issue.assignee

    if old == assignee:
        return issue

    issue.assignee = assignee
    issue.save(update_fields=["assignee", "updated_at"])

    if assignee is None:
        _log(
            issue=issue,
            actor=actor,
            action=IssueActivity.Action.UNASSIGNED,
            field="assignee",
            old_value=getattr(old, "username", ""),
        )
    else:
        _log(
            issue=issue,
            actor=actor,
            action=IssueActivity.Action.ASSIGNED,
            field="assignee",
            old_value=getattr(old, "username", ""),
            new_value=assignee.username,
        )

    return issue


@transaction.atomic
def delete_issue(issue):
    issue.delete()


@transaction.atomic
def create_comment(*, issue, author, body):
    comment = Comment.objects.create(issue=issue, author=author, body=body)

    _log(
        issue=issue,
        actor=author,
        action=IssueActivity.Action.COMMENTED,
        new_value=body,
    )

    return comment


@transaction.atomic
def update_comment(*, comment, body):
    comment.body = body
    comment.save(update_fields=["body", "updated_at"])

    return comment


@transaction.atomic
def delete_comment(comment):
    comment.delete()
