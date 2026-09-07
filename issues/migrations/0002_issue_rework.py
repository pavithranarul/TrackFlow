"""Replace the placeholder `Issues` model with the real `Issue` model.

The original model stored `project`, `reporter` and `assignee` as free text, so
there was no referential integrity and no way to query the issues belonging to
a project. Nothing can be salvaged by altering columns in place — text values
cannot be resolved to foreign keys — so the table is dropped and rebuilt.

That is only safe while the table is empty, which it was when this was written.
The guard below refuses to run rather than silently discarding rows.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def refuse_if_populated(apps, schema_editor):
    Issues = apps.get_model("issues", "Issues")

    count = Issues.objects.count()

    if count:
        raise RuntimeError(
            f"issues_issues holds {count} row(s). This migration drops the "
            "table, so it will not run against real data. Export the rows, "
            "re-import them against the new schema, then re-run."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("issues", "0001_initial"),
        ("projects", "0008_project_issue_counter"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(refuse_if_populated, migrations.RunPython.noop),
        migrations.DeleteModel(name="Issues"),
        migrations.CreateModel(
            name="Issue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField(help_text="Per-project counter. Combined with the project key to form the human-readable issue key.")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("type", models.CharField(choices=[("TASK", "Task"), ("BUG", "Bug"), ("FEATURE", "Feature"), ("CHORE", "Chore")], default="TASK", max_length=20)),
                ("status", models.CharField(choices=[("TODO", "To Do"), ("IN_PROGRESS", "In Progress"), ("TESTING", "Testing"), ("DONE", "Done")], default="TODO", max_length=20)),
                ("priority", models.CharField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("URGENT", "Urgent"), ("CRITICAL", "Critical")], default="MEDIUM", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("closed_at", models.DateTimeField(blank=True, help_text="Set when the issue enters DONE, cleared when it leaves.", null=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_issues", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issues", to="projects.project")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reported_issues", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("project", "number")},
            },
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to=settings.AUTH_USER_MODEL)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="issues.issue")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="IssueActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("CREATED", "Created"), ("STATUS_CHANGED", "Status changed"), ("ASSIGNED", "Assigned"), ("UNASSIGNED", "Unassigned"), ("PRIORITY_CHANGED", "Priority changed"), ("UPDATED", "Updated"), ("COMMENTED", "Commented")], max_length=30)),
                ("field", models.CharField(blank=True, max_length=50)),
                ("old_value", models.CharField(blank=True, max_length=200)),
                ("new_value", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issue_activities", to=settings.AUTH_USER_MODEL)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="issues.issue")),
            ],
            options={"ordering": ["-created_at"], "verbose_name_plural": "issue activities"},
        ),
        migrations.AddIndex(
            model_name="issue",
            index=models.Index(fields=["project", "status"], name="issues_issu_project_939acd_idx"),
        ),
        migrations.AddIndex(
            model_name="issue",
            index=models.Index(fields=["assignee"], name="issues_issu_assigne_32a375_idx"),
        ),
    ]
