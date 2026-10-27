"""What the server tells the shell about ELM (ADR-0010).

Nav items carry `required_permission`; the server filters before sending, so a
link a role cannot use never reaches the browser.
"""
MODULE = {
    "code": "leave", "label": "Leave Management", "icon": "FaUmbrellaBeach",
    "base_path": "/leave", "nav_section": "Human Resources", "sort_order": 20,
    "status": "active",
}

NAV_ITEMS = [
    # -- employee ----------------------------------------------------------
    {"code": "leave.mine", "label": "My Leave", "icon": "FaClipboardList",
     "to": "/leave/mine", "required_permission": "leave.request.view_self",
     "sort_order": 10},
    {"code": "leave.apply", "label": "Apply for Leave", "icon": "FaPlus",
     "to": "/leave/apply", "required_permission": "leave.request.create",
     "sort_order": 20},
    {"code": "leave.balances", "label": "Leave Balances", "icon": "FaWallet",
     "to": "/leave/balances", "required_permission": "leave.request.view_self",
     "sort_order": 30},
    {"code": "leave.approvals", "label": "Approvals", "icon": "FaCheckDouble",
     "to": "/leave/approvals", "required_permission": "leave.request.approve",
     "sort_order": 40},

    # -- administration ----------------------------------------------------
    {"code": "leave.records", "label": "Leave Records", "icon": "FaIdBadge",
     "to": "/leave/records", "required_permission": "leave.record.manage",
     "sort_order": 50},
    {"code": "leave.calendar", "label": "Holiday Calendar", "icon": "FaCalendarAlt",
     "to": "/leave/calendar", "required_permission": "leave.calendar.manage",
     "sort_order": 60},
    {"code": "leave.policy", "label": "Policy & Hierarchy", "icon": "FaCog",
     "to": "/leave/policy", "required_permission": "leave.type.manage",
     "sort_order": 70},
    {"code": "leave.sla", "label": "SLA Settings", "icon": "FaUserClock",
     "to": "/leave/sla", "required_permission": "leave.sla.manage",
     "sort_order": 80},
]

#: Every permission this module recognises; ROLE_GRANTS says who holds each.
PERMISSIONS = [
    ("leave.request.view_self", "View own leave requests and balance"),
    ("leave.request.create", "Apply for leave"),
    ("leave.request.delete", "Withdraw a pending leave request"),
    ("leave.request.view", "View leave requests in scope"),
    ("leave.request.approve", "Review and decide leave requests"),
    ("leave.resume.review", "Review resumption of duty"),
    ("leave.balance.update", "Adjust a leave balance"),
    ("leave.type.manage", "Configure leave policy and hierarchy"),
    ("leave.calendar.manage", "Maintain and publish the holiday/RH calendar"),
    ("leave.record.manage", "Record offline-sanctioned leave and maintain records"),
    ("leave.sla.manage", "Configure workflow SLA thresholds"),
]

#: Performed by a scheduled task, so no designation holds them.
SYSTEM_PERMISSIONS = [
    "leave.year_end.process",
    "leave.sla.process",
]

_EMPLOYEE = [
    "leave.request.view_self",
    "leave.request.create",
    "leave.request.delete",
]

_UNIT_HEAD = [
    *_EMPLOYEE,
    "leave.request.view",
    "leave.request.approve",
    "leave.resume.review",
]

_AUTHORITY = [
    "leave.request.view",
    "leave.request.approve",
    "leave.resume.review",
]

#: Keyed by the designation name as it exists in globals_designation.
ROLE_GRANTS = {
    "faculty": _EMPLOYEE,
    "staff": _EMPLOYEE,
    "unit_head": _UNIT_HEAD,
    "deputy_registrar": _AUTHORITY,
    "Dean": _AUTHORITY,
    "Registrar": _AUTHORITY,
    "Director": _AUTHORITY,
    "leave_admin": [
        "leave.request.view",
        "leave.balance.update",
        "leave.type.manage",
        "leave.calendar.manage",
        "leave.record.manage",
        "leave.sla.manage",
    ],
}
