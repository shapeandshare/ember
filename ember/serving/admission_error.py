"""AdmissionError: the engine's pending-request queue is full (D-001)."""

from __future__ import annotations


class AdmissionError(RuntimeError):
    """Raised when the admission semaphore is full (D-001).

    Signals that ``MAX_PENDING_ADVISE`` requests are already queued. The HTTP
    layer maps this to 503 so the agent knows to retry shortly.
    """
