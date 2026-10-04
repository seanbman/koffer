"""Typed application errors for service boundaries (docs/16)."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base typed application error with stable code and user-safe summary."""

    def __init__(
        self,
        code: str,
        summary: str,
        detail: str = "",
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.detail = detail
        self.retryable = retryable


class NotFoundError(ApplicationError):
    """Requested entity does not exist."""

    def __init__(self, summary: str, detail: str = "") -> None:
        super().__init__("not_found", summary, detail, retryable=False)


class ValidationError(ApplicationError):
    """Caller supplied an invalid argument."""

    def __init__(self, summary: str, detail: str = "") -> None:
        super().__init__("validation", summary, detail, retryable=False)


class PathUnavailableError(ApplicationError):
    """Filesystem path is offline, missing, or not readable."""

    def __init__(self, summary: str, detail: str = "", *, retryable: bool = True) -> None:
        super().__init__("path_unavailable", summary, detail, retryable=retryable)


class UnsupportedOperationError(ApplicationError):
    """Requested operation is not supported for this entity/state."""

    def __init__(self, summary: str, detail: str = "") -> None:
        super().__init__("unsupported_operation", summary, detail, retryable=False)


class ModelUnavailableError(ApplicationError):
    """Semantic model/provider is disabled or weights are absent (S11)."""

    def __init__(self, summary: str, detail: str = "", *, retryable: bool = True) -> None:
        super().__init__("model_unavailable", summary, detail, retryable=retryable)
