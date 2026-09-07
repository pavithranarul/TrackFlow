from django.contrib import admin

from .models import Organization, OrgMember


class OrgMemberInline(admin.TabularInline):
    model = OrgMember
    extra = 1
    raw_id_fields = ("user",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "member_count", "project_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [OrgMemberInline]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()

    @admin.display(description="Projects")
    def project_count(self, obj):
        return obj.projects.count()


@admin.register(OrgMember)
class OrgMemberAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "joined_at")
    list_filter = ("role", "organization")
    search_fields = ("organization__name", "user__username")
    raw_id_fields = ("user",)
