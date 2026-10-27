"""All reads for the leave module.

Visibility is decided by narrowing the queryset here, never by fetching and
checking, so another person's request id yields 404 rather than 403.
"""
from __future__ import annotations

from modules.leave.domain import statuses
from modules.leave.domain.overlap import Interval
from modules.leave.models import (
    LeaveBalance,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveTask,
    SubstituteAssignment,
)


def my_requests(user_id: int, *, kind: str | None = None, status: str | None = None):
    qs = LeaveRequest.objects.filter(applicant_user_id=user_id)
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    return qs


def my_request(user_id: int, pk: int) -> LeaveRequest | None:
    return LeaveRequest.objects.filter(pk=pk, applicant_user_id=user_id).first()


def request_detail(pk: int) -> LeaveRequest | None:
    return LeaveRequest.objects.filter(pk=pk).first()


def approval_queue(role: str, user_id: int):
    """Requests currently waiting on this role.

    Unit Head queues are matched on the role alone; a real deployment narrows
    further by the applicant's organisational unit once that mapping is
    projected from the IAM.
    """
    return LeaveRequest.objects.filter(status__in=statuses.PENDING, current_role=role)


def substitute_queue(user_id: int):
    return (SubstituteAssignment.objects
            .filter(substitute_user_id=user_id, status="requested",
                    request__status=statuses.AWAITING_SUBSTITUTE)
            .select_related("request"))


def active_intervals(user_id: int, *, exclude_pk: int | None = None) -> list[Interval]:
    """Pending and approved intervals, for overlap detection (BR-EL-012)."""
    qs = (LeaveRequest.objects
          .filter(applicant_user_id=user_id, kind="application",
                  status__in=[statuses.APPROVED, *statuses.PENDING]))
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return [Interval(r.start_date, r.end_date, r.half_day) for r in qs]


def balances(user_id: int, year: int) -> list[LeaveBalance]:
    return list(LeaveBalance.objects.filter(user_id=user_id, year=year))


def history(request: LeaveRequest) -> list[LeaveRequestEvent]:
    return list(request.events.order_by("id"))


def approved_ongoing(user_id: int):
    """Approved EL/COL/VL the applicant could still extend (PS §9)."""
    return (LeaveRequest.objects
            .filter(applicant_user_id=user_id, kind="application",
                    status=statuses.APPROVED, category__in=["EL", "COL", "VL"]))


def pending_tasks():
    return (LeaveTask.objects.filter(status="pending")
            .select_related("request").order_by("id"))
