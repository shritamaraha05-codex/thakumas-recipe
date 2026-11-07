"""Expected API failures that use the documented error envelope (docs/04_API.md).

``ApiError`` marks a *known, documented* failure (for example an explicit request
for a parser that is not implemented). It is deliberately narrow: unexpected
exceptions still propagate so programming errors are never hidden.
"""

from __future__ import annotations

from .models import ErrorCode


class ApiError(Exception):
    """A documented API failure, rendered as ``{"error": {code, message, hint}}``."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.hint = hint
