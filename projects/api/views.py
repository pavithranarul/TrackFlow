from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.selectors.org_selector import is_org_member
from projects.api.filters import ProjectFilter
from projects.api.permissions import ProjectPermission
from projects.api.serializers import (
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
)
from projects.models import Project
from projects.selectors.project_selector import (
    get_project_for_user,
    get_projects_for_user,
)
from projects.services.project_service import (
    create_project,
    delete_project,
    update_project,
)


class ProjectListCreateAPIView(ListCreateAPIView):

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = Project.objects.none()

    permission_classes = [IsAuthenticated]
    filterset_class = ProjectFilter
    search_fields = ("name", "key", "description")
    ordering_fields = ("created_at", "updated_at", "name", "key")

    def get_queryset(self):
        return get_projects_for_user(self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectCreateSerializer
        return ProjectListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization = serializer.validated_data["organization"]

        # Belonging to the tenant is what entitles you to create in it. Without
        # this check any authenticated user could post a project into any
        # organization whose id they guessed.
        if not is_org_member(request.user, organization):
            raise PermissionDenied(
                "You are not a member of that organization."
            )

        project = create_project(
            owner=request.user,
            organization=organization,
            validated_data=serializer.validated_data,
        )

        return Response(
            ProjectDetailSerializer(project).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, ProjectPermission]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return ProjectUpdateSerializer
        return ProjectDetailSerializer

    def get_object(self):
        project = get_project_for_user(
            self.request.user, self.kwargs["pk"], with_members=True
        )

        # A project the user cannot see is reported as missing rather than
        # forbidden, so PRIVATE projects do not leak their existence.
        if not project:
            raise NotFound("Project not found.")

        self.check_object_permissions(self.request, project)

        return project

    def update(self, request, *args, **kwargs):
        project = self.get_object()

        serializer = self.get_serializer(
            project,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        project = update_project(
            project=project,
            validated_data=serializer.validated_data,
        )

        return Response(ProjectDetailSerializer(project).data)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()

        delete_project(project)

        return Response(status=status.HTTP_204_NO_CONTENT)
