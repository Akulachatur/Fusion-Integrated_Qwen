"""HTTP layer for the leave lifecycle: parse, scope, delegate, serialise.

`user_id` is never read from the body on the self-service paths — it comes from
the credential, or an employee could act for somebody else.
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.exceptions import BadRequestError, NotFoundError
from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.leave.api import serializers as s
from modules.leave.selectors import leaves as selectors
from modules.leave.services import balances as balance_service
from modules.leave.services import leaves as service

MODULE = HasModuleGrant("leave")
P_SELF = "leave.request.view_self"
P_CREATE = "leave.request.create"
P_DELETE = "leave.request.delete"
P_VIEW = "leave.request.view"
P_APPROVE = "leave.request.approve"
P_RESUME_REVIEW = "leave.resume.review"

#: The roles a queue may be requested for. Anything else is a 400 rather than
#: an empty list that looks like "no work".
QUEUE_ROLES = {"unit_head", "establishment", "dean", "registrar", "director"}


def _actor(request):
    return getattr(request, "principal", None)


def _roles(actor) -> set[str]:
    roles = {r.lower() for r in getattr(actor, "roles", ())}
    active = (getattr(actor, "active_role", None) or "").lower()
    if active:
        roles.add(active)
    return roles


def _is_faculty(actor) -> bool:
    return getattr(actor, "kind", None) == "faculty"


def _is_director(actor) -> bool:
    return "director" in _roles(actor)


def _year(request) -> int:
    raw = request.query_params.get("year")
    if raw in (None, ""):
        return timezone.now().date().year
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise BadRequestError("year must be a number.", code="invalid_filter") from exc


class MyBalancesView(APIView):
    """The caller's own balances for a year (EL-UC-012)."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(responses=s.LeaveBalanceSerializer(many=True))
    def get(self, request):
        user_id = _actor(request).user_id
        year = _year(request)
        balance_service.ensure_year(user_id, year)
        rows = balance_service.balances_for(user_id, year)
        return Response({"results": s.LeaveBalanceSerializer(rows, many=True).data})


class MyRequestsView(APIView):
    """The caller's own requests; POST submits a new one (EL-UC-001)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [MODULE, HasPermission(P_CREATE)]
        return [MODULE, HasPermission(P_SELF)]

    @extend_schema(responses=s.LeaveRequestSerializer(many=True))
    def get(self, request):
        rows = selectors.my_requests(
            _actor(request).user_id,
            kind=request.query_params.get("kind"),
            status=request.query_params.get("status"))
        return Response({"results": s.LeaveRequestSerializer(rows, many=True).data})

    @extend_schema(request=s.SubmitLeaveSerializer,
                   responses={201: s.LeaveRequestDetailSerializer})
    def post(self, request):
        payload = s.SubmitLeaveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        created = service.submit(
            user_id=actor.user_id, applicant_is_faculty=_is_faculty(actor),
            applicant_is_director=_is_director(actor), **payload.validated_data)
        return Response(s.LeaveRequestDetailSerializer(created).data,
                        status=status.HTTP_201_CREATED)


class MyRequestDetailView(APIView):
    """One of the caller's own requests, with its audit trail."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(responses=s.LeaveRequestDetailSerializer)
    def get(self, request, pk):
        row = selectors.my_request(_actor(request).user_id, pk)
        if row is None:
            raise NotFoundError("Leave request not found.")
        return Response(s.LeaveRequestDetailSerializer(row).data)


class WithdrawView(APIView):
    """EL-UC-007: immediate withdrawal of a pending request."""

    permission_classes = [MODULE, HasPermission(P_DELETE)]

    @extend_schema(request=None, responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        row = service.withdraw(_actor(request).user_id, pk)
        return Response(s.LeaveRequestDetailSerializer(row).data)


class NominateReplacementView(APIView):
    """EL-UC-019: nominate a fresh substitute after a decline."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(request=s.NominateReplacementSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.NominateReplacementSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.nominate_replacement(
            _actor(request).user_id, pk, payload.validated_data["substitute_user_id"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class CancelView(APIView):
    """EL-UC-008: request cancellation of an approved leave before it starts."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(request=s.CancellationSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.CancellationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.request_cancellation(_actor(request).user_id, pk,
                                           payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class ExtendView(APIView):
    """EL-UC-009: request an extension of ongoing EL/COL/VL."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(request=s.ExtensionSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.ExtensionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        row = service.request_extension(
            _actor(request).user_id, pk, data["new_end_date"],
            substitute_user_id=data.get("substitute_user_id"),
            purpose=data.get("purpose", ""))
        return Response(s.LeaveRequestDetailSerializer(row).data)


class ResumeView(APIView):
    """EL-UC-010: submit actual resumption of duty."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(request=s.ResumptionSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.ResumptionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.submit_resumption(
            _actor(request).user_id, pk, payload.validated_data["resumption_date"],
            payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class SubstituteQueueView(APIView):
    """EL-UC-002: responsibility requests waiting on the caller."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(responses=s.SubstituteAssignmentSerializer(many=True))
    def get(self, request):
        rows = selectors.substitute_queue(_actor(request).user_id)
        return Response({"results": s.SubstituteAssignmentSerializer(rows, many=True).data})


class SubstituteRespondView(APIView):
    """EL-UC-002: accept or decline a responsibility assignment."""

    permission_classes = [MODULE, HasPermission(P_SELF)]

    @extend_schema(request=s.SubstituteResponseSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.SubstituteResponseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.respond_substitute(
            _actor(request).user_id, pk, accept=payload.validated_data["accept"],
            note=payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class ApprovalQueueView(APIView):
    """Requests waiting on a role. Defaults to the caller's active role."""

    permission_classes = [MODULE, HasPermission(P_VIEW, P_APPROVE)]

    @extend_schema(responses=s.LeaveRequestSerializer(many=True))
    def get(self, request):
        actor = _actor(request)
        role = request.query_params.get("role") or (actor.active_role or "")
        role = role.lower()
        if role not in QUEUE_ROLES:
            raise BadRequestError(
                "role must be one of: " + ", ".join(sorted(QUEUE_ROLES)) + ".",
                code="invalid_filter")
        rows = selectors.approval_queue(role, actor.user_id)
        return Response({"results": s.LeaveRequestSerializer(rows, many=True).data})


class UnitHeadDecisionView(APIView):
    """EL-UC-003: record the Unit Head's decision or recommendation."""

    permission_classes = [MODULE, HasPermission(P_APPROVE)]

    @extend_schema(request=s.UnitHeadDecisionSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.UnitHeadDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.decide_unit_head(
            _actor(request).user_id, pk, payload.validated_data["decision"],
            payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class RouteView(APIView):
    """EL-UC-004: Establishment verifies and routes a higher-sanction request."""

    permission_classes = [MODULE, HasPermission(P_APPROVE)]

    @extend_schema(request=s.CancellationSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.CancellationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.verify_and_route(_actor(request).user_id, pk,
                                       payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class FinalDecisionView(APIView):
    """EL-UC-005: the final sanctioning decision."""

    permission_classes = [MODULE, HasPermission(P_APPROVE)]

    @extend_schema(request=s.FinalDecisionSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.FinalDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.final_decision(
            _actor(request).user_id, pk, approve=payload.validated_data["approve"],
            note=payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)


class ResumptionReviewView(APIView):
    """EL-UC-011: review a submitted resumption."""

    permission_classes = [MODULE, HasPermission(P_RESUME_REVIEW)]

    @extend_schema(request=s.CancellationSerializer,
                   responses=s.LeaveRequestDetailSerializer)
    def post(self, request, pk):
        payload = s.CancellationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.review_resumption(_actor(request).user_id, pk,
                                        payload.validated_data["note"])
        return Response(s.LeaveRequestDetailSerializer(row).data)
