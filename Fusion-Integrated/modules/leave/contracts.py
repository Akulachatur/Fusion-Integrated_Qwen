"""leave's public surface. Plural by signature.

Other modules ask one question: "is this person away, and how much leave do they
have left?" — always about a batch of people, never one, so the batched form is
the only form available.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from modules.leave.domain import statuses
from modules.leave.models import LeaveBalance, LeaveRequest


@dataclass(frozen=True)
class LeaveStatusDTO:
    user_id: int
    #: category code -> available days, as a string because Django serialises
    #: Decimal and float arithmetic on leave balances is not wanted.
    available: dict[str, str]
    pending_requests: int
    on_leave: bool


def get_leave_status(user_ids: Sequence[int], *, as_of: date) -> dict[int, LeaveStatusDTO]:
    ids = {int(i) for i in user_ids if i is not None}
    if not ids:
        return {}

    balances: dict[int, dict[str, str]] = {uid: {} for uid in ids}
    rows = LeaveBalance.objects.filter(user_id__in=ids, year=as_of.year)
    for row in rows:
        available = (row.entitled + row.carried_forward + row.adjusted - row.used)
        balances[row.user_id][row.category] = str(available)

    pending = dict.fromkeys(ids, 0)
    on_leave: set[int] = set()
    active = LeaveRequest.objects.filter(
        applicant_user_id__in=ids, kind="application",
        status__in=[statuses.APPROVED, *statuses.PENDING],
    )
    for request in active:
        if request.status == statuses.APPROVED and request.start_date <= as_of <= request.end_date:
            on_leave.add(request.applicant_user_id)
        if request.status in statuses.PENDING:
            pending[request.applicant_user_id] += 1

    return {
        uid: LeaveStatusDTO(
            user_id=uid,
            available=balances.get(uid, {}),
            pending_requests=pending.get(uid, 0),
            on_leave=uid in on_leave,
        )
        for uid in ids
    }
