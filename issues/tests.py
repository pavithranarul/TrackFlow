"""Tests for the issue domain: CRUD, the transition graph, assignment,
comments, the audit trail, filtering, and the role rules that gate all of it.
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from issues.models import Comment, Issue, IssueActivity
from issues.services.issue_service import (
    TransitionNotAllowed,
    create_issue,
    transition_issue,
)
from organizations.testing import make_org, make_user
from projects.models import Project, ProjectMember

User = get_user_model()


class IssueTestMixin:
    """A project with one member per role, plus a stranger."""

    def build_world(self):
        self.org = make_org()
        self.owner = make_user("i_owner", org=self.org)
        self.manager = make_user("i_manager", org=self.org)
        self.developer = make_user("i_dev", org=self.org)
        self.viewer = make_user("i_viewer", org=self.org)
        self.stranger = make_user("i_stranger", org=self.org)

        self.project = Project.objects.create(
            organization=self.org, name="Issue Project", key="ISS", owner=self.owner
        )
        for user, role in (
            (self.owner, ProjectMember.Role.OWNER),
            (self.manager, ProjectMember.Role.MANAGER),
            (self.developer, ProjectMember.Role.DEVELOPER),
            (self.viewer, ProjectMember.Role.VIEWER),
        ):
            ProjectMember.objects.create(project=self.project, user=user, role=role)

        self.list_url = f"/api/projects/{self.project.id}/issues/"

    def make_issue(self, **kwargs):
        # reporter is a create_issue argument, not part of validated_data, so
        # it has to come out of kwargs before the rest is merged in.
        reporter = kwargs.pop("reporter", self.developer)

        data = {"title": "An issue", "description": "body"}
        data.update(kwargs)

        return create_issue(
            project=self.project,
            reporter=reporter,
            validated_data=data,
        )


class IssueKeyTests(IssueTestMixin, APITestCase):
    """The per-project counter behind TRK-1, TRK-2, ..."""

    def setUp(self):
        self.build_world()

    def test_first_issue_is_number_one(self):
        issue = self.make_issue()
        self.assertEqual(issue.number, 1)
        self.assertEqual(issue.key, "ISS-1")

    def test_numbers_increment_within_a_project(self):
        keys = [self.make_issue().key for _ in range(3)]
        self.assertEqual(keys, ["ISS-1", "ISS-2", "ISS-3"])

    def test_numbering_is_independent_per_project(self):
        other = Project.objects.create(
            organization=self.org, name="Other", key="OTH", owner=self.owner
        )

        self.make_issue()
        self.make_issue()

        second_project_issue = create_issue(
            project=other,
            reporter=self.owner,
            validated_data={"title": "First over here"},
        )

        self.assertEqual(second_project_issue.number, 1)
        self.assertEqual(second_project_issue.key, "OTH-1")

    def test_counter_is_not_reused_after_a_delete(self):
        first = self.make_issue()
        first.delete()
        second = self.make_issue()

        # The counter lives on the project, not on max(number), so a deleted
        # issue's number is retired rather than handed out again.
        self.assertEqual(second.number, 2)


class IssueCreateAPITests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

    def test_developer_can_create_an_issue(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(
            self.list_url, {"title": "Fix the thing"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["key"], "ISS-1")
        self.assertEqual(response.data["reporter"]["username"], "i_dev")
        self.assertEqual(response.data["status"], "TODO")
        self.assertEqual(response.data["priority"], "MEDIUM")

    def test_viewer_cannot_create_an_issue(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(self.list_url, {"title": "Nope"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Issue.objects.count(), 0)

    def test_stranger_gets_404_for_a_private_project(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.post(self.list_url, {"title": "Nope"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reporter_cannot_be_spoofed(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(
            self.list_url,
            {"title": "Spoof", "reporter": self.owner.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reporter"]["username"], "i_dev")

    def test_create_writes_an_activity_row(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(self.list_url, {"title": "Logged"}, format="json")

        activities = IssueActivity.objects.filter(issue_id=response.data["id"])
        self.assertEqual(activities.count(), 1)
        self.assertEqual(activities.first().action, IssueActivity.Action.CREATED)

    def test_creating_with_an_assignee_logs_the_assignment(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(
            self.list_url,
            {"title": "Assigned at birth", "assignee": self.manager.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            IssueActivity.objects.filter(
                issue_id=response.data["id"],
                action=IssueActivity.Action.ASSIGNED,
            ).exists()
        )

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class IssueVisibilityTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()

    def test_member_can_list_issues(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_stranger_cannot_see_issues_of_a_private_project(self):
        self.client.force_authenticate(user=self.stranger)

        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            self.client.get(f"/api/issues/{self.issue.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_stranger_can_read_issues_of_a_public_project(self):
        self.project.visibility = Project.Visibility.PUBLIC
        self.project.save()

        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f"/api/issues/{self.issue.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stranger_cannot_edit_issues_of_a_public_project(self):
        self.project.visibility = Project.Visibility.PUBLIC
        self.project.save()

        self.client.force_authenticate(user=self.stranger)
        response = self.client.patch(
            f"/api/issues/{self.issue.id}/", {"title": "Hijacked"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_global_list_spans_projects_and_excludes_invisible_ones(self):
        other = Project.objects.create(
            organization=self.org, name="Hidden", key="HID", owner=self.stranger
        )
        create_issue(
            project=other, reporter=self.stranger, validated_data={"title": "Secret"}
        )

        self.client.force_authenticate(user=self.developer)
        response = self.client.get("/api/issues/")

        titles = {i["title"] for i in response.data["results"]}
        self.assertNotIn("Secret", titles)
        self.assertEqual(response.data["count"], 1)


class IssueTransitionTests(IssueTestMixin, APITestCase):
    """The status graph: TODO -> IN_PROGRESS -> TESTING -> DONE, with
    backwards steps allowed one at a time."""

    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.url = f"/api/issues/{self.issue.id}/transition/"
        self.client.force_authenticate(user=self.developer)

    def _transition(self, to):
        return self.client.post(self.url, {"status": to}, format="json")

    def test_todo_to_in_progress_is_allowed(self):
        response = self._transition("IN_PROGRESS")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "IN_PROGRESS")

    def test_todo_straight_to_done_is_rejected(self):
        response = self._transition("DONE")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "TODO")

    def test_full_happy_path(self):
        for step in ("IN_PROGRESS", "TESTING", "DONE"):
            self.assertEqual(self._transition(step).status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "DONE")

    def test_reaching_done_sets_closed_at(self):
        for step in ("IN_PROGRESS", "TESTING", "DONE"):
            self._transition(step)

        self.issue.refresh_from_db()
        self.assertIsNotNone(self.issue.closed_at)

    def test_reopening_clears_closed_at(self):
        for step in ("IN_PROGRESS", "TESTING", "DONE"):
            self._transition(step)

        self._transition("IN_PROGRESS")

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "IN_PROGRESS")
        self.assertIsNone(self.issue.closed_at)

    def test_transition_to_the_same_status_is_a_no_op(self):
        response = self._transition("TODO")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            IssueActivity.objects.filter(
                issue=self.issue, action=IssueActivity.Action.STATUS_CHANGED
            ).count(),
            0,
        )

    def test_transition_writes_an_activity_row(self):
        self._transition("IN_PROGRESS")

        activity = IssueActivity.objects.filter(
            issue=self.issue, action=IssueActivity.Action.STATUS_CHANGED
        ).first()

        self.assertIsNotNone(activity)
        self.assertEqual(activity.old_value, "TODO")
        self.assertEqual(activity.new_value, "IN_PROGRESS")
        self.assertEqual(activity.actor, self.developer)

    def test_invalid_status_value_is_rejected(self):
        self.assertEqual(
            self._transition("NONSENSE").status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_viewer_cannot_transition(self):
        self.client.force_authenticate(user=self.viewer)
        self.assertEqual(
            self._transition("IN_PROGRESS").status_code, status.HTTP_403_FORBIDDEN
        )

    def test_detail_advertises_the_allowed_transitions(self):
        response = self.client.get(f"/api/issues/{self.issue.id}/")
        self.assertEqual(response.data["allowed_transitions"], ["IN_PROGRESS"])

    def test_service_raises_rather_than_silently_ignoring(self):
        with self.assertRaises(TransitionNotAllowed):
            transition_issue(
                issue=self.issue, actor=self.developer, new_status="DONE"
            )


class IssueAssignmentTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.url = f"/api/issues/{self.issue.id}/assign/"
        self.client.force_authenticate(user=self.manager)

    def test_assign_to_a_member(self):
        response = self.client.post(
            self.url, {"assignee": self.developer.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.assignee, self.developer)

    def test_assigning_logs_activity(self):
        self.client.post(self.url, {"assignee": self.developer.id}, format="json")

        self.assertTrue(
            IssueActivity.objects.filter(
                issue=self.issue,
                action=IssueActivity.Action.ASSIGNED,
                new_value="i_dev",
            ).exists()
        )

    def test_unassign_with_null(self):
        self.issue.assignee = self.developer
        self.issue.save()

        response = self.client.post(self.url, {"assignee": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.assignee)

    def test_unassigning_logs_activity(self):
        self.issue.assignee = self.developer
        self.issue.save()

        self.client.post(self.url, {"assignee": None}, format="json")

        self.assertTrue(
            IssueActivity.objects.filter(
                issue=self.issue, action=IssueActivity.Action.UNASSIGNED
            ).exists()
        )

    def test_cannot_assign_to_a_non_member(self):
        response = self.client.post(
            self.url, {"assignee": self.stranger.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.assignee)

    def test_viewer_cannot_assign(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(
            self.url, {"assignee": self.developer.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class IssueUpdateDeleteTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.issue = self.make_issue(reporter=self.developer)
        self.url = f"/api/issues/{self.issue.id}/"

    def test_developer_can_patch(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.patch(self.url, {"title": "Renamed"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "Renamed")

    def test_viewer_cannot_patch(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(self.url, {"title": "Nope"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "An issue")

    def test_patch_cannot_change_status(self):
        """Status has transition rules, so PATCH must not be a way around
        them."""
        self.client.force_authenticate(user=self.developer)
        self.client.patch(self.url, {"status": "DONE"}, format="json")

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "TODO")

    def test_patch_logs_field_changes(self):
        self.client.force_authenticate(user=self.developer)
        self.client.patch(self.url, {"priority": "URGENT"}, format="json")

        self.assertTrue(
            IssueActivity.objects.filter(
                issue=self.issue,
                action=IssueActivity.Action.PRIORITY_CHANGED,
                old_value="MEDIUM",
                new_value="URGENT",
            ).exists()
        )

    def test_patch_with_an_unchanged_value_logs_nothing(self):
        self.client.force_authenticate(user=self.developer)
        before = IssueActivity.objects.filter(issue=self.issue).count()

        self.client.patch(self.url, {"title": "An issue"}, format="json")

        self.assertEqual(
            IssueActivity.objects.filter(issue=self.issue).count(), before
        )

    def test_reporter_can_delete_their_own_issue(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Issue.objects.filter(id=self.issue.id).exists())

    def test_manager_can_delete_someone_elses_issue(self):
        self.client.force_authenticate(user=self.manager)
        self.assertEqual(
            self.client.delete(self.url).status_code, status.HTTP_204_NO_CONTENT
        )

    def test_viewer_cannot_delete(self):
        self.client.force_authenticate(user=self.viewer)
        self.assertEqual(
            self.client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_deleting_a_project_cascades_to_its_issues(self):
        self.project.delete()
        self.assertFalse(Issue.objects.filter(id=self.issue.id).exists())

    def test_deleting_a_user_keeps_the_issues_they_touched(self):
        """SET_NULL, not CASCADE — losing a person must not lose the record of
        the work. Both the assignee and the reporter link go null and the issue
        itself survives."""
        self.issue.assignee = self.manager
        self.issue.save()

        self.manager.delete()
        self.developer.delete()  # the reporter

        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.assignee)
        self.assertIsNone(self.issue.reporter)
        self.assertEqual(self.issue.title, "An issue")

    def test_deleting_a_user_keeps_their_comments(self):
        from issues.services.issue_service import create_comment

        comment = create_comment(
            issue=self.issue, author=self.manager, body="worth keeping"
        )

        self.manager.delete()

        comment.refresh_from_db()
        self.assertIsNone(comment.author)
        self.assertEqual(comment.body, "worth keeping")

    def test_orphaned_issue_still_serializes(self):
        """A null reporter must not break the detail endpoint."""
        self.developer.delete()

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["reporter"])


class CommentTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.url = f"/api/issues/{self.issue.id}/comments/"

    def test_member_can_comment(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.post(self.url, {"body": "Looking at it"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"]["username"], "i_dev")
        self.assertEqual(response.data["body"], "Looking at it")

    def test_viewer_cannot_comment(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(self.url, {"body": "Nope"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_commenting_logs_activity(self):
        self.client.force_authenticate(user=self.developer)
        self.client.post(self.url, {"body": "Noted"}, format="json")

        self.assertTrue(
            IssueActivity.objects.filter(
                issue=self.issue, action=IssueActivity.Action.COMMENTED
            ).exists()
        )

    def test_comments_are_listed_oldest_first(self):
        self.client.force_authenticate(user=self.developer)
        for body in ("first", "second", "third"):
            self.client.post(self.url, {"body": body}, format="json")

        response = self.client.get(self.url)
        bodies = [c["body"] for c in response.data["results"]]
        self.assertEqual(bodies, ["first", "second", "third"])

    def test_author_can_edit_their_comment(self):
        self.client.force_authenticate(user=self.developer)
        comment_id = self.client.post(
            self.url, {"body": "typo"}, format="json"
        ).data["id"]

        response = self.client.patch(
            f"/api/comments/{comment_id}/", {"body": "fixed"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Comment.objects.get(id=comment_id).body, "fixed")

    def test_other_member_cannot_edit_someone_elses_comment(self):
        self.client.force_authenticate(user=self.developer)
        comment_id = self.client.post(
            self.url, {"body": "mine"}, format="json"
        ).data["id"]

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            f"/api/comments/{comment_id}/", {"body": "not yours"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Comment.objects.get(id=comment_id).body, "mine")

    def test_manager_can_delete_someone_elses_comment(self):
        """Moderation: a manager may remove a comment without being able to
        rewrite it."""
        self.client.force_authenticate(user=self.developer)
        comment_id = self.client.post(
            self.url, {"body": "spam"}, format="json"
        ).data["id"]

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(f"/api/comments/{comment_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(id=comment_id).exists())

    def test_developer_cannot_delete_someone_elses_comment(self):
        self.client.force_authenticate(user=self.manager)
        comment_id = self.client.post(
            self.url, {"body": "managers words"}, format="json"
        ).data["id"]

        self.client.force_authenticate(user=self.developer)
        self.assertEqual(
            self.client.delete(f"/api/comments/{comment_id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_stranger_cannot_reach_comments(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_deleting_an_issue_cascades_to_comments(self):
        self.client.force_authenticate(user=self.developer)
        self.client.post(self.url, {"body": "bye"}, format="json")

        self.issue.delete()
        self.assertEqual(Comment.objects.count(), 0)


class ActivityFeedTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.client.force_authenticate(user=self.developer)

    def test_feed_is_newest_first_and_covers_every_action(self):
        self.client.post(
            f"/api/issues/{self.issue.id}/transition/",
            {"status": "IN_PROGRESS"},
            format="json",
        )
        self.client.post(
            f"/api/issues/{self.issue.id}/assign/",
            {"assignee": self.manager.id},
            format="json",
        )
        self.client.post(
            f"/api/issues/{self.issue.id}/comments/", {"body": "hi"}, format="json"
        )

        response = self.client.get(f"/api/issues/{self.issue.id}/activity/")
        actions = [a["action"] for a in response.data["results"]]

        self.assertEqual(actions[-1], "CREATED")
        self.assertEqual(
            set(actions),
            {"CREATED", "STATUS_CHANGED", "ASSIGNED", "COMMENTED"},
        )

    def test_activity_is_read_only_over_the_api(self):
        response = self.client.post(
            f"/api/issues/{self.issue.id}/activity/",
            {"action": "CREATED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class IssueFilterTests(IssueTestMixin, APITestCase):
    def setUp(self):
        self.build_world()

        self.todo = self.make_issue(title="Todo item", priority="LOW")
        self.urgent = self.make_issue(title="Urgent bug", priority="URGENT", type="BUG")
        self.assigned = self.make_issue(title="Assigned work")
        self.assigned.assignee = self.developer
        self.assigned.save()

        self.client.force_authenticate(user=self.developer)

    def _keys(self, query):
        response = self.client.get(f"{self.list_url}?{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {i["title"] for i in response.data["results"]}

    def test_filter_by_priority(self):
        self.assertEqual(self._keys("priority=URGENT"), {"Urgent bug"})

    def test_filter_by_type(self):
        self.assertEqual(self._keys("type=BUG"), {"Urgent bug"})

    def test_filter_by_assignee_username(self):
        self.assertEqual(self._keys("assignee_username=i_dev"), {"Assigned work"})

    def test_filter_unassigned(self):
        self.assertEqual(
            self._keys("unassigned=true"), {"Todo item", "Urgent bug"}
        )

    def test_search_matches_title(self):
        self.assertEqual(self._keys("search=urgent"), {"Urgent bug"})

    def test_multiple_status_values(self):
        self.urgent.status = "IN_PROGRESS"
        self.urgent.save()

        self.assertEqual(
            self._keys("status=TODO&status=IN_PROGRESS"),
            {"Todo item", "Urgent bug", "Assigned work"},
        )

    def test_ordering(self):
        response = self.client.get(f"{self.list_url}?ordering=number")
        numbers = [i["key"] for i in response.data["results"]]
        self.assertEqual(numbers, ["ISS-1", "ISS-2", "ISS-3"])


class SerializerNullHandlingTests(IssueTestMixin, APITestCase):
    """Nullable relations must serialize as null rather than disappearing.

    DRF skips a field whose dotted source traverses a None, which silently
    changes the response shape depending on the data. Clients cannot code
    against that, so every nullable traversal carries an explicit default.
    """

    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.client.force_authenticate(user=self.developer)

    def test_list_always_includes_assignee_key(self):
        response = self.client.get(self.list_url)
        item = response.data["results"][0]

        self.assertIn("assignee", item)
        self.assertIsNone(item["assignee"])

    def test_list_always_includes_reporter_key(self):
        self.developer.delete()  # orphans the issue's reporter

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.list_url)
        item = response.data["results"][0]

        self.assertIn("reporter", item)
        self.assertIsNone(item["reporter"])

    def test_activity_always_includes_actor_key(self):
        response = self.client.get(f"/api/issues/{self.issue.id}/activity/")
        entry = response.data["results"][0]

        self.assertIn("actor", entry)
        self.assertEqual(entry["actor"], "i_dev")

    def test_transition_error_is_readable(self):
        """The message goes to an API client, so it must not leak Python
        enum reprs like Issue.Status.IN_PROGRESS."""
        response = self.client.post(
            f"/api/issues/{self.issue.id}/transition/",
            {"status": "DONE"},
            format="json",
        )

        message = str(response.data["status"])
        self.assertIn("IN_PROGRESS", message)
        self.assertNotIn("Issue.Status", message)


class ErrorShapeTests(IssueTestMixin, APITestCase):
    """Field errors are lists of strings, matching what DRF produces for
    serializer validation. A bare string would make `errors.status[0]` return
    a single character in a client."""

    def setUp(self):
        self.build_world()
        self.issue = self.make_issue()
        self.client.force_authenticate(user=self.developer)

    def test_transition_error_is_a_list(self):
        response = self.client.post(
            f"/api/issues/{self.issue.id}/transition/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["status"], list)
        self.assertIn("IN_PROGRESS", response.data["status"][0])

    def test_assignee_error_is_a_list(self):
        response = self.client.post(
            f"/api/issues/{self.issue.id}/assign/",
            {"assignee": self.stranger.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data["assignee"], list)

    def test_matches_serializer_error_shape(self):
        """A plain serializer error, for comparison — the two must look the
        same to a client."""
        response = self.client.post(
            self.list_url, {"title": ""}, format="json"
        )
        self.assertIsInstance(response.data["title"], list)
