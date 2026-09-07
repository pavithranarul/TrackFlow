from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.api.serializers import (
    ProjectMemberCreateSerializer,
    ProjectMemberReadSerializer,
    ProjectMemberRoleSerializer,
)
from projects.models import ProjectMember
from projects.selectors.member_selector import (
    get_member,
    get_members_for_project,
)
from projects.selectors.project_selector import (
    get_effective_role,
    get_project_for_user,
)
from projects.services.member_service import (
    LastOwnerError,
    add_member,
    remove_member,
    update_member_role,
)

MANAGE_ROLES = (
    ProjectMember.Role.OWNER,
    ProjectMember.Role.MANAGER,
)


class ProjectMemberMixin:
    permission_classes = [IsAuthenticated]

    def get_project(self):
        """Resolve and cache the project for this request; several hooks on
        these views need it and would otherwise each re-run the lookup."""
        if not hasattr(self, "_project"):
            project = get_project_for_user(
                self.request.user, self.kwargs["project_id"]
            )

            if not project:
                raise NotFound("Project not found.")

            self._project = project

        return self._project

    def require_manage(self, project):
        """Membership changes are limited to owners and managers.

        Returns the caller's role so that callers can apply the stricter rule
        for handing out OWNER.
        """
        role = get_effective_role(self.request.user, project)

        if role not in MANAGE_ROLES:
            raise PermissionDenied(
                "Only a project owner or manager can change its membership."
            )

        return role


class ProjectMemberListCreateAPIView(ProjectMemberMixin, ListCreateAPIView):
    """GET/POST /api/projects/<project_id>/members/."""

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = ProjectMember.objects.none()

    def get_queryset(self):
        return get_members_for_project(self.get_project())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectMemberCreateSerializer
        return ProjectMemberReadSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        actor_role = self.require_manage(project)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data["role"]

        # A manager must not be able to promote someone (or themselves, via a
        # second account) to a role above their own.
        if role == ProjectMember.Role.OWNER and actor_role != ProjectMember.Role.OWNER:
            raise PermissionDenied("Only an owner can grant the OWNER role.")

        membership = add_member(
            project=project,
            user=serializer.validated_data["user"],
            role=role,
        )

        return Response(
            ProjectMemberReadSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectMemberDetailAPIView(ProjectMemberMixin, APIView):
    """PATCH/DELETE /api/projects/<project_id>/members/<pk>/."""

    serializer_class = ProjectMemberRoleSerializer

    def get_membership(self, project):
        membership = get_member(project, self.kwargs["pk"])

        if not membership:
            raise NotFound("Membership not found.")

        return membership

    def patch(self, request, project_id, pk):
        project = self.get_project()
        actor_role = self.require_manage(project)
        membership = self.get_membership(project)

        serializer = ProjectMemberRoleSerializer(
            membership, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data["role"]

        if actor_role != ProjectMember.Role.OWNER and (
            role == ProjectMember.Role.OWNER
            or membership.role == ProjectMember.Role.OWNER
        ):
            raise PermissionDenied(
                "Only an owner can grant or revoke the OWNER role."
            )

        try:
            membership = update_member_role(
                project=project, membership=membership, role=role
            )
        except LastOwnerError as exc:
            raise ValidationError({"role": [str(exc)]}) from exc

        return Response(ProjectMemberReadSerializer(membership).data)

    def delete(self, request, project_id, pk):
        project = self.get_project()
        actor_role = self.require_manage(project)
        membership = self.get_membership(project)

        if (
            membership.role == ProjectMember.Role.OWNER
            and actor_role != ProjectMember.Role.OWNER
        ):
            raise PermissionDenied("Only an owner can remove another owner.")

        try:
            remove_member(project=project, membership=membership)
        except LastOwnerError as exc:
            raise ValidationError({"detail": [str(exc)]}) from exc

        return Response(status=status.HTTP_204_NO_CONTENT)
