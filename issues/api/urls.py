from django.urls import path

from issues.api.views import (
    CommentDetailAPIView,
    CommentListCreateAPIView,
    IssueActivityListAPIView,
    IssueAssignAPIView,
    IssueDetailAPIView,
    IssueGlobalListAPIView,
    IssueTransitionAPIView,
)

urlpatterns = [
    path("issues/", IssueGlobalListAPIView.as_view(), name="issue-list"),
    path("issues/<int:pk>/", IssueDetailAPIView.as_view(), name="issue-detail"),
    path(
        "issues/<int:pk>/transition/",
        IssueTransitionAPIView.as_view(),
        name="issue-transition",
    ),
    path("issues/<int:pk>/assign/", IssueAssignAPIView.as_view(), name="issue-assign"),
    path(
        "issues/<int:pk>/activity/",
        IssueActivityListAPIView.as_view(),
        name="issue-activity",
    ),
    path(
        "issues/<int:pk>/comments/",
        CommentListCreateAPIView.as_view(),
        name="issue-comment-list",
    ),
    path("comments/<int:pk>/", CommentDetailAPIView.as_view(), name="comment-detail"),
]
