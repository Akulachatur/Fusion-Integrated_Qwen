from django.urls import path

from modules.leave.api import admin as a
from modules.leave.api import views as v

urlpatterns = [
    # employee
    path("balances", v.MyBalancesView.as_view(), name="leave-balances"),
    path("requests", v.MyRequestsView.as_view(), name="leave-requests"),
    path("requests/<int:pk>", v.MyRequestDetailView.as_view(), name="leave-request"),
    path("requests/<int:pk>/withdraw", v.WithdrawView.as_view(),
         name="leave-request-withdraw"),
    path("requests/<int:pk>/nominate-replacement",
         v.NominateReplacementView.as_view(), name="leave-request-nominate"),
    path("requests/<int:pk>/cancel", v.CancelView.as_view(),
         name="leave-request-cancel"),
    path("requests/<int:pk>/extend", v.ExtendView.as_view(),
         name="leave-request-extend"),
    path("requests/<int:pk>/resume", v.ResumeView.as_view(),
         name="leave-request-resume"),

    # substitute
    path("substitute-requests", v.SubstituteQueueView.as_view(),
         name="leave-substitute-queue"),
    path("substitute-requests/<int:pk>/respond", v.SubstituteRespondView.as_view(),
         name="leave-substitute-respond"),

    # approvals
    path("approvals", v.ApprovalQueueView.as_view(), name="leave-approvals"),
    path("approvals/<int:pk>/unit-head", v.UnitHeadDecisionView.as_view(),
         name="leave-approval-unit-head"),
    path("approvals/<int:pk>/route", v.RouteView.as_view(),
         name="leave-approval-route"),
    path("approvals/<int:pk>/decision", v.FinalDecisionView.as_view(),
         name="leave-approval-decision"),
    path("approvals/<int:pk>/resumption-review", v.ResumptionReviewView.as_view(),
         name="leave-approval-resumption"),

    # administration
    path("policy", a.PolicyView.as_view(), name="leave-policy"),
    path("hierarchy", a.HierarchyView.as_view(), name="leave-hierarchy"),
    path("sla", a.SlaView.as_view(), name="leave-sla"),
    path("calendars", a.CalendarView.as_view(), name="leave-calendars"),
    path("vacation-periods", a.VacationView.as_view(), name="leave-vacation-periods"),
    path("records", a.RecordsView.as_view(), name="leave-records"),
    path("balances/adjust", a.BalanceAdjustView.as_view(), name="leave-balance-adjust"),
]
