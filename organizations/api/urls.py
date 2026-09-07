from django.urls import path

from organizations.api.views import (
    OrganizationDetailAPIView,
    OrganizationListCreateAPIView,
    OrgMemberDetailAPIView,
    OrgMemberListCreateAPIView,
)

urlpatterns = [
    path("", OrganizationListCreateAPIView.as_view(), name="organization-list"),
    path("<int:pk>/", OrganizationDetailAPIView.as_view(), name="organization-detail"),
    path(
        "<int:org_id>/members/",
        OrgMemberListCreateAPIView.as_view(),
        name="org-member-list",
    ),
    path(
        "<int:org_id>/members/<int:pk>/",
        OrgMemberDetailAPIView.as_view(),
        name="org-member-detail",
    ),
]
