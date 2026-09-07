from issues.models import Comment, Issue
from projects.selectors.project_selector import get_projects_for_user


def _base_queryset():
    return Issue.objects.select_related(
        "project",
        "reporter",
        "assignee",
    )


def get_issues_for_user(user):
    """Every issue in a project the user can see.

    Issue visibility is derived from project visibility rather than duplicated,
    so the two can never disagree.
    """
    return _base_queryset().filter(
        project__in=get_projects_for_user(user).values("id")
    )


def get_issues_for_project(user, project):
    return get_issues_for_user(user).filter(project=project)


def get_issue_for_user(user, issue_id):
    """A single issue, or None when the user may not see its project.

    IssueDetailSerializer nests comments and the activity feed and reads a
    username from each, so those are prefetched with their people attached.
    """
    return (
        get_issues_for_user(user)
        .prefetch_related("comments__author", "activities__actor")
        .filter(id=issue_id)
        .first()
    )


def get_comments_for_issue(issue):
    return Comment.objects.filter(issue=issue).select_related("author")


def get_comment_for_user(user, comment_id):
    return (
        Comment.objects.select_related("author", "issue", "issue__project")
        .filter(
            id=comment_id,
            issue__project__in=get_projects_for_user(user).values("id"),
        )
        .first()
    )


def get_activities_for_issue(issue):
    return issue.activities.select_related("actor")
