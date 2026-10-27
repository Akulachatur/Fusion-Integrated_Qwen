"""Wire shapes for the leave API.

Read serializers are deliberately narrow; write serializers carry only what a
caller may set. `user_id` is never a write field — it comes from the credential.
"""
from __future__ import annotations

from rest_framework import serializers

from modules.leave.domain import categories
from modules.leave.models import (
    Holiday,
    HolidayCalendar,
    LeaveBalance,
    LeavePolicyParameter,
    LeaveRequest,
    LeaveRequestEvent,
    SlaConfig,
    SubstituteAssignment,
    VacationPeriod,
)


class LeaveBalanceSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display",
                                           read_only=True)
    available = serializers.DecimalField(max_digits=8, decimal_places=2,
                                         read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ["id", "category", "category_label", "year", "entitled",
                  "carried_forward", "used", "adjusted", "available"]


class LeaveEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequestEvent
        fields = ["id", "from_status", "to_status", "actor_role", "outcome",
                  "note", "created_at"]


class SubstituteAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubstituteAssignment
        fields = ["id", "request", "substitute_user_id", "status", "note",
                  "responded_at"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display",
                                           read_only=True)
    status_label = serializers.CharField(source="get_status_display",
                                         read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ["id", "applicant_user_id", "category", "category_label", "kind",
                  "parent", "start_date", "end_date", "half_day", "purpose",
                  "station_leave", "station_place", "station_purpose",
                  "evidence_reference", "status", "status_label", "current_role",
                  "chargeable_days", "substitute_required", "applicant_is_faculty",
                  "applicant_is_director", "decided_at", "decision_note",
                  "is_offline_record", "sanction_reference", "resumption_date",
                  "resumption_reviewed_at", "created_at"]


class LeaveRequestDetailSerializer(LeaveRequestSerializer):
    events = LeaveEventSerializer(many=True, read_only=True)
    substitutes = SubstituteAssignmentSerializer(many=True, read_only=True)

    class Meta(LeaveRequestSerializer.Meta):
        fields = [*LeaveRequestSerializer.Meta.fields, "events", "substitutes"]


class SubmitLeaveSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=categories.CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = serializers.ChoiceField(choices=categories.HALF_DAY_CHOICES,
                                       default=categories.NONE, required=False)
    purpose = serializers.CharField(allow_blank=True, required=False, default="")
    station_leave = serializers.BooleanField(required=False, default=False)
    station_place = serializers.CharField(allow_blank=True, required=False, default="")
    station_purpose = serializers.CharField(allow_blank=True, required=False, default="")
    evidence_reference = serializers.CharField(allow_blank=True, required=False,
                                               default="")
    substitute_user_id = serializers.IntegerField(required=False, allow_null=True,
                                                  default=None)


class SubstituteResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True, required=False, default="")


class NominateReplacementSerializer(serializers.Serializer):
    substitute_user_id = serializers.IntegerField()


class UnitHeadDecisionSerializer(serializers.Serializer):
    #: approve | reject (CL/RH) or recommend | not_recommend (higher-sanction).
    decision = serializers.ChoiceField(
        choices=["approve", "reject", "recommend", "not_recommend"])
    note = serializers.CharField(allow_blank=True, required=False, default="")


class FinalDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True, required=False, default="")


class CancellationSerializer(serializers.Serializer):
    note = serializers.CharField(allow_blank=True, required=False, default="")


class ExtensionSerializer(serializers.Serializer):
    new_end_date = serializers.DateField()
    substitute_user_id = serializers.IntegerField(required=False, allow_null=True,
                                                  default=None)
    purpose = serializers.CharField(allow_blank=True, required=False, default="")


class ResumptionSerializer(serializers.Serializer):
    resumption_date = serializers.DateField()
    note = serializers.CharField(allow_blank=True, required=False, default="")


class OfflineRecordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    category = serializers.ChoiceField(choices=categories.CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = serializers.ChoiceField(choices=categories.HALF_DAY_CHOICES,
                                       default=categories.NONE, required=False)
    sanction_reference = serializers.CharField()
    purpose = serializers.CharField(allow_blank=True, required=False, default="")


class BalanceAdjustSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    category = serializers.ChoiceField(choices=categories.CHOICES)
    year = serializers.IntegerField()
    delta = serializers.DecimalField(max_digits=7, decimal_places=2)
    note = serializers.CharField(allow_blank=True, required=False, default="")


class LeavePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicyParameter
        fields = ["id", "category", "annual_entitlement", "carries_forward",
                  "continuous_counting", "half_day_allowed",
                  "evidence_may_be_required", "is_active"]


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "kind"]


class HolidayCalendarSerializer(serializers.ModelSerializer):
    holidays = HolidaySerializer(many=True, read_only=True)

    class Meta:
        model = HolidayCalendar
        fields = ["id", "year", "status", "published_at", "note", "holidays"]


class PublishCalendarSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    note = serializers.CharField(allow_blank=True, required=False, default="")
    holidays = HolidaySerializer(many=True)
    #: Replaces the caller-supplied ids with fresh rows; ids are ignored.
    replace = serializers.BooleanField(required=False, default=True)


class VacationPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationPeriod
        fields = ["id", "start_date", "end_date", "label", "source", "synced_at"]


class SyncVacationSerializer(serializers.Serializer):
    periods = VacationPeriodSerializer(many=True)


HIERARCHY_ROLES = ["unit_head", "establishment", "dean", "registrar", "director"]


class HierarchyStepSerializer(serializers.Serializer):
    seq = serializers.IntegerField()
    role = serializers.ChoiceField(choices=HIERARCHY_ROLES)
    is_final = serializers.BooleanField(required=False, default=False)


class SetHierarchySerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=categories.CHOICES)
    steps = HierarchyStepSerializer(many=True)


class SlaConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaConfig
        fields = ["id", "task_class", "reminder_hours", "escalation_hours"]
