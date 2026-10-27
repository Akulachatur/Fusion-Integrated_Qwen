"""Event-triggered year-end processing (EL-UC-020, CFR-EL-028).

The year-end boundary is a trigger, not an actor: a scheduled task calls this.
Unused CL/RH/SCL lapse; unused EL/COL carry forward; unused faculty VL converts
to EL at 2:1 with fractions preserved.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from modules.leave.domain import categories
from modules.leave.domain.year_end import CARRY_FORWARD, CONVERT_TO_EL, LAPSE, outcome, vl_to_el
from modules.leave.models import LeaveBalance
from modules.leave.services import balances


def _available(row: LeaveBalance) -> Decimal:
    return row.entitled + row.carried_forward + row.adjusted - row.used


@transaction.atomic
def run(from_year: int, to_year: int) -> dict:
    """Apply every category's year-end outcome for one year boundary."""
    report = {"accounts": 0, "lapsed": 0, "carried": 0, "converted": 0,
              "exceptions": []}
    for row in LeaveBalance.objects.filter(year=from_year).order_by("user_id", "category"):
        report["accounts"] += 1
        available = _available(row)
        if available < 0:
            report["exceptions"].append(
                f"user {row.user_id} {row.category}: negative balance {available}")
            available = Decimal(0)
        if available == 0:
            continue

        action = outcome(row.category)
        if action == LAPSE:
            report["lapsed"] += 1
        elif action == CARRY_FORWARD:
            balances.carry_forward(row.user_id, row.category, from_year, to_year,
                                   available)
            report["carried"] += 1
        elif action == CONVERT_TO_EL:
            converted = vl_to_el(available)
            if converted > 0:
                balances.credit(row.user_id, categories.EL, to_year, converted)
            report["converted"] += 1
    return report
