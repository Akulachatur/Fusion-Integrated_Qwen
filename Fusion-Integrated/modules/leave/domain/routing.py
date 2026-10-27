"""Route resolution (PS §7, BR-EL-017-020).

The processing path depends on the applicant, the category and the current
hierarchy configuration — not on hard-coded role names in the view. These
functions are the single statement of that routing.
"""
from __future__ import annotations

from modules.leave.domain import categories, statuses


def initial_state(*, is_director: bool, substitute_required: bool) -> str:
    """Where a valid submission lands (EL-UC-001 M7)."""
    if substitute_required:
        return statuses.AWAITING_SUBSTITUTE
    if is_director:
        return statuses.AWAITING_DIRECTOR_SELF_SANCTION
    return statuses.AWAITING_UNIT_HEAD


def after_substitute_accept(*, is_director: bool) -> str:
    if is_director:
        return statuses.AWAITING_DIRECTOR_SELF_SANCTION
    return statuses.AWAITING_UNIT_HEAD


def after_unit_head(*, category: str, establishment_configured: bool) -> str:
    """The stage a Unit Head recommendation advances to.

    Only meaningful for higher-sanction categories — for CL/RH the Unit Head's
    outcome is the final decision, and callers must not call this.
    """
    if category in categories.UNIT_HEAD_FINAL:
        raise ValueError("CL/RH are decided finally by the Unit Head.")
    if establishment_configured:
        return statuses.AWAITING_ESTABLISHMENT
    return statuses.AWAITING_FINAL_SANCTION


def after_establishment() -> str:
    return statuses.AWAITING_FINAL_SANCTION
