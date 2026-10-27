"""Demo fixtures.

Lives in `devtools` rather than inside a module: seeding is cross-cutting and
would otherwise make one module import three others' models. `devtools` is a
tool, not a bounded context, so .importlinter exempts it explicitly.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from modules.directory.models import UserRef
from modules.leave.services import balances as leave_balances
from modules.leave.services import configuration as leave_config
from modules.placement.models import Application, Company, JobPosting


class Command(BaseCommand):
    help = "Load demo data (idempotent)"

    @transaction.atomic
    def handle(self, *args, **opts):
        for uid, name, kind, disc in [
            (1001, "Asha Verma", "student", "CSE"),
            (1002, "Bo Li", "student", "CSE"),
            (1003, "Chandra Rao", "student", "ECE"),
            (9001, "Dr. Meera Nair", "faculty", ""),
        ]:
            UserRef.objects.update_or_create(
                user_id=uid,
                defaults={"username": f"u{uid}", "display_name": name, "kind": kind,
                          "discipline": disc,
                          "batch_year": 2023 if kind == "student" else None},
            )

        acme, _ = Company.objects.update_or_create(
            slug="acme", defaults={"name": "Acme Corp", "sector": "IT",
                                       "tier_rank": 1, "status": "active"})

        posting, _ = JobPosting.objects.update_or_create(
            company=acme, title="SDE-1", placement_year="2026-27",
            defaults={
                "ctc_lpa": "18.00", "seats": 4, "status": "published",
                "eligibility_rule": {"all": [{"gte": ["cpi", 7.0]},
                                             {"in": ["discipline", ["CSE", "ECE"]]}]},
                "eligibility_rule_locked_at": timezone.now(),
                "opens_at": timezone.now(),
                "closes_at": timezone.now() + timedelta(days=14),
                "created_by_user_id": 9001,
            })

        for uid, status in [(1001, "submitted"), (1002, "under_review")]:
            Application.objects.update_or_create(
                posting=posting, user_id=uid,
                defaults={"status": status, "cpi_at_apply": "8.10",
                          "eligibility_snapshot": {"is_eligible": True},
                          "applied_at": timezone.now()})

        # ELM: baseline policy/hierarchy/SLA plus one published calendar, so the
        # leave module is usable straight after `make seed`.
        leave_balances.seed_default_policy()
        leave_config.seed_default_hierarchy()
        leave_config.seed_default_sla()
        year = timezone.now().date().year
        leave_config.publish_calendar(year, [
            {"date": date(year, 1, 26), "name": "Republic Day", "kind": "closed"},
            {"date": date(year, 8, 15), "name": "Independence Day", "kind": "closed"},
            {"date": date(year, 10, 2), "name": "Gandhi Jayanti", "kind": "closed"},
        ], note="Demo calendar")
        leave_config.sync_vacation_periods([
            {"start_date": date(year, 5, 15), "end_date": date(year, 6, 30),
             "label": "Summer vacation"},
        ])

        self.stdout.write(self.style.SUCCESS("demo data loaded"))
