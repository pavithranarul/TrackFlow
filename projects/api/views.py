from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from projects.api.serializers import (
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
)
from projects.selectors.project_selector import (
    get_project,
    get_projects,
)
from projects.services.project_service import (
    create_project,
    update_project,
    delete_project,
)

class ProjectListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_projects()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectCreateSerializer
        return ProjectListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = create_project(
            owner=request.user,
            validated_data=serializer.validated_data,
        )

        return Response(
            ProjectDetailSerializer(project).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return ProjectUpdateSerializer
        return ProjectDetailSerializer

    def get_object(self):
        project = get_project(self.kwargs["pk"])

        if not project:
            from rest_framework.exceptions import NotFound

            raise NotFound("Project not found.")

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