from rest_framework.permissions import SAFE_METHODS, BasePermission

from projects.models import ProjectMember
from projects.selectors.project_selector import get_membership

# Roles allowed to change a project's own fields.
WRITE_ROLES = (
    ProjectMember.Role.OWNER,
    ProjectMember.Role.MANAGER,
)


class ProjectPermission(BasePermission):
    """Object-level rules for /api/projects/<id>/.

    Read    — anyone who can see the project. Visibility is already enforced
              by the selector feeding `get_object`, so reaching this check at
              all means the project is visible.
    Update  — OWNER or MANAGER.
    Delete  — OWNER only. Deleting cascades to every member and (later) every
              issue, so it stays with the owner alone.

    The project owner passes every check even without a ProjectMember row, so
    a project created through the admin is still manageable by its owner.
    """

    message = "You do not have permission to modify this project."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if obj.owner_id == request.user.id:
            return True

        if request.method == "DELETE":
            # Only the owner may delete, and that was handled above.
            return False

        membership = get_membership(request.user, obj)

        return membership is not None and membership.role in WRITE_ROLES
