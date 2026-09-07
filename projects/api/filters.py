import django_filters

from projects.models import Project


class ProjectFilter(django_filters.FilterSet):
    """Query filters for the project list."""

    status = django_filters.MultipleChoiceFilter(choices=Project.Status.choices)
    visibility = django_filters.MultipleChoiceFilter(
        choices=Project.Visibility.choices
    )
    owner_username = django_filters.CharFilter(
        field_name="owner__username",
        lookup_expr="iexact",
    )
    key = django_filters.CharFilter(lookup_expr="iexact")
    organization_slug = django_filters.CharFilter(
        field_name="organization__slug",
        lookup_expr="iexact",
    )

    class Meta:
        model = Project
        fields = ("status", "visibility", "owner", "organization")
