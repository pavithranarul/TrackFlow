from django.contrib import admin

from .models import Comment, Issue, IssueActivity


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "title",
        "project",
        "type",
        "status",
        "priority",
        "assignee",
        "created_at",
    )
    list_filter = ("status", "priority", "type", "project")
    search_fields = ("title", "description", "number")
    raw_id_fields = ("reporter", "assignee")
    readonly_fields = ("number", "created_at", "updated_at", "closed_at")

    def get_queryset(self, request):
        # `key` reads project.key, so join it rather than firing a query per row.
        return super().get_queryset(request).select_related("project", "assignee")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "author", "created_at")
    search_fields = ("body",)
    raw_id_fields = ("issue", "author")


@admin.register(IssueActivity)
class IssueActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "actor", "action", "field", "created_at")
    list_filter = ("action",)
    raw_id_fields = ("issue", "actor")

    def has_add_permission(self, request):
        # The audit trail is written by the service layer only.
        return False

    def has_change_permission(self, request, obj=None):
        return False
