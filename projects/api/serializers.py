from rest_framework import serializers

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

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "owner",
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

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "description",
            "owner",
            "status",
            "visibility",
            "members",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Used for POST /api/projects/. Accepts optional extra members."""

    members = ProjectMemberWriteSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "key",
            "description",
            "status",
            "visibility",
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