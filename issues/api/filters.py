import django_filters

from issues.models import Issue


class IssueFilter(django_filters.FilterSet):
    """Query filters for the issue list endpoints.

    `assignee_username` and `unassigned` exist because clients generally know a
    username or want "nobody", not a primary key.
    """

    status = django_filters.MultipleChoiceFilter(choices=Issue.Status.choices)
    priority = django_filters.MultipleChoiceFilter(choices=Issue.Priority.choices)
    type = django_filters.MultipleChoiceFilter(choices=Issue.Type.choices)

    assignee_username = django_filters.CharFilter(
        field_name="assignee__username",
        lookup_expr="iexact",
    )
    reporter_username = django_filters.CharFilter(
        field_name="reporter__username",
        lookup_expr="iexact",
    )
    project_key = django_filters.CharFilter(
        field_name="project__key",
        lookup_expr="iexact",
    )

    unassigned = django_filters.BooleanFilter(
        field_name="assignee",
        lookup_expr="isnull",
    )

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Issue
        fields = (
            "status",
            "priority",
            "type",
            "assignee",
            "reporter",
            "project",
        )
