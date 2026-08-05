"""Typed exception hierarchy. Phase 5 reads `.reason` to route circuit-breaker (Pitfall 1, D-22).

Also exposes ``redact(message)`` — WR-05 hedge against pronotepy echoing user
URLs / credentials inside its raw exception messages, which would otherwise
end up in HA logs (CLAUDE.md "jamais en clair dans les logs"). Every site
that wraps ``str(err)`` from pronotepy should pass it through ``redact()``.
"""

from __future__ import annotations

from enum import StrEnum
import re

# WR-05: tolerant patterns — match common credential-bearing fragments that
# pronotepy or upstream Pronote could surface in an exception message.
_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)password=\S+"),
    re.compile(r"(?i)pwd=\S+"),
    re.compile(r"(?i)token=[A-Za-z0-9+/=._\-]+"),
    re.compile(r"(?i)session=[A-Za-z0-9+/=._\-]+"),
    # ``Authorization: Bearer <token>`` and similar — match through the token
    # value, not just the scheme name (``Bearer``).
    re.compile(r"(?i)authorization:\s*\S+(?:\s+\S+)?"),
)


def redact(message: str) -> str:
    """Return ``message`` with known credential-bearing fragments replaced.

    WR-05: pronotepy exception messages are not strictly redacted; a future
    pronotepy version (or a 500 with the request URL echoed back) could put
    the user's URL, username, or partial token in ``str(err)``. Apply this
    helper before stringifying any pronotepy-derived exception into an
    ``UpdateFailed`` / ``ConfigEntryAuthFailed`` log line.
    """
    for pattern in _REDACT_PATTERNS:
        message = pattern.sub("<redacted>", message)
    return message


class ErrorReason(StrEnum):
    """Reason taxonomy for ``PronoteIntegrationError`` (D-22).

    AUTH_FAILED, IP_SUSPENDED, PROTOCOL_BROKEN, SERVER_DOWN, PARSE_ERROR are
    used in Phase 2; SESSION_EXPIRED and RATE_LIMITED are reserved for
    Phase 5's circuit-breaker (D-22 mandates the 7-member set, PC-02-05).
    """

    AUTH_FAILED = "auth_failed"
    IP_SUSPENDED = "ip_suspended"
    PROTOCOL_BROKEN = "protocol_broken"
    SERVER_DOWN = "server_down"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    PARSE_ERROR = "parse_error"


class PronoteIntegrationError(Exception):
    """Base wrapper for every typed Pronote integration failure."""

    reason: ErrorReason
    message: str

    def __init__(self, reason: ErrorReason, message: str) -> None:
        """Store the reason and message and stringify as ``[reason] message``."""
        self.reason = reason
        self.message = message
        super().__init__(f"[{reason}] {message}")


class AuthError(PronoteIntegrationError):
    """Authentication failure — bad credentials or pronotepy ``CryptoError``."""

    def __init__(
        self,
        message: str,
        reason: ErrorReason = ErrorReason.AUTH_FAILED,
    ) -> None:
        """Default reason is ``AUTH_FAILED``; override allowed for completeness."""
        super().__init__(reason, message)


class RateLimitedError(PronoteIntegrationError):
    """Pronote-side rate-limit signal (e.g. ``"Your IP address is suspended"``)."""

    def __init__(
        self,
        message: str,
        reason: ErrorReason = ErrorReason.IP_SUSPENDED,
    ) -> None:
        """Default reason is ``IP_SUSPENDED``."""
        super().__init__(reason, message)


class CommunicationError(PronoteIntegrationError):
    """Network or protocol failure during a Pronote exchange."""

    def __init__(
        self,
        message: str,
        reason: ErrorReason = ErrorReason.SERVER_DOWN,
    ) -> None:
        """Default reason is ``SERVER_DOWN``; override allowed for protocol breakage."""
        super().__init__(reason, message)


class ParseError(PronoteIntegrationError):
    """Local parsing / model-construction failure (e.g. naive datetime)."""

    def __init__(
        self,
        message: str,
        reason: ErrorReason = ErrorReason.PARSE_ERROR,
    ) -> None:
        """Default reason is ``PARSE_ERROR``."""
        super().__init__(reason, message)
