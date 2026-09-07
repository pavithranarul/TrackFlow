from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from accounts.api.serializers import (
    ChangePasswordSerializer,
    RegisterSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from accounts.selectors.user_selector import get_users
from accounts.services.user_service import (
    change_password,
    register_user,
    update_user,
)


class RegisterAPIView(APIView):
    """POST /api/auth/register/ — create an account and return a token pair.

    Returning tokens straight away saves the client an immediate second round
    trip to /login/.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = register_user(**serializer.validated_data)

        refresh = TokenObtainPairSerializer.get_token(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(TokenObtainPairView):
    """POST /api/auth/login/ — exchange credentials for a token pair."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"


class RefreshAPIView(TokenRefreshView):
    """POST /api/auth/refresh/ — exchange a refresh token for a new pair."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"


class VerifyAPIView(TokenVerifyView):
    """POST /api/auth/verify/ — check whether a token is still valid."""

    permission_classes = [AllowAny]
    authentication_classes = []


class MeAPIView(APIView):
    """GET/PATCH /api/auth/me/ — the authenticated user's own profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        user = update_user(user=request.user, validated_data=serializer.validated_data)

        return Response(UserSerializer(user).data)


class ChangePasswordAPIView(APIView):
    """POST /api/auth/change-password/."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        change_password(
            user=request.user,
            new_password=serializer.validated_data["new_password"],
        )

        # Existing tokens stay valid until they expire; clients should discard
        # them and log in again. Blacklisting is a Phase 5 concern.
        return Response(
            {"detail": "Password changed."},
            status=status.HTTP_200_OK,
        )


class UserListAPIView(ListAPIView):
    """GET /api/auth/users/ — directory used to pick members and assignees.

    Exposes only the public shape, and only active users.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    search_fields = ("username", "first_name", "last_name", "email")
    filterset_fields = ()

    def get_queryset(self):
        return get_users()
