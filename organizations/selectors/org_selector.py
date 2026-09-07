from organizations.models import Organization, OrgMember


def get_organizations_for_user(user):
    """Organizations the user may see.

    A super admin sees every organization — they already have full database
    access through the Django admin, so hiding rows from them in the API would
    be theatre rather than security.
    """
    if user.is_superuser:
        return Organization.objects.all()

    return Organization.objects.filter(
        members__user=user,
        is_active=True,
    ).distinct()


def get_organization_for_user(user, org_id):
    return get_organizations_for_user(user).filter(id=org_id).first()


def get_org_members(organization):
    return (
        OrgMember.objects.filter(organization=organization)
        .select_related("user", "organization")
        .order_by("joined_at")
    )


def get_org_member(organization, member_id):
    return get_org_members(organization).filter(id=member_id).first()


def get_org_role(user, organization):
    """The user's role in `organization`, or None.

    Super admins are reported as ADMIN everywhere, which is what makes them
    able to administer any organization's roster.
    """
    if user.is_superuser:
        return OrgMember.Role.ADMIN

    membership = OrgMember.objects.filter(
        organization=organization, user=user
    ).first()

    return membership.role if membership else None


def is_org_member(user, organization):
    return get_org_role(user, organization) is not None
