"""Impermissible-overlap detection (BR-EL-012, BR-EL-034).

A new request must not overlap the applicant's active pending or approved
leave. First-half and second-half CL on the same date are not an overlap when
they occupy different halves.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from modules.leave.domain import categories


@dataclass(frozen=True)
class Interval:
    """One existing active leave interval, reduced to what overlap needs."""

    start: date
    end: date
    half_day: str = categories.NONE


def _same_day_halves_apart(a: Interval, b: Interval) -> bool:
    if not (a.start == a.end == b.start == b.end):
        return False
    return {a.half_day, b.half_day} == {categories.FIRST_HALF, categories.SECOND_HALF}


def overlaps(a: Interval, b: Interval) -> bool:
    if a.end < b.start or b.end < a.start:
        return False
    return not _same_day_halves_apart(a, b)


def find_overlap(candidate: Interval,
                 existing: Iterable[Interval]) -> Interval | None:
    for other in existing:
        if overlaps(candidate, other):
            return other
    return None
