"""Every leave beat entry must name a task that exists and has a queue."""
import pytest

import modules.leave.tasks  # noqa: F401  — registers the tasks the schedule names
from config.celery import app
from modules.leave.schedule import BEAT_SCHEDULE, TASK_ROUTES


def test_every_scheduled_task_is_registered():
    missing = [entry["task"] for entry in BEAT_SCHEDULE.values()
               if entry["task"] not in app.tasks]
    assert not missing, f"scheduled but not registered: {missing}"


@pytest.mark.parametrize("name,entry", sorted(BEAT_SCHEDULE.items()))
def test_each_entry_expires_before_its_next_run(name, entry):
    """Without `expires`, a broker backlog replays every missed tick at once."""
    assert entry["options"]["expires"] > 0


def test_every_scheduled_task_is_routed_to_a_queue():
    scheduled = {entry["task"] for entry in BEAT_SCHEDULE.values()}
    assert scheduled <= set(TASK_ROUTES)
