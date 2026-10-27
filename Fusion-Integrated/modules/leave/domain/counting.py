"""Chargeable-day counting (PS §4, BR-EL-010-011).

EL, COL and VL count continuously: every calendar day inside the interval,
weekends and closed holidays included. CL, SCL and RH do not — only days that
are neither a weekend nor a closed holiday count. An approved half-day CL
consumes exactly 0.5 day.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, timedelta
from decimal import Decimal

from modules.leave.domain import categories
from modules.leave.domain.errors import LeaveValidationError


def iter_days(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _default_is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def chargeable_days(*, category: str, start: date, end: date,
                    half_day: str = categories.NONE,
                    closed_holidays: Iterable[date] = (),
                    is_weekend: Callable[[date], bool] = _default_is_weekend,
                    ) -> Decimal:
    """Days this request would consume if approved."""
    if end < start:
        raise LeaveValidationError("The end date cannot be before the start date.")

    if half_day != categories.NONE:
        if category not in categories.HALF_DAY_ALLOWED:
            raise LeaveValidationError(
                f"{categories.label(category)} does not support a half day.")
        if start != end:
            raise LeaveValidationError(
                "A half day must start and end on the same date.")
        return Decimal("0.5")

    if category in categories.CONTINUOUS_COUNT:
        return Decimal((end - start).days + 1)

    holidays = set(closed_holidays)
    counted = sum(
        1 for day in iter_days(start, end)
        if not is_weekend(day) and day not in holidays
    )
    return Decimal(counted)
