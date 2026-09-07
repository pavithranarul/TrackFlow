from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from issues.api.filters import IssueFilter
from issues.api.permissions import (
    CommentPermission,
    IssuePermission,
    can_read_project,
    can_write_issues,
)
from issues.api.serializers import (
    CommentSerializer,
    CommentWriteSerializer,
    IssueActivitySerializer,
    IssueAssignSerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    IssueTransitionSerializer,
    IssueUpdateSerializer,
)
from issues.models import Comment, Issue, IssueActivity
from issues.selectors.issue_selector import (
    get_activities_for_issue,
    get_comment_for_user,
    get_comments_for_issue,
    get_issue_for_user,
    get_issues_for_project,
    get_issues_for_user,
)
from issues.services.issue_service import (
    TransitionNotAllowed,
    assign_issue,
    create_comment,
    create_issue,
    delete_comment,
    delete_issue,
    transition_issue,
    update_comment,
    update_issue,
)
from projects.selectors.project_selector import get_project_for_user

SEARCH_FIELDS = ("title", "description")
ORDERING_FIELDS = ("created_at", "updated_at", "priority", "status", "number")


class IssueListCreateAPIView(ListCreateAPIView):
    """GET/POST /api/projects/<project_id>/issues/ — issues within one project."""

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = Issue.objects.none()

    permission_classes = [IsAuthenticated]
    filterset_class = IssueFilter
    search_fields = SEARCH_FIELDS
    ordering_fields = ORDERING_FIELDS

    def get_project(self):
        """Resolve and cache the project for this request.

        Both get_queryset() and create() need it, and without the cache the
        visibility lookup would run twice per request.
        """
        if not hasattr(self, "_project"):
            project = get_project_for_user(
                self.request.user, self.kwargs["project_id"]
            )

            if not project:
                raise NotFound("Project not found.")

            self._project = project

        return self._project

    def get_queryset(self):
        return get_issues_for_project(self.request.user, self.get_project())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return IssueCreateSerializer
        return IssueListSerializer

    def create(self, request, *args, **kwargs):
        project = self.get_project()

        if not can_write_issues(request.user, project):
            raise PermissionDenied(
                "You need to be a developer, manager or owner of this project "
                "to create issues in it."
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        issue = create_issue(
            project=project,
            reporter=request.user,
            validated_data=serializer.validated_data,
        )

        return Response(
            IssueDetailSerializer(issue).data,
            status=status.HTTP_201_CREATED,
        )


class IssueGlobalListAPIView(ListAPIView):
    """GET /api/issues/ — every issue the caller can see, across all projects.

    This is what powers a personal "my issues" view, e.g.
    ``/api/issues/?assignee_username=me&status=TODO``.
    """

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = Issue.objects.none()

    permission_classes = [IsAuthenticated]
    serializer_class = IssueListSerializer
    filterset_class = IssueFilter
    search_fields = SEARCH_FIELDS
    ordering_fields = ORDERING_FIELDS

    def get_queryset(self):
        return get_issues_for_user(self.request.user)


class IssueDetailAPIView(APIView):
    """GET/PATCH/DELETE /api/issues/<id>/."""

    permission_classes = [IsAuthenticated, IssuePermission]
    serializer_class = IssueDetailSerializer

    def get_object(self):
        issue = get_issue_for_user(self.request.user, self.kwargs["pk"])

        # An issue in an invisible project is reported as missing rather than
        # forbidden, matching the behaviour of the project endpoints.
        if not issue:
            raise NotFound("Issue not found.")

        self.check_object_permissions(self.request, issue)

        return issue

    def get(self, request, pk):
        issue = self.get_object()

        return Response(IssueDetailSerializer(issue).data)

    def patch(self, request, pk):
        issue = self.get_object()

        serializer = IssueUpdateSerializer(issue, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        issue = update_issue(
            issue=issue,
            actor=request.user,
            validated_data=serializer.validated_data,
        )

        return Response(IssueDetailSerializer(issue).data)

    def delete(self, request, pk):
        issue = self.get_object()

        delete_issue(issue)

        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTransitionAPIView(APIView):
    """POST /api/issues/<id>/transition/ — change status, rules enforced."""

    permission_classes = [IsAuthenticated, IssuePermission]
    serializer_class = IssueTransitionSerializer

    def get_object(self):
        issue = get_issue_for_user(self.request.user, self.kwargs["pk"])

        if not issue:
            raise NotFound("Issue not found.")

        self.check_object_permissions(self.request, issue)

        return issue

    def post(self, request, pk):
        issue = self.get_object()

        serializer = IssueTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            issue = transition_issue(
                issue=issue,
                actor=request.user,
                new_status=serializer.validated_data["status"],
            )
        except TransitionNotAllowed as exc:
            # A disallowed transition is bad input, not a server fault.
            raise ValidationError({"status": [str(exc)]}) from exc

        return Response(IssueDetailSerializer(issue).data)


class IssueAssignAPIView(APIView):
    """POST /api/issues/<id>/assign/ — set or clear the assignee."""

    permission_classes = [IsAuthenticated, IssuePermission]
    serializer_class = IssueAssignSerializer

    def get_object(self):
        issue = get_issue_for_user(self.request.user, self.kwargs["pk"])

        if not issue:
            raise NotFound("Issue not found.")

        self.check_object_permissions(self.request, issue)

        return issue

    def post(self, request, pk):
        issue = self.get_object()

        serializer = IssueAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignee = serializer.validated_data["assignee"]

        if assignee is not None and not can_read_project(assignee, issue.project):
            raise ValidationError(
                {"assignee": ["That user is not a member of this project."]}
            )

        issue = assign_issue(issue=issue, actor=request.user, assignee=assignee)

        return Response(IssueDetailSerializer(issue).data)


class IssueActivityListAPIView(ListAPIView):
    """GET /api/issues/<id>/activity/ — the audit trail for one issue."""

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = IssueActivity.objects.none()

    permission_classes = [IsAuthenticated]
    serializer_class = IssueActivitySerializer

    def get_queryset(self):
        issue = get_issue_for_user(self.request.user, self.kwargs["pk"])

        if not issue:
            raise NotFound("Issue not found.")

        return get_activities_for_issue(issue)


class CommentListCreateAPIView(ListCreateAPIView):
    """GET/POST /api/issues/<id>/comments/."""

    # Sentinel for schema generation only; the real rows come from
    # get_queryset(), which needs an authenticated request.
    queryset = Comment.objects.none()

    permission_classes = [IsAuthenticated]

    def get_issue(self):
        issue = get_issue_for_user(self.request.user, self.kwargs["pk"])

        if not issue:
            raise NotFound("Issue not found.")

        return issue

    def get_queryset(self):
        return get_comments_for_issue(self.get_issue())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommentWriteSerializer
        return CommentSerializer

    def create(self, request, *args, **kwargs):
        issue = self.get_issue()

        if not can_write_issues(request.user, issue.project):
            raise PermissionDenied(
                "You need to be a developer, manager or owner of this project "
                "to comment on its issues."
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = create_comment(
            issue=issue,
            author=request.user,
            body=serializer.validated_data["body"],
        )

        return Response(
            CommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailAPIView(APIView):
    """GET/PATCH/DELETE /api/comments/<id>/."""

    permission_classes = [IsAuthenticated, CommentPermission]
    serializer_class = CommentSerializer

    def get_object(self):
        comment = get_comment_for_user(self.request.user, self.kwargs["pk"])

        if not comment:
            raise NotFound("Comment not found.")

        self.check_object_permissions(self.request, comment)

        return comment

    def get(self, request, pk):
        return Response(CommentSerializer(self.get_object()).data)

    def patch(self, request, pk):
        comment = self.get_object()

        serializer = CommentWriteSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        comment = update_comment(
            comment=comment,
            body=serializer.validated_data["body"],
        )

        return Response(CommentSerializer(comment).data)

    def delete(self, request, pk):
        comment = self.get_object()

        delete_comment(comment)

        return Response(status=status.HTTP_204_NO_CONTENT)
