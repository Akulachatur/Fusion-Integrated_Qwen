"""Per-person leave accounts (CFR-EL-004-009).

The balance for a year is created lazily from the current configured policy and
then only ever moved through this module, so every debit has a matching audit
event in `services.leaves`.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from modules.leave.domain import categories
from modules.leave.models import LeaveBalance, LeavePolicyParameter

#: Baseline entitlements from PS §3. Seeded once; the policy table is the
#: current configured value thereafter (EL-UC-014).
DEFAULT_POLICY = {
    categories.CL: {"annual_entitlement": Decimal("8"), "carries_forward": False,
                    "continuous_counting": False, "half_day_allowed": True},
    categories.RH: {"annual_entitlement": Decimal("2"), "carries_forward": False,
                    "continuous_counting": False, "half_day_allowed": False},
    categories.SCL: {"annual_entitlement": Decimal("15"), "carries_forward": False,
                     "continuous_counting": False, "half_day_allowed": False},
    categories.EL: {"annual_entitlement": Decimal("30"), "carries_forward": True,
                    "continuous_counting": True, "half_day_allowed": False},
    categories.COL: {"annual_entitlement": Decimal("20"), "carries_forward": True,
                     "continuous_counting": True, "half_day_allowed": False,
                     "evidence_may_be_required": True},
    categories.VL: {"annual_entitlement": Decimal("60"), "carries_forward": False,
                    "continuous_counting": True, "half_day_allowed": False},
}


def seed_default_policy() -> int:
    created = 0
    for category, fields in DEFAULT_POLICY.items():
        _, was_created = LeavePolicyParameter.objects.get_or_create(
            category=category, defaults=fields)
        created += int(was_created)
    return created


def policy_for(category: str) -> LeavePolicyParameter:
    return (LeavePolicyParameter.objects.filter(category=category).first()
            or LeavePolicyParameter(category=category,
                                    **DEFAULT_POLICY.get(category, {})))


@transaction.atomic
def ensure_year(user_id: int, year: int) -> None:
    """Create the year's rows on first touch, entitled from the policy."""
    for category in categories.CATEGORIES:
        LeaveBalance.objects.get_or_create(
            user_id=user_id, category=category, year=year,
            defaults={"entitled": policy_for(category).annual_entitlement},
        )


def balances_for(user_id: int, year: int) -> list[LeaveBalance]:
    return list(LeaveBalance.objects.filter(user_id=user_id, year=year)
                .order_by("category"))


def available(user_id: int, category: str, year: int) -> Decimal:
    ensure_year(user_id, year)
    row = LeaveBalance.objects.get(user_id=user_id, category=category, year=year)
    return row.available


@transaction.atomic
def charge(user_id: int, category: str, year: int, days: Decimal) -> LeaveBalance:
    ensure_year(user_id, year)
    row = (LeaveBalance.objects.select_for_update()
           .get(user_id=user_id, category=category, year=year))
    row.used = row.used + Decimal(days)
    row.save(update_fields=["used", "updated_at"])
    return row


@transaction.atomic
def restore(user_id: int, category: str, year: int, days: Decimal) -> LeaveBalance:
    ensure_year(user_id, year)
    row = (LeaveBalance.objects.select_for_update()
           .get(user_id=user_id, category=category, year=year))
    row.used = max(Decimal(0), row.used - Decimal(days))
    row.save(update_fields=["used", "updated_at"])
    return row


@transaction.atomic
def adjust(user_id: int, category: str, year: int, delta: Decimal) -> LeaveBalance:
    ensure_year(user_id, year)
    row = (LeaveBalance.objects.select_for_update()
           .get(user_id=user_id, category=category, year=year))
    row.adjusted = row.adjusted + Decimal(delta)
    row.save(update_fields=["adjusted", "updated_at"])
    return row


@transaction.atomic
def credit(user_id: int, category: str, year: int, days: Decimal) -> LeaveBalance:
    """Add to the entitled column — used by year-end carry/conversion."""
    ensure_year(user_id, year)
    row = (LeaveBalance.objects.select_for_update()
           .get(user_id=user_id, category=category, year=year))
    row.entitled = row.entitled + Decimal(days)
    row.save(update_fields=["entitled", "updated_at"])
    return row


@transaction.atomic
def carry_forward(user_id: int, category: str, from_year: int, to_year: int,
                  days: Decimal) -> None:
    if days <= 0:
        return
    ensure_year(user_id, to_year)
    row = (LeaveBalance.objects.select_for_update()
           .get(user_id=user_id, category=category, year=to_year))
    row.carried_forward = row.carried_forward + Decimal(days)
    row.save(update_fields=["carried_forward", "updated_at"])
