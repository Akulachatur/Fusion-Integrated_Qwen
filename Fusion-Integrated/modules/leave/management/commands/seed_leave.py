"""Seed the leave module's default configuration.

Idempotent — safe to re-run on every deploy. The defaults come from the ELM
baseline (PS §3 and §7, EL-UC-014/EL-UC-018); an administrator changes them
through the API thereafter.
"""
from django.core.management.base import BaseCommand

from modules.leave.services import balances, configuration


class Command(BaseCommand):
    help = "Seed the default leave policy, hierarchy and SLA thresholds"

    def handle(self, *args, **options):
        policy = balances.seed_default_policy()
        hierarchy = configuration.seed_default_hierarchy()
        sla = configuration.seed_default_sla()
        self.stdout.write(self.style.SUCCESS(
            f"leave: {policy} policy row(s), {hierarchy} hierarchy set(s), "
            f"{sla} SLA row(s)"))
