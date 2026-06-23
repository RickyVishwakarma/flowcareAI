"""External integration adapters.

Each provider exposes a small, uniform surface so the core services stay vendor-
agnostic and degrade gracefully when a provider is not configured:

    result = provider.send(...)   ->  ProviderResult(success, provider, ...)

Adapters raise ``ProviderError(retryable=...)`` for failures the caller should
surface to the task layer (which owns retry → backoff → DLQ). Permanent failures
are returned as a non-success ``ProviderResult`` instead, so a single bad
recipient never blows up an entire workflow execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ProviderError(Exception):
    """Raised for transient/unexpected provider failures worth retrying."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class ProviderResult:
    success: bool
    provider: str
    external_id: str | None = None  # e.g. Twilio message SID
    status: str | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)
