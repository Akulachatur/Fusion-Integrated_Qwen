"""Reads over the holiday/RH calendar and the projected vacation periods.

Ownership filtering is not needed here — calendars are public reference data.
"""
from __future__ import annotations

from datetime import date

from modules.leave.models import Holiday, HolidayCalendar, VacationPeriod


def published_calendar(year: int) -> HolidayCalendar | None:
    """The currently effective published calendar, or None (BR-EL-031)."""
    return (HolidayCalendar.objects
            .filter(year=year, status="published")
            .order_by("-published_at")
            .first())


def holidays_for(year: int, *, kind: str | None = None) -> list[Holiday]:
    calendar = published_calendar(year)
    if calendar is None:
        return []
    rows = calendar.holidays.all()
    if kind is not None:
        rows = rows.filter(kind=kind)
    return list(rows)


def closed_holidays(year: int) -> set[date]:
    return {h.date for h in holidays_for(year, kind="closed")}


def restricted_holidays(year: int) -> set[date]:
    return {h.date for h in holidays_for(year, kind="restricted")}


def is_restricted_holiday(day: date) -> bool:
    return day in restricted_holidays(day.year)


def vacation_periods(start: date, end: date):
    return (VacationPeriod.objects
            .filter(start_date__lte=end, end_date__gte=start)
            .order_by("start_date"))


def covers_vacation(start: date, end: date) -> bool:
    """True only when the whole requested interval sits inside a vacation
    period (BR-EL-006)."""
    for period in VacationPeriod.objects.all():
        if period.start_date <= start and period.end_date >= end:
            return True
    return False
