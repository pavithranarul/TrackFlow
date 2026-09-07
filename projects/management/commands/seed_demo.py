"""Populate a development database with a realistic sample of data.

    uv run manage.py seed_demo

Idempotent: re-running it wipes the demo users and their projects first, so it
can be used repeatedly while developing. It refuses to run when DEBUG is off,
because it creates accounts with known passwords.
"""

import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from issues.services.issue_service import (
    assign_issue,
    create_comment,
    create_issue,
    transition_issue,
)
from organizations.models import Organization, OrgMember
from organizations.services.org_service import create_organization
from projects.models import Project, ProjectMember
from projects.services.project_service import create_project

User = get_user_model()

DEMO_PASSWORD = "demo-passw0rd!"
DEMO_ORG_SLUG = "acme-corp"

PEOPLE = [
    ("ada", "Ada", "Lovelace", ProjectMember.Role.OWNER),
    ("grace", "Grace", "Hopper", ProjectMember.Role.MANAGER),
    ("alan", "Alan", "Turing", ProjectMember.Role.DEVELOPER),
    ("katherine", "Katherine", "Johnson", ProjectMember.Role.DEVELOPER),
    ("margaret", "Margaret", "Hamilton", ProjectMember.Role.VIEWER),
]

ISSUES = [
    ("Login page returns 500 on empty password", "BUG", "CRITICAL"),
    ("Add pagination to the project list", "FEATURE", "HIGH"),
    ("Upgrade Django to 5.2", "CHORE", "MEDIUM"),
    ("Search returns archived projects", "BUG", "HIGH"),
    ("Export issues as CSV", "FEATURE", "LOW"),
    ("Flaky test in the transition suite", "BUG", "MEDIUM"),
    ("Document the deployment steps", "CHORE", "LOW"),
    ("Add keyboard shortcuts to the board", "FEATURE", "URGENT"),
]

COMMENTS = [
    "Reproduced on staging.",
    "Picking this up today.",
    "Blocked on the schema change landing first.",
    "Fixed in the last deploy — please verify.",
    "Can we split this into two issues?",
]


class Command(BaseCommand):
    help = "Create demo users, projects and issues for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--issues",
            type=int,
            default=len(ISSUES),
            help="How many issues to create in the main project.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo creates accounts with a published password and will "
                "not run with DEBUG=False."
            )

        rng = random.Random(20260905)

        usernames = [p[0] for p in PEOPLE]
        # Deleting the organization cascades to its projects and issues.
        Organization.objects.filter(slug=DEMO_ORG_SLUG).delete()
        Project.objects.filter(owner__username__in=usernames).delete()
        User.objects.filter(username__in=usernames).delete()

        users = {}
        for username, first, last, _ in PEOPLE:
            users[username] = User.objects.create_user(
                username=username,
                password=DEMO_PASSWORD,
                email=f"{username}@example.com",
                first_name=first,
                last_name=last,
            )

        owner = users["ada"]

        organization = create_organization(
            validated_data={
                "name": "Acme Corp",
                "slug": DEMO_ORG_SLUG,
                "description": "Demo tenant. Every project below lives inside it.",
            },
            first_admin=owner,
        )

        for username in usernames:
            if username == "ada":
                continue
            OrgMember.objects.create(
                organization=organization,
                user=users[username],
                role=OrgMember.Role.ADMIN
                if username == "grace"
                else OrgMember.Role.MEMBER,
            )

        project = create_project(
            owner=owner,
            organization=organization,
            validated_data={
                "name": "TrackFlow",
                "key": "TRK",
                "description": "Dogfooding the tracker on itself.",
                "members": [
                    {"user": users[username], "role": role}
                    for username, _, _, role in PEOPLE
                    if username != "ada"
                ],
            },
        )

        public = create_project(
            owner=owner,
            organization=organization,
            validated_data={
                "name": "Design System",
                "key": "DS",
                "description": "A public project, readable by any signed-in user.",
                "visibility": Project.Visibility.PUBLIC,
            },
        )

        writers = [users["ada"], users["grace"], users["alan"], users["katherine"]]

        created = 0
        for title, kind, priority in ISSUES[: options["issues"]]:
            issue = create_issue(
                project=project,
                reporter=rng.choice(writers),
                validated_data={
                    "title": title,
                    "description": f"Auto-generated demo issue: {title}.",
                    "type": kind,
                    "priority": priority,
                },
            )
            created += 1

            if rng.random() < 0.7:
                assign_issue(
                    issue=issue,
                    actor=owner,
                    assignee=rng.choice(writers),
                )

            # Walk a random distance along the transition graph.
            for step in rng.choice(
                [
                    [],
                    ["IN_PROGRESS"],
                    ["IN_PROGRESS", "TESTING"],
                    ["IN_PROGRESS", "TESTING", "DONE"],
                ]
            ):
                transition_issue(
                    issue=issue, actor=rng.choice(writers), new_status=step
                )

            for _ in range(rng.randint(0, 2)):
                create_comment(
                    issue=issue,
                    author=rng.choice(writers),
                    body=rng.choice(COMMENTS),
                )

        create_issue(
            project=public,
            reporter=owner,
            validated_data={
                "title": "Publish the colour tokens",
                "type": "FEATURE",
                "priority": "MEDIUM",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded 1 organization, {len(PEOPLE)} users, 2 projects "
                f"and {created + 1} issues."
            )
        )
        self.stdout.write(
            f"\n  Organization:     {organization.name} ({organization.slug})"
            f"\n  Org admins:       ada, grace"
            f"\n  Log in as any of: {', '.join(usernames)}"
            f"\n  Password:         {DEMO_PASSWORD}"
            f"\n\n  {project.key} is PRIVATE with one member per role."
            f"\n  {public.key} is PUBLIC — readable by anyone in the org."
            f"\n\n  Try:  curl -s -X POST localhost:8000/api/auth/login/ \\"
            f"\n          -H 'Content-Type: application/json' \\"
            f"\n          -d '{{\"username\":\"ada\",\"password\":\"{DEMO_PASSWORD}\"}}'\n"
        )
