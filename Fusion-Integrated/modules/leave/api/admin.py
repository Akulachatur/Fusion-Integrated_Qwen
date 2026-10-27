"""Administrative endpoints: policy, hierarchy, SLA, calendars and records.

Every writer here is gated by its own permission, because these are the
endpoints that change what validation and routing do for everyone.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.exceptions import BadRequestError
from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.leave.api import serializers as s
from modules.leave.models import HolidayCalendar, LeavePolicyParameter, SlaConfig, VacationPeriod
from modules.leave.selectors import leaves as selectors
from modules.leave.services import balances as balance_service
from modules.leave.services import configuration as config_service
from modules.leave.services import leaves as service

MODULE = HasModuleGrant("leave")
P_TYPE = "leave.type.manage"
P_CAL = "leave.calendar.manage"
P_RECORD = "leave.record.manage"
P_SLA = "leave.sla.manage"
P_BALANCE = "leave.balance.update"


def _actor(request):
    return getattr(request, "principal", None)


class PolicyView(APIView):
    """EL-UC-014: read or update the current configured policy parameters."""

    permission_classes = [MODULE, HasPermission(P_TYPE)]

    @extend_schema(responses=s.LeavePolicySerializer(many=True))
    def get(self, request):
        rows = LeavePolicyParameter.objects.all()
        return Response({"results": s.LeavePolicySerializer(rows, many=True).data})

    @extend_schema(request=s.LeavePolicySerializer,
                   responses=s.LeavePolicySerializer)
    def post(self, request):
        payload = s.LeavePolicySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        category = data.pop("category")
        config_service.set_policy(category, **data)
        row = LeavePolicyParameter.objects.get(category=category)
        return Response(s.LeavePolicySerializer(row).data, status=status.HTTP_200_OK)


class HierarchyView(APIView):
    """EL-UC-014: replace a category's configured sanctioning path."""

    permission_classes = [MODULE, HasPermission(P_TYPE)]

    @extend_schema(request=s.SetHierarchySerializer,
                   responses=s.HierarchyStepSerializer(many=True))
    def post(self, request):
        payload = s.SetHierarchySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        config_service.set_hierarchy(data["category"], data["steps"])
        return Response({"category": data["category"], "steps": data["steps"]})


class SlaView(APIView):
    """EL-UC-018: read or set reminder/escalation thresholds."""

    permission_classes = [MODULE, HasPermission(P_SLA)]

    @extend_schema(responses=s.SlaConfigSerializer(many=True))
    def get(self, request):
        rows = SlaConfig.objects.all()
        return Response({"results": s.SlaConfigSerializer(rows, many=True).data})

    @extend_schema(request=s.SlaConfigSerializer, responses=s.SlaConfigSerializer)
    def post(self, request):
        payload = s.SlaConfigSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        row = config_service.set_sla(data["task_class"], data["reminder_hours"],
                                     data["escalation_hours"])
        return Response(s.SlaConfigSerializer(row).data)


class CalendarView(APIView):
    """EL-UC-015: list and publish the holiday/RH calendar."""

    permission_classes = [MODULE, HasPermission(P_CAL)]

    @extend_schema(responses=s.HolidayCalendarSerializer(many=True))
    def get(self, request):
        rows = HolidayCalendar.objects.prefetch_related("holidays").all()
        return Response({"results": s.HolidayCalendarSerializer(rows, many=True).data})

    @extend_schema(request=s.PublishCalendarSerializer,
                   responses=s.HolidayCalendarSerializer)
    def post(self, request):
        payload = s.PublishCalendarSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        calendar = config_service.publish_calendar(
            data["year"], data["holidays"], data.get("note", ""))
        return Response(s.HolidayCalendarSerializer(calendar).data)


class VacationView(APIView):
    """EXT-01: list or re-sync the projected vacation periods."""

    permission_classes = [MODULE, HasPermission(P_CAL)]

    @extend_schema(responses=s.VacationPeriodSerializer(many=True))
    def get(self, request):
        rows = VacationPeriod.objects.all()
        return Response({"results": s.VacationPeriodSerializer(rows, many=True).data})

    @extend_schema(request=s.SyncVacationSerializer,
                   responses=s.VacationPeriodSerializer(many=True))
    def post(self, request):
        payload = s.SyncVacationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        count = config_service.sync_vacation_periods(payload.validated_data["periods"])
        rows = VacationPeriod.objects.all()
        return Response({"synced": count,
                         "results": s.VacationPeriodSerializer(rows, many=True).data})


class RecordsView(APIView):
    """EL-UC-016 / EL-UC-017: offline records and permitted maintenance."""

    permission_classes = [MODULE, HasPermission(P_RECORD)]

    @extend_schema(responses=s.LeaveRequestSerializer(many=True))
    def get(self, request):
        raw = request.query_params.get("user_id")
        if raw in (None, ""):
            raise BadRequestError("user_id is required.", code="user_id_required")
        try:
            user_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise BadRequestError("user_id must be a number.",
                                  code="invalid_filter") from exc
        rows = selectors.my_requests(user_id)
        return Response({"results": s.LeaveRequestSerializer(rows, many=True).data})

    @extend_schema(request=s.OfflineRecordSerializer,
                   responses={201: s.LeaveRequestSerializer})
    def post(self, request):
        payload = s.OfflineRecordSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        user_id = data.pop("user_id")
        created = service.record_offline_leave(
            actor_user_id=_actor(request).user_id, user_id=user_id, **data)
        return Response(s.LeaveRequestSerializer(created).data,
                        status=status.HTTP_201_CREATED)


class BalanceAdjustView(APIView):
    """EL-UC-017: adjust a person's balance under authorization."""

    permission_classes = [MODULE, HasPermission(P_BALANCE)]

    @extend_schema(request=s.BalanceAdjustSerializer,
                   responses=s.LeaveBalanceSerializer)
    def post(self, request):
        payload = s.BalanceAdjustSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        row = balance_service.adjust(data["user_id"], data["category"], data["year"],
                                     data["delta"])
        return Response(s.LeaveBalanceSerializer(row).data)
