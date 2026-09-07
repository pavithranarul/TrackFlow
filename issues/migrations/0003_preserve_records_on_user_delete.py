"""Stop deleting a user from deleting their issues and comments.

`Issue.reporter` and `Comment.author` were CASCADE, so removing a user erased
every issue they had filed and every comment they had written. That is data
loss in a system whose whole job is to keep a record. Both become SET_NULL,
matching `Issue.assignee` and `IssueActivity.actor`, which were already
written that way.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("issues", "0002_issue_rework"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="issue",
            name="reporter",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reported_issues",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="comment",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="comments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
