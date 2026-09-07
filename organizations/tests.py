"""Tests for the organization layer.

The isolation tests matter most: they are what prove the tenant boundary is a
boundary and not just a label.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from issues.services.issue_service import create_issue
from organizations.models import Organization, OrgMember
from organizations.services.org_service import LastAdminError, remove_org_member
from organizations.testing import join, make_org, make_superuser, make_user
from projects.models import Project, ProjectMember

ORGS_URL = "/api/organizations/"


class OrganizationCreateTests(APITestCase):
    """Only a super admin may create a tenant."""

    def setUp(self):
        self.root = make_superuser()
        self.org = make_org("existing")
        self.plain = make_user("plain", org=self.org)

    def test_super_admin_can_create(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.post(
            ORGS_URL, {"name": "Acme", "slug": "acme"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Organization.objects.filter(slug="acme").exists())

    def test_creator_becomes_the_first_admin(self):
        """An organization is never created without an admin, or nobody could
        administer it."""
        self.client.force_authenticate(user=self.root)
        response = self.client.post(
            ORGS_URL, {"name": "Acme", "slug": "acme"}, format="json"
        )

        membership = OrgMember.objects.get(
            organization_id=response.data["id"], user=self.root
        )
        self.assertEqual(membership.role, OrgMember.Role.ADMIN)

    def test_super_admin_can_nominate_a_different_admin(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.post(
            ORGS_URL,
            {"name": "Acme", "slug": "acme", "admin": self.plain.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OrgMember.objects.filter(
                organization_id=response.data["id"],
                user=self.plain,
                role=OrgMember.Role.ADMIN,
            ).exists()
        )

    def test_create_with_inline_members(self):
        extra = make_user("extra")
        self.client.force_authenticate(user=self.root)

        response = self.client.post(
            ORGS_URL,
            {
                "name": "Acme",
                "slug": "acme",
                "admin": self.plain.id,
                "members": [{"user": extra.id, "role": "MEMBER"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["members"]), 2)

    def test_ordinary_user_cannot_create(self):
        self.client.force_authenticate(user=self.plain)
        response = self.client.post(
            ORGS_URL, {"name": "Nope", "slug": "nope"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Organization.objects.filter(slug="nope").exists())

    def test_org_admin_cannot_create_another_org(self):
        """Running one tenant does not entitle you to make more."""
        admin = make_user("orgadmin", org=self.org, role=OrgMember.Role.ADMIN)
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            ORGS_URL, {"name": "Nope", "slug": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_slug_rejected(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.post(
            ORGS_URL, {"name": "Dup", "slug": "existing"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        response = self.client.post(ORGS_URL, {"name": "X", "slug": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OrganizationVisibilityTests(APITestCase):
    def setUp(self):
        self.root = make_superuser()
        self.alpha = make_org("alpha")
        self.beta = make_org("beta")

        self.alice = make_user("alice", org=self.alpha)
        self.bob = make_user("bob", org=self.beta)

    def test_user_sees_only_their_own_organizations(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(ORGS_URL)

        slugs = {o["slug"] for o in response.data["results"]}
        self.assertEqual(slugs, {"alpha"})

    def test_super_admin_sees_every_organization(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.get(ORGS_URL)

        slugs = {o["slug"] for o in response.data["results"]}
        self.assertEqual(slugs, {"alpha", "beta"})

    def test_outsider_gets_404_on_detail(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"{ORGS_URL}{self.beta.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactive_organization_is_hidden_from_members(self):
        self.alpha.is_active = False
        self.alpha.save()

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(ORGS_URL)
        self.assertEqual(response.data["count"], 0)

    def test_inactive_organization_still_visible_to_super_admin(self):
        self.alpha.is_active = False
        self.alpha.save()

        self.client.force_authenticate(user=self.root)
        response = self.client.get(ORGS_URL)
        slugs = {o["slug"] for o in response.data["results"]}
        self.assertIn("alpha", slugs)

    def test_detail_reports_my_role(self):
        join(self.beta, self.alice, OrgMember.Role.ADMIN)

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"{ORGS_URL}{self.beta.id}/")
        self.assertEqual(response.data["my_role"], "ADMIN")

    def test_list_reports_counts(self):
        Project.objects.create(
            organization=self.alpha, name="P", key="P1", owner=self.alice
        )

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(ORGS_URL)

        row = response.data["results"][0]
        self.assertEqual(row["project_count"], 1)
        self.assertEqual(row["member_count"], 1)


class OrganizationUpdateDeleteTests(APITestCase):
    def setUp(self):
        self.root = make_superuser()
        self.org = make_org("acme")
        self.admin = make_user("admin1", org=self.org, role=OrgMember.Role.ADMIN)
        self.member = make_user("member1", org=self.org)
        self.url = f"{ORGS_URL}{self.org.id}/"

    def test_org_admin_can_rename(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(self.url, {"name": "Renamed"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Renamed")

    def test_member_cannot_rename(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.patch(self.url, {"name": "Nope"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_slug_is_immutable(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(self.url, {"slug": "hacked"}, format="json")

        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, "acme")

    def test_org_admin_cannot_delete(self):
        """Deleting a tenant destroys every project inside it, so it stays
        with the super admin."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Organization.objects.filter(id=self.org.id).exists())

    def test_super_admin_can_delete(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Organization.objects.filter(id=self.org.id).exists())

    def test_deleting_cascades_to_projects_and_issues(self):
        project = Project.objects.create(
            organization=self.org, name="P", key="P1", owner=self.admin
        )
        create_issue(
            project=project, reporter=self.admin, validated_data={"title": "doomed"}
        )

        self.client.force_authenticate(user=self.root)
        self.client.delete(self.url)

        self.assertFalse(Project.objects.filter(id=project.id).exists())

    def test_deactivating_is_the_reversible_alternative(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(self.url, {"is_active": False}, format="json")

        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)
        self.assertTrue(Organization.objects.filter(id=self.org.id).exists())


class OrgMembershipTests(APITestCase):
    def setUp(self):
        self.root = make_superuser()
        self.org = make_org("acme")
        self.admin = make_user("oadmin", org=self.org, role=OrgMember.Role.ADMIN)
        self.member = make_user("omember", org=self.org)
        self.outsider = make_user("outsider")
        self.url = f"{ORGS_URL}{self.org.id}/members/"

    def test_admin_can_add_a_member(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "MEMBER"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "outsider")

    def test_super_admin_can_add_to_any_org(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_plain_member_cannot_add(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            self.url, {"user": self.outsider.id, "role": "MEMBER"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_gets_404(self):
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_members_can_read_the_roster(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_duplicate_membership_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.url, {"user": self.member.id, "role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_promote_a_member(self):
        membership = OrgMember.objects.get(organization=self.org, user=self.member)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"{self.url}{membership.id}/", {"role": "ADMIN"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrgMember.Role.ADMIN)

    def test_last_admin_cannot_be_demoted(self):
        membership = OrgMember.objects.get(organization=self.org, user=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"{self.url}{membership.id}/", {"role": "MEMBER"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["role"], list)
        membership.refresh_from_db()
        self.assertEqual(membership.role, OrgMember.Role.ADMIN)

    def test_last_admin_cannot_be_removed(self):
        membership = OrgMember.objects.get(organization=self.org, user=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(f"{self.url}{membership.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["detail"], list)

    def test_second_admin_can_be_removed(self):
        join(self.org, self.outsider, OrgMember.Role.ADMIN)
        membership = OrgMember.objects.get(organization=self.org, user=self.outsider)

        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f"{self.url}{membership.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_service_raises_last_admin_error(self):
        membership = OrgMember.objects.get(organization=self.org, user=self.admin)
        with self.assertRaises(LastAdminError):
            remove_org_member(organization=self.org, membership=membership)

    def test_removing_a_member_strips_their_project_memberships(self):
        """Otherwise they keep a ProjectMember row for a project they can no
        longer reach — an inconsistency that resurfaces if they rejoin."""
        project = Project.objects.create(
            organization=self.org, name="P", key="P1", owner=self.admin
        )
        ProjectMember.objects.create(
            project=project, user=self.member, role=ProjectMember.Role.DEVELOPER
        )

        membership = OrgMember.objects.get(organization=self.org, user=self.member)
        self.client.force_authenticate(user=self.admin)
        self.client.delete(f"{self.url}{membership.id}/")

        self.assertFalse(
            ProjectMember.objects.filter(project=project, user=self.member).exists()
        )

    def test_removing_a_member_leaves_other_orgs_alone(self):
        other_org = make_org("other")
        other_project = Project.objects.create(
            organization=other_org, name="O", key="O1", owner=self.member
        )
        join(other_org, self.member)
        ProjectMember.objects.create(
            project=other_project, user=self.member, role=ProjectMember.Role.DEVELOPER
        )

        membership = OrgMember.objects.get(organization=self.org, user=self.member)
        self.client.force_authenticate(user=self.admin)
        self.client.delete(f"{self.url}{membership.id}/")

        self.assertTrue(
            ProjectMember.objects.filter(
                project=other_project, user=self.member
            ).exists()
        )


class TenantIsolationTests(APITestCase):
    """The load-bearing tests. Nothing crosses an organization boundary.

    Each case is written from the point of view of someone in Alpha trying to
    reach something in Beta.
    """

    def setUp(self):
        self.alpha = make_org("alpha")
        self.beta = make_org("beta")

        self.alice = make_user("alice", org=self.alpha)
        self.bob = make_user("bob", org=self.beta)
        self.root = make_superuser()

        # A PUBLIC project in Beta. "Public" must mean public within Beta.
        self.beta_public = Project.objects.create(
            organization=self.beta,
            name="Beta Public",
            key="BPUB",
            owner=self.bob,
            visibility=Project.Visibility.PUBLIC,
        )
        ProjectMember.objects.create(
            project=self.beta_public, user=self.bob, role=ProjectMember.Role.OWNER
        )

        self.beta_issue = create_issue(
            project=self.beta_public,
            reporter=self.bob,
            validated_data={"title": "Beta internal work"},
        )

        self.alpha_project = Project.objects.create(
            organization=self.alpha, name="Alpha", key="ALP", owner=self.alice
        )
        ProjectMember.objects.create(
            project=self.alpha_project, user=self.alice, role=ProjectMember.Role.OWNER
        )

    def test_public_project_does_not_escape_its_organization(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/projects/")

        keys = {p["key"] for p in response.data["results"]}
        self.assertEqual(keys, {"ALP"})
        self.assertNotIn("BPUB", keys)

    def test_cannot_retrieve_another_tenants_project(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"/api/projects/{self.beta_public.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_list_another_tenants_issues(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/issues/")

        titles = {i["title"] for i in response.data["results"]}
        self.assertNotIn("Beta internal work", titles)

    def test_cannot_retrieve_another_tenants_issue(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"/api/issues/{self.beta_issue.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_reach_another_tenants_project_issue_list(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"/api/projects/{self.beta_public.id}/issues/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_comment_on_another_tenants_issue(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            f"/api/issues/{self.beta_issue.id}/comments/",
            {"body": "should not land"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_transition_another_tenants_issue(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            f"/api/issues/{self.beta_issue.id}/transition/",
            {"status": "IN_PROGRESS"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_read_another_tenants_member_roster(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"/api/projects/{self.beta_public.id}/members/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_create_a_project_in_another_tenant(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/projects/",
            {"organization": self.beta.id, "name": "Trespass", "key": "TRS"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.filter(key="TRS").exists())

    def test_can_create_a_project_in_own_tenant(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/projects/",
            {"organization": self.alpha.id, "name": "Mine", "key": "MIN"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_project_cannot_be_moved_between_tenants(self):
        self.client.force_authenticate(user=self.alice)
        self.client.patch(
            f"/api/projects/{self.alpha_project.id}/",
            {"organization": self.beta.id},
            format="json",
        )

        self.alpha_project.refresh_from_db()
        self.assertEqual(self.alpha_project.organization, self.alpha)

    def test_losing_org_membership_revokes_project_access(self):
        """Even with the ProjectMember row intact, the outer gate closes."""
        OrgMember.objects.filter(organization=self.alpha, user=self.alice).delete()

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(f"/api/projects/{self.alpha_project.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deactivating_an_org_hides_its_projects(self):
        self.alpha.is_active = False
        self.alpha.save()

        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/projects/")
        self.assertEqual(response.data["count"], 0)

    def test_membership_in_both_orgs_sees_both(self):
        join(self.beta, self.alice)

        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/projects/")

        keys = {p["key"] for p in response.data["results"]}
        self.assertEqual(keys, {"ALP", "BPUB"})

    def test_super_admin_sees_across_tenants(self):
        self.client.force_authenticate(user=self.root)
        response = self.client.get("/api/projects/")

        keys = {p["key"] for p in response.data["results"]}
        self.assertEqual(keys, {"ALP", "BPUB"})
