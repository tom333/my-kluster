"""Typed runtime_data payload for HA-Pronote ConfigEntries (D-21).

D-21 — runtime_data, NOT the legacy ``hass.data[<domain>]`` global registry
(Anti-Pattern 6). The dataclass holds the live ``pronotepy.Client`` so the
coordinator can call ``client.export_credentials()`` between polls and reuse
the client without rebuilding (Anti-Pattern 7).

NOT frozen: ``client`` is reassigned by the coordinator on D-09 silent-recovery
when a mid-poll AuthError triggers a single fresh re-login. Phase 5:
``holiday_dates`` + ``holiday_dates_year`` are also reassigned by the
coordinator on year rollover.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from zoneinfo import ZoneInfo

    import pronotepy

    from homeassistant.config_entries import ConfigEntry

    from .coordinator import PronoteDataUpdateCoordinator


@dataclass
class PronoteData:
    """Runtime payload — owned by the ConfigEntry, lives until unload (D-21)."""

    coordinator: PronoteDataUpdateCoordinator
    client: pronotepy.Client | pronotepy.ParentClient
    child_identifier: str
    child_index: int | None
    school_tz: ZoneInfo
    # Phase 5 (C-07, D-02): NC fériés precomputed at async_setup_entry; reassigned on year rollover.
    holiday_dates: frozenset[date]
    holiday_dates_year: int


type PronoteConfigEntry = ConfigEntry[PronoteData]
