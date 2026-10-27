"""Leave categories and their fixed per-category policy flags.

The baseline (PS v1.4 §3) fixes the *shape* of each category: which are
Unit-Head-final, which count continuously, which are faculty-only. An
administrator may reconfigure entitlements through the policy table, but these
flags are constants, not configuration — a category does not drift.
"""
from __future__ import annotations

CL = "CL"
RH = "RH"
SCL = "SCL"
EL = "EL"
COL = "COL"
VL = "VL"

CATEGORIES = (CL, RH, SCL, EL, COL, VL)

LABELS = {
    CL: "Casual Leave",
    RH: "Restricted Holiday",
    SCL: "Special Casual Leave",
    EL: "Earned Leave",
    COL: "Commuted Leave",
    VL: "Vacation Leave",
}
CHOICES = [(c, LABELS[c]) for c in CATEGORIES]

#: CL and RH are decided finally by the Unit Head. SCL/EL/COL/VL are reviewed
#: there and sanctioned higher up (PS §7).
UNIT_HEAD_FINAL = frozenset({CL, RH})
HIGHER_SANCTION = frozenset({SCL, EL, COL, VL})

#: EL, COL and VL count every day inside the interval; CL, SCL and RH do not
#: (PS §4).
CONTINUOUS_COUNT = frozenset({EL, COL, VL})

#: Only CL supports a half day, and an approved half day consumes 0.5 day.
HALF_DAY_ALLOWED = frozenset({CL})

#: COL may require supporting medical evidence where applicable (PS §3).
EVIDENCE_MAY_BE_REQUIRED = frozenset({COL})

#: VL is associated with faculty; EL's 30-day credit is for non-faculty.
FACULTY_ONLY = frozenset({VL})
NON_FACULTY_ONLY = frozenset({EL})

#: The only category an ongoing-leave extension may extend (PS §9).
EXTENDABLE = frozenset({EL, COL, VL})

#: Resumption is reviewed only for EL, COL and VL (PS §10).
RESUMABLE = frozenset({EL, COL, VL})

NONE = "none"
FIRST_HALF = "first_half"
SECOND_HALF = "second_half"
HALF_DAY_CHOICES = [
    (NONE, "Full day"),
    (FIRST_HALF, "First half"),
    (SECOND_HALF, "Second half"),
]


def label(category: str) -> str:
    return LABELS.get(category, category)
