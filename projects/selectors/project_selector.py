from projects.models import Project


def get_projects():
    return Project.objects.all()


def get_project(project_id):
    return Project.objects.filter(id=project_id).first()


def get_projects_for_user(user):
    return Project.objects.filter(members__user=user).distinct()