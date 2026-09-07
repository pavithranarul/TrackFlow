from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0007_alter_project_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="issue_counter",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Highest issue number handed out for this project. "
                          "Bumped with an atomic F() update so two concurrent "
                          "creates can never be given the same number.",
            ),
        ),
    ]
