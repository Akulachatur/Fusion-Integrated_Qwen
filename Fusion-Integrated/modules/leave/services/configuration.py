"""Administrative configuration: policy, hierarchy, SLA and calendars.

Every writer here is idempotent and audited by whichever view calls it. There is
no draft/publish lifecycle for policy or hierarchy (adjudication G-03), but the
holiday/RH calendar does publish (EL-UC-015).
"""
from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from modules.leave.models import HierarchyStep, Holiday, HolidayCalendar, SlaConfig, VacationPeriod


@transaction.atomic
def set_policy(category: str, **fields) -> None:
    from modules.leave.models import LeavePolicyParameter

    allowed = {"annual_entitlement", "carries_forward", "continuous_counting",
               "half_day_allowed", "evidence_may_be_required", "is_active"}
    policy, _ = LeavePolicyParameter.objects.get_or_create(category=category)
    for key, value in fields.items():
        if key in allowed:
            setattr(policy, key, value)
    policy.save()


@transaction.atomic
def set_hierarchy(category: str, steps: list[dict]) -> None:
    """Replace a category's path. `steps` is [{seq, role, is_final}, …]."""
    HierarchyStep.objects.filter(category=category).delete()
    HierarchyStep.objects.bulk_create([
        HierarchyStep(category=category, seq=s["seq"], role=s["role"],
                      is_final=s.get("is_final", False))
        for s in steps
    ])


def establishment_configured(category: str) -> bool:
    return HierarchyStep.objects.filter(category=category, is_active=True,
                                        role="establishment").exists()


def resolve_final_role(category: str) -> str:
    step = (HierarchyStep.objects
            .filter(category=category, is_active=True, is_final=True)
            .order_by("seq").first())
    return step.role if step else "registrar"


@transaction.atomic
def set_sla(task_class: str, reminder_hours: int, escalation_hours: int) -> SlaConfig:
    row, _ = SlaConfig.objects.update_or_create(
        task_class=task_class,
        defaults={"reminder_hours": reminder_hours,
                  "escalation_hours": escalation_hours})
    return row


def sla_config(task_class: str) -> SlaConfig:
    return (SlaConfig.objects.filter(task_class=task_class).first()
            or SlaConfig(task_class=task_class))


@transaction.atomic
def publish_calendar(year: int, holidays: list[dict], note: str = "") -> HolidayCalendar:
    """Create or revise a year's calendar and make it effective (EL-UC-015).

    Until a replacement is published the previously published row remains
    governing (alternative flow A1).
    """
    calendar, _ = HolidayCalendar.objects.get_or_create(year=year)
    calendar.note = note or calendar.note
    calendar.status = "published"
    calendar.published_at = timezone.now()
    calendar.save()
    calendar.holidays.all().delete()
    Holiday.objects.bulk_create([
        Holiday(calendar=calendar, date=h["date"], name=h["name"],
                kind=h.get("kind", "closed"))
        for h in holidays
    ])
    return calendar


@transaction.atomic
def sync_vacation_periods(periods: list[dict]) -> int:
    """Project vacation periods from the external Academic Calendar (EXT-01).

    Replace-in-place rather than merge: the Academic Calendar is the source of
    truth and a removed period must disappear here too.
    """
    VacationPeriod.objects.all().delete()
    VacationPeriod.objects.bulk_create([
        VacationPeriod(start_date=p["start_date"], end_date=p["end_date"],
                       label=p.get("label", ""))
        for p in periods
    ])
    return len(periods)


def seed_default_hierarchy() -> int:
    """A working default path for every category, so routing never dead-ends."""
    defaults = {
        "CL": [{"seq": 1, "role": "unit_head", "is_final": True}],
        "RH": [{"seq": 1, "role": "unit_head", "is_final": True}],
        "SCL": [{"seq": 1, "role": "unit_head"},
                {"seq": 2, "role": "registrar", "is_final": True}],
        "EL": [{"seq": 1, "role": "unit_head"},
               {"seq": 2, "role": "establishment"},
               {"seq": 3, "role": "registrar", "is_final": True}],
        "COL": [{"seq": 1, "role": "unit_head"},
                {"seq": 2, "role": "establishment"},
                {"seq": 3, "role": "registrar", "is_final": True}],
        "VL": [{"seq": 1, "role": "unit_head"},
               {"seq": 2, "role": "establishment"},
               {"seq": 3, "role": "dean", "is_final": True}],
    }
    count = 0
    for category, steps in defaults.items():
        if not HierarchyStep.objects.filter(category=category).exists():
            set_hierarchy(category, steps)
            count += 1
    return count


def seed_default_sla() -> int:
    defaults = {
        "unit_head_review": (24, 48),
        "establishment_routing": (24, 48),
        "final_sanction": (48, 96),
        "resumption_review": (48, 96),
    }
    count = 0
    for task_class, (reminder, escalation) in defaults.items():
        _, created = SlaConfig.objects.get_or_create(
            task_class=task_class,
            defaults={"reminder_hours": reminder, "escalation_hours": escalation})
        count += int(created)
    return count


def parse_horizon(value: str | None) -> date:
    if not value:
        return timezone.now().date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value)).date()
