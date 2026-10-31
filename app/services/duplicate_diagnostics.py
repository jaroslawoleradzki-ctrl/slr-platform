"""Privacy-safe per-request diagnostic correlation, with no research identifiers."""

from contextvars import ContextVar

request_correlation: ContextVar[str] = ContextVar("duplicate_request_correlation", default="internal")
