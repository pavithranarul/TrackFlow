from django.db import transaction

from organizations.models import Organization, OrgMember


class LastAdminError(Exception):
    """Raised when an operation would leave an organization with no ADMIN."""


@transaction.atomic
def create_organization(*, validated_data, first_admin=None):
    """Create an organization and, optionally, seed its first admin.

    Seeding an admin at creation time is what lets a super admin hand the
    organization over immediately rather than staying in the loop for every
    later membership change.
    """
    members = validated_data.pop("members", [])

    organization = Organization.objects.create(**validated_data)

    if first_admin is not None:
        OrgMember.objects.create(
            organization=organization,
            user=first_admin,
            role=OrgMember.Role.ADMIN,
        )

    for member in members:
        if first_admin is not None and member["user"] == first_admin:
            continue

        OrgMember.objects.create(
            organization=organization,
            user=member["user"],
            role=member.get("role", OrgMember.Role.MEMBER),
        )

    return organization


@transaction.atomic
def update_organization(*, organization, validated_data):
    validated_data.pop("members", None)

    for field, value in validated_data.items():
        setattr(organization, field, value)

    organization.save()

    return organization


@transaction.atomic
def delete_organization(organization):
    """Deleting cascades to every project, issue and comment inside it.

    Deactivating (`is_active=False`) is the reversible alternative and is what
    should normally be used.
    """
    organization.delete()


def _admin_count(organization):
    return organization.members.filter(role=OrgMember.Role.ADMIN).count()


def _would_orphan(*, organization, membership):
    if membership.role != OrgMember.Role.ADMIN:
        return False

    return _admin_count(organization) <= 1


@transaction.atomic
def add_org_member(*, organization, user, role):
    return OrgMember.objects.create(
        organization=organization,
        user=user,
        role=role,
    )


@transaction.atomic
def update_org_member_role(*, organization, membership, role):
    if role == membership.role:
        return membership

    if _would_orphan(organization=organization, membership=membership):
        raise LastAdminError(
            "This is the organization's only admin. Promote another member to "
            "ADMIN before changing this role."
        )

    membership.role = role
    membership.save(update_fields=["role"])

    return membership


@transaction.atomic
def remove_org_member(*, organization, membership):
    """Remove someone from an organization.

    Their project memberships inside it go too — otherwise they would keep a
    ProjectMember row granting access to a project they can no longer reach,
    which would come back as an inconsistency the moment they were re-added.
    """
    from projects.models import ProjectMember

    if _would_orphan(organization=organization, membership=membership):
        raise LastAdminError(
            "This is the organization's only admin and cannot be removed. "
            "Promote another member to ADMIN first."
        )

    ProjectMember.objects.filter(
        user=membership.user,
        project__organization=organization,
    ).delete()

    membership.delete()
