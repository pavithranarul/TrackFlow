from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import Organization, OrgMember

User = get_user_model()


class OrgMemberWriteSerializer(serializers.ModelSerializer):
    """Accepts members inline when an organization is created."""

    class Meta:
        model = OrgMember
        fields = ("user", "role")


class OrgMemberReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True, source="user.username", default=None)
    email = serializers.CharField(read_only=True, source="user.email", default=None)

    class Meta:
        model = OrgMember
        fields = ("id", "user", "username", "email", "role", "joined_at")
        read_only_fields = fields


class OrganizationListSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    project_count = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "member_count",
            "project_count",
            "my_role",
            "created_at",
        )
        read_only_fields = fields

    def get_my_role(self, obj) -> str | None:
        from organizations.selectors.org_selector import get_org_role

        request = self.context.get("request")
        if not request:
            return None

        return get_org_role(request.user, obj)


class OrganizationDetailSerializer(OrganizationListSerializer):
    members = OrgMemberReadSerializer(many=True, read_only=True)

    class Meta(OrganizationListSerializer.Meta):
        fields = OrganizationListSerializer.Meta.fields + ("description", "members", "updated_at")
        read_only_fields = fields


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """POST /api/organizations/ — super admin only.

    `admin` names the person who will run the organization. Leaving it out
    makes the creating super admin its first admin, so an organization is
    never created without one.
    """

    members = OrgMemberWriteSerializer(many=True, required=False, write_only=True)

    admin = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "description", "is_active", "admin", "members")
        read_only_fields = ("id",)


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """PATCH. `slug` is immutable — it identifies the tenant in URLs and logs.
    Membership changes go through the members endpoints."""

    class Meta:
        model = Organization
        fields = ("id", "name", "description", "is_active")
        read_only_fields = ("id",)


class OrgMemberCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgMember
        fields = ("id", "user", "role")
        read_only_fields = ("id",)

    def validate(self, attrs):
        organization = self.context["organization"]

        if OrgMember.objects.filter(
            organization=organization, user=attrs["user"]
        ).exists():
            raise serializers.ValidationError(
                {"user": ["That user is already a member of this organization."]}
            )

        return attrs


class OrgMemberRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgMember
        fields = ("id", "role")
        read_only_fields = ("id",)
