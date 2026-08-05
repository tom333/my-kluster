"""API subpackage — pure-sync facade over pronotepy==2.14.6.

Phase 2 D-19: zero ``homeassistant.*`` imports anywhere in this package.
Phase 2 D-20: imports limited to stdlib + pronotepy + python-slugify (lazy).

Public surface (consumed by Phase 3 coordinator via ``async_add_executor_job``):

- ``build_client(url, account_type, username, password)``
- ``fetch_all(client, today, school_tz, child_index_or_identifier=None)``
- ``AuthError``, ``CommunicationError``, ``RateLimitedError``, ``ParseError``,
  ``PronoteIntegrationError``, ``ErrorReason``
- ``Lesson``, ``Grade``, ``Information``, ``Snapshot``

Token persistence (``client.export_credentials()``) is Phase 3's coordinator
responsibility — NOT exposed here. The coordinator owns ``entry.data`` storage
for the token round-trip (AUTH-04, PC-02-04). Adding an
``export_credentials_dict()`` wrapper to ``api/`` would couple the pure-Python
layer to HA's storage concerns; resist the temptation.
"""

from .client import build_client, build_or_resume_client, set_active_child
from .errors import (
    AuthError,
    CommunicationError,
    ErrorReason,
    ParseError,
    PronoteIntegrationError,
    RateLimitedError,
    redact,
)
from .fetcher import fetch_all
from .models import Grade, Information, Lesson, Snapshot

__all__ = [
    "AuthError",
    "CommunicationError",
    "ErrorReason",
    "Grade",
    "Information",
    "Lesson",
    "ParseError",
    "PronoteIntegrationError",
    "RateLimitedError",
    "Snapshot",
    "build_client",
    "build_or_resume_client",
    "fetch_all",
    "redact",
    "set_active_child",
]
