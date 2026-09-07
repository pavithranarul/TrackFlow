"""
Full test suite for the Project API: CRUD endpoints, automatic owner
ProjectMember creation, and the split serializer shapes (List/Detail/
Create/Update).

Drop this in as projects/tests.py and run:

    python manage.py test projects
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.testing import make_org, make_user
from projects.models import Project, ProjectMember

User = get_user_model()


class ProjectCreateTests(APITestCase):
    """POST /api/projects/"""

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("owner", org=self.org)
        self.other_user = make_user("other", org=self.org)
        self.client.force_authenticate(user=self.owner)
        self.url = "/api/projects/"

    def test_create_project_returns_201(self):
        payload = {
            "organization": self.org.id,
            "name": "TrackFlow",
            "key": "TRK",
            "description": "PM backend",
            "status": "ACTIVE",
            "visibility": "PRIVATE",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_project_persists_correct_fields(self):
        payload = {"organization": self.org.id, "name": "TrackFlow", "key": "TRK"}
        response = self.client.post(self.url, payload, format="json")

        project = Project.objects.get(key="TRK")
        self.assertEqual(project.name, "TrackFlow")
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(response.data["owner"], self.owner.username)

    def test_create_project_creates_owner_membership(self):
        payload = {"organization": self.org.id, "name": "TrackFlow", "key": "TRK"}
        response = self.client.post(self.url, payload, format="json")
        project_id = response.data["id"]

        membership = ProjectMember.objects.filter(
            project_id=project_id, user=self.owner
        ).first()

        self.assertIsNotNone(membership, "Owner ProjectMember was not created")
        self.assertEqual(membership.role, ProjectMember.Role.OWNER)

    def test_create_project_with_additional_members(self):
        payload = {
            "organization": self.org.id,
            "name": "TrackFlow",
            "key": "TRK2",
            "members": [{"user": self.other_user.id, "role": "DEVELOPER"}],
        }
        response = self.client.post(self.url, payload, format="json")
        project_id = response.data["id"]

        self.assertTrue(
            ProjectMember.objects.filter(
                project_id=project_id, user=self.owner, role="OWNER"
            ).exists()
        )
        self.assertTrue(
            ProjectMember.objects.filter(
                project_id=project_id, user=self.other_user, role="DEVELOPER"
            ).exists()
        )

    def test_create_project_does_not_duplicate_owner_if_listed_in_members(self):
        payload = {
            "organization": self.org.id,
            "name": "TrackFlow",
            "key": "TRK3",
            "members": [{"user": self.owner.id, "role": "VIEWER"}],
        }
        response = self.client.post(self.url, payload, format="json")
        project_id = response.data["id"]

        count = ProjectMember.objects.filter(
            project_id=project_id, user=self.owner
        ).count()
        self.assertEqual(count, 1)

    def test_create_project_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {"organization": self.org.id, "name": "X", "key": "X1"}, format="json")
        # JWTAuthentication sends a WWW-Authenticate challenge, so an
        # unauthenticated request is a 401 rather than the 403 that plain
        # SessionAuthentication used to produce.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_project_duplicate_key_rejected(self):
        Project.objects.create(
            organization=self.org, name="First", key="DUP", owner=self.owner)
        response = self.client.post(
            self.url, {"organization": self.org.id, "name": "Second", "key": "DUP"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProjectListTests(APITestCase):
    """GET /api/projects/"""

    def setUp(self):
        self.org = make_org()
        self.user = make_user("lister", org=self.org)
        self.client.force_authenticate(user=self.user)
        Project.objects.create(
            organization=self.org, name="A", key="AAA", owner=self.user)
        Project.objects.create(
            organization=self.org, name="B", key="BBB", owner=self.user)

    def test_list_projects_returns_200_and_all_projects(self):
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Responses are paginated: {count, next, previous, results}.
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)


class ProjectDetailTests(APITestCase):
    """GET / PATCH / DELETE /api/projects/<id>/"""

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("owner2", org=self.org)
        self.client.force_authenticate(user=self.owner)
        self.project = Project.objects.create(
            organization=self.org, name="Detail Project", key="DET", owner=self.owner
        )
        ProjectMember.objects.create(
            project=self.project, user=self.owner, role=ProjectMember.Role.OWNER
        )
        self.url = f"/api/projects/{self.project.id}/"

    def test_retrieve_project(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["key"], "DET")

    def test_retrieve_nonexistent_project_returns_404(self):
        response = self.client.get("/api/projects/999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_project_updates_fields(self):
        response = self.client.patch(
            self.url, {"name": "Renamed Project"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Renamed Project")

    def test_patch_project_does_not_remove_owner_membership(self):
        self.client.patch(self.url, {"status": "ARCHIVED"}, format="json")
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.project, user=self.owner, role=ProjectMember.Role.OWNER
            ).exists()
        )

    def test_delete_project_returns_204(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_delete_project_cascades_to_members(self):
        self.client.delete(self.url)
        self.assertFalse(
            ProjectMember.objects.filter(project_id=self.project.id).exists()
        )


class ProjectMemberModelTests(APITestCase):
    """Sanity checks on the ProjectMember constraint itself."""

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("owner3", org=self.org)
        self.project = Project.objects.create(
            organization=self.org, name="Constraint Project", key="CON", owner=self.owner
        )

    def test_duplicate_membership_raises_integrity_error(self):
        from django.db import IntegrityError

        ProjectMember.objects.create(
            project=self.project, user=self.owner, role=ProjectMember.Role.OWNER
        )
        with self.assertRaises(IntegrityError):
            ProjectMember.objects.create(
                project=self.project, user=self.owner, role=ProjectMember.Role.VIEWER
            )


class ProjectSerializerShapeTests(APITestCase):
    """Confirms List/Detail/Create/Update serializers return distinct,
    correct shapes."""

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("shapeowner", org=self.org)
        self.member_user = make_user("member1", org=self.org)
        self.client.force_authenticate(user=self.owner)

        self.project = Project.objects.create(
            organization=self.org, name="Shape Project", key="SHP", owner=self.owner, description="desc"
        )
        ProjectMember.objects.create(
            project=self.project, user=self.owner, role=ProjectMember.Role.OWNER
        )
        ProjectMember.objects.create(
            project=self.project, user=self.member_user, role=ProjectMember.Role.DEVELOPER
        )

    def test_list_response_excludes_description_and_members(self):
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        item = response.data["results"][0]
        self.assertNotIn("description", item)
        self.assertNotIn("members", item)
        self.assertIn("key", item)
        self.assertIn("owner", item)

    def test_detail_response_includes_description_and_nested_members(self):
        response = self.client.get(f"/api/projects/{self.project.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("description", response.data)
        self.assertIn("members", response.data)
        self.assertEqual(len(response.data["members"]), 2)

        roles = {m["role"] for m in response.data["members"]}
        self.assertEqual(roles, {"OWNER", "DEVELOPER"})

        usernames = {m["username"] for m in response.data["members"]}
        self.assertEqual(usernames, {"shapeowner", "member1"})

    def test_create_response_uses_detail_shape(self):
        response = self.client.post(
            "/api/projects/", {"organization": self.org.id, "name": "New", "key": "NEW"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("members", response.data)
        self.assertEqual(len(response.data["members"]), 1)
        self.assertEqual(response.data["members"][0]["role"], "OWNER")

    def test_update_cannot_change_key(self):
        original_key = self.project.key
        response = self.client.patch(
            f"/api/projects/{self.project.id}/",
            {"key": "HACKED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        self.assertEqual(self.project.key, original_key)

    def test_update_cannot_change_members_via_project_endpoint(self):
        response = self.client.patch(
            f"/api/projects/{self.project.id}/",
            {
                "name": "Renamed",
                "members": [{"user": self.member_user.id, "role": "VIEWER"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        membership = ProjectMember.objects.get(
            project=self.project, user=self.member_user
        )
        self.assertEqual(membership.role, ProjectMember.Role.DEVELOPER)  # unchanged

    def test_update_response_uses_detail_shape(self):
        response = self.client.patch(
            f"/api/projects/{self.project.id}/",
            {"name": "Renamed Again"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("members", response.data)
        self.assertIn("description", response.data)

class ProjectVisibilityTests(APITestCase):
    """Who can *see* which projects.

    Visibility is enforced in the selector layer, so an invisible project is
    reported as 404 rather than 403 and never leaks its existence.
    """

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("visowner", org=self.org)
        self.member = make_user("vismember", org=self.org)
        self.stranger = make_user("stranger", org=self.org)

        self.private = Project.objects.create(
            organization=self.org, name="Private Project", key="PRV", owner=self.owner
        )
        ProjectMember.objects.create(
            project=self.private, user=self.owner, role=ProjectMember.Role.OWNER
        )
        ProjectMember.objects.create(
            project=self.private, user=self.member, role=ProjectMember.Role.DEVELOPER
        )

        self.public = Project.objects.create(
            organization=self.org, name="Public Project",
            key="PUB",
            owner=self.owner,
            visibility=Project.Visibility.PUBLIC,
        )

    def test_member_sees_private_project_in_list(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get("/api/projects/")
        keys = {p["key"] for p in response.data["results"]}
        self.assertIn("PRV", keys)

    def test_stranger_does_not_see_private_project_in_list(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/projects/")
        keys = {p["key"] for p in response.data["results"]}
        self.assertNotIn("PRV", keys)

    def test_stranger_sees_public_project_in_list(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/projects/")
        keys = {p["key"] for p in response.data["results"]}
        self.assertEqual(keys, {"PUB"})

    def test_stranger_retrieving_private_project_gets_404_not_403(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f"/api/projects/{self.private.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stranger_can_retrieve_public_project(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f"/api/projects/{self.public.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_sees_project_without_a_membership_row(self):
        """A project created through the admin has no ProjectMember row; its
        owner must still see it."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f"/api/projects/{self.public.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.public, user=self.owner).exists()
        )

    def test_list_is_not_duplicated_by_multiple_memberships(self):
        """owner + member + PUBLIC all match in one OR'd query; distinct()
        must keep each project to a single row."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/projects/")
        keys = [p["key"] for p in response.data["results"]]
        self.assertEqual(sorted(keys), ["PRV", "PUB"])
        self.assertEqual(response.data["count"], 2)


class ProjectWritePermissionTests(APITestCase):
    """Who can *modify* a project. Read access alone is never enough."""

    def setUp(self):
        self.org = make_org()
        self.owner = make_user("permowner", org=self.org)
        self.manager = make_user("permmanager", org=self.org)
        self.developer = make_user("permdev", org=self.org)
        self.viewer = make_user("permviewer", org=self.org)
        self.stranger = make_user("permstranger", org=self.org)

        self.project = Project.objects.create(
            organization=self.org, name="Perm Project",
            key="PRM",
            owner=self.owner,
            visibility=Project.Visibility.PUBLIC,
        )
        for user, role in (
            (self.owner, ProjectMember.Role.OWNER),
            (self.manager, ProjectMember.Role.MANAGER),
            (self.developer, ProjectMember.Role.DEVELOPER),
            (self.viewer, ProjectMember.Role.VIEWER),
        ):
            ProjectMember.objects.create(project=self.project, user=user, role=role)

        self.url = f"/api/projects/{self.project.id}/"

    def _patch_as(self, user):
        self.client.force_authenticate(user=user)
        return self.client.patch(self.url, {"name": "Touched"}, format="json")

    def _delete_as(self, user):
        self.client.force_authenticate(user=user)
        return self.client.delete(self.url)

    def test_owner_can_patch(self):
        self.assertEqual(self._patch_as(self.owner).status_code, status.HTTP_200_OK)

    def test_manager_can_patch(self):
        self.assertEqual(self._patch_as(self.manager).status_code, status.HTTP_200_OK)

    def test_developer_cannot_patch(self):
        self.assertEqual(self._patch_as(self.developer).status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_patch(self):
        self.assertEqual(self._patch_as(self.viewer).status_code, status.HTTP_403_FORBIDDEN)

    def test_denied_patch_does_not_change_the_project(self):
        self._patch_as(self.viewer)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Perm Project")

    def test_stranger_patching_public_project_is_forbidden(self):
        """A PUBLIC project is readable by anyone but writable by nobody
        outside its member list."""
        self.assertEqual(self._patch_as(self.stranger).status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        self.assertEqual(self._delete_as(self.owner).status_code, status.HTTP_204_NO_CONTENT)

    def test_manager_cannot_delete(self):
        self.assertEqual(self._delete_as(self.manager).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Project.objects.filter(id=self.project.id).exists())

    def test_developer_cannot_delete(self):
        self.assertEqual(self._delete_as(self.developer).status_code, status.HTTP_403_FORBIDDEN)


class ProjectFilterTests(APITestCase):
    """The project list honours search, filter and ordering parameters.

    Without explicit `search_fields` the globally-configured SearchFilter
    silently ignores ?search=, which is worse than not offering it at all.
    """

    def setUp(self):
        self.org = make_org()
        self.user = make_user("filterer", org=self.org)
        self.client.force_authenticate(user=self.user)

        self.tracker = Project.objects.create(
            organization=self.org, name="TrackFlow", key="TRK", owner=self.user, description="the tracker"
        )
        self.design = Project.objects.create(
            organization=self.org, name="Design System",
            key="DS",
            owner=self.user,
            visibility=Project.Visibility.PUBLIC,
        )
        self.archived = Project.objects.create(
            organization=self.org, name="Old Thing", key="OLD", owner=self.user, status=Project.Status.ARCHIVED
        )

    def _names(self, query=""):
        response = self.client.get(f"/api/projects/?{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {p["name"] for p in response.data["results"]}

    def test_search_matches_name(self):
        self.assertEqual(self._names("search=TrackFlow"), {"TrackFlow"})

    def test_search_matches_key(self):
        self.assertEqual(self._names("search=DS"), {"Design System"})

    def test_filter_by_status(self):
        self.assertEqual(self._names("status=ARCHIVED"), {"Old Thing"})

    def test_filter_by_visibility(self):
        self.assertEqual(self._names("visibility=PUBLIC"), {"Design System"})

    def test_filter_by_key(self):
        self.assertEqual(self._names("key=trk"), {"TrackFlow"})

    def test_ordering_by_name(self):
        response = self.client.get("/api/projects/?ordering=name")
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(names, ["Design System", "Old Thing", "TrackFlow"])

    def test_no_query_returns_everything_visible(self):
        self.assertEqual(len(self._names()), 3)
