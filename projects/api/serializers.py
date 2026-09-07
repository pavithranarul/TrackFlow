from rest_framework import serializers

from organizations.models import Organization
from projects.models import Project, ProjectMember


class ProjectMemberWriteSerializer(serializers.ModelSerializer):
    """Used only for accepting member input on project creation."""

    class Meta:
        model = ProjectMember
        fields = (
            "user",
            "role",
        )


class ProjectMemberReadSerializer(serializers.ModelSerializer):
    """Used for showing members on project detail."""

    username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = ProjectMember
        fields = (
            "id",
            "user",
            "username",
            "role",
            "joined_at",
        )


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight shape for GET /api/projects/ — no description, no members."""

    owner = serializers.ReadOnlyField(source="owner.username")
    organization_name = serializers.CharField(
        read_only=True, source="organization.name", default=None
    )
    organization_slug = serializers.CharField(
        read_only=True, source="organization.slug", default=None
    )

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "owner",
            "organization",
            "organization_name",
            "organization_slug",
            "status",
            "visibility",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Full shape for GET /api/projects/<id>/ — includes nested members."""

    owner = serializers.ReadOnlyField(source="owner.username")
    members = ProjectMemberReadSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(
        read_only=True, source="organization.name", default=None
    )
    organization_slug = serializers.CharField(
        read_only=True, source="organization.slug", default=None
    )

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "description",
            "owner",
            "organization",
            "organization_name",
            "organization_slug",
            "status",
            "visibility",
            "members",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Used for POST /api/projects/. Accepts optional extra members.

    `organization` is required: a project has to live in a tenant. The view
    checks that the caller actually belongs to the one they named — the field
    only establishes that it exists and is active.
    """

    members = ProjectMemberWriteSerializer(many=True, required=False, write_only=True)

    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True),
    )

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "description",
            "status",
            "visibility",
            "organization",
            "members",
        )
        read_only_fields = ("id",)


class ProjectUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH /api/projects/<id>/. No key changes, no member changes
    here — that belongs to a dedicated members endpoint in Sprint 4."""

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "description",
            "status",
            "visibility",
        )
        read_only_fields = ("id",)


class ProjectMemberCreateSerializer(serializers.ModelSerializer):
    """POST /api/projects/<id>/members/."""

    class Meta:
        model = ProjectMember
        fields = ("id", "user", "role")
        read_only_fields = ("id",)

    def validate(self, attrs):
        project = self.context["project"]

        if ProjectMember.objects.filter(
            project=project, user=attrs["user"]
        ).exists():
            raise serializers.ValidationError(
                {"user": "That user is already a member of this project."}
            )

        return attrs


class ProjectMemberRoleSerializer(serializers.ModelSerializer):
    """PATCH /api/projects/<id>/members/<member_id>/. Only the role is
    mutable — moving a membership to a different user would silently rewrite
    history, so that is a remove plus an add."""

    class Meta:
        model = ProjectMember
        fields = ("id", "role")
        read_only_fields = ("id",)
