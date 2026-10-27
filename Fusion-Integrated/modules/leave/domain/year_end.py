"""Event-triggered year-end outcomes (PS §13, BR-EL-002-009, EL-UC-020).

Unused CL, RH and SCL lapse; unused EL and COL carry forward; unused faculty
VL converts to EL at 2 VL : 1 EL, fractional results preserved, and no VL
carries forward as VL.
"""
from __future__ import annotations

from decimal import Decimal

from modules.leave.domain import categories

LAPSE = "lapse"
CARRY_FORWARD = "carry_forward"
CONVERT_TO_EL = "convert_to_el"

_VL_TO_EL_RATIO = Decimal(2)


def outcome(category: str) -> str:
    if category in {categories.CL, categories.RH, categories.SCL}:
        return LAPSE
    if category in {categories.EL, categories.COL}:
        return CARRY_FORWARD
    if category == categories.VL:
        return CONVERT_TO_EL
    raise ValueError(f"unknown leave category: {category!r}")


def vl_to_el(unused_vl: Decimal) -> Decimal:
    """2 VL : 1 EL, preserving fractions (BR-EL-007)."""
    if unused_vl <= 0:
        return Decimal(0)
    return (Decimal(unused_vl) / _VL_TO_EL_RATIO).quantize(Decimal("0.01"))
