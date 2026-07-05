from django.db import models
from projects.models import Project

# Create your models here.
class Issues(models.Model):
    status_choices = [
        ("TODO", "todo"),
        ("IN_PROGRESS", "in_progress"),
        ("TESTING", "testing"),
        ("DONE", "done")
    ]
    priority_choices = [
        ("LOW", "low"),
        ("MEDIUM", "medium"),
        ("HIGH", "high"),
        ("URGENT", "urgent"),
        ("CRITICAL", "critical")
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    project = models.CharField()
    reporter = models.TextField()
    assignee = models.TextField()
    status = models.TextField(max_length=20, choices=status_choices)
    priority = models.TextField(max_length=20, choices=priority_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
