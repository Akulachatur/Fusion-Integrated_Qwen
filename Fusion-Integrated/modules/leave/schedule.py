"""What the leave module needs run on a timer.

Tasks are named by string, not imported, so config assembles the schedule
without importing anything out of the module.
"""
from celery.schedules import crontab

#: Which worker pool each task lands on; without it everything queues on default.
TASK_ROUTES = {
    "leave.run_year_end": {"queue": "leave"},
    "leave.process_sla": {"queue": "notifications"},
}

BEAT_SCHEDULE = {
    # Drains often; each pass is capped by the pending-task query itself.
    "leave.process-sla": {
        "task": "leave.process_sla",
        "schedule": 300.0,
        "options": {"expires": 290},
    },
    # The year-end boundary is an event trigger, not an actor: run once, just
    # after the calendar year closes.
    "leave.run-year-end": {
        "task": "leave.run_year_end",
        "schedule": crontab(month_of_year="1", day_of_month="1", hour="0", minute="15"),
        "options": {"expires": 3600},
    },
}
