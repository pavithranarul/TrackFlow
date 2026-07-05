from django.db import transaction

from projects.models import Project, ProjectMember


@transaction.atomic
def create_project(*, owner, validated_data):
    members = validated_data.pop("members", [])

    project = Project.objects.create(
        owner=owner,
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
    validated_data.pop("members", None)

    for field, value in validated_data.items():
        setattr(project, field, value)

    project.save()

    return project


@transaction.atomic
def delete_project(project):
    project.delete()