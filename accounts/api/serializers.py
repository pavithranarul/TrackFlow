from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public shape of a user. Never exposes the password hash.

    `is_superuser` is included and read-only: the UI needs it to decide whether
    to offer platform-level actions such as creating an organization. It is a
    hint for rendering, not a grant — every such endpoint checks the flag again
    server-side.
    """

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_superuser",
        )
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    """POST /api/auth/register/."""

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "The two password fields do not match."}
            )

        attrs.pop("password_confirm")

        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/auth/me/. Username is immutable; it is how members are
    identified across the API."""

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
        )


class ChangePasswordSerializer(serializers.Serializer):
    """POST /api/auth/change-password/."""

    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    def validate_current_password(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")

        return value
