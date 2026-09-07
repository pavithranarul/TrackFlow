"""Tests for the membership management endpoints.

The rule that matters most here is that a project can never be left without an
OWNER, whether by demotion or by removal.
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.testing import make_org, make_user
from projects.models import Project, ProjectMember
from projects.services.member_service import LastOwnerError, remove_member

User = get_user_model()


class MemberTestMixin:
    def build_world(self):
        self.org = make_org()
        self.owner = make_user("m_owner", org=self.org)
        self.manager = make_user("m_manager", org=self.org)
        self.developer = make_user("m_dev", org=self.org)
        self.viewer = make_user("m_viewer", org=self.org)
        self.outsider = make_user("m_outsider", org=self.org)

        self.project = Project.objects.create(
            organization=self.org, name="Member Project", key="MEM", owner=self.owner
        )

        self.memberships = {}
        for user, role in (
            (self.owner, ProjectMember.Role.OWNER),
            (self.manager, ProjectMember.Role.MANAGER),
            (self.developer, ProjectMember.Role.DEVELOPER),
            (self.viewer, ProjectMember.Role.VIEWER),
        ):
            self.memberships[role] = ProjectMember.objects.create(
                project=self.project, user=user, role=role
            )

        self.url = f"/api/projects/{self.project.id}/members/"

    def detail_url(self, membership):
        return f"{self.url}{membership.id}/"


class MemberListTests(MemberTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def test_member_can_list_membership(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)

        roles = {m["role"] for m in response.data["results"]}
        self.assertEqual(roles, {"OWNER", "MANAGER", "DEVELOPER", "VIEWER"})

    def test_outsider_gets_404(self):
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )


class MemberAddTests(MemberTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def test_owner_can_add_a_member(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "DEVELOPER"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "m_outsider")
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.project, user=self.outsider, role="DEVELOPER"
            ).exists()
        )

    def test_manager_can_add_a_member(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "VIEWER"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_developer_cannot_add_a_member(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "VIEWER"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_grant_owner(self):
        """A manager must not be able to hand out a role above their own."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "OWNER"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.project, user=self.outsider).exists()
        )

    def test_owner_can_grant_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "OWNER"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_adding_an_existing_member_is_rejected(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.url, {"user": self.developer.id, "role": "MANAGER"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            ProjectMember.objects.filter(
                project=self.project, user=self.developer
            ).count(),
            1,
        )


class MemberRoleChangeTests(MemberTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def test_owner_can_change_a_role(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.DEVELOPER]),
            {"role": "MANAGER"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.memberships[ProjectMember.Role.DEVELOPER].refresh_from_db()
        self.assertEqual(
            self.memberships[ProjectMember.Role.DEVELOPER].role, "MANAGER"
        )

    def test_manager_can_change_a_non_owner_role(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.VIEWER]),
            {"role": "DEVELOPER"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_promote_to_owner(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.DEVELOPER]),
            {"role": "OWNER"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_demote_an_owner(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER]),
            {"role": "VIEWER"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.memberships[ProjectMember.Role.OWNER].refresh_from_db()
        self.assertEqual(self.memberships[ProjectMember.Role.OWNER].role, "OWNER")

    def test_viewer_cannot_change_roles(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.DEVELOPER]),
            {"role": "MANAGER"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_demoting_the_only_owner_is_refused(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER]),
            {"role": "VIEWER"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.memberships[ProjectMember.Role.OWNER].refresh_from_db()
        self.assertEqual(self.memberships[ProjectMember.Role.OWNER].role, "OWNER")

    def test_ownership_transfer_promote_then_demote(self):
        """The supported way to hand a project over: promote the successor,
        then step down."""
        self.client.force_authenticate(user=self.owner)

        promote = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.MANAGER]),
            {"role": "OWNER"},
            format="json",
        )
        self.assertEqual(promote.status_code, status.HTTP_200_OK)

        demote = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER]),
            {"role": "DEVELOPER"},
            format="json",
        )
        self.assertEqual(demote.status_code, status.HTTP_200_OK)

        self.assertEqual(
            self.project.members.filter(role=ProjectMember.Role.OWNER).count(), 1
        )


class MemberRemovalTests(MemberTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def test_owner_can_remove_a_member(self):
        self.client.force_authenticate(user=self.owner)
        membership = self.memberships[ProjectMember.Role.DEVELOPER]

        response = self.client.delete(self.detail_url(membership))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProjectMember.objects.filter(id=membership.id).exists())

    def test_manager_can_remove_a_non_owner(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.VIEWER])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_manager_cannot_remove_an_owner(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_developer_cannot_remove_anyone(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.VIEWER])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_removing_the_only_owner_is_refused(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            ProjectMember.objects.filter(
                id=self.memberships[ProjectMember.Role.OWNER].id
            ).exists()
        )

    def test_second_owner_can_be_removed(self):
        ProjectMember.objects.filter(
            id=self.memberships[ProjectMember.Role.MANAGER].id
        ).update(role=ProjectMember.Role.OWNER)

        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.MANAGER])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_service_raises_last_owner_error(self):
        with self.assertRaises(LastOwnerError):
            remove_member(
                project=self.project,
                membership=self.memberships[ProjectMember.Role.OWNER],
            )

    def test_removing_a_member_does_not_touch_their_issues(self):
        """Membership is access, not authorship. Removing someone must not
        delete the work they reported."""
        from issues.services.issue_service import create_issue

        issue = create_issue(
            project=self.project,
            reporter=self.developer,
            validated_data={"title": "Still here"},
        )

        self.client.force_authenticate(user=self.owner)
        self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.DEVELOPER])
        )

        issue.refresh_from_db()
        self.assertEqual(issue.reporter, self.developer)


class MemberErrorShapeTests(MemberTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.client.force_authenticate(user=self.owner)

    def test_last_owner_demotion_error_is_a_list(self):
        response = self.client.patch(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER]),
            {"role": "VIEWER"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["role"], list)

    def test_last_owner_removal_error_is_a_list(self):
        response = self.client.delete(
            self.detail_url(self.memberships[ProjectMember.Role.OWNER])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["detail"], list)
