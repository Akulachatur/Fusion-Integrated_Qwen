"""The write path for the whole leave lifecycle.

Every state change goes through `_transition`, which is the only place that
reads the state machine, writes an append-only audit row and (re)opens the
matching work item. A rule violation raises a domain error that is translated
to the platform's HTTP envelope here, so the same service stays callable from a
management command or a scheduled task.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import BadRequestError, ConflictError, NotFoundError
from modules.leave.domain import categories, routing, statuses
from modules.leave.domain.counting import chargeable_days
from modules.leave.domain.errors import (
    InvalidTransitionError,
    LeaveError,
    LeaveValidationError,
    RoutingError,
)
from modules.leave.domain.overlap import Interval, find_overlap
from modules.leave.models import LeaveRequest, LeaveRequestEvent, LeaveTask, SubstituteAssignment
from modules.leave.selectors import calendars, leaves
from modules.leave.services import balances, configuration

UNIT_HEAD_ROLE = "unit_head"
ESTABLISHMENT_ROLE = "establishment"
DIRECTOR_ROLE = "director"
ACTOR_EMPLOYEE = "employee"
ACTOR_SUBSTITUTE = "substitute"
ACTOR_AUTHORITY = "sanctioning_authority"
ACTOR_ADMIN = "leave_admin"

APPROVE = "approve"
REJECT = "reject"
RECOMMEND = "recommend"
NOT_RECOMMEND = "not_recommend"


@contextmanager
def _translate():
    """Domain errors become the platform's error envelope."""
    try:
        yield
    except InvalidTransitionError as exc:
        raise ConflictError(exc.message, code=exc.code) from exc
    except RoutingError as exc:
        raise ConflictError(exc.message, code=exc.code) from exc
    except LeaveError as exc:
        raise BadRequestError(exc.message, code=exc.code) from exc


def _record(request: LeaveRequest, *, to_status: str, from_status: str = "",
            actor_user_id: int | None = None, actor_role: str = "",
            outcome: str = "", note: str = "") -> LeaveRequestEvent:
    return LeaveRequestEvent.objects.create(
        request=request, from_status=from_status or "", to_status=to_status,
        actor_user_id=actor_user_id, actor_role=actor_role, outcome=outcome,
        note=note)


def _transition(request: LeaveRequest, dst: str, *, current_role: str | None = None,
                actor_user_id: int | None = None, actor_role: str = "",
                outcome: str = "", note: str = "") -> LeaveRequest:
    src = request.status
    if not statuses.can_transition(src, dst):
        raise InvalidTransitionError(
            f"A request in state {src!r} cannot move to {dst!r}.", )
    request.status = dst
    if current_role is not None:
        request.current_role = current_role
    request.save(update_fields=["status", "current_role", "updated_at"])
    _record(request, from_status=src, to_status=dst, actor_user_id=actor_user_id,
            actor_role=actor_role, outcome=outcome, note=note)
    return request


def _open_task(request: LeaveRequest, *, stage: str, role: str,
               assignee_user_id: int | None = None) -> LeaveTask:
    return LeaveTask.objects.create(request=request, stage=stage,
                                    assignee_role=role,
                                    assignee_user_id=assignee_user_id)


def _close_tasks(request: LeaveRequest) -> None:
    LeaveTask.objects.filter(request=request, status="pending").update(status="cancelled")


def _count_days(category: str, start: date, end: date, half_day: str) -> Decimal:
    return chargeable_days(category=category, start=start, end=end, half_day=half_day,
                           closed_holidays=calendars.closed_holidays(start.year))


def _validate(category: str, start: date, end: date, half_day: str, *,
              user_id: int, exclude_pk: int | None = None) -> Decimal:
    if category not in categories.CATEGORIES:
        raise LeaveValidationError("Unsupported leave category.")
    if end < start:
        raise LeaveValidationError("The end date cannot be before the start date.")
    if category == categories.RH and not calendars.is_restricted_holiday(start):
        raise LeaveValidationError(
            "This date is not an applicable Restricted Holiday in the published calendar.")
    if category == categories.VL and not calendars.covers_vacation(start, end):
        raise LeaveValidationError(
            "Vacation Leave may be availed only inside a published vacation period.")

    days = _count_days(category, start, end, half_day)
    available = balances.available(user_id, category, start.year)
    if days > available:
        raise LeaveValidationError(
            f"Insufficient {categories.label(category)} balance: {days} requested, "
            f"{available} available.")

    clash = find_overlap(Interval(start, end, half_day),
                         leaves.active_intervals(user_id, exclude_pk=exclude_pk))
    if clash is not None:
        raise LeaveValidationError(
            "This request overlaps active pending or approved leave.")
    return days


def _assign_substitute(request: LeaveRequest, substitute_user_id: int, *,
                       actor_user_id: int | None) -> SubstituteAssignment:
    if substitute_user_id == request.applicant_user_id:
        raise LeaveValidationError("The substitute cannot be the applicant.")
    clash = find_overlap(
        Interval(request.start_date, request.end_date, request.half_day),
        leaves.active_intervals(substitute_user_id))
    if clash is not None:
        raise LeaveValidationError(
            "The nominated substitute has overlapping leave for this period.")
    SubstituteAssignment.objects.filter(request=request,
                                        status="requested").update(status="superseded")
    return SubstituteAssignment.objects.create(
        request=request, substitute_user_id=substitute_user_id, status="requested")


# --------------------------------------------------------------------------- #
# Employee actions
# --------------------------------------------------------------------------- #
@transaction.atomic
def submit(*, user_id: int, category: str, start_date: date, end_date: date,
           half_day: str = categories.NONE, purpose: str = "", station_leave: bool = False,
           station_place: str = "", station_purpose: str = "",
           evidence_reference: str = "", substitute_user_id: int | None = None,
           applicant_is_faculty: bool = False,
           applicant_is_director: bool = False) -> LeaveRequest:
    with _translate():
        if category in categories.FACULTY_ONLY and not applicant_is_faculty:
            raise LeaveValidationError("Vacation Leave is available to faculty only.")
        if category in categories.NON_FACULTY_ONLY and applicant_is_faculty:
            raise LeaveValidationError("Earned Leave is available to non-faculty only.")

        days = _validate(category, start_date, end_date, half_day, user_id=user_id)
        request = LeaveRequest.objects.create(
            applicant_user_id=user_id, category=category, kind="application",
            start_date=start_date, end_date=end_date, half_day=half_day,
            purpose=purpose, station_leave=station_leave, station_place=station_place,
            station_purpose=station_purpose, evidence_reference=evidence_reference,
            applicant_is_faculty=applicant_is_faculty,
            applicant_is_director=applicant_is_director, chargeable_days=days,
            status=statuses.DRAFT, substitute_required=bool(substitute_user_id))
        _record(request, to_status=statuses.DRAFT, actor_user_id=user_id,
                actor_role=ACTOR_EMPLOYEE, outcome="created")

        if substitute_user_id:
            _assign_substitute(request, substitute_user_id, actor_user_id=user_id)
            _transition(
                request,
                routing.initial_state(is_director=applicant_is_director,
                                      substitute_required=True),
                current_role="", actor_user_id=user_id, actor_role=ACTOR_EMPLOYEE,
                outcome="submitted")
            _open_task(request, stage="substitute_response", role="",
                       assignee_user_id=substitute_user_id)
        else:
            dst = routing.initial_state(is_director=applicant_is_director,
                                        substitute_required=False)
            role = (DIRECTOR_ROLE
                    if dst == statuses.AWAITING_DIRECTOR_SELF_SANCTION
                    else UNIT_HEAD_ROLE)
            _transition(request, dst, current_role=role, actor_user_id=user_id,
                        actor_role=ACTOR_EMPLOYEE, outcome="submitted")
            _open_task(request, stage="final_sanction" if role == DIRECTOR_ROLE
                       else "unit_head_review", role=role)
        return request


@transaction.atomic
def withdraw(user_id: int, pk: int) -> LeaveRequest:
    request = leaves.my_request(user_id, pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status not in statuses.WITHDRAWABLE:
            raise InvalidTransitionError(
                "Only a pending request can be withdrawn.")
        _transition(request, statuses.WITHDRAWN, current_role="", actor_user_id=user_id,
                    actor_role=ACTOR_EMPLOYEE, outcome="withdrawn")
        _close_tasks(request)
        SubstituteAssignment.objects.filter(request=request,
                                            status="requested").update(status="superseded")
    return request


@transaction.atomic
def nominate_replacement(user_id: int, pk: int, substitute_user_id: int) -> LeaveRequest:
    request = leaves.my_request(user_id, pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status != statuses.APPLICANT_ACTION_REQUIRED:
            raise InvalidTransitionError(
                "A replacement can be nominated only after a substitute declines.")
        _assign_substitute(request, substitute_user_id, actor_user_id=user_id)
        _transition(request, statuses.AWAITING_SUBSTITUTE, current_role="",
                    actor_user_id=user_id, actor_role=ACTOR_EMPLOYEE,
                    outcome="replacement_nominated")
        _open_task(request, stage="substitute_response", role="",
                   assignee_user_id=substitute_user_id)
    return request


@transaction.atomic
def request_cancellation(user_id: int, pk: int, note: str = "") -> LeaveRequest:
    parent = leaves.my_request(user_id, pk)
    if parent is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if parent.kind != "application" or parent.status != statuses.APPROVED:
            raise InvalidTransitionError("Only an approved leave can be cancelled.")
        if parent.start_date <= timezone.now().date():
            raise LeaveValidationError(
                "This leave has already started; cancellation is unavailable.")

        cancellation = LeaveRequest.objects.create(
            applicant_user_id=user_id, category=parent.category, kind="cancellation",
            parent=parent, start_date=parent.start_date, end_date=parent.end_date,
            half_day=parent.half_day, purpose=note,
            chargeable_days=parent.chargeable_days, status=statuses.DRAFT,
            applicant_is_faculty=parent.applicant_is_faculty,
            applicant_is_director=parent.applicant_is_director)
        _record(cancellation, to_status=statuses.DRAFT, actor_user_id=user_id,
                actor_role=ACTOR_EMPLOYEE, outcome="created")
        _transition(cancellation, statuses.AWAITING_UNIT_HEAD, current_role=UNIT_HEAD_ROLE,
                    actor_user_id=user_id, actor_role=ACTOR_EMPLOYEE,
                    outcome="cancellation_requested", note=note)
        _open_task(cancellation, stage="unit_head_review", role=UNIT_HEAD_ROLE)
    return cancellation


@transaction.atomic
def request_extension(user_id: int, pk: int, new_end_date: date, *,
                      substitute_user_id: int | None = None,
                      purpose: str = "") -> LeaveRequest:
    parent = leaves.my_request(user_id, pk)
    if parent is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if parent.kind != "application" or parent.status != statuses.APPROVED:
            raise InvalidTransitionError("Only an approved leave can be extended.")
        if parent.category not in categories.EXTENDABLE:
            raise LeaveValidationError(
                "Extensions are supported only for EL, COL and VL.")
        if parent.end_date < timezone.now().date():
            raise LeaveValidationError("This leave is no longer ongoing.")
        if new_end_date <= parent.end_date:
            raise LeaveValidationError(
                "An extension must end after the current approved end date.")

        extra_start = parent.end_date + timedelta(days=1)
        days = _validate(parent.category, extra_start, new_end_date, categories.NONE,
                         user_id=user_id)
        extension = LeaveRequest.objects.create(
            applicant_user_id=user_id, category=parent.category, kind="extension",
            parent=parent, start_date=extra_start, end_date=new_end_date,
            purpose=purpose, chargeable_days=days,
            substitute_required=bool(substitute_user_id), status=statuses.DRAFT,
            applicant_is_faculty=parent.applicant_is_faculty,
            applicant_is_director=parent.applicant_is_director)
        _record(extension, to_status=statuses.DRAFT, actor_user_id=user_id,
                actor_role=ACTOR_EMPLOYEE, outcome="created")

        if substitute_user_id:
            _assign_substitute(extension, substitute_user_id, actor_user_id=user_id)
            _transition(extension, statuses.AWAITING_SUBSTITUTE, current_role="",
                        actor_user_id=user_id, actor_role=ACTOR_EMPLOYEE,
                        outcome="extension_requested")
            _open_task(extension, stage="substitute_response", role="",
                       assignee_user_id=substitute_user_id)
        else:
            _transition(extension, statuses.AWAITING_UNIT_HEAD,
                        current_role=UNIT_HEAD_ROLE, actor_user_id=user_id,
                        actor_role=ACTOR_EMPLOYEE, outcome="extension_requested")
            _open_task(extension, stage="unit_head_review", role=UNIT_HEAD_ROLE)
    return extension


@transaction.atomic
def submit_resumption(user_id: int, pk: int, resumption_date: date,
                      note: str = "") -> LeaveRequest:
    request = leaves.my_request(user_id, pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status != statuses.APPROVED or request.category not in categories.RESUMABLE:
            raise InvalidTransitionError(
                "Resumption applies only to approved EL, COL or VL.")
        request.resumption_date = resumption_date
        request.save(update_fields=["resumption_date", "updated_at"])
        _record(request, from_status=request.status, to_status=request.status,
                actor_user_id=user_id, actor_role=ACTOR_EMPLOYEE,
                outcome="resumption_submitted", note=note)
        _open_task(request, stage="resumption_review",
                   role=configuration.resolve_final_role(request.category))
    return request


# --------------------------------------------------------------------------- #
# Substitute and approver actions
# --------------------------------------------------------------------------- #
@transaction.atomic
def respond_substitute(user_id: int, pk: int, *, accept: bool,
                       note: str = "") -> LeaveRequest:
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    assignment = SubstituteAssignment.objects.filter(
        request=request, substitute_user_id=user_id, status="requested").first()
    if assignment is None:
        raise NotFoundError("No substitute request is assigned to you.")

    with _translate():
        if request.status != statuses.AWAITING_SUBSTITUTE:
            raise InvalidTransitionError(
                "This request is no longer awaiting a substitute response.")
        assignment.status = "accepted" if accept else "declined"
        assignment.note = note
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=["status", "note", "responded_at", "updated_at"])

        if accept:
            dst = routing.after_substitute_accept(
                is_director=request.applicant_is_director)
            role = (DIRECTOR_ROLE
                    if dst == statuses.AWAITING_DIRECTOR_SELF_SANCTION
                    else UNIT_HEAD_ROLE)
            _transition(request, dst, current_role=role, actor_user_id=user_id,
                        actor_role=ACTOR_SUBSTITUTE, outcome="accepted", note=note)
            _close_tasks(request)
            _open_task(request, stage="final_sanction" if role == DIRECTOR_ROLE
                       else "unit_head_review", role=role)
        else:
            _transition(request, statuses.APPLICANT_ACTION_REQUIRED, current_role="",
                        actor_user_id=user_id, actor_role=ACTOR_SUBSTITUTE,
                        outcome="declined", note=note)
            _close_tasks(request)
    return request


@transaction.atomic
def decide_unit_head(user_id: int, pk: int, decision: str,
                     note: str = "") -> LeaveRequest:
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status != statuses.AWAITING_UNIT_HEAD:
            raise InvalidTransitionError(
                "This request is not awaiting Unit Head review.")

        if request.category in categories.UNIT_HEAD_FINAL:
            if decision not in (APPROVE, REJECT):
                raise InvalidTransitionError(
                    "CL and RH are decided by the Unit Head: approve or reject.")
            final = statuses.APPROVED if decision == APPROVE else statuses.REJECTED
            _transition(request, final, current_role="", actor_user_id=user_id,
                        actor_role=UNIT_HEAD_ROLE, outcome=decision, note=note)
            request.decided_at = timezone.now()
            request.decided_by_user_id = user_id
            request.decision_note = note
            request.save(update_fields=["decided_at", "decided_by_user_id",
                                        "decision_note", "updated_at"])
            if decision == APPROVE:
                _apply_final_effects(request)
            _close_tasks(request)
        else:
            if decision not in (RECOMMEND, NOT_RECOMMEND):
                raise InvalidTransitionError(
                    "Higher-sanction categories are recommended or not recommended."
                    " Not Recommended is not a final rejection.")
            dst = routing.after_unit_head(
                category=request.category,
                establishment_configured=configuration.establishment_configured(
                    request.category))
            role = (ESTABLISHMENT_ROLE if dst == statuses.AWAITING_ESTABLISHMENT
                    else configuration.resolve_final_role(request.category))
            _transition(request, dst, current_role=role, actor_user_id=user_id,
                        actor_role=UNIT_HEAD_ROLE, outcome=decision, note=note)
            _close_tasks(request)
            _open_task(request, stage="establishment_routing"
                       if dst == statuses.AWAITING_ESTABLISHMENT else "final_sanction",
                       role=role)
    return request


@transaction.atomic
def verify_and_route(user_id: int, pk: int, note: str = "") -> LeaveRequest:
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status != statuses.AWAITING_ESTABLISHMENT:
            raise InvalidTransitionError(
                "This request is not awaiting Establishment routing.")
        role = configuration.resolve_final_role(request.category)
        _transition(request, routing.after_establishment(), current_role=role,
                    actor_user_id=user_id, actor_role=ESTABLISHMENT_ROLE,
                    outcome="routed", note=note)
        _close_tasks(request)
        _open_task(request, stage="final_sanction", role=role)
    return request


@transaction.atomic
def final_decision(user_id: int, pk: int, *, approve: bool,
                   note: str = "") -> LeaveRequest:
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.status not in (statuses.AWAITING_FINAL_SANCTION,
                                  statuses.AWAITING_DIRECTOR_SELF_SANCTION):
            raise InvalidTransitionError(
                "This request is not awaiting a final sanctioning decision.")
        dst = statuses.APPROVED if approve else statuses.REJECTED
        _transition(request, dst, current_role="", actor_user_id=user_id,
                    actor_role=ACTOR_AUTHORITY,
                    outcome="approved" if approve else "rejected", note=note)
        request.decided_at = timezone.now()
        request.decided_by_user_id = user_id
        request.decision_note = note
        request.save(update_fields=["decided_at", "decided_by_user_id",
                                    "decision_note", "updated_at"])
        if approve:
            _apply_final_effects(request)
        _close_tasks(request)
    return request


@transaction.atomic
def review_resumption(user_id: int, pk: int, note: str = "") -> LeaveRequest:
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    with _translate():
        if request.resumption_date is None:
            raise InvalidTransitionError("No resumption has been submitted.")
        if request.resumption_reviewed_at is not None:
            raise InvalidTransitionError("This resumption is already reviewed.")

        actual = request.resumption_date
        if actual < request.end_date:
            new_days = _count_days(request.category, request.start_date, actual,
                                   request.half_day)
            balances.restore(request.applicant_user_id, request.category,
                             request.start_date.year,
                             request.chargeable_days - new_days)
            request.end_date = actual
            request.chargeable_days = new_days
        elif actual > request.end_date:
            extra = _count_days(request.category, request.end_date + timedelta(days=1),
                                actual, categories.NONE)
            balances.charge(request.applicant_user_id, request.category,
                            request.start_date.year, extra)
            request.end_date = actual
            request.chargeable_days = request.chargeable_days + extra

        request.resumption_reviewed_at = timezone.now()
        request.save(update_fields=["end_date", "chargeable_days",
                                    "resumption_reviewed_at", "updated_at"])
        _record(request, from_status=request.status, to_status=request.status,
                actor_user_id=user_id, actor_role=ACTOR_AUTHORITY,
                outcome="resumption_reviewed", note=note)
        _close_tasks(request)
    return request


# --------------------------------------------------------------------------- #
# Administrative actions
# --------------------------------------------------------------------------- #
@transaction.atomic
def record_offline_leave(*, actor_user_id: int, user_id: int, category: str,
                         start_date: date, end_date: date,
                         sanction_reference: str, half_day: str = categories.NONE,
                         purpose: str = "") -> LeaveRequest:
    """EL-UC-016: synchronize leave already sanctioned offline. Not a workflow."""
    with _translate():
        if not sanction_reference:
            raise LeaveValidationError(
                "Sanction/reference evidence is required for an offline record.")
        if category not in categories.CATEGORIES:
            raise LeaveValidationError("Unsupported leave category.")
        days = _count_days(category, start_date, end_date, half_day)
        request = LeaveRequest.objects.create(
            applicant_user_id=user_id, category=category, kind="application",
            start_date=start_date, end_date=end_date, half_day=half_day,
            purpose=purpose, chargeable_days=days, status=statuses.APPROVED,
            is_offline_record=True, sanction_reference=sanction_reference,
            decided_at=timezone.now(), decided_by_user_id=actor_user_id)
        _record(request, to_status=statuses.APPROVED, actor_user_id=actor_user_id,
                actor_role=ACTOR_ADMIN, outcome="offline_recorded",
                note=sanction_reference)
        balances.charge(user_id, category, start_date.year, days)
    return request


@transaction.atomic
def maintain_record(pk: int, *, actor_user_id: int, note: str = "",
                    purpose: str | None = None,
                    station_place: str | None = None,
                    station_purpose: str | None = None) -> LeaveRequest:
    """EL-UC-017: permitted record maintenance. Never a new decision."""
    request = leaves.request_detail(pk)
    if request is None:
        raise NotFoundError("Leave request not found.")
    if purpose is not None:
        request.purpose = purpose
    if station_place is not None:
        request.station_place = station_place
    if station_purpose is not None:
        request.station_purpose = station_purpose
    request.save(update_fields=["purpose", "station_place", "station_purpose",
                                "updated_at"])
    _record(request, from_status=request.status, to_status=request.status,
            actor_user_id=actor_user_id, actor_role=ACTOR_ADMIN,
            outcome="record_maintained", note=note)
    return request


# --------------------------------------------------------------------------- #
# Effects applied when a request becomes final
# --------------------------------------------------------------------------- #
def _apply_final_effects(request: LeaveRequest) -> None:
    if request.kind == "application":
        balances.charge(request.applicant_user_id, request.category,
                        request.start_date.year, request.chargeable_days)
    elif request.kind == "cancellation" and request.parent is not None:
        parent = request.parent
        balances.restore(parent.applicant_user_id, parent.category,
                         parent.start_date.year, parent.chargeable_days)
        parent.status = statuses.CANCELLED
        parent.save(update_fields=["status", "updated_at"])
    elif request.kind == "extension" and request.parent is not None:
        parent = request.parent
        if request.end_date > parent.end_date:
            parent.end_date = request.end_date
            parent.save(update_fields=["end_date", "updated_at"])
        balances.charge(request.applicant_user_id, request.category,
                        request.start_date.year, request.chargeable_days)
