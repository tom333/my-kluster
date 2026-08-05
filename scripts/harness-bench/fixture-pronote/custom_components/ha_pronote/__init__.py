"""HA-Pronote — Home Assistant integration for Pronote.

Phase 3: real ConfigEntry setup. The coordinator wraps api.fetcher in executor;
the sensor platform reads coordinator.data: Snapshot.

Decisions enforced here:
- D-07: try Client.token_login first via build_or_resume_client; on failure,
        fresh login with the same helper. Both paths via async_add_executor_job.
- D-18 / AUTH-07: device_name = ``f"home-assistant-{entry.entry_id[:8]}"``.
- D-21: entry.runtime_data = PronoteData(...). NEVER the legacy
        ``hass.data[<domain>]`` global registry (Anti-Pattern 6).
- D-25: PLATFORMS = (Platform.SENSOR,). Phase 4 adds CALENDAR.
- D-26 / ENT-04: async_migrate_entry skeleton returns True; entry.version stays 1.
"""

from __future__ import annotations

from functools import partial
import logging
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.util.dt as dt_util

from .api import AuthError, PronoteIntegrationError, set_active_child
from .api.client import build_or_resume_client
from .const import DEFAULT_SCHOOL_TZ, DOMAIN, PLATFORMS
from .coordinator import PronoteDataUpdateCoordinator
from .data import PronoteConfigEntry, PronoteData
from .holiday_dates import compute_holiday_dates_for_year  # Phase 5 WR-2 — neutral HA-free helper

if TYPE_CHECKING:
    import pronotepy

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "PronoteConfigEntry"]


_REQUIRED_ENTRY_DATA_KEYS = (
    "url",
    "account_type",
    "username",
    "password",
    "child_identifier",
    "child_name",
)


async def async_setup_entry(hass: HomeAssistant, entry: PronoteConfigEntry) -> bool:
    """Set up HA-Pronote from a ConfigEntry (D-07, D-21, D-25)."""
    # WR-02: validate required entry.data keys upfront and fail with a clean
    # ConfigEntryNotReady. Without this guard, a corrupted entry (manual JSON
    # edit, stale Phase 1 placeholder, future-migration regression) would
    # surface as a raw KeyError traceback in HA logs. async_migrate_entry is
    # a no-op in v1 (D-26), so this is the only line of defence at setup time.
    missing = [k for k in _REQUIRED_ENTRY_DATA_KEYS if k not in entry.data]
    if missing:
        raise ConfigEntryNotReady(f"entry.data missing required keys: {missing}")

    # Phase 6 D-09 / OPT-04 — per-entry school_tz override via entry.options.
    # The OptionsFlow (Plan 06-05) validates this string at submit-time inside
    # async_step_display (Pitfall #5) — that is the PRIMARY validation gate.
    # Here, ZoneInfo() is called directly with NO try/except: per user feedback
    # memory feedback_no_silent_exceptions.md, ZoneInfoNotFoundError MUST propagate
    # raw. HA logs the traceback; the entry enters SETUP_ERROR with the raw error
    # text visible to the developer / power-user who manually edited .storage JSON.
    school_tz_name = entry.options.get("school_tz", DEFAULT_SCHOOL_TZ)
    school_tz = ZoneInfo(school_tz_name)
    device_name = f"home-assistant-{entry.entry_id[:8]}"  # AUTH-07 / D-18 / C-04.

    # D-07: try token_login fast path first; build_or_resume_client falls back
    # to fresh login internally. AuthError -> ConfigEntryAuthFailed (HA reauth);
    # other PronoteIntegrationError -> ConfigEntryNotReady (HA retries setup).
    try:
        client = await hass.async_add_executor_job(
            partial(
                build_or_resume_client,
                entry.data["url"],
                entry.data["account_type"],
                entry.data["username"],
                entry.data["password"],
                entry.data.get("session"),  # may be None on first setup
                device_name,
            )
        )
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except PronoteIntegrationError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # D-08: parent accounts ship a child_index — apply it before the first fetch
    # so coordinator.data is scoped to the chosen child from the very first poll.
    # CR-04: set_active_child wraps client.set_child with our typed-error mapping
    # so a CryptoError / PronoteAPIError surfaces as ConfigEntryAuthFailed or
    # ConfigEntryNotReady (below) rather than escaping as a raw pronotepy traceback.
    child_index = entry.data.get("child_index")
    if child_index is not None and hasattr(client, "set_child"):
        try:
            await hass.async_add_executor_job(
                partial(set_active_child, cast("pronotepy.ParentClient", client), child_index)
            )
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PronoteIntegrationError as err:
            raise ConfigEntryNotReady(str(err)) from err

    # Phase 5 (C-07, D-02, WR-2): precompute NC fériés for current school year via
    # the neutral helper module. Executor-wrapped even though holidays==0.97 does no
    # I/O (RESEARCH verified) — keeps the policy uniform per CLAUDE.md "executor for
    # any blocking work" discipline.
    now_year = dt_util.now(school_tz).year
    holiday_dates = await hass.async_add_executor_job(compute_holiday_dates_for_year, now_year)

    coordinator = PronoteDataUpdateCoordinator(
        hass,
        entry,
        client=client,
        child_identifier=entry.data["child_identifier"],
        child_index=child_index,
        school_tz=school_tz,
    )
    # D-22: setup-time auth fail aborts setup cleanly via the standard helper.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PronoteData(
        coordinator=coordinator,
        client=client,
        child_identifier=entry.data["child_identifier"],
        child_index=child_index,
        school_tz=school_tz,
        holiday_dates=holiday_dates,
        holiday_dates_year=now_year,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)  # D-25
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PronoteConfigEntry) -> bool:
    """Unload all platforms and stop the coordinator's polling loop (D-25, WR-07).

    WR-07: ``async_unload_platforms`` removes the entities, but
    ``TimestampDataUpdateCoordinator`` keeps its scheduled refresh alive until
    garbage-collected. Without ``async_shutdown`` the coordinator can fire one
    more poll AFTER unload — a violation of CLAUDE.md "politesse polling".
    """
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ENT-04 / D-26 — skeleton. Phase 6+ fills the body when entry shapes change."""
    _LOGGER.debug(
        "Migrating entry %s (version %s) — no-op in v1",
        entry.entry_id,
        entry.version,
    )
    return True
