"""Bring the `key` column in line with the model.

Migration 0006 added Project.key as nullable and blankable, but the model has
always declared it `CharField(max_length=10, unique=True)` with neither null
nor blank. The two had drifted apart; this closes the gap.

Written by hand rather than generated because `makemigrations` insists on a
default for the null -> not-null transition. No default is needed: `key`
identifies a project's board (TRK, OPS, ...) and there is no sensible value to
invent for a row that lacks one, so the accompanying data migration refuses to
guess and instead fails loudly if any such row exists.
"""

from django.db import migrations, models


def forbid_null_keys(apps, schema_editor):
    Project = apps.get_model("projects", "Project")

    offenders = Project.objects.filter(
        models.Q(key__isnull=True) | models.Q(key="")
    )

    if offenders.exists():
        raise RuntimeError(
            "Cannot make Project.key non-nullable: "
            f"{offenders.count()} project(s) have no key "
            f"(ids: {list(offenders.values_list('id', flat=True))}). "
            "Assign each one a unique key before running this migration."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_alter_project_options_and_more"),
    ]

    operations = [
        migrations.RunPython(
            forbid_null_keys,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="project",
            name="key",
            field=models.CharField(max_length=10, unique=True),
        ),
    ]
