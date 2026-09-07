from rest_framework.permissions import SAFE_METHODS, BasePermission

from projects.models import Project, ProjectMember
from projects.selectors.project_selector import get_effective_role

# Roles that may create and modify issues. VIEWER is deliberately absent: it is
# a read-only role everywhere in the API.
WRITE_ROLES = (
    ProjectMember.Role.OWNER,
    ProjectMember.Role.MANAGER,
    ProjectMember.Role.DEVELOPER,
)

# Roles that may delete an issue or moderate someone else's comment.
MODERATE_ROLES = (
    ProjectMember.Role.OWNER,
    ProjectMember.Role.MANAGER,
)


def can_write_issues(user, project):
    return get_effective_role(user, project) in WRITE_ROLES


def can_moderate(user, project):
    return get_effective_role(user, project) in MODERATE_ROLES


def can_read_project(user, project):
    """Read access mirrors project visibility exactly."""
    if project.visibility == Project.Visibility.PUBLIC:
        return True

    return get_effective_role(user, project) is not None


class IssuePermission(BasePermission):
    """Object-level rules for an issue.

    Read    — anyone who can see the project. Visibility is already applied by
              the selector feeding `get_object`, so arriving here means the
              issue is visible.
    Write   — OWNER, MANAGER or DEVELOPER.
    Delete  — OWNER or MANAGER, or the person who reported the issue.
    """

    message = "You do not have permission to modify this issue."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if request.method == "DELETE":
            return (
                can_moderate(request.user, obj.project)
                or obj.reporter_id == request.user.id
            )

        return can_write_issues(request.user, obj.project)


class CommentPermission(BasePermission):
    """A comment is editable only by its author. Project owners and managers
    may additionally delete one, so a thread can be moderated."""

    message = "You may only edit your own comments."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if obj.author_id == request.user.id:
            return True

        if request.method == "DELETE":
            return can_moderate(request.user, obj.issue.project)

        return False
