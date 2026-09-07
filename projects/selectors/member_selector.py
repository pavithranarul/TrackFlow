from projects.models import ProjectMember


def get_members_for_project(project):
    return (
        ProjectMember.objects.filter(project=project)
        .select_related("user", "project")
        .order_by("joined_at")
    )


def get_member(project, member_id):
    return get_members_for_project(project).filter(id=member_id).first()
