from django.urls import path

from issues.api.views import IssueListCreateAPIView
from projects.api.member_views import (
    ProjectMemberDetailAPIView,
    ProjectMemberListCreateAPIView,
)
from projects.api.views import (
    ProjectDetailAPIView,
    ProjectListCreateAPIView,
)

urlpatterns = [
    path(
        "",
        ProjectListCreateAPIView.as_view(),
        name="project-list-create",
    ),
    path(
        "<int:pk>/",
        ProjectDetailAPIView.as_view(),
        name="project-detail",
    ),
    # Membership
    path(
        "<int:project_id>/members/",
        ProjectMemberListCreateAPIView.as_view(),
        name="project-member-list",
    ),
    path(
        "<int:project_id>/members/<int:pk>/",
        ProjectMemberDetailAPIView.as_view(),
        name="project-member-detail",
    ),
    # Issues scoped to a project
    path(
        "<int:project_id>/issues/",
        IssueListCreateAPIView.as_view(),
        name="project-issue-list",
    ),
]
