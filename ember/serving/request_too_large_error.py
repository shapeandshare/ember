"""RequestTooLargeError: the encoded request exceeds the enforced limit."""

from __future__ import annotations

from .limits import Limits
from .request_size import RequestSize


class RequestTooLargeError(ValueError):
    """Raised when the encoded request exceeds the enforced limit.

    The HTTP layer maps this to 413, with the message as ``detail``.

    Parameters
    ----------
    message : str
        The refusal, from ``request_size.refusal_message``.
    size : RequestSize
        The refused request's measured size.
    limits : Limits
        The limits it exceeded.
    """

    def __init__(self, message: str, *, size: RequestSize, limits: Limits) -> None:
        super().__init__(message)
        self.size = size
        self.limits = limits
