"""Event-triggered SLA reminder and escalation (EL-UC-021, CFR-EL-031-032).

A reminder or escalation is issued only while the task is still pending; a task
closed by a decision is skipped rather than reminded. Time is the trigger, so a
scheduled task calls this.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

from modules.leave.models import LeaveTask
from modules.leave.services import configuration


def process(now: datetime | None = None) -> dict:
    now = now or timezone.now()
    report = {"reminded": 0, "escalated": 0, "skipped": 0}
    rows = LeaveTask.objects.filter(status="pending").select_related("request")
    for task in rows:
        config = configuration.sla_config(task.stage)
        age = now - task.created_at
        if task.escalated_at is not None:
            report["skipped"] += 1
            continue
        if age >= timedelta(hours=config.escalation_hours):
            task.escalated_at = now
            report["escalated"] += 1
        elif task.reminded_at is None and age >= timedelta(hours=config.reminder_hours):
            task.reminded_at = now
            report["reminded"] += 1
        else:
            report["skipped"] += 1
            continue
        task.save(update_fields=["reminded_at", "escalated_at", "updated_at"])
    return report
