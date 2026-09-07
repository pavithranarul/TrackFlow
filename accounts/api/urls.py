from django.urls import path

from accounts.api.views import (
    ChangePasswordAPIView,
    LoginAPIView,
    MeAPIView,
    RefreshAPIView,
    RegisterAPIView,
    UserListAPIView,
    VerifyAPIView,
)

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="auth-register"),
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("refresh/", RefreshAPIView.as_view(), name="auth-refresh"),
    path("verify/", VerifyAPIView.as_view(), name="auth-verify"),
    path("me/", MeAPIView.as_view(), name="auth-me"),
    path(
        "change-password/",
        ChangePasswordAPIView.as_view(),
        name="auth-change-password",
    ),
    path("users/", UserListAPIView.as_view(), name="auth-user-list"),
]
