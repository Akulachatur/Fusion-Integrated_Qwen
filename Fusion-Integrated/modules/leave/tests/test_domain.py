"""Domain tests: pure Python, no database, milliseconds."""
from datetime import date
from decimal import Decimal

import pytest

from modules.leave.domain import categories as cats
from modules.leave.domain import routing, statuses
from modules.leave.domain.counting import chargeable_days
from modules.leave.domain.errors import LeaveValidationError
from modules.leave.domain.overlap import Interval, find_overlap, overlaps
from modules.leave.domain.year_end import CARRY_FORWARD, CONVERT_TO_EL, LAPSE, outcome, vl_to_el

FRIDAY = date(2026, 1, 2)
SATURDAY = date(2026, 1, 3)
SUNDAY = date(2026, 1, 4)


# ---- counting: the continuous-day rule --------------------------------------
def test_el_counts_intervening_weekend():
    assert chargeable_days(category=cats.EL, start=FRIDAY, end=SUNDAY) == Decimal(3)


def test_cl_does_not_count_the_weekend():
    assert chargeable_days(category=cats.CL, start=FRIDAY, end=SUNDAY) == Decimal(1)


def test_a_closed_holiday_is_excluded_for_cl():
    days = chargeable_days(category=cats.CL, start=FRIDAY, end=FRIDAY,
                           closed_holidays=[FRIDAY])
    assert days == Decimal(0)


def test_half_day_cl_consumes_half_a_day():
    assert chargeable_days(category=cats.CL, start=FRIDAY, end=FRIDAY,
                           half_day=cats.FIRST_HALF) == Decimal("0.5")


def test_half_day_is_rejected_for_el():
    with pytest.raises(LeaveValidationError):
        chargeable_days(category=cats.EL, start=FRIDAY, end=FRIDAY,
                        half_day=cats.FIRST_HALF)


# ---- overlap: the half-day exception ----------------------------------------
def test_different_halves_of_the_same_day_do_not_overlap():
    first = Interval(FRIDAY, FRIDAY, cats.FIRST_HALF)
    second = Interval(FRIDAY, FRIDAY, cats.SECOND_HALF)
    assert overlaps(first, second) is False


def test_a_full_day_conflicts_with_a_half_day():
    assert overlaps(Interval(FRIDAY, FRIDAY, cats.NONE),
                    Interval(FRIDAY, FRIDAY, cats.FIRST_HALF)) is True


def test_disjoint_ranges_do_not_overlap():
    assert find_overlap(Interval(FRIDAY, FRIDAY),
                        [Interval(SATURDAY, SUNDAY)]) is None


# ---- year-end outcomes -------------------------------------------------------
def test_category_outcomes():
    assert outcome(cats.CL) == LAPSE
    assert outcome(cats.SCL) == LAPSE
    assert outcome(cats.EL) == CARRY_FORWARD
    assert outcome(cats.COL) == CARRY_FORWARD
    assert outcome(cats.VL) == CONVERT_TO_EL


def test_vl_to_el_preserves_the_fraction():
    assert vl_to_el(Decimal(5)) == Decimal("2.50")
    assert vl_to_el(Decimal(1)) == Decimal("0.50")
    assert vl_to_el(Decimal(0)) == Decimal(0)


# ---- state machine -----------------------------------------------------------
def test_any_pending_state_may_be_withdrawn():
    for state in statuses.PENDING:
        assert statuses.can_transition(state, statuses.WITHDRAWN)


def test_draft_cannot_jump_straight_to_approved():
    assert statuses.can_transition(statuses.DRAFT, statuses.APPROVED) is False


def test_an_approved_leave_may_only_become_cancelled():
    assert statuses.next_states(statuses.APPROVED) == (statuses.CANCELLED,)


# ---- routing -----------------------------------------------------------------
def test_substitute_required_lands_in_awaiting_substitute():
    assert routing.initial_state(is_director=False,
                                 substitute_required=True) == statuses.AWAITING_SUBSTITUTE


def test_director_without_substitute_self_sanctions():
    assert routing.initial_state(is_director=True,
                                 substitute_required=False) == statuses.AWAITING_DIRECTOR_SELF_SANCTION


def test_higher_sanction_skips_establishment_when_unconfigured():
    assert routing.after_unit_head(
        category=cats.EL, establishment_configured=False) == statuses.AWAITING_FINAL_SANCTION


def test_unit_head_final_categories_have_no_further_stage():
    with pytest.raises(ValueError):
        routing.after_unit_head(category=cats.CL, establishment_configured=False)
