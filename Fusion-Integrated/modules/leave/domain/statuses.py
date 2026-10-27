"""The ELM request state machine (Workflow SPEC v1.6, authoritative STT).

One status column drives every request kind. A cancellation and an extension
are separate rows (kind = cancellation / extension) rather than an in-place
edit of an approved leave, so they walk the same status set: substitute consent
where required, Unit Head review, optional Establishment routing, final
decision. That is why there is no cancellation- or extension-specific state
family here.
"""
from __future__ import annotations

DRAFT = "draft"
AWAITING_SUBSTITUTE = "awaiting_substitute"
APPLICANT_ACTION_REQUIRED = "applicant_action_required"
AWAITING_UNIT_HEAD = "awaiting_unit_head"
AWAITING_ESTABLISHMENT = "awaiting_establishment"
AWAITING_FINAL_SANCTION = "awaiting_final_sanction"
AWAITING_DIRECTOR_SELF_SANCTION = "awaiting_director_self_sanction"
APPROVED = "approved"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"
CANCELLED = "cancelled"

CHOICES = [
    (DRAFT, "Draft / Not Submitted"),
    (AWAITING_SUBSTITUTE, "Awaiting Substitute Response"),
    (APPLICANT_ACTION_REQUIRED, "Applicant Action Required"),
    (AWAITING_UNIT_HEAD, "Awaiting Unit Head Review"),
    (AWAITING_ESTABLISHMENT, "Awaiting Establishment Routing"),
    (AWAITING_FINAL_SANCTION, "Awaiting Final Sanction Decision"),
    (AWAITING_DIRECTOR_SELF_SANCTION, "Awaiting Director Self-Sanction"),
    (APPROVED, "Approved"),
    (REJECTED, "Rejected"),
    (WITHDRAWN, "Withdrawn"),
    (CANCELLED, "Cancelled"),
]

ALL = tuple(code for code, _ in CHOICES)
LABELS = dict(CHOICES)

TERMINAL = frozenset({APPROVED, REJECTED, WITHDRAWN, CANCELLED})
#: Everything the applicant may still withdraw (EL-UC-007) and everything that
#: counts as an active request for overlap (BR-EL-012).
PENDING = frozenset(code for code in ALL if code != DRAFT and code not in TERMINAL)
WITHDRAWABLE = PENDING

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    DRAFT: (AWAITING_SUBSTITUTE, AWAITING_UNIT_HEAD,
            AWAITING_DIRECTOR_SELF_SANCTION),
    AWAITING_SUBSTITUTE: (AWAITING_UNIT_HEAD, AWAITING_DIRECTOR_SELF_SANCTION,
                          APPLICANT_ACTION_REQUIRED, WITHDRAWN),
    APPLICANT_ACTION_REQUIRED: (AWAITING_SUBSTITUTE, WITHDRAWN),
    AWAITING_UNIT_HEAD: (APPROVED, REJECTED, AWAITING_ESTABLISHMENT,
                         AWAITING_FINAL_SANCTION, WITHDRAWN),
    AWAITING_ESTABLISHMENT: (AWAITING_FINAL_SANCTION, WITHDRAWN),
    AWAITING_FINAL_SANCTION: (APPROVED, REJECTED, WITHDRAWN),
    AWAITING_DIRECTOR_SELF_SANCTION: (APPROVED, REJECTED, WITHDRAWN),
    # An approved leave is not edited in place, but a finally-approved
    # cancellation does mark it Cancelled (PS §8, BW-EL-10-11).
    APPROVED: (CANCELLED,),
}


def next_states(status: str) -> tuple[str, ...]:
    return _TRANSITIONS.get(status, ())


def can_transition(src: str, dst: str) -> bool:
    return dst in _TRANSITIONS.get(src, ())


def is_pending(status: str) -> bool:
    return status in PENDING
