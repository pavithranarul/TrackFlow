from rest_framework.permissions import SAFE_METHODS, BasePermission

from organizations.models import OrgMember
from organizations.selectors.org_selector import get_org_role


class IsSuperAdmin(BasePermission):
    """Platform-level administration: creating and deleting organizations.

    Super admin is Django's `is_superuser`, so `createsuperuser` is all it
    takes to make one and the same account already works in /admin/.
    """

    message = "Only a super admin can do that."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class OrganizationPermission(BasePermission):
    """Object-level rules for /api/organizations/<id>/.

    Read   — any member. Visibility is already applied by the selector feeding
             `get_object`, so arriving here means the org is visible.
    Update — super admin or an org ADMIN.
    Delete — super admin only. It cascades to every project inside.
    """

    message = "You do not have permission to modify this organization."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if request.user.is_superuser:
            return True

        if request.method == "DELETE":
            return False

        return get_org_role(request.user, obj) == OrgMember.Role.ADMIN
