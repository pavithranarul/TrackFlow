"""Shared test helpers for the tenant layer.

Every project now needs an organization, and every user needs membership of
that organization before they can see anything in it. Rather than repeat that
setup in each test class, tests build their world through these helpers.
"""

from django.contrib.auth import get_user_model

from organizations.models import Organization, OrgMember

User = get_user_model()


def make_org(slug="test-org", name=None, **kwargs):
    return Organization.objects.create(
        name=name or slug.replace("-", " ").title(),
        slug=slug,
        **kwargs,
    )


def make_user(username, *, org=None, role=OrgMember.Role.MEMBER, **kwargs):
    """Create a user and, when an organization is given, put them in it."""
    user = User.objects.create_user(
        username=username,
        password="pw-12345678!",
        **kwargs,
    )

    if org is not None:
        OrgMember.objects.create(organization=org, user=user, role=role)

    return user


def make_superuser(username="root"):
    return User.objects.create_superuser(username=username, password="pw-12345678!")


def join(org, user, role=OrgMember.Role.MEMBER):
    return OrgMember.objects.create(organization=org, user=user, role=role)
