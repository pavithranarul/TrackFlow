"""Root URL configuration for TrackFlow.

    /admin/                     Django admin
    /api/auth/                  registration, JWT tokens, profile
    /api/organizations/         tenants and their rosters (super admin creates)
    /api/projects/              projects, their members and their issues
    /api/issues/, /api/comments/  issues and comments addressed directly
    /api/schema/                OpenAPI schema, Swagger UI, ReDoc
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/auth/", include("accounts.api.urls")),
    path("api/organizations/", include("organizations.api.urls")),
    path("api/projects/", include("projects.api.urls")),
    path("api/", include("issues.api.urls")),

    # Interactive API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),

    # Browsable-API login/logout, useful in development.
    path("api-auth/", include("rest_framework.urls")),
]
