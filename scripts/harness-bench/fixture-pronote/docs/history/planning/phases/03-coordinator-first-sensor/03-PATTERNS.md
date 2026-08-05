# Phase 3: Coordinator & First Sensor - Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 14 (8 NEW production/test, 6 MODIFIED)
**Analogs found:** 14 / 14 (mix of internal Phase 1+2 + external delphiki/HA-Core idea-only)

## Cross-Cutting Notice — Internal vs External Analogs

Phase 1 shipped: `__init__.py` (no-op), `const.py`, placeholder `config_flow.py`, `manifest.json`, `strings.json`, `tests/conftest.py`, `tests/test_init.py`.
Phase 2 shipped: `api/{__init__,client,fetcher,errors,models,_strip}.py`, `diff/{__init__,events,lessons,grades,notifications}.py`, `tests/test_api/*`, `tests/test_diff/*`, `tests/test_fixtures.py`, `tests/test_no_ha_imports.py`.

Phase 3 is **the first phase that imports `homeassistant.*` in `custom_components/ha_pronote/`**. The greenfield zone is the entire HA-side runtime: `__init__.py:async_setup_entry`, `coordinator.py`, `data.py`, `entity.py`, `sensor.py`, the real `config_flow.py`. There is **zero internal HA-side analog** to copy from — every HA pattern is external (delphiki/hass-pronote, HA Core master, HA developer docs, ludeeus blueprint). Internal analogs cover only:

- **Module shape / docstring style / `__all__` re-exports** (Phase 1 `__init__.py`, Phase 2 `api/__init__.py`)
- **Dataclass discipline** (Phase 2 `api/models.py:Snapshot` mutable→**use plain `@dataclass`**, NOT `frozen=True`, because `PronoteData.client` is held live)
- **Test plumbing** (Phase 1 `tests/conftest.py` autouse; Phase 1 `tests/test_init.py` `hass.config_entries.flow.async_init` shape; Phase 2 `tests/test_api/test_client.py` monkeypatch idiom)
- **Error hierarchy reuse** (Phase 2 `api/errors.py:{AuthError, RateLimitedError, CommunicationError, ErrorReason, PronoteIntegrationError}` — Phase 3's coordinator/setup catches and remaps these; the hierarchy is locked, no extension needed)
- **Constants-append style** (Phase 1 `const.py:DOMAIN` `Final`-typed; Phase 2 appended `DEFAULT_SCHOOL_TZ` etc. — Phase 3 appends `DEFAULT_REFRESH_INTERVAL` + `PLATFORMS` in the same style)

**Planner directive:** every HA-side new file cites an external analog (delphiki, HA Core docs, ludeeus blueprint). Do NOT re-fetch external repos — the architectural shape is locked by CONTEXT.md D-01..D-26 + CLAUDE.md "What NOT to Use" + this pattern map. The literal code excerpts below come from the actual shipped Phase 1+2 files in this repo.

---

## File Classification

### NEW files (8)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `custom_components/ha_pronote/coordinator.py` | service (HA cloud-polling coordinator) | request-response (async loop) + transform (executor → Snapshot) + event-driven (UpdateFailed / ConfigEntryAuthFailed) | `delphiki/hass-pronote/.../coordinator.py:_async_update_data` (executor wrap idea, NOT literal — uses `hass.data[DOMAIN]` legacy). HA developer docs §"DataUpdateCoordinator". Phase 2 `api/fetcher.py` for the sync core it wraps. | role-match (idea, not code) |
| `custom_components/ha_pronote/data.py` | model (typed runtime_data dataclass) | declarative (held between polls) | Phase 2 `api/models.py:Snapshot` (dataclass discipline) — but **plain `@dataclass`**, NOT frozen, because `client` is mutable. HA developer docs §"`runtime_data`" (typed `ConfigEntry[T]` pattern). | role-match (Phase 2 dataclass shape) |
| `custom_components/ha_pronote/entity.py` | service (CoordinatorEntity base) | declarative (`device_info` / `available` properties) | HA developer docs §"DeviceInfo" + §"CoordinatorEntity". `delphiki/hass-pronote/.../entity.py` (idea — single base class subclassed by every sensor). | role-match (idea, not code) |
| `custom_components/ha_pronote/sensor.py` | service (HA platform module) | request-response (HA → `async_setup_entry` → `add_entities`) | HA developer docs §"Sensor entity". `delphiki/hass-pronote/.../sensor.py` (idea — single-platform setup callback). Phase 2 `api/models.py:Snapshot.lessons_today` for the data read. | role-match (idea, not code) |
| `tests/test_config_flow.py` | test (HA-side, async, `hass` fixture) | unit + integration | Phase 1 `tests/test_init.py:test_config_flow_placeholder_aborts` (lines 19-31 — the exact `hass.config_entries.flow.async_init` shape). Phase 2 `tests/test_api/test_client.py` (lines 11-28 — `_make_init_silent`/`_make_init_raising` monkeypatch idiom). PHACC `MockConfigEntry`. | role-match (Phase 1 + Phase 2 idioms compose) |
| `tests/test_coordinator.py` | test (HA-side, async, `hass` fixture) | unit + integration | Phase 2 `tests/test_api/test_client.py` (monkeypatch idiom for pronotepy methods). PHACC `MockConfigEntry` + `entry.add_to_hass(hass)` + `hass.config_entries.async_setup(entry.entry_id)`. | role-match |
| `tests/test_sensor.py` | test (HA-side, async, `hass` fixture) | unit + integration | Phase 1 `tests/test_init.py` (lines 19-31 — `hass` fixture pattern). PHACC entity-state assertion: `hass.states.get("sensor.pronote_<slug>_lessons_today")`. | role-match |
| `tests/test_token_persistence.py` | test (HA-side, async, `hass` fixture) | unit + integration | Phase 2 `tests/test_api/test_client.py` (monkeypatch on `pronotepy.Client.__init__` + `pronotepy.Client.token_login`). PHACC `MockConfigEntry` + `entry.data` round-trip via `hass.config_entries.async_update_entry`. | role-match |

### MODIFIED files (6)

| Existing File | Role | Modification | Internal Analog (the file itself) | Match Quality |
|---------------|------|--------------|------------------------------------|---------------|
| `custom_components/ha_pronote/__init__.py` | package (Phase 1 no-op stub) | **REPLACE** — add real `async_setup_entry`/`async_unload_entry`/`async_migrate_entry` with `runtime_data` typed pattern (D-21, D-25, D-26) and token_login-or-fresh-fallback restart (D-07) | `delphiki/hass-pronote/.../__init__.py` (idea — multi-platform setup), HA developer docs §"Integration `async_setup_entry`". Existing Phase 1 `__init__.py` lines 1-11 retained as docstring/import shape model. | role-match (idea, not code) |
| `custom_components/ha_pronote/config_flow.py` | package (Phase 1 placeholder) | **REPLACE** — real flow with `async_step_user` (URL+account_type+username+password) + `async_step_pick_child` (D-01..D-05) | `delphiki/hass-pronote/.../config_flow.py` (single-step `async_step_user` shape — Phase 3 IMPROVES with explicit pick_child step). HA developer docs §"Config Flow". `voluptuous.Url()` schema (D-03). | role-match (idea, refined) |
| `custom_components/ha_pronote/api/client.py` | service (Phase 2 sync facade) | **EXTEND** — add `build_or_resume_client(url, account_type, username, password, session, device_name)` (C-02) wrapping `Client.token_login(...)` first then fresh login fallback, passing `device_name` (D-18, AUTH-07) | The file itself — `build_client(...)` lines 19-58 already locks the error mapping table. New helper reuses the same `try/except pronotepy.PronoteAPIError / pronotepy.exceptions.CryptoError / OSError` ladder and the `_IP_SUSPENDED_LITERAL` substring check. | exact (extension in same file) |
| `custom_components/ha_pronote/strings.json` | config (Phase 1 minimal) | **EXTEND** — add `config.step.user.data.{url,account_type,username,password}` labels, `config.step.pick_child.data.child_index` label, `config.error.{invalid_auth,cannot_connect,ip_suspended,unknown}`, `config.abort.{already_configured}` (REMOVE `not_implemented`), `entity.sensor.lessons_today.name` translation_key | The file itself — Phase 1 `config.abort.not_implemented` is the existing shape; replace + extend. HA developer docs §"strings.json schema". | exact (extension in same file) |
| `custom_components/ha_pronote/const.py` | constants module | **APPEND** — `DEFAULT_REFRESH_INTERVAL = timedelta(minutes=30)` (D-24), `PLATFORMS: Final = (Platform.SENSOR,)` (D-25) | The file itself — Phase 1 (lines 7) + Phase 2 (lines 9-14) appended `Final`-typed constants in the same shape. **NEW import**: `from datetime import timedelta`, `from homeassistant.const import Platform`. | exact |
| `tests/test_init.py` | test (Phase 1 contract) | **EXTEND** — add `async_setup_entry` happy path (using `MockConfigEntry` + monkeypatched `build_or_resume_client`) + `async_migrate_entry` skeleton check (returns `True`). DELETE `test_config_flow_placeholder_aborts` (Phase 3 ships the real flow — no longer placeholder). | The file itself — lines 1-31 are Phase 1's exact contract. Replace + extend in same shape. | exact |
| `tests/conftest.py` | test fixture | **MAY EXTEND** — add `mock_pronote_client` fixture (C-05 — `MagicMock` of `pronotepy.Client`/`pronotepy.ParentClient` with `info.name`, `children`, `export_credentials()`, `lessons()`, `current_period.grades`, `information_and_surveys()` set up) and `mock_config_entry` fixture (PHACC `MockConfigEntry` with the D-08 `entry.data` keys pre-populated) | The file itself — Phase 1 lines 1-16 ship the autouse `enable_custom_integrations` wrap. Append fixtures in the same `@pytest.fixture` style. | exact (extension in same file) |

---

## Pattern Assignments

### `custom_components/ha_pronote/coordinator.py` (service, request-response + transform + event-driven)

**External analog:** `delphiki/hass-pronote/.../coordinator.py` — the `_async_update_data` shape (executor fetch → diff → bus fire → store) — **idea only**. Phase 3 implements only the executor fetch + token capture; Phase 4 adds diff + fire. Delphiki uses legacy `hass.data[DOMAIN]`; we use `runtime_data` per D-21 (Anti-Pattern 7).
**Internal analog (the sync core wrapped):** `custom_components/ha_pronote/api/fetcher.py:fetch_all` (lines 25-90 — locked signature `fetch_all(client, today, school_tz, child_index_or_identifier)` per Phase 2 D-15..D-18).
**Source for HA-side imports:** HA developer docs §"DataUpdateCoordinator" + `homeassistant.helpers.update_coordinator` (`TimestampDataUpdateCoordinator`, `UpdateFailed`); `homeassistant.exceptions.ConfigEntryAuthFailed`; `homeassistant.util.dt as dt_util`.

**Imports pattern** (mirror Phase 2 `api/fetcher.py` lines 1-23, but with HA imports):
```python
"""HA cloud-polling coordinator. Wraps api/fetcher.fetch_all in executor (D-19, COORD-01).

D-19: TimestampDataUpdateCoordinator subclass — gives last_update_success_time
      for free (Phase 4's diff layer reads it).
D-20: coordinator.data: Snapshot directly (no extra wrapper).
D-22: AuthError -> ConfigEntryAuthFailed; RateLimitedError(IP_SUSPENDED) -> UpdateFailed;
      CommunicationError / other -> UpdateFailed.
D-23: school_tz from const.DEFAULT_SCHOOL_TZ; today via dt_util.now(school_tz).date().
D-24: update_interval = const.DEFAULT_REFRESH_INTERVAL (30 min hardcoded; Phase 5 adapts).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
import homeassistant.util.dt as dt_util

from .api import (
    AuthError,
    CommunicationError,
    ErrorReason,
    PronoteIntegrationError,
    RateLimitedError,
    fetch_all,
)
from .api.client import build_or_resume_client  # C-02 helper added in api/client.py
from .const import DEFAULT_REFRESH_INTERVAL, DEFAULT_SCHOOL_TZ, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    import pronotepy

    from .api.models import Snapshot
```

**Class skeleton + executor wrap pattern** (D-19, D-20, COORD-02):
```python
_LOGGER = logging.getLogger(__name__)


class PronoteDataUpdateCoordinator(TimestampDataUpdateCoordinator["Snapshot"]):
    """One coordinator per ConfigEntry. Polls Pronote on a 30-min cadence."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: pronotepy.Client | pronotepy.ParentClient,
        child_identifier: str,
        child_index: int | None,
        school_tz: ZoneInfo,
    ) -> None:
        """Initialize the coordinator with a live pronotepy client."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{child_identifier}",
            update_interval=DEFAULT_REFRESH_INTERVAL,
            config_entry=entry,
        )
        self._client = client                      # live, between polls (D-21)
        self._child_identifier = child_identifier  # frozen at flow time (D-11)
        self._child_index = child_index            # for ParentClient.set_child (D-08)
        self._school_tz = school_tz
        self._previous_snapshot: Snapshot | None = None  # C-03 — Phase 4 reads

    async def _async_update_data(self) -> Snapshot:
        """Fetch a Snapshot via executor; capture session token on success."""
        today = dt_util.now(self._school_tz).date()  # D-23 — coordinator owns dt_util
        try:
            snapshot = await self.hass.async_add_executor_job(
                partial(
                    fetch_all,
                    self._client,
                    today,
                    self._school_tz,
                    self._child_index,
                )
            )
        except AuthError as err:
            # D-09 — silent recovery: try ONE fresh re-login + retry the fetch.
            snapshot = await self._recover_from_auth_error(err, today)
        except RateLimitedError as err:
            # D-22 — IP_SUSPENDED propagates as UpdateFailed; Phase 5's circuit
            # breaker will read .reason to enter long-backoff.
            raise UpdateFailed(f"[{err.reason}] {err.message}") from err
        except (CommunicationError, PronoteIntegrationError) as err:
            raise UpdateFailed(f"[{err.reason}] {err.message}") from err

        # D-06 — capture session AFTER every successful poll, write to entry.data.
        await self._capture_session()

        # C-03 — Phase 4 reads self._previous_snapshot to compute diff events.
        self._previous_snapshot = snapshot
        return snapshot
```

**Auth error mid-poll silent-recovery pattern** (D-09):
```python
    async def _recover_from_auth_error(
        self,
        original_err: AuthError,
        today,
    ) -> Snapshot:
        """D-09 — single fresh re-login + retry; on second failure raise ConfigEntryAuthFailed."""
        entry = self.config_entry
        if entry is None:
            raise ConfigEntryAuthFailed(str(original_err)) from original_err
        try:
            self._client = await self.hass.async_add_executor_job(
                partial(
                    build_or_resume_client,
                    entry.data["url"],
                    entry.data["account_type"],
                    entry.data["username"],
                    entry.data["password"],
                    None,  # force fresh login (skip token_login path)
                    f"home-assistant-{entry.entry_id[:8]}",  # AUTH-07 (D-18)
                )
            )
            if entry.data.get("child_index") is not None and hasattr(self._client, "set_child"):
                await self.hass.async_add_executor_job(
                    self._client.set_child, entry.data["child_index"]
                )
            snapshot = await self.hass.async_add_executor_job(
                partial(fetch_all, self._client, today, self._school_tz, self._child_index)
            )
        except (AuthError, PronoteIntegrationError) as err:
            raise ConfigEntryAuthFailed(f"[{err.reason}] {err.message}") from err
        return snapshot
```

**Token capture pattern** (D-06):
```python
    async def _capture_session(self) -> None:
        """D-06 — call client.export_credentials() in executor, write to entry.data."""
        entry = self.config_entry
        if entry is None:
            return
        new_session = await self.hass.async_add_executor_job(self._client.export_credentials)
        if new_session != entry.data.get("session"):
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, "session": new_session}
            )
```

**Banned in this file** (CLAUDE.md "What NOT to Use" + Phase 1 D-30..D-35):
- NO `async_timeout` — `asyncio.timeout()` only (banned-API)
- NO `pytz` — `zoneinfo.ZoneInfo` only (banned-API)
- NO `requests` directly (banned-API)
- NO calling pronotepy without `async_add_executor_job` (Pitfall 3, COORD-02)
- NO storing pronotepy Client in `coordinator.data` (Anti-Pattern 7) — store in `runtime_data: PronoteData` per D-21; `coordinator.data` is `Snapshot` only (D-20)

**Error mapping table** (D-22 — locks the contract Phase 5/6 build on):
| api/errors raises | Coordinator catches | Coordinator raises | Reason |
|---|---|---|---|
| `AuthError` | yes — silent recovery first (D-09) | `ConfigEntryAuthFailed` if recovery fails | HA fires reauth (Phase 6) |
| `RateLimitedError(IP_SUSPENDED)` | yes | `UpdateFailed` | Phase 5 circuit breaker reads `.reason` |
| `CommunicationError` | yes | `UpdateFailed` | retry next interval |
| `PronoteIntegrationError` (catch-all) | yes | `UpdateFailed` | retry next interval |

---

### `custom_components/ha_pronote/data.py` (model, declarative)

**Internal analog:** `custom_components/ha_pronote/api/models.py:Snapshot` (lines 133-173) — dataclass discipline. **Phase 3 difference:** `PronoteData` holds the **live `pronotepy.Client`** between polls, so it must be a **plain `@dataclass`**, NOT `@dataclass(frozen=True)` (Phase 2's idiom for value types only). Per `<code_context>` "Established Patterns" line 242: "Phase 3's `PronoteData` is mutable (holds the live `client` between polls), so use plain `@dataclass`."
**External analog:** HA developer docs §"`runtime_data`" — the `type ConfigEntry[T] = ...` typed config entry pattern.

**Pattern** (locked by D-21):
```python
"""Typed runtime_data payload for HA-Pronote ConfigEntries (D-21).

D-21 — ARCHITECTURE.md Pattern 6 — store runtime state on ``entry.runtime_data``
NOT ``hass.data[DOMAIN]``. The dataclass holds the live ``pronotepy.Client`` so
the coordinator can call ``client.export_credentials()`` between polls and
(in Phase 4) reuse the client without rebuilding.

NOT frozen: ``client`` is reassigned by the coordinator on D-09 silent-recovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    import pronotepy
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import PronoteDataUpdateCoordinator


@dataclass
class PronoteData:
    """Runtime payload — owned by the ConfigEntry, lives until unload."""

    coordinator: PronoteDataUpdateCoordinator
    client: pronotepy.Client | pronotepy.ParentClient
    child_identifier: str
    child_index: int | None
    school_tz: ZoneInfo


type PronoteConfigEntry = ConfigEntry[PronoteData]
```

**Why not frozen** (`<code_context>` Established Patterns):
> "Frozen `@dataclass(frozen=True)` for value types (Phase 2 `api/models.py`, `diff/events.py`) — Phase 3's `PronoteData` is mutable (holds the live `client` between polls), so use plain `@dataclass`."

---

### `custom_components/ha_pronote/__init__.py` (REPLACE — package, real setup)

**External analog:** HA developer docs §"Integration `async_setup_entry`" + `delphiki/hass-pronote/.../__init__.py` (idea-only — delphiki uses `hass.data[DOMAIN]`; we use `runtime_data` per D-21).
**Internal analog (docstring/import shape only):** Phase 1 `custom_components/ha_pronote/__init__.py` lines 1-11.

**Existing Phase 1 docstring/import shape** (the `from .const import DOMAIN` + `__all__` style is preserved):
```python
"""HA-Pronote — Home Assistant integration for Pronote.

Phase 1: package skeleton only. The coordinator, sensors, calendar entity, and
real Config Flow ship in subsequent phases (see ROADMAP.md). This file is
intentionally minimal so the integration can be loaded by HA / HACS without
exposing any runtime behavior yet.
"""

from .const import DOMAIN

__all__ = ["DOMAIN"]
```

**Phase 3 replacement pattern** (D-07, D-21, D-25, D-26):
```python
"""HA-Pronote — Home Assistant integration for Pronote.

Phase 3: real ConfigEntry setup. The coordinator wraps api.fetcher in executor;
the sensor platform reads coordinator.data: Snapshot. ENT-04 — async_migrate_entry
skeleton ships with body Phase 6+ fills.
"""

from __future__ import annotations

from functools import partial
import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import AuthError, PronoteIntegrationError
from .api.client import build_or_resume_client  # C-02 helper (api/client.py extension)
from .const import DEFAULT_SCHOOL_TZ, DOMAIN, PLATFORMS
from .coordinator import PronoteDataUpdateCoordinator
from .data import PronoteData, PronoteConfigEntry

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "PronoteConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: PronoteConfigEntry) -> bool:
    """Set up HA-Pronote from a ConfigEntry (D-07, D-21, D-25)."""
    school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)  # Phase 6 will read entry.options
    device_name = f"home-assistant-{entry.entry_id[:8]}"  # AUTH-07 (D-18)

    # D-07 — try token_login first, fall back to fresh login on AuthError.
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

    # D-08 — for parent accounts, set the chosen child before the first fetch.
    child_index = entry.data.get("child_index")
    if child_index is not None and hasattr(client, "set_child"):
        await hass.async_add_executor_job(client.set_child, child_index)

    coordinator = PronoteDataUpdateCoordinator(
        hass,
        entry,
        client=client,
        child_identifier=entry.data["child_identifier"],
        child_index=child_index,
        school_tz=school_tz,
    )
    await coordinator.async_config_entry_first_refresh()  # D-22

    entry.runtime_data = PronoteData(
        coordinator=coordinator,
        client=client,
        child_identifier=entry.data["child_identifier"],
        child_index=child_index,
        school_tz=school_tz,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)  # D-25
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PronoteConfigEntry) -> bool:
    """Unload all platforms and drop runtime_data."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ENT-04 — skeleton. Phase 6+ fills the body when entry shapes change (D-26)."""
    _LOGGER.debug("Migrating entry %s (version %s) — no-op in v1", entry.entry_id, entry.version)
    return True
```

**Anti-pattern guards:**
- NO `hass.data[DOMAIN][entry.entry_id] = ...` (D-21 / Anti-Pattern 6 — use `entry.runtime_data`)
- NO bare `pronotepy.Client(url, ...)` call in `async_setup_entry` (must go through `api/client.py` and `async_add_executor_job` — Pitfall 6)

---

### `custom_components/ha_pronote/config_flow.py` (REPLACE — package, real flow)

**External analog:** `delphiki/hass-pronote/.../config_flow.py` — single-step `async_step_user` shape; Phase 3 IMPROVES with explicit `async_step_pick_child` (D-02). HA developer docs §"Config Flow" — `async_set_unique_id`, `_abort_if_unique_id_configured`, `async_show_form`, `errors` dict.
**Internal analog (placeholder shape only):** Phase 1 `custom_components/ha_pronote/config_flow.py` lines 1-29 (the `class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN): VERSION = 1` declaration is preserved).

**Existing Phase 1 placeholder** (replace the `async_step_user` body):
```python
class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Placeholder config flow — real implementation in Phase 3."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reject user-initiated setup until Phase 3 ships the real flow."""
        return self.async_abort(reason="not_implemented")
```

**Phase 3 replacement pattern** (D-01..D-05, D-10..D-12):
```python
"""Real Config Flow — D-01 (single-step user form), D-02 (pick_child sub-step).

Calls api.client.build_client(...) via executor (Pitfall 6). Maps typed errors
from api/errors.py to errors={"base": "..."} per D-04. unique_id format per D-05.
child_identifier source per D-10 (slugify(name)) frozen at flow time per D-11.
"""

from __future__ import annotations

from functools import partial
from typing import Any
from urllib.parse import urlparse

import pronotepy
from slugify import slugify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import AuthError, CommunicationError, PronoteIntegrationError, RateLimitedError, build_client
from .const import DOMAIN

_USER_SCHEMA = vol.Schema(
    {
        vol.Required("url"): vol.Url(),  # D-03 — voluptuous URL validator
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Real flow — D-01 user step, optional D-02 pick_child step."""

    VERSION = 1

    def __init__(self) -> None:
        """Stash inter-step state."""
        self._client: pronotepy.Client | pronotepy.ParentClient | None = None
        self._user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single-step credential form per D-01."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await self.hass.async_add_executor_job(
                    partial(
                        build_client,
                        user_input["url"],
                        user_input["account_type"],
                        user_input["username"],
                        user_input["password"],
                    )
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except RateLimitedError:
                errors["base"] = "ip_suspended"
            except CommunicationError:
                errors["base"] = "cannot_connect"
            except PronoteIntegrationError:
                errors["base"] = "unknown"
            else:
                self._client = client
                self._user_input = user_input
                # D-01 — eleve OR parent-with-1-child = direct entry create.
                if isinstance(client, pronotepy.ParentClient) and len(client.children) > 1:
                    return await self.async_step_pick_child()
                return await self._create_entry(child_index=None)

        return self.async_show_form(
            step_id="user", data_schema=_USER_SCHEMA, errors=errors
        )

    async def async_step_pick_child(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """D-02 — single-select dropdown of ParentClient.children."""
        assert self._client is not None and isinstance(self._client, pronotepy.ParentClient)
        children = self._client.children
        if user_input is not None:
            return await self._create_entry(child_index=int(user_input["child_index"]))

        schema = vol.Schema(
            {
                vol.Required("child_index"): vol.In(
                    {str(i): child.name for i, child in enumerate(children)}
                )
            }
        )
        return self.async_show_form(step_id="pick_child", data_schema=schema)

    async def _create_entry(self, child_index: int | None) -> ConfigFlowResult:
        """Common tail — set child if needed, derive identifier, set unique_id, create entry."""
        assert self._client is not None and self._user_input is not None

        if child_index is not None and isinstance(self._client, pronotepy.ParentClient):
            await self.hass.async_add_executor_job(self._client.set_child, child_index)
            child_name = self._client.children[child_index].name
        elif isinstance(self._client, pronotepy.ParentClient):
            child_name = self._client.children[0].name
        else:
            child_name = self._client.info.name

        child_identifier = slugify(child_name)  # D-10
        # D-12 collision suffix — Phase 3 ships hex tail derivation.
        # (planner: spell out the precheck pass with hex suffix from
        # client.children[i].identifier when slug collides; falls back to clean slug otherwise.)

        url_host = urlparse(self._user_input["url"]).hostname or ""
        unique_id = f"{url_host.lower()}:{self._user_input['username']}:{child_identifier}"  # D-05
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        session = await self.hass.async_add_executor_job(self._client.export_credentials)  # D-06

        return self.async_create_entry(
            title=f"{child_name} ({self._user_input['account_type']})",
            data={
                "url": self._user_input["url"],
                "account_type": self._user_input["account_type"],
                "username": self._user_input["username"],
                "password": self._user_input["password"],  # D-08 — kept for AUTH-04 fallback
                "session": session,
                "child_identifier": child_identifier,  # D-11 frozen
                "child_index": child_index,
                "child_name": child_name,
            },
        )
```

**Banned in this file:**
- NO `requests` calls outside pronotepy
- NO synchronous pronotepy calls without `async_add_executor_job` (Pitfall 6)
- NO HEAD probe before auth (D-03 explicitly rejects)

---

### `custom_components/ha_pronote/api/client.py` (EXTEND — service, sync facade)

**Internal analog (the file itself):** `custom_components/ha_pronote/api/client.py` lines 19-58 — `build_client(url, account_type, username, password)` is the existing function. Phase 3 ADDS a sibling `build_or_resume_client(...)` that wraps the same `try/except` ladder and adds `device_name` kwarg + `token_login` fast path.

**Existing pattern** (lines 19-58 — DO NOT MODIFY):
```python
def build_client(
    url: str,
    account_type: AccountType,
    username: str,
    password: str,
) -> pronotepy.Client | pronotepy.ParentClient:
    """Construct a pronotepy client (D-21)."""
    cls: type[pronotepy.Client | pronotepy.ParentClient]
    cls = pronotepy.ParentClient if account_type == "parent" else pronotepy.Client
    try:
        return cls(url, username=username, password=password)
    except pronotepy.exceptions.CryptoError as err:
        raise AuthError(str(err)) from err
    except pronotepy.PronoteAPIError as err:
        if _IP_SUSPENDED_LITERAL in str(err):
            raise RateLimitedError(str(err)) from err
        raise CommunicationError(
            str(err),
            reason=ErrorReason.PROTOCOL_BROKEN,
        ) from err
    except OSError as err:
        raise CommunicationError(str(err)) from err
```

**Phase 3 extension pattern** (C-02, C-04, D-07, D-18, AUTH-07):
```python
def build_or_resume_client(
    url: str,
    account_type: AccountType,
    username: str,
    password: str,
    session: dict[str, Any] | None,
    device_name: str,
) -> pronotepy.Client | pronotepy.ParentClient:
    """Resume from stored session if present (token_login), else fresh login (D-07).

    Args:
        url, account_type, username, password: same as ``build_client``.
        session: dict from a prior ``client.export_credentials()`` call,
            or ``None`` to skip the token_login fast path.
        device_name: AUTH-07 label (e.g. ``"home-assistant-abc12345"``) — surfaces
            in the user's Pronote app under "connected devices" (D-18).

    Returns:
        Same as ``build_client``.

    Raises:
        AuthError, RateLimitedError, CommunicationError — same mapping as ``build_client``.
    """
    cls: type[pronotepy.Client | pronotepy.ParentClient]
    cls = pronotepy.ParentClient if account_type == "parent" else pronotepy.Client

    # D-07 fast path — token_login if we have stored session.
    if session is not None:
        try:
            return cls.token_login(
                url,
                username=username,
                device_name=device_name,
                **session,
            )
        except pronotepy.exceptions.CryptoError:
            # Stale session — fall through to fresh login.
            pass
        except pronotepy.PronoteAPIError:
            # token_login can fail for non-auth reasons (e.g. session expired);
            # treat all token_login failures as a signal to do fresh login.
            pass
        except OSError:
            # Network failure during token_login — fresh login won't help either,
            # but try once: if Pronote is reachable but session was just rejected,
            # fresh login succeeds.
            pass

    # Fresh login — same error mapping as build_client.
    try:
        return cls(url, username=username, password=password, device_name=device_name)
    except pronotepy.exceptions.CryptoError as err:
        raise AuthError(str(err)) from err
    except pronotepy.PronoteAPIError as err:
        if _IP_SUSPENDED_LITERAL in str(err):
            raise RateLimitedError(str(err)) from err
        raise CommunicationError(
            str(err),
            reason=ErrorReason.PROTOCOL_BROKEN,
        ) from err
    except OSError as err:
        raise CommunicationError(str(err)) from err
```

**Add to `api/__init__.py` re-exports:**
```python
from .client import build_client, build_or_resume_client  # noqa
```

**D-19 invariant preserved:** `api/client.py` still imports nothing from `homeassistant.*`; `tests/test_no_ha_imports.py` continues to pass.

---

### `custom_components/ha_pronote/entity.py` (NEW — service, base class)

**External analog:** `delphiki/hass-pronote/.../entity.py` (idea only — single base class subclassed by every sensor) + HA developer docs §"`CoordinatorEntity`" + §"`DeviceInfo`".
**Internal analog (docstring shape only):** Phase 2 `api/__init__.py` lines 1-19 (module docstring style).

**Pattern** (C-01, D-15, D-17):
```python
"""Base entity class for HA-Pronote — C-01, D-15, D-17.

C-01 — single source of truth for the CoordinatorEntity base. Phase 4's
calendar.py and grades/notifications sensors will subclass this same base.

D-17 — DeviceInfo: identifiers={(DOMAIN, child_identifier)}, name=child_name,
manufacturer="Pronote". NO model/sw_version/configuration_url in Phase 3
(model = <class level> lands in Phase 4 per ROADMAP success criterion #2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import PronoteDataUpdateCoordinator
    from .data import PronoteConfigEntry


class PronoteEntity(CoordinatorEntity["PronoteDataUpdateCoordinator"]):
    """Base for every HA-Pronote entity (C-01, D-15)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: PronoteConfigEntry,
    ) -> None:
        """Bind to coordinator + entry; subclass declares unique_id + translation_key."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """D-17 — DeviceInfo from runtime_data + entry.data['child_name']."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.runtime_data.child_identifier)},
            name=self._entry.data["child_name"],
            manufacturer="Pronote",
        )

    @property
    def available(self) -> bool:
        """D-15 — coordinator failure -> entity unavailable."""
        return self.coordinator.last_update_success
```

**Anti-pattern guard:** NO `model=...` field (D-17 — Phase 4's owner). NO `sw_version`, NO `configuration_url`.

---

### `custom_components/ha_pronote/sensor.py` (NEW — service, HA platform)

**External analog:** HA developer docs §"Sensor entity" + `delphiki/hass-pronote/.../sensor.py` (idea — single-platform setup callback). `homeassistant.components.sensor.SensorEntity` / `SensorStateClass`.
**Internal analog (data read shape):** `api/models.py:Snapshot.lessons_today` property (lines 144-146) — locked Phase 2 D-16. Sensor reads `coordinator.data.lessons_today`.

**Pattern** (D-13, D-14, D-15, D-16):
```python
"""Sensor platform — D-14 (state-only), D-15 (PronoteEntity base), D-16 (state_class)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .const import DOMAIN
from .entity import PronoteEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PronoteDataUpdateCoordinator
    from .data import PronoteConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PronoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Single sensor in Phase 3 — Phase 4 adds grades, notifications."""
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([PronoteLessonsTodaySensor(coordinator, entry)])


class PronoteLessonsTodaySensor(PronoteEntity, SensorEntity):
    """TIME-01 — count of today's lessons. D-14 state-only, no extra_state_attributes."""

    _attr_translation_key = "lessons_today"
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "lessons"

    def __init__(self, coordinator, entry) -> None:
        """Bind unique_id per D-13 ``f"pronote_{child_identifier}_lessons_today"``."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"pronote_{entry.runtime_data.child_identifier}_lessons_today"
        )

    @property
    def native_value(self) -> int:
        """D-14 — state == count of today's lessons. Phase 4 adds J/J+1 attributes (TIME-02)."""
        return len(self.coordinator.data.lessons_today)
```

**Banned in this file:**
- NO `extra_state_attributes` (D-14 — Phase 4 adds TIME-02)
- NO `device_class` (D-16 — no fitting `SensorDeviceClass`)
- NO direct `coordinator.data.lessons` filter (use the locked Phase 2 `Snapshot.lessons_today` property — D-16)

---

### `custom_components/ha_pronote/strings.json` (EXTEND — config, i18n)

**Internal analog (the file itself):** Phase 1 `custom_components/ha_pronote/strings.json` (lines 1-7).
**External analog:** HA developer docs §"strings.json schema".

**Existing Phase 1 file** (replace `not_implemented` abort key):
```json
{
  "config": {
    "abort": {
      "not_implemented": "HA-Pronote is in early development. Account setup will be available in a future release."
    }
  }
}
```

**Phase 3 replacement** (D-01..D-05, D-15):
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Pronote",
        "data": {
          "url": "Pronote space URL",
          "account_type": "Account type",
          "username": "Username",
          "password": "Password"
        },
        "data_description": {
          "url": "Full URL of your Pronote space (e.g. https://0123456a.index-education.net/pronote/eleve.html).",
          "account_type": "'eleve' for the student's account, 'parent' for the parent portal."
        }
      },
      "pick_child": {
        "title": "Select child",
        "description": "Your Pronote account has multiple children. Choose which one to add. To add another child, run the integration setup again.",
        "data": {
          "child_index": "Child"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid credentials. Check your username and password.",
      "cannot_connect": "Cannot reach Pronote. Check the URL and your network.",
      "ip_suspended": "Your IP address has been temporarily suspended by Pronote. Wait a few minutes before retrying.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This Pronote account / child is already configured."
    }
  },
  "entity": {
    "sensor": {
      "lessons_today": {
        "name": "Lessons today"
      }
    }
  }
}
```

**Anti-pattern guard:** the `not_implemented` abort key MUST be removed — Phase 3 ships the real flow; if the key remains, dead-code lint fails. The Phase 1 `tests/test_init.py:test_config_flow_placeholder_aborts` MUST be deleted in the same change.

---

### `custom_components/ha_pronote/const.py` (APPEND — constants module)

**Internal analog (the file itself):** `custom_components/ha_pronote/const.py` lines 1-14 — Phase 1 + Phase 2 `Final`-typed constants. Phase 3 appends in the same shape.

**Existing Phase 1+2 contents** (lines 1-14 — DO NOT MODIFY):
```python
"""Constants for HA-Pronote."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_pronote"

# Phase 2 additions (D-15, D-18) — defaults consumed by Phase 3 coordinator.
# NOT imported by api/ — fetcher.py takes today / school_tz as arguments
# (D-17, D-18) so the api/ subpackage stays free of ambient state.
DEFAULT_SCHOOL_TZ: Final = "Pacific/Noumea"
DEFAULT_LOOKBACK_DAYS: Final = 7  # J-7
DEFAULT_LOOKAHEAD_DAYS: Final = 14  # J+14
```

**Phase 3 appendix** (D-24, D-25):
```python
# Phase 3 additions (D-24, D-25) — HA-side runtime defaults.
# Imports added at top of file (NOT inside the appendix):
#   from datetime import timedelta
#   from homeassistant.const import Platform

DEFAULT_REFRESH_INTERVAL: Final = timedelta(minutes=30)  # D-24
PLATFORMS: Final = (Platform.SENSOR,)                    # D-25 (Phase 4 adds CALENDAR)
```

**D-19 invariant note:** `const.py` now imports `homeassistant.const.Platform` — `tests/test_no_ha_imports.py` does NOT guard `const.py` (only `api/` and `diff/`). Confirmed by `tests/test_no_ha_imports.py:GUARDED_PATHS` (lines 28-33).

---

### `tests/conftest.py` (EXTEND — test fixture)

**Internal analog (the file itself):** `tests/conftest.py` lines 1-16 — Phase 1 PHACC autouse `enable_custom_integrations`.

**Existing Phase 1 fixture** (lines 1-16 — DO NOT MODIFY):
```python
"""Shared fixtures for HA-Pronote tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests.

    Without this, the ``hass`` fixture refuses to load anything from
    ``custom_components/`` and our integration would be invisible.
    """
    yield
```

**Phase 3 appendix pattern** (C-05 — `MagicMock` strategy for HA-side tests):
```python
# Phase 3 additions — HA-side test fixtures (C-05 — MagicMock at the
# build_or_resume_client seam, NOT requests-mock).

from datetime import date
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote.api.models import Snapshot
from custom_components.ha_pronote.const import DOMAIN


@pytest.fixture
def mock_pronote_client():
    """A MagicMock(spec=pronotepy.Client) — info.name, lessons(), grades, info, export_credentials."""
    client = MagicMock()
    client.info.name = "Jean Dupont"
    client.children = []  # eleve
    client.current_period = MagicMock()
    client.current_period.grades = []
    client.lessons = MagicMock(return_value=[])
    client.information_and_surveys = MagicMock(return_value=[])
    client.export_credentials = MagicMock(return_value={"token": "abc123"})
    return client


@pytest.fixture
def mock_parent_client_two_children():
    """A MagicMock for ParentClient with 2 children (D-02 pick_child path)."""
    client = MagicMock()
    children = [MagicMock(name="Alice"), MagicMock(name="Bob")]
    children[0].name = "Alice Dupont"
    children[1].name = "Bob Dupont"
    children[0].identifier = "a3b4c5"
    children[1].identifier = "d6e7f8"
    client.children = children
    client.set_child = MagicMock()
    client.lessons = MagicMock(return_value=[])
    client.current_period = MagicMock()
    client.current_period.grades = []
    client.information_and_surveys = MagicMock(return_value=[])
    client.export_credentials = MagicMock(return_value={"token": "parent_abc"})
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A MockConfigEntry with the D-08 entry.data shape pre-populated."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:user:jean_dupont",
        data={
            "url": "https://example.com/pronote/eleve.html",
            "account_type": "eleve",
            "username": "user",
            "password": "pass",
            "session": {"token": "abc123"},
            "child_identifier": "jean_dupont",
            "child_index": None,
            "child_name": "Jean Dupont",
        },
        version=1,
    )
```

---

### `tests/test_init.py` (EXTEND — test contract)

**Internal analog (the file itself):** `tests/test_init.py` lines 1-31 (Phase 1).

**Existing Phase 1 file** (DELETE `test_config_flow_placeholder_aborts` in Phase 3 — placeholder no longer ships):
```python
"""Smoke tests for the HA-Pronote package skeleton."""

from custom_components.ha_pronote import DOMAIN
from custom_components.ha_pronote.const import DOMAIN as DOMAIN_CONST


def test_domain_constant_is_ha_pronote() -> None:
    """The package's DOMAIN constant must equal the manifest.domain value."""
    assert DOMAIN == "ha_pronote"
    assert DOMAIN_CONST == DOMAIN


async def test_config_flow_placeholder_aborts(hass) -> None:
    """The Phase 1 placeholder Config Flow must abort cleanly.

    Once Phase 3 ships the real flow, this test will need to be replaced.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_implemented"
```

**Phase 3 replacement pattern** — keep `test_domain_constant_is_ha_pronote`; replace placeholder test with happy-path setup + migrate-skeleton check:
```python
"""Smoke + setup_entry contract tests for HA-Pronote (Phase 3)."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.ha_pronote import DOMAIN, async_migrate_entry
from custom_components.ha_pronote.const import DOMAIN as DOMAIN_CONST


def test_domain_constant_is_ha_pronote() -> None:
    """Unchanged from Phase 1."""
    assert DOMAIN == "ha_pronote"
    assert DOMAIN_CONST == DOMAIN


async def test_async_setup_entry_happy_path(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """C-05 — setup uses build_or_resume_client (mocked); coordinator first-refresh OK."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.client is mock_pronote_client
    assert mock_config_entry.runtime_data.child_identifier == "jean_dupont"


async def test_async_migrate_entry_returns_true(hass, mock_config_entry) -> None:
    """ENT-04 / D-26 — skeleton returns True; Phase 6+ fills the body."""
    assert await async_migrate_entry(hass, mock_config_entry) is True
```

---

### `tests/test_config_flow.py` (NEW — test, HA-side)

**Internal analog (idiom):** Phase 1 `tests/test_init.py:test_config_flow_placeholder_aborts` lines 19-31 (the `hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})` shape) + Phase 2 `tests/test_api/test_client.py` lines 11-28 (`_make_init_silent` / `_make_init_raising` monkeypatch idiom — applied here at the `build_client` seam).

**Phase 1 reference test** (lines 19-31):
```python
async def test_config_flow_placeholder_aborts(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_implemented"
```

**Phase 2 monkeypatch idiom** (`tests/test_api/test_client.py` lines 11-28):
```python
def _make_init_raising(exc: BaseException):
    def _raise(self, *_args, **_kwargs):
        raise exc
    return _raise


def _make_init_silent():
    def _ok(self, *_args, **_kwargs):
        return None
    return _ok
```

**Phase 3 pattern** (D-01..D-05, C-05 — patch `build_client` instead of pronotepy internals):
```python
"""HA-side tests for the real Config Flow (D-01..D-05).

C-05 — patch custom_components.ha_pronote.config_flow.build_client to return
a MagicMock client. This decouples HA-side tests from pronotepy internals
(which are exercised separately by tests/test_api/test_client.py via
requests-mock).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.ha_pronote.api import AuthError, CommunicationError, RateLimitedError
from custom_components.ha_pronote.const import DOMAIN


async def test_user_step_eleve_happy_path(hass, mock_pronote_client) -> None:
    """D-01 — eleve account, single-step flow creates entry directly."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        return_value=mock_pronote_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "url": "https://example.com/pronote/eleve.html",
                "account_type": "eleve",
                "username": "u",
                "password": "p",
            },
        )
    assert result["type"] == "create_entry"
    assert result["data"]["child_identifier"] == "jean_dupont"
    assert result["data"]["account_type"] == "eleve"


async def test_user_step_parent_two_children_transitions_to_pick_child(
    hass, mock_parent_client_two_children
) -> None:
    """D-02 — ParentClient with > 1 child triggers pick_child step."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        return_value=mock_parent_client_two_children,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "url": "https://example.com/pronote/parent.html",
                "account_type": "parent",
                "username": "u",
                "password": "p",
            },
        )
    assert result["type"] == "form"
    assert result["step_id"] == "pick_child"


@pytest.mark.parametrize(
    ("raised", "expected_error"),
    [
        (AuthError("bad creds"), "invalid_auth"),
        (RateLimitedError("Your IP address is suspended"), "ip_suspended"),
        (CommunicationError("network unreachable"), "cannot_connect"),
    ],
)
async def test_user_step_error_mapping(hass, raised, expected_error) -> None:
    """D-04 — AuthError -> invalid_auth; RateLimited -> ip_suspended; etc."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        side_effect=raised,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "url": "https://example.com/pronote/eleve.html",
                "account_type": "eleve",
                "username": "u",
                "password": "p",
            },
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}


async def test_unique_id_format_locks_d05(hass, mock_pronote_client) -> None:
    """D-05 — ``f"{url_host}:{username}:{child_identifier}"``."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        return_value=mock_pronote_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "url": "https://example.com/pronote/eleve.html",
                "account_type": "eleve",
                "username": "alice",
                "password": "p",
            },
        )
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "example.com:alice:jean_dupont"
```

---

### `tests/test_coordinator.py` (NEW — test, HA-side)

**Internal analog (idiom):** Phase 2 `tests/test_api/test_client.py` (monkeypatch idiom — at the `pronotepy.Client.__init__` level for that test; Phase 3 patches at `build_or_resume_client` instead per C-05).

**Phase 3 pattern** (D-06, D-07, D-09, D-19, D-22):
```python
"""HA-side tests for PronoteDataUpdateCoordinator (D-06, D-09, D-19, D-22)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ha_pronote.api import AuthError, RateLimitedError, ErrorReason


async def test_first_refresh_writes_session_to_entry_data(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-06 — coordinator captures export_credentials() after a successful poll."""
    mock_pronote_client.export_credentials.return_value = {"token": "fresh_token"}
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.data["session"] == {"token": "fresh_token"}


async def test_coordinator_data_is_snapshot(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-20 — coordinator.data: Snapshot directly (no extra wrapper)."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert hasattr(coordinator.data, "lessons_today")  # Snapshot duck-typing


async def test_auth_error_during_setup_raises_auth_failed(
    hass, mock_config_entry
) -> None:
    """D-22 — AuthError during async_config_entry_first_refresh -> ConfigEntryAuthFailed."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        side_effect=AuthError("bad creds"),
    ):
        # async_config_entry_first_refresh should bubble ConfigEntryAuthFailed
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is False  # setup failed cleanly


async def test_rate_limited_during_poll_raises_update_failed(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-22 — RateLimitedError -> UpdateFailed (Phase 5 reads .reason for backoff)."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        side_effect=RateLimitedError("Your IP address is suspended"),
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_no_blocking_calls_during_poll(
    hass, caplog, mock_config_entry, mock_pronote_client
) -> None:
    """COORD-02 — every pronotepy call wrapped in async_add_executor_job.

    HA's blocking-call detector logs "Detected blocking call" if a sync I/O
    call escapes the executor boundary. This test asserts the log is clean.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert "Detected blocking call" not in caplog.text
```

---

### `tests/test_sensor.py` (NEW — test, HA-side)

**Internal analog (idiom):** Phase 1 `tests/test_init.py` (lines 19-31 — `hass` fixture pattern). Phase 2 `tests/test_api/test_client.py` (the per-test `with patch(...)` idiom at the build_or_resume_client seam, C-05).

**Phase 3 pattern** (D-13, D-14, D-15, D-16, D-17):
```python
"""HA-side tests for PronoteLessonsTodaySensor (D-13..D-17)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from custom_components.ha_pronote.api.models import Snapshot, Lesson


async def test_sensor_native_value_equals_lessons_today_count(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-14 — native_value = len(coordinator.data.lessons_today)."""
    today = date(2026, 5, 7)
    snapshot = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[
            Lesson(
                date=today,
                start=...,  # tz-aware datetimes — fixture builder helper
                end=...,
                subject=f"Math{i}",
                teacher="Mme A",
                classroom="101",
                canceled=False,
                status="",
            )
            for i in range(3)
        ],
    )
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ), patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        return_value=snapshot,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_lessons_today")
    assert state is not None
    assert state.state == "3"


async def test_sensor_unique_id_locks_d13(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-13 — unique_id == ``f"pronote_{child_identifier}_lessons_today"``."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = hass.helpers.entity_registry.async_get(hass)  # noqa
    # Inspect via entity_registry by unique_id, OR by inspecting added entities.
    # Concrete pattern: list registered entries, filter by domain, assert unique_id.
    # Lock D-13: f"pronote_jean_dupont_lessons_today"


async def test_sensor_no_extra_state_attributes(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-14 — Phase 3 sensor is state-only; extra_state_attributes empty."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get("sensor.jean_dupont_lessons_today")
    # D-14: NO J/J+1 attributes in Phase 3 (added in Phase 4 TIME-02).
    assert "lessons" not in (state.attributes if state else {})
```

---

### `tests/test_token_persistence.py` (NEW — test, HA-side)

**Internal analog (idiom):** Phase 2 `tests/test_api/test_client.py` (monkeypatch on `pronotepy.Client.__init__` lines 31-44; Phase 3 monkeypatches `pronotepy.Client.token_login` analogously).

**Phase 3 pattern** (D-06, D-07, D-09):
```python
"""Token persistence round-trip — D-06, D-07, D-09."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pronotepy

from custom_components.ha_pronote.api import AuthError
from custom_components.ha_pronote.api.client import build_or_resume_client


def test_build_or_resume_client_uses_token_login_when_session_present(monkeypatch):
    """D-07 fast path — token_login first when session is non-None."""
    captured: dict = {}
    def _token_login(url, **kwargs):
        captured.update(kwargs)
        client = MagicMock(spec=pronotepy.Client)
        return client
    monkeypatch.setattr(pronotepy.Client, "token_login", classmethod(_token_login))

    client = build_or_resume_client(
        "https://example.com/pronote/eleve.html",
        "eleve",
        "u",
        "p",
        session={"token": "abc"},
        device_name="home-assistant-12345678",
    )
    assert client is not None
    assert captured.get("device_name") == "home-assistant-12345678"
    assert captured.get("token") == "abc"


def test_build_or_resume_client_falls_back_to_fresh_login_on_token_login_failure(
    monkeypatch,
):
    """D-07 — token_login fails -> fresh Client(...) call."""
    def _token_login_fail(*_a, **_kw):
        raise pronotepy.exceptions.CryptoError("Padding error")
    def _fresh_init_ok(self, *_args, **_kwargs):
        return None

    monkeypatch.setattr(pronotepy.Client, "token_login", classmethod(_token_login_fail))
    monkeypatch.setattr(pronotepy.Client, "__init__", _fresh_init_ok)

    client = build_or_resume_client(
        "https://example.com/pronote/eleve.html",
        "eleve",
        "u",
        "p",
        session={"token": "stale"},
        device_name="home-assistant-12345678",
    )
    assert client is not None  # fresh login succeeded


async def test_coordinator_writes_new_session_after_silent_recovery(
    hass, mock_config_entry, mock_pronote_client
) -> None:
    """D-09 — mid-poll AuthError -> single fresh re-login -> new session captured."""
    mock_config_entry.add_to_hass(hass)
    fresh_client = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "post_recovery"})
    fresh_client.lessons = MagicMock(return_value=[])
    fresh_client.current_period = MagicMock()
    fresh_client.current_period.grades = []
    fresh_client.information_and_surveys = MagicMock(return_value=[])

    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    # Make the fetch raise AuthError once, then recovery should rebuild client.
    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        side_effect=[AuthError("session expired"), MagicMock()],
    ), patch(
        "custom_components.ha_pronote.coordinator.build_or_resume_client",
        return_value=fresh_client,
    ):
        await coordinator.async_refresh()
    assert mock_config_entry.data["session"]["token"] == "post_recovery"
```

---

## Shared Patterns

### Executor wrap (COORD-02, Pitfall 3)

**Source:** `custom_components/ha_pronote/api/fetcher.py` is sync; coordinator + setup_entry + config_flow MUST wrap every pronotepy call. CLAUDE.md "What NOT to Use" — first row.
**Apply to:** `coordinator.py:_async_update_data`, `coordinator.py:_recover_from_auth_error`, `coordinator.py:_capture_session`, `__init__.py:async_setup_entry`, `config_flow.py:async_step_user`, `config_flow.py:async_step_pick_child`, `config_flow.py:_create_entry`.

```python
# Canonical shape — partial(...) so kwargs are preserved through executor:
result = await self.hass.async_add_executor_job(
    partial(fetch_all, self._client, today, self._school_tz, self._child_index)
)

# Or for simple positional calls:
session = await self.hass.async_add_executor_job(self._client.export_credentials)
```

### Error mapping (D-22)

**Source:** Phase 2 `api/errors.py` typed hierarchy + Phase 2 `api/client.py` lines 45-57 (the literal `_IP_SUSPENDED_LITERAL` substring check).
**Apply to:** `coordinator.py:_async_update_data` (catch + map), `__init__.py:async_setup_entry` (catch + map), `config_flow.py:async_step_user` (catch + form errors).

```python
# Coordinator + __init__:
try:
    snapshot = await ...
except AuthError as err:
    raise ConfigEntryAuthFailed(...) from err  # HA fires reauth (Phase 6)
except RateLimitedError as err:
    raise UpdateFailed(...) from err           # Phase 5 reads .reason for backoff
except (CommunicationError, PronoteIntegrationError) as err:
    raise UpdateFailed(...) from err

# Config Flow (errors dict, not exceptions):
except AuthError:
    errors["base"] = "invalid_auth"
except RateLimitedError:
    errors["base"] = "ip_suspended"
except CommunicationError:
    errors["base"] = "cannot_connect"
except PronoteIntegrationError:
    errors["base"] = "unknown"
```

### `runtime_data` typed pattern (D-21, ARCHITECTURE.md Pattern 6)

**Source:** HA developer docs §"`runtime_data`". `<canonical_refs>` ARCHITECTURE.md Pattern 6.
**Apply to:** `data.py` (defines), `__init__.py` (sets `entry.runtime_data = ...`), `sensor.py:async_setup_entry` (reads `entry.runtime_data.coordinator`), `entity.py:device_info` (reads `entry.runtime_data.child_identifier`).

```python
# data.py:
type PronoteConfigEntry = ConfigEntry[PronoteData]

# __init__.py:async_setup_entry:
entry.runtime_data = PronoteData(coordinator=..., client=..., ...)

# sensor.py:
async def async_setup_entry(hass, entry: PronoteConfigEntry, async_add_entities):
    coordinator = entry.runtime_data.coordinator
```

**Anti-pattern guard:** NEVER `hass.data[DOMAIN][entry.entry_id] = ...` (Anti-Pattern 6). NEVER store the live `pronotepy.Client` in `coordinator.data` (Anti-Pattern 7) — it goes in `entry.runtime_data.client`.

### tz-aware datetime (D-23, Pitfall 4)

**Source:** Phase 2 `api/fetcher.py:_localize` (lines 93-100). CLAUDE.md "What NOT to Use" — `pytz` is banned-API.
**Apply to:** `coordinator.py` (calls `dt_util.now(self._school_tz).date()` to inject `today` into `fetch_all`); `__init__.py:async_setup_entry` (constructs `ZoneInfo(DEFAULT_SCHOOL_TZ)`).

```python
# Coordinator:
import homeassistant.util.dt as dt_util  # HA's stdlib dt wrapper, NOT pytz
from zoneinfo import ZoneInfo

today = dt_util.now(self._school_tz).date()  # tz-aware "now" in school-local
```

### Banned-API discipline (CLAUDE.md "What NOT to Use" + Phase 1 D-30..D-35)

**Source:** `pyproject.toml` lines 138-142 — `[tool.ruff.lint.flake8-tidy-imports.banned-api]`.
**Apply to:** every Phase 3 file.

```toml
"async_timeout".msg = "use asyncio.timeout instead"  # D-30
"pytz".msg        = "use zoneinfo instead"           # D-31
"requests".msg    = "use pronotepy via executor (D-32)"
```

Phase 3 files MUST NOT import any of these. Use:
- `asyncio.timeout(seconds)` (stdlib ≥ 3.11) — never `async_timeout`
- `zoneinfo.ZoneInfo("Pacific/Noumea")` — never `pytz.timezone(...)`
- `pronotepy` only (via executor) — never `requests` directly
- `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` — never `aiohttp.ClientSession()` (NOT needed in Phase 3 — pronotepy does its own sync HTTP)
- Never `from pronotepy.ent import ...` (D-33)
- Never `entry.async_add_job(...)` (deprecated; use `hass.async_add_executor_job` per Phase 1 D-32)

### `MockConfigEntry` + `hass.config_entries.async_setup` (PHACC pattern)

**Source:** `pytest-homeassistant-custom-component` README §"Testing config flows" (RESEARCH.md L1149-1167). Phase 1 `tests/conftest.py:auto_enable_custom_integrations` autouse already enabled.
**Apply to:** `tests/test_config_flow.py`, `tests/test_coordinator.py`, `tests/test_sensor.py`, `tests/test_token_persistence.py`, extended `tests/test_init.py`.

```python
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Setup:
mock_config_entry.add_to_hass(hass)
with patch("custom_components.ha_pronote.build_or_resume_client",
           return_value=mock_pronote_client):
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

# Read state:
coordinator = mock_config_entry.runtime_data.coordinator
state = hass.states.get("sensor.jean_dupont_lessons_today")
```

### Mock at `build_or_resume_client` seam, NOT `requests` (C-05)

**Source:** `<decisions>` C-05 — RECOMMEND `MagicMock` of `pronotepy.Client`/`pronotepy.ParentClient` rather than `requests-mock` at the HTTP layer for HA-side tests. The `requests-mock` strategy stays for `tests/test_api/` (pure-python).
**Apply to:** all `tests/test_{config_flow,coordinator,sensor,token_persistence}.py`.

```python
# HA-side (Phase 3) — patch the seam:
with patch("custom_components.ha_pronote.build_or_resume_client",
           return_value=mock_pronote_client):
    ...

# Pure-Python (Phase 2) — requests-mock:
with requests_mock.Mocker() as mocker:
    mocker.post("https://example.com/pronote/...", json={...})
    ...
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase 3 file has at least an idea-level external analog (delphiki, HA Core docs, ludeeus blueprint) plus a Phase 1+2 internal idiom for module shape, error hierarchy reuse, dataclass discipline, or test plumbing. The greenfield zone is the runtime HA wiring; the cited external analogs cover it (CONTEXT.md `<canonical_refs>` + RESEARCH.md sections referenced inline). |

---

## Metadata

**Analog search scope:**
- `custom_components/ha_pronote/` (Phase 1+2 shipped)
- `tests/` (Phase 1+2 shipped)
- `.planning/phases/01-foundations-skeleton/` (PATTERNS.md, CONTEXT.md, plan files)
- `.planning/phases/02-api-diff-layer-ha-free/` (PATTERNS.md, CONTEXT.md, plan files)
- `pyproject.toml` (banned-api block)
- `CLAUDE.md` "What NOT to Use" table (binding for every Phase 3 file)

**External analogs cited (idea-only — NOT re-fetched):**
- `delphiki/HomeAssistant-Pronote/coordinator.py` (executor fetch + diff + bus fire shape)
- `delphiki/HomeAssistant-Pronote/config_flow.py` (single-step user form shape)
- `delphiki/HomeAssistant-Pronote/entity.py` (single base CoordinatorEntity)
- `delphiki/HomeAssistant-Pronote/__init__.py` (multi-platform setup)
- `bain3/pronotepy/clients.py` (`Client.token_login`, `ParentClient.set_child`, `Client.export_credentials`, `device_name` kwarg)
- HA developer docs §"DataUpdateCoordinator", §"Config Flow", §"DeviceInfo", §"`runtime_data`", §"`CoordinatorEntity`"
- `ludeeus/integration_blueprint` (subclass shape for ConfigFlow + minimal __init__)

**Files scanned (in-repo):** 25 (`__init__.py`, `const.py`, `manifest.json`, `strings.json`, `config_flow.py`, all `api/*.py`, all `diff/*.py`, all `tests/*.py`, all `tests/test_api/*.py`, all `tests/test_diff/*.py`, `pyproject.toml`, both Phase 1+2 PATTERNS.md and CONTEXT.md, `CLAUDE.md`).

**Pattern extraction date:** 2026-05-07.
