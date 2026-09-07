from django.db import transaction

from projects.models import Project, ProjectMember


@transaction.atomic
def create_project(*, owner, organization, validated_data):
    members = validated_data.pop("members", [])
    validated_data.pop("organization", None)

    project = Project.objects.create(
        owner=owner,
        organization=organization,
        **validated_data,
    )

    ProjectMember.objects.create(
        project=project,
        user=owner,
        role=ProjectMember.Role.OWNER,
    )

    for member in members:
        if member["user"] == owner:
            continue

        ProjectMember.objects.create(
            project=project,
            user=member["user"],
            role=member["role"],
        )

    return project


@transaction.atomic
def update_project(*, project, validated_data):
    # A project cannot be moved between tenants: its issues, members and
    # history all belong to the organization it was created in.
    validated_data.pop("members", None)
    validated_data.pop("organization", None)

    for field, value in validated_data.items():
        setattr(project, field, value)

    project.save()

    return project


@transaction.atomic
def delete_project(project):
    project.delete()