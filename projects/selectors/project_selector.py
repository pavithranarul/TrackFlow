from django.db.models import Q

from projects.models import Project


def _visible_to(user):
    """Q object describing which projects `user` is allowed to see.

    Two independent gates, both of which must pass:

      1. Tenant — the project's organization must be active and the user must
         be a member of it. Nothing crosses an organization boundary, not even
         a PUBLIC project: "public" means public *within its organization*.
      2. Project — the user must be a member of the project, own it, or the
         project must be PUBLIC.

    Ownership is checked explicitly alongside membership because a project
    created straight through the admin has no ProjectMember row, and an owner
    must never lose sight of their own project.
    """
    in_tenant = Q(organization__members__user=user) & Q(organization__is_active=True)

    in_project = (
        Q(members__user=user)
        | Q(owner=user)
        | Q(visibility=Project.Visibility.PUBLIC)
    )

    return in_tenant & in_project


def _base(user):
    """Every project the user can see, before any further filtering.

    A super admin bypasses the tenant gate. They already have full database
    access through the Django admin, so withholding rows here would be theatre
    rather than security — and they are the account that has to be able to
    diagnose any organization.
    """
    if user.is_superuser:
        return Project.objects.all()

    return Project.objects.filter(_visible_to(user))


def get_projects():
    """Every project, unscoped and across all tenants. Admin, migrations and
    reporting only — never serve this directly from an API view."""
    return Project.objects.all()


def get_project(project_id):
    """A single project, unscoped. Prefer `get_project_for_user`."""
    return Project.objects.filter(id=project_id).first()


def get_projects_for_user(user):
    """Projects `user` may list, newest first."""
    return _base(user).select_related("owner", "organization").distinct()


def get_projects_in_organization(user, organization):
    return get_projects_for_user(user).filter(organization=organization)


def get_project_for_user(user, project_id, *, with_members=False):
    """A single project, or None when `user` may not see it.

    Returning None for an invisible project lets the view raise 404 rather
    than 403, so neither a private project nor another tenant's project leaks
    its existence.

    `with_members` is opt-in because most callers only need to know that the
    project exists and is visible. Only ProjectDetailSerializer nests the
    member list, and prefetching it for everyone else costs two wasted queries
    per request.
    """
    queryset = (
        _base(user)
        .filter(id=project_id)
        .select_related("owner", "organization")
    )

    if with_members:
        queryset = queryset.prefetch_related("members__user")

    return queryset.distinct().first()


def get_membership(user, project):
    """The user's ProjectMember row for `project`, or None."""
    return project.members.filter(user=user).first()


def get_effective_role(user, project):
    """The role `user` holds on `project`, or None if they hold none.

    The project owner is reported as OWNER whether or not a ProjectMember row
    exists, which keeps a project created through the admin manageable. A
    super admin is reported as OWNER on every project, matching the access
    they already hold through the Django admin.

    This is the single place role is resolved, so the projects and issues apps
    cannot drift apart on what a role means.
    """
    from projects.models import ProjectMember

    if user.is_superuser or project.owner_id == user.id:
        return ProjectMember.Role.OWNER

    membership = get_membership(user, project)

    return membership.role if membership else None
