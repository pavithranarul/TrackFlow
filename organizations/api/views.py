from django.db.models import Count
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.api.permissions import IsSuperAdmin, OrganizationPermission
from organizations.api.serializers import (
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationUpdateSerializer,
    OrgMemberCreateSerializer,
    OrgMemberReadSerializer,
    OrgMemberRoleSerializer,
)
from organizations.models import Organization, OrgMember
from organizations.selectors.org_selector import (
    get_org_member,
    get_org_members,
    get_org_role,
    get_organization_for_user,
    get_organizations_for_user,
)
from organizations.services.org_service import (
    LastAdminError,
    add_org_member,
    create_organization,
    delete_organization,
    remove_org_member,
    update_org_member_role,
    update_organization,
)

COUNTS = {
    "member_count": Count("members", distinct=True),
    "project_count": Count("projects", distinct=True),
}


def _with_counts(pk):
    """Fetch one organization with its counts, bypassing visibility.

    Only ever called with a pk the caller has already been authorised for.
    """
    return Organization.objects.annotate(**COUNTS).get(pk=pk)


class OrganizationListCreateAPIView(ListCreateAPIView):
    """GET  /api/organizations/ — the ones you belong to (all, for a super admin).
    POST /api/organizations/ — super admin only."""

    queryset = Organization.objects.none()

    permission_classes = [IsAuthenticated]
    search_fields = ("name", "slug", "description")
    ordering_fields = ("name", "created_at")
    filterset_fields = ("is_active",)

    def get_queryset(self):
        return get_organizations_for_user(self.request.user).annotate(**COUNTS)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrganizationCreateSerializer
        return OrganizationListSerializer

    def create(self, request, *args, **kwargs):
        # Creating a tenant is a platform-level act, so it is gated here
        # rather than by the class-wide permissions (which must stay open
        # enough for any authenticated user to LIST their own orgs).
        if not IsSuperAdmin().has_permission(request, self):
            raise PermissionDenied("Only a super admin can create an organization.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        admin = data.pop("admin", None) or request.user

        organization = create_organization(validated_data=data, first_admin=admin)

        return Response(
            OrganizationDetailSerializer(
                _with_counts(organization.pk),
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationDetailAPIView(APIView):
    """GET/PATCH/DELETE /api/organizations/<id>/."""

    permission_classes = [IsAuthenticated, OrganizationPermission]
    serializer_class = OrganizationDetailSerializer

    def get_object(self):
        organization = (
            get_organizations_for_user(self.request.user)
            .annotate(**COUNTS)
            .filter(id=self.kwargs["pk"])
            .first()
        )

        if not organization:
            raise NotFound("Organization not found.")

        self.check_object_permissions(self.request, organization)

        return organization

    def get(self, request, pk):
        return Response(
            OrganizationDetailSerializer(
                self.get_object(), context={"request": request}
            ).data
        )

    def patch(self, request, pk):
        organization = self.get_object()

        serializer = OrganizationUpdateSerializer(
            organization, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        organization = update_organization(
            organization=organization,
            validated_data=serializer.validated_data,
        )

        # Re-annotated from the row we already hold rather than re-queried
        # through get_organizations_for_user: deactivating an organization
        # removes it from that selector, so re-querying would 500 on exactly
        # the request that turned it off.
        return Response(
            OrganizationDetailSerializer(
                _with_counts(organization.pk),
                context={"request": request},
            ).data
        )

    def delete(self, request, pk):
        organization = self.get_object()

        delete_organization(organization)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrgMemberMixin:
    permission_classes = [IsAuthenticated]

    def get_organization(self):
        if not hasattr(self, "_organization"):
            organization = get_organization_for_user(
                self.request.user, self.kwargs["org_id"]
            )

            if not organization:
                raise NotFound("Organization not found.")

            self._organization = organization

        return self._organization

    def require_admin(self, organization):
        if get_org_role(self.request.user, organization) != OrgMember.Role.ADMIN:
            raise PermissionDenied(
                "Only a super admin or an organization admin can change its "
                "membership."
            )


class OrgMemberListCreateAPIView(OrgMemberMixin, ListCreateAPIView):
    """GET/POST /api/organizations/<org_id>/members/."""

    queryset = OrgMember.objects.none()

    def get_queryset(self):
        return get_org_members(self.get_organization())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrgMemberCreateSerializer
        return OrgMemberReadSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["organization"] = self.get_organization()
        return context

    def create(self, request, *args, **kwargs):
        organization = self.get_organization()
        self.require_admin(organization)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = add_org_member(
            organization=organization,
            user=serializer.validated_data["user"],
            role=serializer.validated_data["role"],
        )

        return Response(
            OrgMemberReadSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class OrgMemberDetailAPIView(OrgMemberMixin, APIView):
    """PATCH/DELETE /api/organizations/<org_id>/members/<pk>/."""

    serializer_class = OrgMemberRoleSerializer

    def get_membership(self, organization):
        membership = get_org_member(organization, self.kwargs["pk"])

        if not membership:
            raise NotFound("Membership not found.")

        return membership

    def patch(self, request, org_id, pk):
        organization = self.get_organization()
        self.require_admin(organization)
        membership = self.get_membership(organization)

        serializer = OrgMemberRoleSerializer(
            membership, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        try:
            membership = update_org_member_role(
                organization=organization,
                membership=membership,
                role=serializer.validated_data["role"],
            )
        except LastAdminError as exc:
            raise ValidationError({"role": [str(exc)]}) from exc

        return Response(OrgMemberReadSerializer(membership).data)

    def delete(self, request, org_id, pk):
        organization = self.get_organization()
        self.require_admin(organization)
        membership = self.get_membership(organization)

        try:
            remove_org_member(organization=organization, membership=membership)
        except LastAdminError as exc:
            raise ValidationError({"detail": [str(exc)]}) from exc

        return Response(status=status.HTTP_204_NO_CONTENT)
