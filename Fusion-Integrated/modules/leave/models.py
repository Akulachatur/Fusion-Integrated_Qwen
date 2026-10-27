"""ELM tables.

Person references are plain integer `user_id`s, never ForeignKeys: there is no
user table in this database, and a cross-module FK would make the module
impossible to lift out. Every FK here points inside `leave`.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from core.db.mixins import TimeStampedModel
from modules.leave.domain import categories, statuses

REQUEST_KINDS = [("application", "Application"), ("cancellation", "Cancellation"),
                 ("extension", "Extension")]

CALENDAR_STATUS = [("draft", "Draft"), ("published", "Published")]
HOLIDAY_KINDS = [("closed", "Closed holiday"), ("restricted", "Restricted holiday")]

SUBSTITUTE_STATUS = [("requested", "Requested"), ("accepted", "Accepted"),
                     ("declined", "Declined"), ("superseded", "Superseded")]

TASK_STATUS = [("pending", "Pending"), ("done", "Done"), ("cancelled", "Cancelled")]

ROLE_CHOICES = [
    ("unit_head", "Unit Head"),
    ("establishment", "Establishment / Deputy Registrar (Estt.)"),
    ("dean", "Dean"),
    ("registrar", "Registrar"),
    ("director", "Director"),
]


class LeavePolicyParameter(TimeStampedModel):
    """The current configured policy (EL-UC-014).

    No draft/publish/effective-version lifecycle in this baseline — a saved row
    is the value validation uses (adjudication G-03).
    """

    category = models.CharField(max_length=8, choices=categories.CHOICES, unique=True)
    annual_entitlement = models.DecimalField(max_digits=6, decimal_places=2,
                                             default=Decimal("0"))
    carries_forward = models.BooleanField(default=False)
    continuous_counting = models.BooleanField(default=False)
    half_day_allowed = models.BooleanField(default=False)
    evidence_may_be_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "leave_policy_parameter"
        ordering = ["category"]

    def __str__(self) -> str:
        return f"{self.category}: {self.annual_entitlement}"


class HierarchyStep(TimeStampedModel):
    """One step of a category's configured sanctioning path (EL-UC-014)."""

    category = models.CharField(max_length=8, choices=categories.CHOICES)
    seq = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    is_final = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "leave_hierarchy_step"
        ordering = ["category", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["category", "seq"],
                                    name="leave_hierarchy_category_seq_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.category}#{self.seq}:{self.role}"


class SlaConfig(TimeStampedModel):
    """Reminder and escalation thresholds per actionable task class (EL-UC-018)."""

    task_class = models.CharField(max_length=48, unique=True)
    reminder_hours = models.PositiveIntegerField(default=24)
    escalation_hours = models.PositiveIntegerField(default=48)

    class Meta:
        db_table = "leave_sla_config"
        ordering = ["task_class"]

    def __str__(self) -> str:
        return self.task_class


class HolidayCalendar(TimeStampedModel):
    """A holiday/RH calendar. The published row for a year governs validation."""

    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=CALENDAR_STATUS, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "leave_holiday_calendar"
        ordering = ["-year"]
        constraints = [
            models.UniqueConstraint(fields=["year"], name="leave_calendar_year_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.year} ({self.status})"


class Holiday(TimeStampedModel):
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE,
                                 related_name="holidays")
    date = models.DateField()
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=HOLIDAY_KINDS, default="closed")

    class Meta:
        db_table = "leave_holiday"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["calendar", "date"],
                                    name="leave_holiday_calendar_date_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.name}"


class VacationPeriod(TimeStampedModel):
    """A faculty vacation period supplied by the external Academic Calendar.

    Projected here so date checks can run without an HTTP call per request;
    never authored by hand (EXT-01).
    """

    start_date = models.DateField()
    end_date = models.DateField()
    label = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=48, default="academic_calendar")
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_vacation_period"
        ordering = ["start_date"]
        indexes = [models.Index(fields=["start_date", "end_date"],
                                name="leave_vacation_range_idx")]

    def __str__(self) -> str:
        return f"{self.start_date}-{self.end_date}"


class LeaveBalance(TimeStampedModel):
    """A person's per-category account for a calendar year (CFR-EL-004-009)."""

    user_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=8, choices=categories.CHOICES)
    year = models.PositiveSmallIntegerField()
    entitled = models.DecimalField(max_digits=7, decimal_places=2,
                                   default=Decimal("0"))
    carried_forward = models.DecimalField(max_digits=7, decimal_places=2,
                                          default=Decimal("0"))
    used = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    adjusted = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))

    class Meta:
        db_table = "leave_balance"
        ordering = ["year", "category"]
        constraints = [
            models.UniqueConstraint(fields=["user_id", "category", "year"],
                                    name="leave_balance_user_cat_year_uniq"),
        ]

    @property
    def available(self) -> Decimal:
        return (self.entitled + self.carried_forward + self.adjusted - self.used)

    def __str__(self) -> str:
        return f"{self.user_id} {self.category}/{self.year}: {self.available}"


class LeaveRequest(TimeStampedModel):
    """A leave request row.

    `kind` separates a fresh application from the two post-approval flows, both
    of which are their own row pointing back at the approved parent — an
    approved leave is never edited in place (PS §8, BR-EL-034).
    """

    applicant_user_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=8, choices=categories.CHOICES)
    kind = models.CharField(max_length=12, choices=REQUEST_KINDS, default="application")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                               related_name="derived")
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.CharField(max_length=12, choices=categories.HALF_DAY_CHOICES,
                                default=categories.NONE)
    purpose = models.TextField(blank=True)
    station_leave = models.BooleanField(default=False)
    station_place = models.CharField(max_length=120, blank=True)
    station_purpose = models.CharField(max_length=200, blank=True)
    evidence_reference = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=32, choices=statuses.CHOICES, default=statuses.DRAFT)
    current_role = models.CharField(max_length=24, blank=True)
    applicant_is_director = models.BooleanField(default=False)
    applicant_is_faculty = models.BooleanField(default=False)
    substitute_required = models.BooleanField(default=False)
    chargeable_days = models.DecimalField(max_digits=7, decimal_places=2,
                                          default=Decimal("0"))

    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_user_id = models.IntegerField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    # EL-UC-016: leave already sanctioned through a paper/offline route.
    is_offline_record = models.BooleanField(default=False)
    sanction_reference = models.CharField(max_length=200, blank=True)

    resumption_date = models.DateField(null=True, blank=True)
    resumption_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "leave_request"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["applicant_user_id", "status"],
                         name="leave_req_user_status_idx"),
            models.Index(fields=["status", "current_role"],
                         name="leave_req_status_role_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.applicant_user_id} {self.category} {self.status}"


class LeaveRequestEvent(TimeStampedModel):
    """Append-only audit trail: one row per state change (BR-EL-008 analog)."""

    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE,
                                related_name="events")
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32)
    actor_user_id = models.IntegerField(null=True, blank=True)
    actor_role = models.CharField(max_length=24, blank=True)
    outcome = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "leave_request_event"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"#{self.request_id}: {self.from_status}->{self.to_status}"


class SubstituteAssignment(TimeStampedModel):
    """One nominated substitute and their response (EL-UC-002, EL-UC-019)."""

    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE,
                                related_name="substitutes")
    substitute_user_id = models.IntegerField(db_index=True)
    status = models.CharField(max_length=12, choices=SUBSTITUTE_STATUS,
                              default="requested")
    note = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "leave_substitute_assignment"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"#{self.request_id} -> {self.substitute_user_id} ({self.status})"


class LeaveTask(TimeStampedModel):
    """An actionable work item for SLA reminder/escalation (EL-UC-021)."""

    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE,
                                related_name="tasks")
    stage = models.CharField(max_length=32)
    assignee_role = models.CharField(max_length=24, blank=True)
    assignee_user_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=TASK_STATUS, default="pending")
    reminded_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "leave_task"
        ordering = ["-id"]
        indexes = [models.Index(fields=["status", "assignee_role"],
                                name="leave_task_status_role_idx")]

    def __str__(self) -> str:
        return f"task#{self.pk} {self.stage} ({self.status})"
