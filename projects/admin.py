from django.contrib import admin

from .models import Project, ProjectMember


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "key",
        "owner",
        "status",
        "visibility",
        "created_at",
    )

    search_fields = (
        "name",
        "key",
    )

    list_filter = (
        "status",
        "visibility",
    )


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "user",
        "role",
        "joined_at",
    )

    list_filter = (
        "role",
    )

    search_fields = (
        "project__name",
        "user__username",
    )