"""Domain errors, raised by domain/ and translated to HTTP by services/.

Deliberately not DRF exceptions: a rule must stay checkable from a Celery
task or a management command, where an HTTP status is noise. `services/`
catches these and re-raises the platform's DomainError equivalents.
"""
from __future__ import annotations


class LeaveError(Exception):
    code = "leave_error"
    message = "The leave request could not be processed."

    def __init__(self, message: str | None = None, *, code: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code


class LeaveValidationError(LeaveError):
    """A rule refused the input (BR-EL-001…013, BR-EL-030…031)."""

    code = "leave_validation_failed"
    message = "The leave request did not pass validation."


class InvalidTransitionError(LeaveError):
    """The request is not in a state that allows the requested action."""

    code = "invalid_leave_transition"
    message = "The request is not in a state that allows this action."


class RoutingError(LeaveError):
    """The configured hierarchy could not resolve a competent authority."""

    code = "leave_routing_unresolved"
    message = "No sanctioning path is configured for this request."
