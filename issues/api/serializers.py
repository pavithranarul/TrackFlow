from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.api.serializers import UserSerializer
from issues.models import Comment, Issue, IssueActivity

User = get_user_model()


class IssueListSerializer(serializers.ModelSerializer):
    """Lightweight shape for list endpoints — no description, no comments."""

    key = serializers.CharField(read_only=True)
    project_key = serializers.CharField(read_only=True, source="project.key")
    # default=None matters: without it DRF drops the key entirely when
    # the traversal hits a null FK, so clients cannot rely on the field
    # being present.
    reporter = serializers.CharField(
        read_only=True, source="reporter.username", default=None
    )
    # default=None matters: without it DRF drops the key entirely when
    # the traversal hits a null FK, so clients cannot rely on the field
    # being present.
    assignee = serializers.CharField(
        read_only=True, source="assignee.username", default=None
    )

    class Meta:
        model = Issue
        fields = (
            "id",
            "key",
            "project",
            "project_key",
            "title",
            "type",
            "status",
            "priority",
            "reporter",
            "assignee",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "issue",
            "author",
            "body",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "issue", "author", "created_at", "updated_at")


class IssueActivitySerializer(serializers.ModelSerializer):
    # default=None matters: without it DRF drops the key entirely when
    # the traversal hits a null FK, so clients cannot rely on the field
    # being present.
    actor = serializers.CharField(
        read_only=True, source="actor.username", default=None
    )

    class Meta:
        model = IssueActivity
        fields = (
            "id",
            "actor",
            "action",
            "field",
            "old_value",
            "new_value",
            "created_at",
        )
        read_only_fields = fields


class IssueDetailSerializer(serializers.ModelSerializer):
    """Full shape, with nested people, comments and audit trail."""

    key = serializers.CharField(read_only=True)
    project_key = serializers.CharField(read_only=True, source="project.key")
    reporter = UserSerializer(read_only=True)
    assignee = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    activities = IssueActivitySerializer(many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = (
            "id",
            "key",
            "project",
            "project_key",
            "title",
            "description",
            "type",
            "status",
            "priority",
            "reporter",
            "assignee",
            "comments",
            "activities",
            "allowed_transitions",
            "created_at",
            "updated_at",
            "closed_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_allowed_transitions(self, obj):
        """Lets a client render only the status buttons that will succeed."""
        return obj.allowed_next_statuses()


class IssueCreateSerializer(serializers.ModelSerializer):
    """POST. `project`, `reporter` and `number` come from the URL, the request
    user and the service layer respectively, so none are accepted as input."""

    class Meta:
        model = Issue
        fields = (
            "id",
            "title",
            "description",
            "type",
            "status",
            "priority",
            "assignee",
        )
        read_only_fields = ("id",)


class IssueUpdateSerializer(serializers.ModelSerializer):
    """PATCH. Status is excluded on purpose — it has transition rules and goes
    through POST /issues/<id>/transition/ instead."""

    class Meta:
        model = Issue
        fields = (
            "id",
            "title",
            "description",
            "type",
            "priority",
            "assignee",
        )
        read_only_fields = ("id",)


class IssueTransitionSerializer(serializers.Serializer):
    """POST /issues/<id>/transition/."""

    status = serializers.ChoiceField(choices=Issue.Status.choices)


class IssueAssignSerializer(serializers.Serializer):
    """POST /issues/<id>/assign/. A null assignee unassigns the issue.

    The view additionally checks that the chosen user can actually see the
    project; this field only establishes that they exist and are active.
    """

    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        allow_null=True,
    )


class CommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("id", "body")
        read_only_fields = ("id",)
