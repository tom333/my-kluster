# Phase 6: Auth Lifecycle & Options — Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 9 (5 modify production + 2 i18n + 2 tests)
**Analogs found:** 9/9 (every Phase 6 surface has a Phase 3/5 analog already in tree)

> **CRITICAL preface — read before any other section:**
> RESEARCH.md flags THREE deviations from CONTEXT.md that MUST be reflected in code:
> 1. **D-12 → use `OptionsFlowWithReload`**, NOT `entry.add_update_listener` (deprecated 2026-05-07).
> 2. **D-16 → drop `vol.Strip`** (doesn't exist); replace with `lambda v: v.strip()` in the `vol.All(...)` chain.
> 3. **`OptionsFlow.__init__` → do NOT assign `self.config_entry = config_entry`** (deprecated 2024.12, raises 2025.12). HA injects `self.config_entry` automatically.
>
> These three corrections are NOT optional. Every pattern below is written to comply.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `custom_components/ha_pronote/config_flow.py` (extend: `async_step_reauth`, `async_step_reauth_confirm`, `async_step_reconfigure`, `async_get_options_flow`, `HaPronoteOptionsFlow`) | controller (config flow handler) | request-response (form-submit cycle, HA-driven) | `config_flow.py:async_step_user` + `_create_entry` (same file, Phase 3) | **exact** |
| `custom_components/ha_pronote/__init__.py:async_setup_entry` (extend: read `school_tz` from `entry.options`) | service (entry-setup orchestrator) | request-response (HA lifecycle) | `__init__.py:async_setup_entry` lines 53-130 (Phase 3/5) | **exact (in-place)** |
| `custom_components/ha_pronote/coordinator.py:_resolve_options` (extend: 3 new option keys) | service (options-to-typed-dataclass adapter) | transform (dict → frozen dataclass) | `coordinator.py:_resolve_options` lines 374-436 (Phase 5) | **exact (in-place)** |
| `custom_components/ha_pronote/politesse.py` (extend: `PolitesseOptions.adaptive_enabled`, `compute_interval` short-circuit) | model + utility (frozen dataclass + pure function) | transform (now + options → timedelta) | `politesse.py:PolitesseOptions` + `compute_interval` lines 59-77, 282-348 (Phase 5) | **exact (in-place)** |
| `custom_components/ha_pronote/entity.py:device_info` (extend: nickname fallback) | model (entity base) | transform (entry → DeviceInfo) | `entity.py:PronoteEntity.device_info` lines 57-90 (Phase 3/4) | **exact (in-place)** |
| `custom_components/ha_pronote/const.py` (append: `DEFAULT_ADAPTIVE_POLLING_ENABLED`, `NICKNAME_MAX_LEN`) | config (constants) | n/a (constants only) | `const.py` lines 51-87 (Phase 5 append-block) | **exact** |
| `custom_components/ha_pronote/strings.json` (append: 5 new step blocks + abort/error keys) | config (i18n source-of-truth) | n/a | existing `config.step.user.*`, `config.error.*`, `config.abort.*` blocks | **exact (append-only)** |
| `custom_components/ha_pronote/translations/{en,fr}.json` (mirror strings.json additions) | config (i18n translations) | n/a | existing `en.json` + `fr.json` mirrors | **exact (append-only)** |
| `tests/test_config_flow.py` (extend: ~17 new tests across 3 groups) | test | request-response (PHACC `hass.config_entries.flow.async_init`/`async_configure`) | `tests/test_config_flow.py:test_user_step_*` + `test_already_configured_aborts` lines 42-152 (Phase 3) | **exact** |
| `tests/test_coordinator.py` (extend: `test_options_change_triggers_reload`, `test_adaptive_polling_disabled_skips_branch`) | test | request-response | `tests/test_coordinator.py:test_first_refresh_writes_session_to_entry_data` lines 53-75 | **role-match (coordinator setup harness reused)** |

**No new files.** Phase 6 is 100% in-place extension of existing modules.

---

## Pattern Assignments

### `config_flow.py` — reauth flow (controller, request-response)

**Analog:** `config_flow.py:async_step_user` + `_create_entry` (same file, lines 73-168)

The existing `async_step_user` pattern locks: voluptuous schema as module-level constant, `partial(...)` + `hass.async_add_executor_job(...)` for pronotepy calls, error mapping via `errors={"base": "..."}`. Reauth mirrors all three; the only addition is `_get_reauth_entry()` (HA 2024.10+ helper) and `async_update_reload_and_abort(data_updates=...)` (HA 2024 official commit idiom).

**Imports pattern to copy (from `config_flow.py:31-45`):**

```python
from __future__ import annotations

from functools import partial
from typing import Any
from urllib.parse import urlparse

import pronotepy
from slugify import slugify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import build_client, set_active_child
from .const import DOMAIN
```

**Phase 6 ADDS these imports:**

```python
from collections.abc import Mapping  # for async_step_reauth(entry_data: Mapping[str, Any])
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # for options.school_tz validation

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,  # ← CRITICAL: replaces deprecated add_update_listener (D-12 revision)
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .api import (
    AuthError,
    CommunicationError,
    PronoteIntegrationError,
    RateLimitedError,
    build_client,
    set_active_child,
)
from .api.client import build_or_resume_client  # reauth/reconfigure single seam (C-02 Phase 3)
from .const import (
    DEFAULT_AFTERNOON_INTERVAL,
    DEFAULT_AFTERNOON_WINDOW,
    DEFAULT_QUIET_CADENCE,
    DEFAULT_QUIET_HOURS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SCHOOL_TZ,
    DEFAULT_SUSPENDED_CADENCE,
    DOMAIN,
    NICKNAME_MAX_LEN,
)
```

**Voluptuous schema pattern** (analog: `config_flow.py:47-60`):

```python
_USER_SCHEMA = vol.Schema(
    {
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
```

**Phase 6 reauth schema (D-01) — two fields, password masked:**

```python
_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)
```

**Executor-job pattern to copy (from `config_flow.py:83-94`):**

```python
if user_input is not None:
    client = await self.hass.async_add_executor_job(
        partial(
            build_client,
            user_input["url"],
            user_input["account_type"],
            user_input["username"],
            user_input["password"],
        )
    )
    self._client = client
    self._user_input = user_input
```

**Phase 6 reauth body (analog adapted; D-01/D-02/D-03 + RESEARCH Pattern 1):**

```python
async def async_step_reauth(
    self, entry_data: Mapping[str, Any]
) -> ConfigFlowResult:
    """HA invokes this when ConfigEntryAuthFailed is raised. Trampoline."""
    return await self.async_step_reauth_confirm()

async def async_step_reauth_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """D-01 form: username + password. URL + account_type read from entry."""
    entry = self._get_reauth_entry()  # HA 2024.10+ helper — RESEARCH Pattern 1
    errors: dict[str, str] = {}

    if user_input is not None:
        # D-03: reuse existing device_name (entry_id stable across reauth).
        device_name = f"home-assistant-{entry.entry_id[:8]}"
        try:
            await self.hass.async_add_executor_job(
                partial(
                    build_or_resume_client,
                    entry.data["url"],
                    entry.data["account_type"],
                    user_input["username"],
                    user_input["password"],
                    None,                  # D-02: session=None → fresh login branch
                    device_name,
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
            # D-02: clear session. async_update_reload_and_abort merges via data_updates.
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    "username": user_input["username"],
                    "password": user_input["password"],
                    "session": None,
                },
            )

    return self.async_show_form(
        step_id="reauth_confirm",
        data_schema=_REAUTH_SCHEMA,
        errors=errors,
        description_placeholders={"child_name": entry.data["child_name"]},
    )
```

**Error-mapping pattern (verbatim from existing `test_user_step_error_mapping` lines 87-111 — assertions reuse the exact same exception → key mapping):**

```python
# Phase 3 D-04 mapping — DO NOT diverge in Phase 6:
#   AuthError              → errors={"base": "invalid_auth"}
#   RateLimitedError       → errors={"base": "ip_suspended"}
#   CommunicationError     → errors={"base": "cannot_connect"}
#   PronoteIntegrationError→ errors={"base": "unknown"}
```

**No-silent-exception rule (user memory `feedback_no_silent_exceptions.md`):** the four `except` arms above are the ONLY tolerated catches. NEVER `except Exception: pass`. NEVER `except: errors["base"] = "unknown"` as a fallthrough.

---

### `config_flow.py` — reconfigure flow (controller, request-response)

**Analog:** `config_flow.py:_create_entry` lines 118-168 (Phase 3) — the "validate + resolve child_identifier + assert unique_id" sequence is the pattern reconfigure mimics, but it commits via `async_update_reload_and_abort` instead of `async_create_entry`.

**`_create_entry` excerpt to mimic (lines 131-149):**

```python
if isinstance(self._client, pronotepy.ParentClient):
    if child_index is None:
        child_index = 0
    await self.hass.async_add_executor_job(set_active_child, self._client, child_index)
    child = self._client.children[child_index]
    child_name = child.name
else:
    child_name = self._client.info.name

child_identifier = slugify(child_name, separator="_")

# D-05 unique_id: f"{url_host.lower()}:{username}:{child_identifier}"
url_host = (urlparse(self._user_input["url"]).hostname or "").lower()
unique_id = f"{url_host}:{self._user_input['username']}:{child_identifier}"
await self.async_set_unique_id(unique_id)
self._abort_if_unique_id_configured()
```

**Phase 6 reconfigure body (D-05..D-08 + RESEARCH Pattern 2):**

```python
_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
    }
)


async def async_step_reconfigure(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """D-05: edit URL + account_type. Username/password preserved from entry.data."""
    entry = self._get_reconfigure_entry()  # HA 2024.10+
    errors: dict[str, str] = {}

    if user_input is not None:
        new_url = user_input["url"].strip()
        new_account_type = user_input["account_type"]
        device_name = f"home-assistant-{entry.entry_id[:8]}"

        # D-07: re-validate via the SAME single seam used by Phase 3 setup.
        try:
            client = await self.hass.async_add_executor_job(
                partial(
                    build_or_resume_client,
                    new_url,
                    new_account_type,
                    entry.data["username"],
                    entry.data["password"],
                    None,            # session=None — old session is for old URL
                    device_name,
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
            # D-06: re-derive child_identifier under the new URL.
            child_index = entry.data.get("child_index")
            if child_index is not None and hasattr(client, "set_child"):
                try:
                    await self.hass.async_add_executor_job(
                        set_active_child, client, child_index
                    )
                except AuthError:
                    errors["base"] = "invalid_auth"
                except (RateLimitedError, CommunicationError, PronoteIntegrationError):
                    errors["base"] = "cannot_connect"
                else:
                    child_name = client.children[child_index].name
            else:
                child_name = client.info.name

            if not errors:
                new_child_identifier = slugify(child_name, separator="_")
                if new_child_identifier != entry.data["child_identifier"]:
                    return self.async_abort(reason="child_identifier_changed")

                # D-08: clear session only if URL or account_type changed.
                old_url = entry.data["url"].strip()
                url_changed = new_url != old_url
                at_changed = new_account_type != entry.data["account_type"]
                data_updates: dict[str, Any] = {
                    "url": new_url,
                    "account_type": new_account_type,
                }
                if url_changed or at_changed:
                    data_updates["session"] = None

                # Belt-and-braces: assert unique_id stays the same.
                url_host = (urlparse(new_url).hostname or "").lower()
                await self.async_set_unique_id(
                    f"{url_host}:{entry.data['username']}:{new_child_identifier}"
                )
                self._abort_if_unique_id_mismatch(reason="child_identifier_changed")

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

    # First entry to step OR post-error re-render.
    return self.async_show_form(
        step_id="reconfigure",
        data_schema=self.add_suggested_values_to_schema(
            _RECONFIGURE_SCHEMA,
            {
                "url": entry.data["url"],
                "account_type": entry.data["account_type"],
            },
        ),
        errors=errors,
        description_placeholders={"child_name": entry.data["child_name"]},
    )
```

**Pitfall reminder (RESEARCH Pitfall #4):** `set_active_child` MUST be wrapped — its raw `pronotepy.CryptoError` is mapped by `api/client.py:set_active_child` to `AuthError`, but Phase 6 must still catch it explicitly in the reconfigure body to surface the form error correctly.

---

### `config_flow.py` — OptionsFlow (controller, request-response)

**Analog:** `config_flow.py:async_step_user` + `async_step_pick_child` (multi-step pattern with `self._user_input` inter-step state, lines 73-116) — the OptionsFlow mirrors this multi-step shape but uses `OptionsFlowWithReload` as base.

**Multi-step pattern from `async_step_user` → `async_step_pick_child` (lines 96-98):**

```python
# D-01: parent with >1 children -> pick_child; otherwise create.
if isinstance(client, pronotepy.ParentClient) and len(client.children) > 1:
    return await self.async_step_pick_child()
return await self._create_entry(child_index=None)
```

**Inter-step state stash pattern (`config_flow.py:68-71`):**

```python
def __init__(self) -> None:
    """Stash inter-step state -- pronotepy client + last user_input."""
    self._client: pronotepy.Client | pronotepy.ParentClient | None = None
    self._user_input: dict[str, Any] | None = None
```

**Phase 6 OptionsFlow (D-09..D-16 + RESEARCH Pattern 3):**

```python
_POLLING_SCHEMA = vol.Schema(
    {
        vol.Required("refresh_interval"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX,
                                 unit_of_measurement="min")
        ),
        vol.Required("adaptive_polling_enabled"): BooleanSelector(),
        vol.Required("afternoon_interval"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX,
                                 unit_of_measurement="min")
        ),
        vol.Required("afternoon_window_start"): TimeSelector(),
        vol.Required("afternoon_window_end"): TimeSelector(),
        vol.Required("suspended_cadence"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX,
                                 unit_of_measurement="min")
        ),
        vol.Required("quiet_cadence"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX,
                                 unit_of_measurement="min")
        ),
        vol.Required("quiet_hours_start"): TimeSelector(),
        vol.Required("quiet_hours_end"): TimeSelector(),
    }
)

# D-16 REVISED — vol.Strip doesn't exist; use lambda v: v.strip().
_DISPLAY_SCHEMA = vol.Schema(
    {
        vol.Optional("nickname", default=""): vol.All(
            cv.string,
            vol.Length(max=NICKNAME_MAX_LEN),
            lambda v: v.strip(),     # ← was vol.Strip in CONTEXT.md D-16
        ),
        vol.Required("school_tz", default=DEFAULT_SCHOOL_TZ): str,
    }
)


class HaPronoteOptionsFlow(OptionsFlowWithReload):
    """Phase 6 — multi-step OptionsFlow with auto-reload on commit."""

    def __init__(self) -> None:
        # CRITICAL Gotcha #3: do NOT assign self.config_entry = config_entry —
        # the property is read-only since HA 2025.12. HA injects it automatically.
        # Source: RESEARCH.md Critical Gotcha #3 (citing hacs/integration#4314,
        # rospogrigio/localtuya#1931, HA 2024.12 changelog).
        self._step1_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trampoline to step 'polling' (D-10)."""
        return await self.async_step_polling()

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """9-field 'Polling' form; transitions to async_step_display (D-10)."""
        if user_input is not None:
            self._step1_data = user_input
            return await self.async_step_display()

        suggested = _options_schema_defaults(self.config_entry)
        return self.async_show_form(
            step_id="polling",
            data_schema=self.add_suggested_values_to_schema(_POLLING_SCHEMA, suggested),
        )

    async def async_step_display(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """2-field 'Display' form; commits both step dicts (D-10/D-16)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Pitfall #5: validate school_tz IN THE FORM, not at coordinator setup.
            try:
                ZoneInfo(user_input["school_tz"])
            except (ZoneInfoNotFoundError, ValueError):
                errors["school_tz"] = "invalid_school_tz"
            else:
                # OptionsFlowWithReload triggers async_unload + async_setup.
                return self.async_create_entry(
                    title="",
                    data={**self._step1_data, **user_input},
                )

        suggested = _options_schema_defaults(self.config_entry)
        return self.async_show_form(
            step_id="display",
            data_schema=self.add_suggested_values_to_schema(_DISPLAY_SCHEMA, suggested),
            errors=errors,
        )


# In HaPronoteConfigFlow:

@staticmethod
@callback
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    """HA-standard hook. Critical Gotcha #3: don't pass config_entry to ctor."""
    return HaPronoteOptionsFlow()
```

**`_options_schema_defaults` helper (D-11) — single source of truth shared with `coordinator._resolve_options`:**

```python
def _options_schema_defaults(entry: ConfigEntry) -> dict[str, Any]:
    """D-11 — voluptuous defaults derived from the SAME const.DEFAULT_* the
    coordinator's _resolve_options reads. A drift between the two would mean
    the OptionsFlow UI shows a default that runtime never uses.

    Single-test invariant: for any empty-options entry,
        _options_schema_defaults(empty_entry) == _resolve_options(empty_entry).asdict()
    modulo the int(minutes) ↔ timedelta type mismatch on minute-valued keys.
    """
    opts = entry.options
    return {
        "refresh_interval": opts.get(
            "refresh_interval", int(DEFAULT_REFRESH_INTERVAL.total_seconds() // 60)
        ),
        "adaptive_polling_enabled": opts.get("adaptive_polling_enabled", True),
        "afternoon_interval": opts.get(
            "afternoon_interval", int(DEFAULT_AFTERNOON_INTERVAL.total_seconds() // 60)
        ),
        "afternoon_window_start": opts.get(
            "afternoon_window_start", DEFAULT_AFTERNOON_WINDOW[0].isoformat()
        ),
        "afternoon_window_end": opts.get(
            "afternoon_window_end", DEFAULT_AFTERNOON_WINDOW[1].isoformat()
        ),
        "quiet_hours_start": opts.get(
            "quiet_hours_start", DEFAULT_QUIET_HOURS[0].isoformat()
        ),
        "quiet_hours_end": opts.get(
            "quiet_hours_end", DEFAULT_QUIET_HOURS[1].isoformat()
        ),
        "suspended_cadence": opts.get(
            "suspended_cadence", int(DEFAULT_SUSPENDED_CADENCE.total_seconds() // 60)
        ),
        "quiet_cadence": opts.get(
            "quiet_cadence", int(DEFAULT_QUIET_CADENCE.total_seconds() // 60)
        ),
        "nickname": opts.get("nickname", ""),
        "school_tz": opts.get("school_tz", DEFAULT_SCHOOL_TZ),
    }
```

---

### `__init__.py:async_setup_entry` — `school_tz` per-entry override (service)

**Analog:** `__init__.py:async_setup_entry` lines 53-130 (Phase 3/5).

**ONE-LINE pattern change (line 64 today):**

```python
# CURRENT (line 64):
school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)  # Phase 6 OPT-04 reads entry.options.

# PHASE 6 REPLACEMENT (D-09 / OPT-04, RESEARCH Code Example 6):
school_tz_name = entry.options.get("school_tz", DEFAULT_SCHOOL_TZ)
try:
    school_tz = ZoneInfo(school_tz_name)
except (ZoneInfoNotFoundError, ValueError) as err:
    # Belt-and-braces: the OptionsFlow validates this (Pitfall #5), but a
    # corrupted entry (manual JSON edit, future-migration regression) must
    # still fail with ConfigEntryNotReady instead of a raw traceback.
    raise ConfigEntryNotReady(f"Invalid school_tz {school_tz_name!r}") from err
```

**Required import addition (alongside existing `from zoneinfo import ZoneInfo`):**

```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

**D-12 REVISION — DO NOT add `entry.add_update_listener` here.** `OptionsFlowWithReload` handles the reload internally; adding the listener would (a) emit the 2026-05-07 deprecation warning, (b) fire reloads TWICE on every options save (RESEARCH Critical Gotcha #1, warning signs).

---

### `coordinator.py:_resolve_options` — extend with 3 new keys (service, transform)

**Analog:** `coordinator.py:_resolve_options` lines 374-436 (Phase 5 — the entire helper is the pattern).

**Imports pattern (already present in coordinator.py header):**

```python
from .const import (
    DEFAULT_AFTERNOON_INTERVAL,
    DEFAULT_AFTERNOON_WINDOW,
    DEFAULT_QUIET_CADENCE,
    DEFAULT_QUIET_HOURS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SUSPENDED_CADENCE,
    JITTER_SECONDS,
    NC_VACATION_RANGES_2026,
    # ... + Phase 6 adds nothing here; defaults live in const.py
)
```

**Existing fallback-aware reader pattern (lines 384-408) — verbatim to mimic:**

```python
def _read_minutes(key: str, default: timedelta) -> timedelta:
    raw = opts.get(key)
    if raw is None:
        return default
    try:
        return timedelta(minutes=int(raw))
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Phase 5 _resolve_options: malformed option %s=%r; falling back to %s",
            key, raw, default,
        )
        return default
```

**Phase 6 EXTEND the return statement (current lines 419-436) with three new resolved values:**

```python
return PolitesseOptions(
    school_tz=self._school_tz,
    refresh_interval=_read_minutes("refresh_interval", DEFAULT_REFRESH_INTERVAL),
    afternoon_interval=_read_minutes("afternoon_interval", DEFAULT_AFTERNOON_INTERVAL),
    afternoon_window=(
        _read_time("afternoon_window_start", DEFAULT_AFTERNOON_WINDOW[0]),
        _read_time("afternoon_window_end", DEFAULT_AFTERNOON_WINDOW[1]),
    ),
    quiet_hours=(
        _read_time("quiet_hours_start", DEFAULT_QUIET_HOURS[0]),
        _read_time("quiet_hours_end", DEFAULT_QUIET_HOURS[1]),
    ),
    suspended_cadence=_read_minutes("suspended_cadence", DEFAULT_SUSPENDED_CADENCE),
    quiet_cadence=_read_minutes("quiet_cadence", DEFAULT_QUIET_CADENCE),
    vacation_ranges=NC_VACATION_RANGES_2026,
    holiday_dates=holiday_dates,
    jitter_seconds=JITTER_SECONDS,
    # Phase 6 NEW — bool, no fallback log needed (truthiness coerces None/missing → True via default)
    adaptive_enabled=bool(opts.get("adaptive_polling_enabled", True)),
)
```

**Note on `nickname` and `school_tz`:** these two are NOT read by `_resolve_options` because they don't feed `PolitesseOptions`. `nickname` is read by `entity.py:device_info` directly off `entry.options`; `school_tz` is read by `__init__.py:async_setup_entry` and converted to `ZoneInfo` before being injected into the coordinator. The single-source-of-truth invariant (D-11) holds because both read paths use the same `entry.options.get(KEY, DEFAULT_*)` shape.

**Error handling rule (carry forward):** `(ValueError, TypeError)` catch + `_LOGGER.warning` + fallback to default. NEVER bare `except`. The warning IS the trace (per `feedback_no_silent_exceptions.md`); the default IS the fallback. This is the project's "no silent exceptions" pattern.

---

### `politesse.py` — extend `PolitesseOptions` + `compute_interval` short-circuit (model + utility, transform)

**Analog:** `politesse.py:PolitesseOptions` lines 59-77 (frozen dataclass) + `compute_interval` lines 282-348 (pure function with branching).

**Existing dataclass pattern to extend (lines 59-77):**

```python
@dataclass(frozen=True)
class PolitesseOptions:
    school_tz: ZoneInfo
    refresh_interval: timedelta
    afternoon_interval: timedelta
    afternoon_window: tuple[time, time]
    quiet_hours: tuple[time, time]
    suspended_cadence: timedelta
    quiet_cadence: timedelta
    vacation_ranges: tuple[tuple[date, date], ...]
    holiday_dates: frozenset[date]
    jitter_seconds: int
```

**Phase 6 ADDS one field (with default to preserve forward-compat with Phase 5 test fixtures that don't pass it):**

```python
@dataclass(frozen=True)
class PolitesseOptions:
    # ... 10 existing fields unchanged ...
    jitter_seconds: int
    adaptive_enabled: bool = True   # NEW — Phase 6 OPT-02 (D-09)
```

**Existing `compute_interval` branching pattern (lines 313-348) — Phase 6 adds a TOP-OF-FUNCTION short-circuit:**

```python
def compute_interval(
    now: datetime,
    options: PolitesseOptions,
    *,
    rng: random.Random | random = random,
) -> timedelta:
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")

    # Phase 6 D-09 / OPT-02 — short-circuit when user disabled adaptive polling.
    # Skip the quiet-hours / suspended / afternoon branches entirely. Always return
    # refresh_interval + jitter, clamped to >= 1 min (matches the existing tail logic).
    if not options.adaptive_enabled:
        jittered = options.refresh_interval + timedelta(
            seconds=rng.uniform(-options.jitter_seconds, options.jitter_seconds)
        )
        return max(jittered, timedelta(minutes=1))

    # ... existing branches 1-4 unchanged below ...
    if is_quiet_hours(now, school_tz=options.school_tz, ...):
        base = options.quiet_cadence
    elif not should_poll(now, options):
        base = options.suspended_cadence
    # ... etc.
```

**Test invariant to add (tests/test_politesse_tz_matrix.py):** parametrize over the 4 existing branch-triggering `now` values; when `adaptive_enabled=False`, ALL four must collapse to `refresh_interval ± jitter`. The TZ matrix (Europe/Paris × Pacific/Noumea per Phase 5 DIST-06) carries forward; Phase 6 adds NO new TZ markers.

---

### `entity.py:device_info` — nickname fallback (model, transform)

**Analog:** `entity.py:PronoteEntity.device_info` lines 57-90 (Phase 3/4).

**Existing pattern (lines 73-90):**

```python
client = self._entry.runtime_data.client
if isinstance(client, pronotepy.ParentClient):
    child_index = self._entry.runtime_data.child_index
    if child_index is not None:
        info_obj = client.children[child_index]
    else:
        info_obj = client.info
else:
    info_obj = client.info
class_label = getattr(info_obj, CLASS_LEVEL_ATTR, None) or None
return DeviceInfo(
    identifiers={(DOMAIN, self._entry.runtime_data.child_identifier)},
    name=self._entry.data["child_name"],   # ← Phase 6 CHANGES this line only
    manufacturer="Pronote",
    model=class_label,
)
```

**Phase 6 ONE-LINE CHANGE (D-14, RESEARCH Code Example 7):**

```python
# D-14: empty-after-strip → fall back to entry.data["child_name"] (Phase 3 D-08).
# Matches the OptionsFlow validation (D-16 revised) where vol.All(.strip()) already
# coerces "   " → "" — but defensive-strip here protects against legacy entries.
display_name = (
    (self._entry.options.get("nickname") or "").strip()
    or self._entry.data["child_name"]
)

return DeviceInfo(
    identifiers={(DOMAIN, self._entry.runtime_data.child_identifier)},
    name=display_name,                       # CHANGED — was entry.data["child_name"]
    manufacturer="Pronote",
    model=class_label,
)
```

**No new imports.** `DeviceInfo` is already imported (line 33).

**Has-entity-name invariant:** `_attr_has_entity_name = True` (line 46) means HA composes the displayed entity label as `f"{DeviceInfo.name} {entity.name}"` (e.g. "Petit Louïc Notes"). Nickname propagates to ALL sensors automatically on reload — no per-sensor code change needed (ENT-03).

---

### `const.py` — append two new constants (config)

**Analog:** existing append-block pattern (lines 51-87) where Phase 5 added `BACKOFF_SCHEDULE`, `JITTER_SECONDS`, `DEFAULT_AFTERNOON_INTERVAL`, etc.

**Existing block to mirror (lines 60-72):**

```python
BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
    timedelta(hours=1),
    timedelta(hours=2),
    timedelta(hours=4),
    timedelta(hours=12),
    timedelta(hours=24),
)
JITTER_SECONDS: Final = 30
DEFAULT_AFTERNOON_INTERVAL: Final = timedelta(minutes=15)
```

**Phase 6 appends (RESEARCH Code Example 3):**

```python
# Phase 6 additions — OptionsFlow OPT-02 + OPT-03 defaults.
# D-09 Phase 6 — adaptive polling toggle defaults to ON (preserve Phase 5 behaviour).
# D-16 Phase 6 — nickname length cap (40 chars covers long French + emoji names
# without risking the 255-char limit on sensor state strings).

DEFAULT_ADAPTIVE_POLLING_ENABLED: Final = True
NICKNAME_MAX_LEN: Final = 40
```

**`DEFAULT_SCHOOL_TZ` already exists** (line 15) — no change needed there. RESEARCH Code Example 3 confirms.

---

### `strings.json` — append new step blocks + abort/error keys (config, i18n)

**Analog:** existing `config.step.user.*` and `config.step.pick_child.*` blocks (lines 4-23) — same nested shape: `title` / `description` / `data` / optional `data_description`.

**Existing block to mirror (verbatim from `strings.json` lines 4-23):**

```jsonc
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
  }
}
```

**Phase 6 appends (RESEARCH Code Example 2 — five new blocks):**

```jsonc
// Inside "config.step":
"reauth_confirm": {
  "title": "Re-authenticate Pronote",
  "description": "Pronote rejected the stored credentials for {child_name}. Enter the current username and password.",
  "data": {
    "username": "Username",
    "password": "Password"
  }
},
"reconfigure": {
  "title": "Change Pronote URL or account type",
  "description": "Edit the Pronote space URL or account type for {child_name}. Username and password stay the same.",
  "data": {
    "url": "Pronote space URL",
    "account_type": "Account type"
  }
}

// "config.abort" gains:
"reauth_successful": "Re-authentication successful — Pronote credentials updated.",
"reconfigure_successful": "Configuration successful — Pronote settings updated.",
"child_identifier_changed": "The new URL/account exposes a different child. Delete this entry and re-add it to track the new child."

// NEW top-level "options" sibling to "config":
"options": {
  "step": {
    "polling": {
      "title": "Polling",
      "description": "How often HA-Pronote queries Pronote, when to poll more frequently, and when to stay quiet.",
      "data": {
        "refresh_interval": "Refresh interval (min)",
        "adaptive_polling_enabled": "Tighten polling 17h–20h on school evenings",
        "afternoon_interval": "Afternoon refresh interval (min)",
        "afternoon_window_start": "Afternoon tightening starts",
        "afternoon_window_end": "Afternoon tightening ends",
        "suspended_cadence": "Suspended cadence (weekends, vacations) (min)",
        "quiet_cadence": "Night quiet cadence (min)",
        "quiet_hours_start": "Quiet hours start",
        "quiet_hours_end": "Quiet hours end"
      }
    },
    "display": {
      "title": "Display",
      "description": "Optional per-child nickname and school timezone.",
      "data": {
        "nickname": "Child nickname (display only)",
        "school_tz": "School timezone (IANA, e.g. Pacific/Noumea or Europe/Paris)"
      }
    }
  },
  "error": {
    "invalid_school_tz": "Unknown timezone. Use an IANA name like Pacific/Noumea or Europe/Paris."
  }
}
```

**i18n dotted-path convention (existing):** `config.step.<step_id>.title`, `config.step.<step_id>.data.<field>`, `config.error.<key>`, `config.abort.<reason>`. Phase 6 reuses this verbatim. The `{child_name}` placeholder is interpolated by HA core via `description_placeholders={"child_name": ...}` in `async_show_form` (RESEARCH Pitfall #7).

---

### `translations/{en,fr}.json` — mirror strings.json additions (config, i18n)

**Analog:** existing `en.json` and `fr.json` — they are byte-for-byte mirrors of `strings.json` for the EN locale, and a hand-translated mirror for FR (Phase 5 ships both with all keys translated).

**`fr.json` translation reference (from existing lines 4-22):**

```jsonc
"config": {
  "step": {
    "user": {
      "title": "Connexion à Pronote",
      "data": {
        "url": "URL de votre espace Pronote",
        "account_type": "Type de compte",
        "username": "Identifiant",
        "password": "Mot de passe"
      }
    }
  },
  "error": {
    "invalid_auth": "Identifiants invalides. Vérifiez votre identifiant et votre mot de passe.",
    "cannot_connect": "Impossible de joindre Pronote. Vérifiez l'URL et votre connexion réseau.",
    "ip_suspended": "Votre IP a été suspendue temporairement par Pronote. Patientez quelques minutes avant de réessayer.",
    "unknown": "Une erreur inattendue est survenue."
  },
  "abort": {
    "already_configured": "Ce compte / enfant Pronote est déjà configuré."
  }
}
```

**Phase 6 FR additions (Claude rédige — CONTEXT.md "Claude's Discretion: Translations i18n"):**

```jsonc
"reauth_confirm": {
  "title": "Ré-authentification Pronote",
  "description": "Pronote a rejeté les identifiants enregistrés pour {child_name}. Saisissez l'identifiant et le mot de passe actuels.",
  "data": {
    "username": "Identifiant",
    "password": "Mot de passe"
  }
},
"reconfigure": {
  "title": "Modifier l'URL ou le type de compte Pronote",
  "description": "Modifiez l'URL de l'espace Pronote ou le type de compte pour {child_name}. L'identifiant et le mot de passe restent inchangés.",
  "data": {
    "url": "URL de votre espace Pronote",
    "account_type": "Type de compte"
  }
},
// abort:
"reauth_successful": "Ré-authentification réussie — identifiants Pronote mis à jour.",
"reconfigure_successful": "Configuration réussie — paramètres Pronote mis à jour.",
"child_identifier_changed": "La nouvelle URL/compte expose un enfant différent. Supprimez cette entrée et recréez-la pour suivre le nouvel enfant."
// "options" block: same shape, French labels for the 11 keys.
```

**EN mirrors `strings.json` verbatim.** Phase 7 I18N-01/I18N-02 does the exhaustive sweep; Phase 6 only ships the Phase 6 keys.

---

### `tests/test_config_flow.py` — extend with reauth/reconfigure/options tests (test)

**Analog:** entire file `tests/test_config_flow.py` (Phase 3, 8 test functions). Each Phase 6 test mimics one of the existing 8.

**Existing test pattern — happy path (`test_user_step_eleve_happy_path` lines 42-56):**

```python
async def test_user_step_eleve_happy_path(hass, mock_pronote_client) -> None:
    """D-01: eleve account, single-step flow creates entry directly."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        return_value=mock_pronote_client,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=_USER_INPUT_ELEVE)
    assert result["type"] == "create_entry"
    assert result["data"]["child_identifier"] == "jean_dupont"
    assert result["data"]["account_type"] == "eleve"
    assert result["data"]["child_name"] == "Jean Dupont"
```

**Existing test pattern — parametrized error mapping (`test_user_step_error_mapping` lines 87-111):**

```python
@pytest.mark.parametrize(
    ("raised", "expected_error"),
    [
        (AuthError("bad creds"), "invalid_auth"),
        (RateLimitedError("Your IP address is suspended"), "ip_suspended"),
        (CommunicationError("network unreachable"), "cannot_connect"),
        (PronoteIntegrationError(ErrorReason.PARSE_ERROR, "weird"), "unknown"),
    ],
)
async def test_user_step_error_mapping(hass, raised, expected_error) -> None:
    """D-04: AuthError -> invalid_auth; RateLimited -> ip_suspended; etc."""
    with patch(
        "custom_components.ha_pronote.config_flow.build_client",
        side_effect=raised,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=_USER_INPUT_ELEVE)
    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}
```

**Existing test pattern — pre-seeded MockConfigEntry (`test_already_configured_aborts` lines 134-152):**

```python
pre_existing = MockConfigEntry(
    domain=DOMAIN,
    unique_id="example.com:alice:jean_dupont",
    data={"placeholder": "preexisting"},
    version=1,
)
pre_existing.add_to_hass(hass)
```

**Phase 6 reauth test template (RESEARCH Pattern 5):**

```python
_ENTRY_DATA = {
    "url": "https://example.com/pronote/eleve.html",
    "account_type": "eleve",
    "username": "alice",
    "password": "old_pw",
    "session": {"token": "old"},
    "child_identifier": "jean_dupont",
    "child_index": None,
    "child_name": "Jean Dupont",
}


async def test_reauth_flow_happy_path(hass, mock_pronote_client) -> None:
    """AUTH-05: D-01/D-02/D-03 — new credentials persisted, session cleared."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data=_ENTRY_DATA,
        version=1,
    )
    entry.add_to_hass(hass)

    # PHACC helper — equivalent to HA raising ConfigEntryAuthFailed.
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.ha_pronote.config_flow.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"username": "alice", "password": "new_pw"},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data["username"] == "alice"
    assert entry.data["password"] == "new_pw"
    assert entry.data["session"] is None              # D-02
    assert entry.data["url"] == _ENTRY_DATA["url"]    # D-08 preserved (merge, not replace)
    assert entry.data["account_type"] == "eleve"
    assert entry.data["child_identifier"] == "jean_dupont"
```

**Phase 6 reauth error-mapping (mimics Phase 3 `test_user_step_error_mapping`):**

```python
@pytest.mark.parametrize(
    ("raised", "expected_error"),
    [
        (AuthError("bad creds"), "invalid_auth"),
        (RateLimitedError("Your IP address is suspended"), "ip_suspended"),
        (CommunicationError("network down"), "cannot_connect"),
        (PronoteIntegrationError(ErrorReason.PARSE_ERROR, "x"), "unknown"),
    ],
)
async def test_reauth_error_mapping(hass, raised, expected_error) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="example.com:alice:jean_dupont",
                            data=_ENTRY_DATA, version=1)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    with patch(
        "custom_components.ha_pronote.config_flow.build_or_resume_client",
        side_effect=raised,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"username": "alice", "password": "p"}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}
```

**Phase 6 options test template:**

```python
async def test_options_flow_polling_then_display_commit(hass, mock_pronote_client) -> None:
    """COORD-03 + OPT-01..OPT-04 — multi-step OptionsFlow writes all 11 keys."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="example.com:alice:jean_dupont",
                            data=_ENTRY_DATA, version=1)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "polling"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "refresh_interval": 15,
            "adaptive_polling_enabled": False,
            "afternoon_interval": 10,
            "afternoon_window_start": "17:00:00",
            "afternoon_window_end": "20:00:00",
            "suspended_cadence": 360,
            "quiet_cadence": 240,
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "06:00:00",
        },
    )
    assert result["step_id"] == "display"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"nickname": "Jeannot", "school_tz": "Pacific/Noumea"},
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert entry.options["refresh_interval"] == 15
    assert entry.options["adaptive_polling_enabled"] is False
    assert entry.options["nickname"] == "Jeannot"
    assert entry.options["school_tz"] == "Pacific/Noumea"
```

**Multi-child isolation test (RESEARCH Pattern 4):** mimics `test_already_configured_aborts` but creates TWO entries with different `child_identifier`, opens options on entry A only, asserts entry B's options unchanged.

**Test data fixture (NEW module-level constant — mirror existing `_USER_INPUT_ELEVE` lines 27-32):**

```python
# Module-level reusable entry-data dict for reauth/reconfigure tests.
# Mirrors mock_config_entry fixture (tests/conftest.py:91) but module-local
# to keep multi-entry tests self-contained.
_ENTRY_DATA = {
    "url": "https://example.com/pronote/eleve.html",
    "account_type": "eleve",
    "username": "alice",
    "password": "old_pw",
    "session": {"token": "old"},
    "child_identifier": "jean_dupont",
    "child_index": None,
    "child_name": "Jean Dupont",
}
```

---

### `tests/test_coordinator.py` — extend with options-reload + adaptive-disabled tests (test)

**Analog:** `tests/test_coordinator.py:test_first_refresh_writes_session_to_entry_data` lines 53-75 (setup-entry-then-assert pattern). The autouse `_frozen_school_day` fixture (lines 42-50) is unmodified — Phase 6 tests inherit the same Thursday 14:00 NC clock pin.

**Existing pattern (lines 53-75):**

```python
async def test_first_refresh_writes_session_to_entry_data(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-06: coordinator captures export_credentials() after a successful poll."""
    today = date(2026, 5, 7)
    mock_pronote_client.export_credentials.return_value = {"token": "fresh_token"}
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.data["session"] == {"token": "fresh_token"}
```

**Phase 6 `test_options_change_triggers_reload` template:**

```python
async def test_options_change_triggers_reload(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """COORD-03 / OPT-04: OptionsFlowWithReload causes coordinator re-instantiation.

    No add_update_listener needed (D-12 REVISED — OptionsFlowWithReload handles it).
    """
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client",
              return_value=mock_pronote_client),
        patch("custom_components.ha_pronote.coordinator.fetch_all",
              return_value=snapshot_with_n_lessons_today(today, n=1)),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coord_before = mock_config_entry.runtime_data.coordinator

        # Drive the OptionsFlow to completion.
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={...9 polling keys...}
        )
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"nickname": "", "school_tz": "Pacific/Noumea"}
        )
        await hass.async_block_till_done()

    # OptionsFlowWithReload teardown + re-setup → new coordinator instance.
    coord_after = mock_config_entry.runtime_data.coordinator
    assert coord_after is not coord_before
```

**Phase 6 `test_adaptive_polling_disabled_skips_branch` (pure-Python — lives in `tests/test_politesse_tz_matrix.py`, not test_coordinator.py — better split):**

```python
def test_compute_interval_respects_adaptive_disabled() -> None:
    """OPT-02 D-09 — adaptive_enabled=False bypasses afternoon/quiet/suspended branches."""
    # Build options with adaptive_enabled=False; pick a `now` that WOULD trigger
    # the afternoon-window branch under adaptive_enabled=True; assert we get
    # refresh_interval ± jitter instead.
    options = PolitesseOptions(
        school_tz=ZoneInfo("Pacific/Noumea"),
        refresh_interval=timedelta(minutes=30),
        # ... etc ...
        adaptive_enabled=False,
    )
    now = datetime(2026, 5, 7, 18, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    rng = random.Random(42)  # reproducible jitter
    interval = compute_interval(now, options, rng=rng)
    assert timedelta(minutes=29, seconds=30) <= interval <= timedelta(minutes=30, seconds=30)
```

**conftest.py read-only constraint** (per upstream input "tests/conftest.py — read but DO NOT extend"): the existing `mock_pronote_client`, `mock_parent_client_two_children`, `mock_config_entry`, `mock_persistent_notification` fixtures are reused without modification. NO new autouse fixtures in Phase 6.

---

## Shared Patterns

### Authentication / pronotepy seam

**Source:** `custom_components/ha_pronote/api/client.py:build_or_resume_client` lines 71-154 (Phase 3 C-02)

**Apply to:** Both `async_step_reauth_confirm` AND `async_step_reconfigure` in `config_flow.py`. NEVER call `pronotepy.Client(...)` or `Client.token_login(...)` directly — go through this single seam.

```python
# CALL SHAPE (used in __init__.py:71-82, coordinator.py, and Phase 6 reauth/reconfigure):
client = await hass.async_add_executor_job(
    partial(
        build_or_resume_client,
        url,
        account_type,
        username,
        password,
        session,         # None for fresh-login, dict for token_login fast path
        device_name,     # f"home-assistant-{entry.entry_id[:8]}"
    )
)

# RAISES (4 typed exceptions — map per Phase 3 D-04):
#   AuthError              ← pronotepy.CryptoError (wrong password)
#   RateLimitedError       ← "Your IP address is suspended" literal
#   CommunicationError     ← network / protocol failures
#   PronoteIntegrationError← catch-all parent class for "unknown"
```

### Error handling — no silent exceptions

**Source:** `custom_components/ha_pronote/coordinator.py:_resolve_options` lines 384-408 (typed `(ValueError, TypeError)` catch + warning + fallback) AND `config_flow.py:async_step_user` D-04 mapping (form errors dict).

**Apply to:** ALL Phase 6 try/except blocks. User memory `feedback_no_silent_exceptions.md` is binding.

```python
# PATTERN A — form-level mapping (config_flow.py D-04, Phase 6 reauth/reconfigure):
except AuthError:
    errors["base"] = "invalid_auth"
except RateLimitedError:
    errors["base"] = "ip_suspended"
except CommunicationError:
    errors["base"] = "cannot_connect"
except PronoteIntegrationError:
    errors["base"] = "unknown"
# No bare except. No `except Exception:`. No `try: ... except: pass`.

# PATTERN B — resolve-fallback with explicit log (coordinator._resolve_options):
try:
    return timedelta(minutes=int(raw))
except (ValueError, TypeError):
    _LOGGER.warning(
        "_resolve_options: malformed option %s=%r; falling back to %s",
        key, raw, default,
    )
    return default
# The warning IS the trace. The default IS the fallback. Never both swallowed.
```

### Voluptuous schema construction

**Source:** `config_flow.py:_USER_SCHEMA` lines 47-60 (Phase 3).

**Apply to:** All four new schemas — `_REAUTH_SCHEMA`, `_RECONFIGURE_SCHEMA`, `_POLLING_SCHEMA`, `_DISPLAY_SCHEMA`. Module-level constants (NOT instance fields), named with leading underscore, `vol.Required` for everything except optional nickname (`vol.Optional("nickname", default="")`).

```python
# Existing convention:
_USER_SCHEMA = vol.Schema(
    {
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
```

### i18n key dotted-path convention

**Source:** `strings.json` lines 4-33 (Phase 3) + `en.json` + `fr.json`.

**Apply to:** All Phase 6 i18n additions. Schema:

```
config.step.<step_id>.title
config.step.<step_id>.description           ← optional
config.step.<step_id>.data.<field_key>
config.step.<step_id>.data_description.<field_key>  ← optional, longer help text
config.error.<error_key>
config.abort.<abort_reason>
options.step.<step_id>.title
options.step.<step_id>.description
options.step.<step_id>.data.<field_key>
options.error.<error_key>
```

The handler code references step_id ONLY (`step_id="reauth_confirm"`) — HA core resolves the strings.json keys automatically.

### `description_placeholders` for multi-child context

**Source:** RESEARCH Pitfall #7.

**Apply to:** EVERY `async_show_form` call in reauth, reconfigure, AND OptionsFlow steps. The placeholder `{child_name}` interpolates into the strings.json `description` field.

```python
return self.async_show_form(
    step_id="reauth_confirm",
    data_schema=_REAUTH_SCHEMA,
    errors=errors,
    description_placeholders={"child_name": entry.data["child_name"]},
)
```

Without this, a user with two entries doing reauth simultaneously sees "Re-authenticate Pronote" with no child context.

### Tests — MockConfigEntry + PHACC flow helpers

**Source:** `tests/test_config_flow.py:test_already_configured_aborts` lines 134-152 + `tests/conftest.py:mock_config_entry` lines 91-112.

**Apply to:** Every Phase 6 test that needs a pre-existing entry. Use the existing `mock_config_entry` fixture where the D-08 shape suffices; create explicit `MockConfigEntry(...)` instances for multi-entry scenarios (multi-child isolation, error-mapping with custom data).

**PHACC helpers (RESEARCH Pattern 5, A4 assumption):**

```python
# Equivalent to HA raising ConfigEntryAuthFailed:
result = await entry.start_reauth_flow(hass)

# Equivalent to user clicking "Reconfigure" in entry kebab menu:
result = await entry.start_reconfigure_flow(hass)
```

**Patch target convention (existing — line 117-123):**

```python
# Patch at the import site used by config_flow.py, not the original module:
patch("custom_components.ha_pronote.config_flow.build_or_resume_client", ...)
patch("custom_components.ha_pronote.build_or_resume_client", ...)  # __init__.py import site
patch("custom_components.ha_pronote.coordinator.fetch_all", ...)
```

---

## No Analog Found

None. Every Phase 6 surface has a Phase 3/5 analog already in the tree:

| Hypothetical "no analog" risk | Resolved by |
|-------------------------------|-------------|
| `OptionsFlowWithReload` subclass | Not strictly an analog, but `HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN)` (Phase 3) shows the same subclass-with-state shape, plus RESEARCH Pattern 3 gives the verbatim template. |
| Multi-step OptionsFlow | `async_step_user` → `async_step_pick_child` (Phase 3) is the same pattern (one method `await`s another and stashes inter-step state on `self`). |
| Reauth helper `_get_reauth_entry()` | First use in this codebase, but it's a one-line HA-native helper (HA 2024.10+). RESEARCH Pattern 1 gives the call shape. |
| `async_update_reload_and_abort(data_updates=...)` | First use in this codebase, but RESEARCH Pattern 1/2/6 gives the verbatim shape. The merge-vs-replace contract is documented in RESEARCH Pitfall #6. |
| `add_suggested_values_to_schema` | First use in this codebase. RESEARCH Pattern 2/3 gives the call shape. |

---

## Metadata

**Analog search scope:**
- `custom_components/ha_pronote/` (entire integration module) — config_flow.py, __init__.py, coordinator.py, politesse.py, entity.py, const.py, api/client.py, strings.json, translations/{en,fr}.json
- `tests/` (entire test suite) — test_config_flow.py, test_coordinator.py, test_init.py, conftest.py
- `.planning/phases/03-coordinator-first-sensor/03-CONTEXT.md` — Phase 3 decisions (D-05, D-06, D-07, D-08, D-15, C-02)
- `.planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/05-CONTEXT.md` — Phase 5 decisions (D-17, D-23, D-24)
- RESEARCH.md Code Examples 1-7 + Pattern 1-5 — used for HA-framework patterns that have no in-tree analog yet

**Files scanned:** 11 production files + 4 test files + 2 i18n files = 17 files total.

**Pattern extraction date:** 2026-05-25

**Key invariants enforced:**
1. `feedback_no_silent_exceptions.md` — every except arm is a known typed exception with explicit form-error mapping or a warned-fallback (Phase 5 `_resolve_options` pattern). NEVER bare except, NEVER `Exception:` catch-all.
2. `pronotepy` always wrapped in `hass.async_add_executor_job(partial(...))` (Phase 3 C-02 single seam).
3. `unique_id` format `f"{url_host}:{username}:{child_identifier}"` is frozen (Phase 3 D-05) — reauth/reconfigure NEVER recompute it from scratch (only verify via `_abort_if_unique_id_mismatch` on reconfigure).
4. Entry data uses `data_updates=` (merge) NEVER `data=` (replace) on reauth/reconfigure (RESEARCH Pitfall #6).
5. RESEARCH-flagged THREE corrections to CONTEXT.md (D-12, D-16, OptionsFlow.__init__) are encoded in every relevant pattern above.
