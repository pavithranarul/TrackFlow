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

from projects.models import Project, ProjectMember

User = get_user_model()


class ProjectCreateTests(APITestCase):
    """POST /api/projects/"""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass1234")
        self.other_user = User.objects.create_user(username="other", password="pass1234")
        self.client.force_authenticate(user=self.owner)
        self.url = "/api/projects/"

    def test_create_project_returns_201(self):
        payload = {
            "name": "TrackFlow",
            "key": "TRK",
            "description": "PM backend",
            "status": "ACTIVE",
            "visibility": "PRIVATE",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_project_persists_correct_fields(self):
        payload = {"name": "TrackFlow", "key": "TRK"}
        response = self.client.post(self.url, payload, format="json")

        project = Project.objects.get(key="TRK")
        self.assertEqual(project.name, "TrackFlow")
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(response.data["owner"], self.owner.username)

    def test_create_project_creates_owner_membership(self):
        payload = {"name": "TrackFlow", "key": "TRK"}
        response = self.client.post(self.url, payload, format="json")
        project_id = response.data["id"]

        membership = ProjectMember.objects.filter(
            project_id=project_id, user=self.owner
        ).first()

        self.assertIsNotNone(membership, "Owner ProjectMember was not created")
        self.assertEqual(membership.role, ProjectMember.Role.OWNER)

    def test_create_project_with_additional_members(self):
        payload = {
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
        response = self.client.post(self.url, {"name": "X", "key": "X1"}, format="json")
        # SessionAuthentication has no WWW-Authenticate challenge, so DRF
        # returns 403 rather than 401 for unauthenticated requests. Expect
        # this to become 401 once JWT auth lands in Sprint 2.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_project_duplicate_key_rejected(self):
        Project.objects.create(name="First", key="DUP", owner=self.owner)
        response = self.client.post(
            self.url, {"name": "Second", "key": "DUP"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProjectListTests(APITestCase):
    """GET /api/projects/"""

    def setUp(self):
        self.user = User.objects.create_user(username="lister", password="pass1234")
        self.client.force_authenticate(user=self.user)
        Project.objects.create(name="A", key="AAA", owner=self.user)
        Project.objects.create(name="B", key="BBB", owner=self.user)

    def test_list_projects_returns_200_and_all_projects(self):
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class ProjectDetailTests(APITestCase):
    """GET / PATCH / DELETE /api/projects/<id>/"""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner2", password="pass1234")
        self.client.force_authenticate(user=self.owner)
        self.project = Project.objects.create(
            name="Detail Project", key="DET", owner=self.owner
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
        self.owner = User.objects.create_user(username="owner3", password="pass1234")
        self.project = Project.objects.create(
            name="Constraint Project", key="CON", owner=self.owner
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
        self.owner = User.objects.create_user(username="shapeowner", password="pass1234")
        self.member_user = User.objects.create_user(username="member1", password="pass1234")
        self.client.force_authenticate(user=self.owner)

        self.project = Project.objects.create(
            name="Shape Project", key="SHP", owner=self.owner, description="desc"
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

        item = response.data[0]
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
            "/api/projects/", {"name": "New", "key": "NEW"}, format="json"
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