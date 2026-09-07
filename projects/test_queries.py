"""Query-count guards.

These pin the number of SQL queries the list and detail endpoints run, so an
innocent-looking serializer change that reintroduces an N+1 fails the build
instead of quietly slowing the API down.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from issues.services.issue_service import create_comment, create_issue
from organizations.testing import make_org, make_user
from projects.models import Project, ProjectMember

User = get_user_model()


class QueryCountTests(APITestCase):
    def setUp(self):
        self.org = make_org()
        self.owner = make_user("q_owner", org=self.org)
        self.project = Project.objects.create(
            organization=self.org, name="Query Project", key="QRY", owner=self.owner
        )
        ProjectMember.objects.create(
            project=self.project, user=self.owner, role=ProjectMember.Role.OWNER
        )

        # Enough rows that an N+1 would show up clearly in the count.
        for i in range(5):
            user = make_user(f"q_member{i}", org=self.org)
            ProjectMember.objects.create(
                project=self.project, user=user, role=ProjectMember.Role.DEVELOPER
            )

        self.issues = [
            create_issue(
                project=self.project,
                reporter=self.owner,
                validated_data={"title": f"Issue {i}"},
            )
            for i in range(5)
        ]

        for i in range(5):
            create_comment(
                issue=self.issues[0], author=self.owner, body=f"comment {i}"
            )

        self.client.force_authenticate(user=self.owner)

    def test_project_list_does_not_scale_with_project_count(self):
        for i in range(5):
            Project.objects.create(
                organization=self.org, name=f"Extra {i}", key=f"EX{i}", owner=self.owner
            )

        with self.assertNumQueries(2):  # count + page of rows
            self.client.get("/api/projects/")

    def test_project_detail_does_not_scale_with_member_count(self):
        with self.assertNumQueries(3):  # project + members + their users
            self.client.get(f"/api/projects/{self.project.id}/")

    def test_issue_list_does_not_scale_with_issue_count(self):
        with self.assertNumQueries(3):  # project lookup + count + rows
            self.client.get(f"/api/projects/{self.project.id}/issues/")

    def test_issue_detail_does_not_scale_with_comment_count(self):
        with self.assertNumQueries(5):  # issue + comments + their authors
                                      # + activities + their actors
            self.client.get(f"/api/issues/{self.issues[0].id}/")
