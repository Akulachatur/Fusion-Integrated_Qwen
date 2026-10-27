"""Scheduled work.

Ids only in arguments, never ORM objects. Everything is idempotent, because
`acks_late` means a task can run twice if a worker dies mid-flight.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

log = logging.getLogger("fusion.leave.tasks")


@shared_task(
    name="leave.run_year_end",
    acks_late=True, reject_on_worker_lost=True,
    soft_time_limit=270, time_limit=300,
)
def run_year_end(from_year: int | None = None, to_year: int | None = None) -> dict:
    """EL-UC-020: apply the year-end outcomes for one boundary."""
    from modules.leave.services import year_end

    year = timezone.now().date().year
    report = year_end.run(from_year or year - 1, to_year or year)
    log.info("leave.year_end %s", report)
    return report


@shared_task(
    name="leave.process_sla",
    acks_late=True, reject_on_worker_lost=True,
    soft_time_limit=120, time_limit=150,
)
def process_sla() -> dict:
    """EL-UC-021: remind or escalate any actionable task past its threshold."""
    from modules.leave.services import sla

    report = sla.process()
    if report["reminded"] or report["escalated"]:
        log.info("leave.sla %s", report)
    return report
