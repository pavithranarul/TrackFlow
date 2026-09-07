from django.db import transaction

from projects.models import ProjectMember


class LastOwnerError(Exception):
    """Raised when an operation would leave a project with no OWNER."""


def _owner_count(project):
    return project.members.filter(role=ProjectMember.Role.OWNER).count()


def _would_orphan_project(*, project, membership):
    """True when changing or removing `membership` removes the last OWNER."""
    if membership.role != ProjectMember.Role.OWNER:
        return False

    return _owner_count(project) <= 1


@transaction.atomic
def add_member(*, project, user, role):
    return ProjectMember.objects.create(project=project, user=user, role=role)


@transaction.atomic
def update_member_role(*, project, membership, role):
    """Change a member's role.

    A project must always retain at least one OWNER, so demoting the last one
    is refused. Promoting someone to OWNER is allowed and simply results in two
    owners — that is how ownership is transferred: promote, then demote.
    """
    if role == membership.role:
        return membership

    if _would_orphan_project(project=project, membership=membership):
        raise LastOwnerError(
            "This is the project's only owner. Promote another member to "
            "OWNER before changing this role."
        )

    membership.role = role
    membership.save(update_fields=["role"])

    return membership


@transaction.atomic
def remove_member(*, project, membership):
    if _would_orphan_project(project=project, membership=membership):
        raise LastOwnerError(
            "This is the project's only owner and cannot be removed. Promote "
            "another member to OWNER first."
        )

    membership.delete()
