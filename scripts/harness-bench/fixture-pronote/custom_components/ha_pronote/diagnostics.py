"""DIAG-01 — config entry diagnostics dump, PII-safe by default.

HA auto-discovers this platform by filename. The dump is downloadable from
Settings → Devices & Services → (entry) → ⋮ → Download diagnostics, and is
designed to be paste-able into a GitHub issue without leaking credentials or
the establishment URL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import PronoteConfigEntry

# `session` is redacted WHOLESALE (not by sub-key): the dict from
# pronotepy.export_credentials() nests `pronote_url`, `client_identifier`,
# `uuid`, `qr_code_uuid`, `token`, `username`, `password` under names that
# differ from the top level. A bare {"url"} would leak the establishment URL
# via `pronote_url`. Redacting the whole key is future-proof against new
# pronotepy session keys.
TO_REDACT = {"password", "username", "uuid", "qr_code_uuid", "token", "url", "session"}


def _iso(value: Any) -> str | None:
    """ISO-format a datetime-like attribute, or None."""
    return value.isoformat() if value is not None else None


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PronoteConfigEntry) -> dict[str, Any]:
    """Return a redacted diagnostics dump for one ConfigEntry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = coordinator.data

    data_summary: dict[str, Any] = {
        "lessons_today": len(snapshot.lessons_today) if snapshot is not None else None,
        "grades": len(snapshot.grades) if snapshot is not None else None,
        "notifications": len(snapshot.information) if snapshot is not None else None,
        "has_previous_snapshot": coordinator._previous_snapshot is not None,  # noqa: SLF001
    }

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "runtime": {
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": _iso(coordinator.last_update_success_time),
            "backoff_until": _iso(coordinator._backoff_until),  # noqa: SLF001
            "consecutive_failures": coordinator._consecutive_failures,  # noqa: SLF001
            "last_recovery_at": _iso(coordinator._last_recovery_at),  # noqa: SLF001
        },
        "data_summary": data_summary,
    }
