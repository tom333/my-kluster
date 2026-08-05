# Phase 6: Auth Lifecycle & Options — Research

**Researched:** 2026-05-25
**Domain:** Home Assistant 2026.4 ConfigFlow / OptionsFlow lifecycle (reauth + reconfigure + multi-step options)
**Confidence:** HIGH on framework surface (Context7 unavailable; verified via official HA docs + May 2026 deprecation blog). MEDIUM on test idioms (multiple credible community sources agree).

## Summary

Phase 6 is **pure UI/lifecycle wiring on top of already-locked architecture** — Phase 3 froze `entry.data` shape, Phase 5 froze `entry.options` shape, and Phase 6 just adds the three flows (reauth, reconfigure, OptionsFlow) plus the reload-on-change pipe. The hard work was choosing patterns; the code is short.

**One critical finding that contradicts CONTEXT.md D-12:** Home Assistant deprecated the `entry.add_update_listener` + `async_reload` combo on **2026-05-07** (twelve days before this research was written). Using it WILL produce a deprecation warning today, becomes an error in 2026.6, and is removed entirely in 2026.12. The replacement is `homeassistant.config_entries.OptionsFlowWithReload` (introduced HA 2024.11) — same outcome, zero hand-rolled wiring, single import change. **Update D-12 before planning starts.** [CITED: developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/]

**Other key validations:**

- The reauth pattern in 2026.4 uses `self._get_reauth_entry()` (HA 2024.10+) instead of `self.hass.config_entries.async_get_entry(self.context["entry_id"])`. Same for reconfigure with `self._get_reconfigure_entry()`. [CITED: developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/]
- The canonical commit idiom is `return self.async_update_reload_and_abort(entry, data_updates={...})` — the `data_updates=` kwarg (merge into existing data) is preferred over `data=` (full replace) per HA docs. [CITED: same blog]
- Multi-step OptionsFlow IS supported by redirecting from `async_step_init` → `async_step_polling` → `async_step_display`. The "options flow only has init step" line in some docs is wrong/outdated; multi-step is achieved by `async_step_init` returning `await self.async_step_polling(user_input)` or `self.async_show_form(step_id="polling", ...)`. CONTEXT.md D-10 is correct.
- `pronotepy.Client.token_login(...)` is sync, lives in `clients.py`, accepts only the keys that `export_credentials()` produced — passing `session=None` to `build_or_resume_client` falls through to fresh login (verified live in the existing Phase 3 code: `api/client.py:116 if session is not None:`).

**Primary recommendation:** Replace D-12's `entry.add_update_listener` pattern with `OptionsFlowWithReload`. Keep everything else in CONTEXT.md. The 11-key surface, the multi-step polling+display split, the 17-decision lock — all sound.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Reauth flow (AUTH-05)**
- **D-01:** `async_step_reauth_confirm` exposes **two fields** (`password` + `username`); URL and account_type preserved from `entry.data`.
- **D-02:** After reauth success, **clear `entry.data["session"]`** so next setup hits fresh-login branch.
- **D-03:** **Reuse existing `device_name`** = `f"home-assistant-{entry.entry_id[:8]}"` (entry_id stable across reauth).
- **D-04:** **Native trigger** via `ConfigEntryAuthFailed` — no Repair Issue plumbing in Phase 6 (deferred Phase 7 DIAG-03).

**Reconfigure flow (AUTH-06)**
- **D-05:** `async_step_reconfigure` exposes **only URL + account_type**. Username/password stay in reauth lane.
- **D-06:** **Abort if `child_identifier` changes** under the new URL — user must delete+recreate (preserves Recorder history of OTHER entries).
- **D-07:** **Re-validate via `build_or_resume_client(..., session=None)` BEFORE `async_update_entry`** — errors stay in form, never persisted.
- **D-08:** **Clear `entry.data["session"]` only if URL OR account_type changed** (string-equal after strip).

**OptionsFlow (COORD-03 + OPT-01..04)**
- **D-09:** **11 keys total**: 8 Phase 5 inherited (`refresh_interval`, `afternoon_interval`, `afternoon_window_start`, `afternoon_window_end`, `quiet_hours_start`, `quiet_hours_end`, `suspended_cadence`, `quiet_cadence`) + 2 new (`nickname`, `school_tz`) + 1 toggle (`adaptive_polling_enabled`).
- **D-10:** **Multi-step layout**: `async_step_init` → `async_step_polling` (9 keys) → `async_step_display` (2 keys) → commit.
- **D-11:** **Defaults via `_options_schema_defaults(entry)`** helper reading the same `DEFAULT_*` constants as `coordinator._resolve_options`.
- **D-12:** **Reload-on-options-change naïve listener** — `entry.async_on_unload(entry.add_update_listener(_async_reload_entry))`. ⚠️ **OBSOLETE in HA 2026.4** — see [Critical Gotcha #1](#critical-gotcha-1-d-12-is-deprecated-in-may-2026) below.

**Nickname (OPT-03)**
- **D-13:** Nickname affects **`DeviceInfo.name` only** — `unique_id` and `entity_id` remain frozen (ENT-02).
- **D-14:** **Fallback `entry.options.get("nickname") or entry.data["child_name"]`**.
- **D-15:** **Update `entry.title`** in reload listener (or coordinator setup) when nickname changes.
- **D-16:** **Voluptuous validation**: `vol.All(cv.string, vol.Length(max=40), vol.Strip)` — empty-post-strip → treated as None.

**Multi-child interaction (AUTH-03)**
- **D-17:** **No new code** — Phase 3 D-05 pattern (`url_host:username:child_identifier` unique_id) already permits multi-child. Phase 6 ships a test that two entries' options remain independent.

### Claude's Discretion

- **Tests TZ matrix on flows** — Phase 6 flows are tz-independent; no new DIST-06 markers needed.
- **Ordering of fields inside step 1 "Polling"** — cosmetic; recommended order: `refresh_interval` first, then `adaptive_polling_enabled`, then `afternoon_window_*`, then `suspended_cadence`, then `quiet_*`.
- **Translation strings** — Phase 6 adds the new keys (en + fr) at-the-fly; Phase 7 I18N-01/02 will do the exhaustive sweep.

### Deferred Ideas (OUT OF SCOPE)

- Repair Issue with "Reauth" button + troubleshooting link → Phase 7 DIAG-03
- Diagnostics dump with redact for new option keys → Phase 7 DIAG-01
- Exhaustive translation pass → Phase 7 I18N-01/02
- TZ matrix tests on config flows → not needed (flows are tz-independent)
- Hot-swap `school_tz` without reload → naïve reload (1s) is fine; diff-aware optimisation deferred
- `async_migrate_entry` v1→v2 — not needed; new keys use `.get(KEY, DEFAULT)` forward-compat
- Multi-child "Add another child" shortcut from existing entry → backlog v2

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-03 | Multi-child — one ConfigEntry per child | Phase 3 D-05 already ships this; Phase 6 needs a single coexistence test. See [Pattern 4](#pattern-4-multi-child-independence-test) |
| AUTH-05 | Reauth flow on password change | [Pattern 1](#pattern-1-reauth-flow-ha-202410-helpers) — `_get_reauth_entry` + `async_update_reload_and_abort(data_updates=...)` |
| AUTH-06 | Reconfigure flow for URL/account_type | [Pattern 2](#pattern-2-reconfigure-flow) — `_get_reconfigure_entry` + `_abort_if_unique_id_mismatch` for D-06 |
| COORD-03 | Polling interval editable via OptionsFlow | OptionsFlow step "Polling" reads `entry.options` already wired by Phase 5 D-17. See [Pattern 3](#pattern-3-optionsflow-with-multi-step-via-redirect) |
| OPT-01 | Edit `refresh_interval` from OptionsFlow | Same as COORD-03 |
| OPT-02 | Toggle adaptive polling on/off | Boolean field `adaptive_polling_enabled` in step "Polling"; `PolitesseOptions.adaptive_enabled` field addition |
| OPT-03 | Rename child via nickname | Step "Display" with `vol.All(cv.string, vol.Length(max=40), vol.Strip)`; consumed by `entity.py:DeviceInfo.name` |
| OPT-04 | Coordinator auto-reloads on options change | **CRITICAL: use `OptionsFlowWithReload`, NOT `add_update_listener`** — see [Critical Gotcha #1](#critical-gotcha-1-d-12-is-deprecated-in-may-2026) |

## Project Constraints (from CLAUDE.md)

These directives are binding for Phase 6 planning. Plans MUST honor them or explicitly justify deviation.

- **Python `>=3.14.2`** — match HA 2026.4 floor. Already enforced in `pyproject.toml`.
- **HA `>=2026.4.x`** — `OptionsFlowWithReload` exists since 2024.11, so the floor is fine; the May 2026 deprecation warning is a separate behavior.
- **`pronotepy==2.14.6` exact pin** — Phase 6 calls `Client(...)` and `Client.token_login(...)` indirectly via `build_or_resume_client`. No new pronotepy surfaces touched.
- **`ruff` + `pyright` + `uv`** — no new tooling. Existing `pyproject.toml` configs apply.
- **`asyncio.timeout` only** (no `async_timeout`). Phase 6 doesn't time-out anything; N/A.
- **`zoneinfo.ZoneInfo` only** (no `pytz`). Phase 6's `school_tz` option is an IANA string fed to `ZoneInfo(...)` in coordinator setup.
- **`pronotepy` calls always wrapped in `hass.async_add_executor_job`**. Phase 6's reauth (D-04) and reconfigure (D-07) both call `build_or_resume_client` via executor.
- **No `pronotepy.ent.*`** — direct auth only. Phase 6 doesn't touch.
- **No hardcoded URL** — Phase 6's reconfigure form reads the URL from user input.
- **No monkey-patching** — Phase 6 stays inside `config_flow.py`.
- **No silent exceptions** (user memory `feedback_no_silent_exceptions.md`) — Phase 6 surface area: `vol.Invalid`, `AuthError`, `CommunicationError`, `RateLimitedError`. They propagate raw via form errors dict (`errors={"base": "invalid_auth"}` etc.) per the Phase 3 D-04 mapping. **No `try/except: pass`. No mapping to anonymous "Unknown error".**

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reauth UI form rendering | HA frontend (browser, served by HA server) | API (HA core) | HA renders the form from voluptuous schema + strings.json; user input round-trips to `config_flow.py` on the server. |
| Reauth credential validation | Coordinator/executor (server) | pronotepy (sync, executor-isolated) | `build_or_resume_client(...)` is called via `hass.async_add_executor_job` — pronotepy talks to the school server. |
| Reauth commit (entry.data mutation) | HA config_entries storage (server) | — | `async_update_reload_and_abort(data_updates=...)` writes via HA's storage layer. |
| Reconfigure UI + validation | Same as reauth | Same | Identical seam (`build_or_resume_client`) for D-07 re-validation. |
| OptionsFlow UI | HA frontend | API | Same as reauth, but no executor call (pure form submission). |
| OptionsFlow commit + reload | HA config_entries storage + setup machinery | Coordinator (re-init) | `OptionsFlowWithReload` triggers `async_unload_entry` → `async_setup_entry`. |
| Nickname display propagation | HA entity_registry / device_registry | Sensor entity (re-init on reload) | `PronoteEntity.device_info` re-reads `entry.options.get("nickname")` on each reload. |
| Multi-child entry isolation | HA config_entries (one entry per `unique_id`) | Coordinator instance (per-entry) | Phase 3 D-05 unique_id format already isolates; Phase 6 just verifies via test. |

**Why this matters:** Every Phase 6 capability lives on the HA server side. No browser-side state, no client-side validation beyond what voluptuous schemas emit. The split that matters is `config_flow.py` (HA event loop, async) ↔ `pronotepy` (sync, executor). Plans should preserve this seam — never call `build_or_resume_client` directly from a flow step body.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `homeassistant.config_entries.ConfigFlow` | bundled HA 2026.4.x | base class for reauth + reconfigure | already used in Phase 3; no change |
| `homeassistant.config_entries.OptionsFlowWithReload` | bundled HA 2024.11+ | OptionsFlow base that auto-reloads entry on commit | **replaces the deprecated `add_update_listener` pattern (D-12)** — see [Critical Gotcha #1](#critical-gotcha-1-d-12-is-deprecated-in-may-2026) |
| `homeassistant.config_entries.ConfigFlowResult` | bundled HA | return type annotation | already used in Phase 3 |
| `homeassistant.config_entries.SOURCE_REAUTH` | bundled HA | source constant for `self.source` check (when steps are shared) | only needed if reauth_confirm shares schema with user step — Phase 6 keeps them separate so this is optional |
| `homeassistant.config_entries.SOURCE_RECONFIGURE` | bundled HA | same idea for reconfigure | same |
| `voluptuous` | transitive via HA | schema validation (Phase 3 already uses) | unchanged |
| `homeassistant.helpers.selector.{TextSelector, BooleanSelector, NumberSelector, SelectSelector}` | bundled HA | UI selectors for typed fields (rendered as proper widgets) | richer UX than raw `cv.boolean` / `int`. Used in Phase 3 for password masking |

[VERIFIED: HA source + dev docs] `OptionsFlowWithReload` is in `homeassistant.config_entries`, exported alongside `OptionsFlow`. Import: `from homeassistant.config_entries import OptionsFlowWithReload`.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `homeassistant.helpers.config_validation as cv` | bundled | `cv.string`, `cv.boolean`, `cv.time` validators | reuse for every field that maps to a HA-native type |
| `vol.All` / `vol.Length` / `vol.Strip` (or stdlib `.strip()`) | voluptuous bundled | nickname strip + length | **see Critical Gotcha #2 below — `vol.Strip` doesn't exist in voluptuous; use a lambda or `lambda v: v.strip()`** |
| `pronotepy 2.14.6` | exact-pinned | only via `build_or_resume_client` seam — no new pronotepy surface in Phase 6 | unchanged from Phase 3 |
| `zoneinfo.ZoneInfo` | stdlib | validate `school_tz` IANA string at coordinator setup time | called by `__init__.py:async_setup_entry`; Phase 6 lets user override per-entry |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `OptionsFlowWithReload` | `OptionsFlow` + manual `add_update_listener` (D-12) | **DON'T — deprecated 2026-05-07, error in 2026.6, removed in 2026.12. No reason to do this work, then remove it next minor release.** |
| `_get_reauth_entry()` | `self.hass.config_entries.async_get_entry(self.context["entry_id"])` | The helper exists since 2024.10 specifically to avoid the verbose lookup. Use it. |
| `_get_reconfigure_entry()` | same long form | same |
| `async_update_reload_and_abort(data_updates=...)` | `hass.config_entries.async_update_entry(...)` + `async_reload()` + `async_abort()` | The helper bundles three operations atomically. The May 2026 deprecation flips `_reload_and_abort` ↔ `_and_abort` only for the listener interaction; calling `async_update_reload_and_abort` from a flow's reauth/reconfigure step is still the official idiom. |
| `vol.All(cv.string, vol.Length(max=40), vol.Strip)` (D-16 literal) | `vol.All(cv.string, vol.Length(max=40), lambda v: v.strip())` | `vol.Strip` is **not** part of voluptuous proper — D-16 must be revised. See Critical Gotcha #2. |
| `cv.time` for IANA tz field | `cv.string` + custom `ZoneInfo` validator | `school_tz` is an IANA string, not a `time(HH,MM)`. `cv.string` + `lambda v: ZoneInfo(v)` (caught `ZoneInfoNotFoundError`) is the idiom. |
| `BooleanSelector()` | `vol.Coerce(bool)` / `cv.boolean` | `BooleanSelector` renders as a proper HA toggle widget; `cv.boolean` renders as a checkbox. Use `BooleanSelector` for adaptive_polling_enabled per ENT-03 modern naming spirit. |
| `NumberSelector(NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX))` | raw `vol.All(int, vol.Range(min=1, max=1440))` | NumberSelector gives a typed input box with min/max enforcement client-side; raw `int` works server-side only. Use `NumberSelector` for the 6 minute-valued fields (cleaner UX, fewer round-trips on invalid input). |

**Installation:** No new packages. `OptionsFlowWithReload` ships with HA 2024.11+; HA 2026.4 floor already satisfies. No `manifest.json` change.

**Version verification:**

```bash
# Confirm HA local version supplies OptionsFlowWithReload
python -c "from homeassistant.config_entries import OptionsFlowWithReload; print(OptionsFlowWithReload)"
# Expected: <class 'homeassistant.config_entries.OptionsFlowWithReload'>
```

[VERIFIED: `pip show pronotepy` returned `Version: 2.14.6` — matches CLAUDE.md exact pin. No package version drift since Phase 5.]

## Architecture Patterns

### System Architecture Diagram

Phase 6 inserts three new flows into the existing `config_flow.py`. All three reuse the Phase 3 `build_or_resume_client` seam and the Phase 5 `_resolve_options` read path. The only new permanent state shape is `entry.options` (10 new keys + 1 toggle on top of the 8 Phase 5 keys, so 11 keys total — see D-09).

```
                                ┌────────────────────────────────────────┐
                                │       Pronote password change          │
                                │       (external trigger)               │
                                └────────────────┬───────────────────────┘
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │ Phase 3/5 coordinator._async_update_data raises  │
                       │ ConfigEntryAuthFailed (existing — no change)     │
                       └────────────────────────┬─────────────────────────┘
                                                │
                                                ▼
                       ┌──────────────────────────────────────────────────┐
                       │ HA core: starts SOURCE_REAUTH flow on this entry │
                       │ Calls async_step_reauth(entry_data)               │
                       └────────────────────────┬─────────────────────────┘
                                                │
                                                ▼
                       ┌──────────────────────────────────────────────────┐
                       │ async_step_reauth → async_step_reauth_confirm    │  ← AUTH-05
                       │ Show form: {username, password}                  │
                       │ URL + account_type read from _get_reauth_entry()  │
                       └────────────────────────┬─────────────────────────┘
                                                │ form submit
                                                ▼
                       ┌──────────────────────────────────────────────────┐
                       │ hass.async_add_executor_job(build_or_resume_     │
                       │   client, url, account_type, NEW_username,       │
                       │   NEW_password, session=None, device_name)        │
                       └────────────────────────┬─────────────────────────┘
                                                │
                  ┌─────────────────────────────┴────────────────────────┐
                  │                                                       │
                  ▼ AuthError / CommunicationError                       ▼ success
       errors={"base": "invalid_auth"}                  return self.async_update_reload_and_abort(
       (re-show form)                                       reauth_entry,
                                                            data_updates={
                                                              "username": NEW_username,
                                                              "password": NEW_password,
                                                              "session":  None,   # D-02
                                                            },
                                                       )

  (separate independent track — RECONFIGURE)                    (separate — OPTIONS)
            │                                                          │
            ▼                                                          ▼
  ┌─────────────────────────────────┐         ┌─────────────────────────────────────┐
  │ User clicks "Reconfigure" in    │         │ User clicks "Configure" in UI       │
  │ entry kebab menu                │         │ HA invokes OptionsFlowWithReload    │
  └────────────┬────────────────────┘         └─────────────┬───────────────────────┘
               │                                            │
               ▼                                            ▼
  async_step_reconfigure                       async_step_init → async_step_polling
   show form: {url, account_type}              (9 keys) → async_step_display
                                               (2 keys) → async_create_entry
               │                                            │
               ▼                                            ▼
  re-validate via build_or_resume_client       OptionsFlowWithReload triggers
  AuthError → errors={"base": "invalid_auth"}  unload_entry + setup_entry
  child_identifier mismatch → async_abort(     coordinator re-instantiated with
       reason="child_identifier_changed")       fresh entry.options
               │ success
               ▼
  self._abort_if_unique_id_mismatch()  ← optional safety: assert unique_id stable
  return self.async_update_reload_and_abort(
      reconf_entry,
      data_updates={"url": new_url, "account_type": new_at,
                    "session": None if url_or_at_changed else old_session},
      title=self._derive_title(new_at, child_name),  # optional D-15-ish
  )
```

**Component responsibilities:**

| Component | File | Responsibility |
|-----------|------|----------------|
| `async_step_reauth` | `config_flow.py` | trampoline — receives `entry_data` from HA, redirects to `async_step_reauth_confirm` |
| `async_step_reauth_confirm` | `config_flow.py` | render form, call `build_or_resume_client` via executor, commit via `async_update_reload_and_abort(data_updates=...)` |
| `async_step_reconfigure` | `config_flow.py` | render form (URL + account_type), validate via `build_or_resume_client`, check `child_identifier` invariant (D-06), commit |
| `async_get_options_flow` | `config_flow.py` (static method on `HaPronoteConfigFlow`) | returns instance of `HaPronoteOptionsFlow(OptionsFlowWithReload)` |
| `HaPronoteOptionsFlow.async_step_init` | `config_flow.py` | trampolines to `async_step_polling` |
| `HaPronoteOptionsFlow.async_step_polling` | `config_flow.py` | 9-field form; submit transitions to `async_step_display(user_input_step1)` |
| `HaPronoteOptionsFlow.async_step_display` | `config_flow.py` | 2-field form (nickname + school_tz); `async_create_entry(data={**step1, **step2})` commits |
| `_options_schema_defaults(entry)` | `config_flow.py` (module-level helper) | per D-11 — reads `const.py` defaults + `entry.options` overrides, returns dict for `add_suggested_values_to_schema` |
| `_derive_title(account_type, child_name, nickname)` | `config_flow.py` (helper) | builds `f"{nickname or child_name} ({account_type})"` for `entry.title` |
| `coordinator._resolve_options` | `coordinator.py` (Phase 5) | already reads 8 keys; Phase 6 EXTENDS to read `adaptive_polling_enabled`, `nickname`, `school_tz` |
| `PolitesseOptions` | `politesse.py` (Phase 5) | already a frozen dataclass; Phase 6 ADDS `adaptive_enabled: bool = True` field |
| `compute_interval` | `politesse.py` (Phase 5) | already branches; Phase 6 ADDS short-circuit `if not options.adaptive_enabled: return options.refresh_interval + jitter` before the afternoon-window branch |
| `PronoteEntity.device_info` | `entity.py` (Phase 3/4) | already reads `entry.data["child_name"]`; Phase 6 CHANGES to `entry.options.get("nickname") or entry.data["child_name"]` (D-14) |
| `__init__.py:async_setup_entry` | `__init__.py` | Phase 6 ADDS `school_tz = ZoneInfo(entry.options.get("school_tz", DEFAULT_SCHOOL_TZ))` instead of the current hardcoded `ZoneInfo(DEFAULT_SCHOOL_TZ)` (D-09 / OPT-04) |
| `tests/test_config_flow.py` | tests | EXTEND with 3 new test groups: reauth (~6 tests), reconfigure (~5 tests), options flow (~6 tests). Plus 1 multi-child isolation test. |

### Recommended Project Structure

No new files. All Phase 6 code lives in existing modules:

```
custom_components/ha_pronote/
├── config_flow.py        # EXTEND — add reauth + reconfigure + OptionsFlow classes
├── const.py              # APPEND — DEFAULT_ADAPTIVE_POLLING_ENABLED, NICKNAME_MAX_LEN
├── __init__.py           # EXTEND — school_tz read from entry.options; OPTIONAL: drop the
│                         #          add_update_listener wiring (since OptionsFlowWithReload)
├── coordinator.py        # EXTEND — _resolve_options reads 3 new keys
├── politesse.py          # EXTEND — PolitesseOptions.adaptive_enabled; compute_interval short-circuit
├── entity.py             # EXTEND — DeviceInfo.name nickname fallback (D-14)
├── strings.json          # APPEND — config.step.reauth_confirm.*, config.step.reconfigure.*,
│                         #          options.step.polling.*, options.step.display.*,
│                         #          config.abort.child_identifier_changed,
│                         #          config.abort.reauth_successful, config.abort.reconfigure_successful
└── translations/{en,fr}.json   # mirror strings.json — Phase 6 adds keys at-the-fly,
                                # Phase 7 I18N-01/02 does the exhaustive sweep

tests/
└── test_config_flow.py   # EXTEND — ~17 new tests grouped by flow
```

### Pattern 1: Reauth flow (HA 2024.10+ helpers)

**What:** The 2024.10 blog introduced `_get_reauth_entry()` and `_abort_if_unique_id_mismatch()` to eliminate the verbose `self.hass.config_entries.async_get_entry(self.context["entry_id"])` lookup. Combined with `async_update_reload_and_abort(data_updates=...)`, the whole reauth path is ~30 LOC.

**When to use:** Any flow triggered by `ConfigEntryAuthFailed` raised from `async_setup_entry` or `coordinator._async_update_data`. The trigger is HA-native — Phase 3 `__init__.py:async_setup_entry` already raises `ConfigEntryAuthFailed` from line 82-83, and Phase 3 `coordinator._recover_from_auth_error` already raises it from line 294. Phase 6 doesn't add any trigger code, only the receiver flow.

**Example:**

```python
# Source: developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/
# Source: developers.home-assistant.io/docs/config_entries_config_flow_handler/
# Adapted for HA-Pronote D-01/D-02/D-03.

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """HA invokes this when ConfigEntryAuthFailed is raised. Trampoline only."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """D-01 form: username + password. URL + account_type read from entry."""
        entry = self._get_reauth_entry()  # HA 2024.10+
        errors: dict[str, str] = {}

        if user_input is not None:
            # AUTH-07 / D-03: reuse existing device_name (entry_id stable).
            device_name = f"home-assistant-{entry.entry_id[:8]}"
            try:
                client = await self.hass.async_add_executor_job(
                    partial(
                        build_or_resume_client,
                        entry.data["url"],
                        entry.data["account_type"],
                        user_input["username"],     # NEW
                        user_input["password"],     # NEW
                        None,                       # session=None → fresh login
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
                # D-02: clear session. Next async_setup_entry hits fresh login branch.
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
            description_placeholders={
                "child_name": entry.data["child_name"],
            },
        )
```

**Verbatim guarantees from official sources:**
- `_get_reauth_entry()` available since HA 2024.10 [CITED: developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/]
- `async_update_reload_and_abort(entry, data_updates=...)` is the official commit idiom [CITED: developers.home-assistant.io/docs/config_entries_config_flow_handler/]
- `data_updates=` (merge) preferred over `data=` (full replace) — "reduces the risk of data loss if the schema is updated" [CITED: same docs]
- The reauth flow MUST end with `async_update_reload_and_abort` — reauth flows MUST update + reload + abort, NOT create new entries [CITED: same]
- `description_placeholders` interpolates `{child_name}` into the strings.json `config.step.reauth_confirm.description` value — gives the user context which child they're re-authing for (vital when two entries) [CITED: data_entry_flow_index.md]

### Pattern 2: Reconfigure flow

**What:** Symmetric to reauth but for "things the user CAN change without losing entity history" — URL and account_type. The trigger is the user clicking "Reconfigure" in the entry kebab menu (HA exposes the button automatically when `async_step_reconfigure` is defined).

**When to use:** When the integration needs to support edits to `entry.data` keys that are part of the unique_id derivation BUT must preserve entity_id history. The Phase 6 D-05 case fits exactly: URL host changes the unique_id PREFIX but does NOT change the `child_identifier` SUFFIX (Phase 3 D-05); same for `account_type` which doesn't appear in unique_id at all.

**Example:**

```python
# Source: developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step/
# Source: developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/
# Adapted for HA-Pronote D-05/D-06/D-07/D-08.

_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
    }
)


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):

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

            # D-07: re-validate against new URL/account_type BEFORE any persistence.
            try:
                client = await self.hass.async_add_executor_job(
                    partial(
                        build_or_resume_client,
                        new_url,
                        new_account_type,
                        entry.data["username"],     # preserved
                        entry.data["password"],     # preserved
                        None,                       # fresh login — session is for old URL
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
                # If parent account, must re-select the same child_index.
                child_index = entry.data.get("child_index")
                if child_index is not None and hasattr(client, "set_child"):
                    try:
                        await self.hass.async_add_executor_job(
                            set_active_child, client, child_index
                        )
                    except PronoteIntegrationError:
                        errors["base"] = "cannot_connect"
                        return self.async_show_form(
                            step_id="reconfigure",
                            data_schema=_RECONFIGURE_SCHEMA,
                            errors=errors,
                        )
                    child_name = client.children[child_index].name
                else:
                    child_name = client.info.name

                new_child_identifier = slugify(child_name, separator="_")
                if new_child_identifier != entry.data["child_identifier"]:
                    return self.async_abort(reason="child_identifier_changed")

                # D-08: clear session only if URL or account_type changed.
                url_changed = new_url != entry.data["url"].strip()
                at_changed = new_account_type != entry.data["account_type"]

                data_updates: dict[str, Any] = {
                    "url": new_url,
                    "account_type": new_account_type,
                }
                if url_changed or at_changed:
                    data_updates["session"] = None

                # Optional safety belt — assert unique_id stayed stable.
                url_host = (urlparse(new_url).hostname or "").lower()
                await self.async_set_unique_id(
                    f"{url_host}:{entry.data['username']}:{new_child_identifier}"
                )
                self._abort_if_unique_id_mismatch(reason="child_identifier_changed")

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

        # First entry into the step or post-error re-render.
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

**Verbatim guarantees:**
- `async_step_reconfigure` exists since HA 2024.3 [CITED: developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step/]
- `_get_reconfigure_entry()` and `_abort_if_unique_id_mismatch()` exist since HA 2024.10 [CITED: developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/]
- HA exposes the "Reconfigure" button automatically once the step is defined [CITED: integration-quality-scale/rules/reconfiguration-flow/]
- `add_suggested_values_to_schema(SCHEMA, existing_values)` pre-fills the form fields so the user sees the current URL/account_type as starting values [CITED: developers.home-assistant.io/docs/config_entries_options_flow_handler/]

### Pattern 3: OptionsFlow with multi-step via redirect

**What:** OptionsFlow technically requires `async_step_init` as the entry point. Multi-step is achieved by `async_step_init` either directly delegating (`return await self.async_step_polling()`) or by showing the first form with `step_id="polling"`. The "options flow only has init step" line from some 2022-era community docs is wrong/outdated.

**When to use:** Whenever the option surface is wide enough that a single 11-field form feels overwhelming. CONTEXT.md D-10 prescribes a 9-field "Polling" step + a 2-field "Display" step — exactly the right split.

**Example:**

```python
# Source: developers.home-assistant.io/docs/config_entries_options_flow_handler/
# Source: home-assistant.io 2024.11 changelog (OptionsFlowWithReload introduction)
# Adapted for HA-Pronote D-09/D-10/D-11.

from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)


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

_DISPLAY_SCHEMA = vol.Schema(
    {
        vol.Optional("nickname", default=""): vol.All(
            cv.string,
            vol.Length(max=NICKNAME_MAX_LEN),
            # NB: vol.Strip does NOT exist — use a lambda. See Critical Gotcha #2.
            lambda v: v.strip(),
        ),
        vol.Required("school_tz", default=DEFAULT_SCHOOL_TZ): str,
    }
)


class HaPronoteOptionsFlow(OptionsFlowWithReload):

    def __init__(self) -> None:
        # NB: do NOT assign self.config_entry = config_entry — deprecated since 2024.12,
        # raises in 2025.12+ (read-only). HA injects it automatically. See Critical Gotcha #3.
        self._step1_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trampoline to step "polling"."""
        return await self.async_step_polling()

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """9-field form. On submit, transition to async_step_display."""
        if user_input is not None:
            # Validate time crossings handled by politesse (already tested).
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
        """2-field form. On submit, async_create_entry merges both step dicts."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate school_tz IANA string (D-09 / OPT-04).
            try:
                ZoneInfo(user_input["school_tz"])
            except (ZoneInfoNotFoundError, ValueError):
                errors["school_tz"] = "invalid_school_tz"
            else:
                # Persist. OptionsFlowWithReload triggers async_unload + async_setup.
                return self.async_create_entry(
                    title="",  # OptionsFlow title is ignored by HA
                    data={**self._step1_data, **user_input},
                )

        suggested = _options_schema_defaults(self.config_entry)
        return self.async_show_form(
            step_id="display",
            data_schema=self.add_suggested_values_to_schema(_DISPLAY_SCHEMA, suggested),
            errors=errors,
        )


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HaPronoteOptionsFlow()


def _options_schema_defaults(entry: ConfigEntry) -> dict[str, Any]:
    """D-11 — single source of truth between OptionsFlow + coordinator._resolve_options."""
    opts = entry.options
    return {
        "refresh_interval": opts.get(
            "refresh_interval",
            int(DEFAULT_REFRESH_INTERVAL.total_seconds() // 60),
        ),
        "adaptive_polling_enabled": opts.get(
            "adaptive_polling_enabled", True
        ),
        "afternoon_interval": opts.get(
            "afternoon_interval",
            int(DEFAULT_AFTERNOON_INTERVAL.total_seconds() // 60),
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
            "suspended_cadence",
            int(DEFAULT_SUSPENDED_CADENCE.total_seconds() // 60),
        ),
        "quiet_cadence": opts.get(
            "quiet_cadence",
            int(DEFAULT_QUIET_CADENCE.total_seconds() // 60),
        ),
        "nickname": opts.get("nickname", ""),
        "school_tz": opts.get("school_tz", DEFAULT_SCHOOL_TZ),
    }
```

**Verbatim guarantees:**
- `OptionsFlowWithReload` introduced HA 2024.11 [CITED: developers.home-assistant.io/docs/config_entries_options_flow_handler/]
- `OptionsFlow.__init__(config_entry)` deprecated since HA 2024.12; setter removed in HA 2025.12 — DO NOT assign `self.config_entry = config_entry` [CITED: HA 2024.12 changelog + multiple github issues incl. hacs/integration#4314, rospogrigio/localtuya#1931]
- `add_suggested_values_to_schema(schema, suggested_dict)` is the idiomatic way to pre-fill form fields with current option values [CITED: developers.home-assistant.io/docs/config_entries_options_flow_handler/]
- `async_get_options_flow` is `@staticmethod` + `@callback` decorated [CITED: same]
- Multi-step achievable via redirect from `async_step_init` to step-named methods that show different forms via `step_id="polling"` / `step_id="display"` [CITED: developers.home-assistant.io/docs/data_entry_flow_index/]

### Pattern 4: Multi-child independence test

**What:** AUTH-03 says "user can configure multiple children — one ConfigEntry per child." Phase 3 D-05 already ships this via the unique_id format `f"{url_host}:{username}:{child_identifier}"` (different child → different unique_id → second `async_set_unique_id` succeeds). Phase 6 needs **one** test confirming the OptionsFlow + reload listener don't accidentally couple two entries.

**When to use:** A single PHACC test that creates two `MockConfigEntry`s for the same `url_host:username` but different `child_identifier`, opens options on entry A, asserts entry B's options didn't change.

**Example:**

```python
# Adapted from existing tests/test_config_flow.py:test_already_configured_aborts.

async def test_two_children_options_are_independent(
    hass: HomeAssistant,
    mock_pronote_client,
) -> None:
    """AUTH-03: two child entries reload independently when one changes options."""
    entry_a = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data={**_BASE_ENTRY_DATA, "child_identifier": "jean_dupont",
              "child_name": "Jean Dupont", "child_index": 0},
        options={"refresh_interval": 30},
        version=1,
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:marie_dupont",
        data={**_BASE_ENTRY_DATA, "child_identifier": "marie_dupont",
              "child_name": "Marie Dupont", "child_index": 1},
        options={"refresh_interval": 60},
        version=1,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    # Open OptionsFlow on entry_a only.
    result = await hass.config_entries.options.async_init(entry_a.entry_id)
    assert result["step_id"] == "polling"

    # Complete both steps with new value for entry_a.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"refresh_interval": 15, ...},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"nickname": "Jeannot", "school_tz": "Pacific/Noumea"},
    )
    await hass.async_block_till_done()

    # Entry A reflects the change; entry B does not.
    assert entry_a.options["refresh_interval"] == 15
    assert entry_a.options["nickname"] == "Jeannot"
    assert entry_b.options["refresh_interval"] == 60          # unchanged
    assert entry_b.options.get("nickname") is None             # unchanged
```

[VERIFIED via existing test patterns in `tests/test_config_flow.py:134-152`] — `MockConfigEntry`, `add_to_hass`, `hass.config_entries.options.async_init` are all the idiomatic surface for HA options testing.

### Pattern 5: Triggering reauth from tests

**What:** PHACC provides `entry.start_reauth_flow(hass)` helper (HA core `tests/common.py`) — the test-side equivalent of HA core raising `ConfigEntryAuthFailed` in production. Same for `entry.start_reconfigure_flow(hass)`.

**Example:**

```python
# Source: github.com/home-assistant/home-assistant/blob/dev/tests/common.py
# start_reauth_flow / start_reconfigure_flow helpers on MockConfigEntry.

async def test_reauth_flow_happy_path(hass, mock_pronote_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, ..., data=_ENTRY_DATA_WITH_SESSION)
    entry.add_to_hass(hass)

    # PHACC start_reauth_flow == hass.config_entries.flow.async_init with SOURCE_REAUTH
    # and entry_data == entry.data context. Equivalent to HA raising ConfigEntryAuthFailed.
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
    assert entry.data["password"] == "new_pw"
    assert entry.data["session"] is None     # D-02 clear
    assert entry.data["url"] == _ENTRY_DATA_WITH_SESSION["url"]   # preserved
```

[VERIFIED: github.com/home-assistant/core/blob/dev/tests/common.py contains `start_reauth_flow` and `start_reconfigure_flow` methods on `MockConfigEntry`. PHACC re-exports them via `from pytest_homeassistant_custom_component.common import MockConfigEntry`.]

### Anti-Patterns to Avoid

- **`self.config_entry = config_entry` in `OptionsFlow.__init__`** — Deprecated HA 2024.12. The property is read-only since HA 2025.12. Use `self.config_entry` (which HA injects). Tons of integrations broke on this — see [Critical Gotcha #3](#critical-gotcha-3-optionsflow__init__config_entry-deprecation).
- **`entry.add_update_listener(_async_reload_entry)`** — Deprecated 2026-05-07, error in 2026.6, removed in 2026.12. Use `OptionsFlowWithReload`. **CONTEXT.md D-12 must be updated.**
- **`vol.Strip`** — Does not exist in voluptuous. Use a lambda `lambda v: v.strip()` or stdlib `.strip()` in the handler post-validation. **CONTEXT.md D-16 must be revised** (cosmetic — the intent is preserved).
- **`async_step_reauth(entry_data)` raw form rendering** — `async_step_reauth(entry_data)` is HA's call-in; the convention is to immediately delegate to `async_step_reauth_confirm()`. Don't render forms or run network calls in `async_step_reauth` itself. The 2-step split makes strings.json simpler (one "Are you sure?" step, one form step — Phase 6 collapses into form-only by skipping the confirm dialog and going straight to credentials).
- **Try/except: pass around `vol.Invalid` / form errors** — User memory explicit: NO mapping of typed exceptions to anonymous "Unknown error". Use the form `errors={"base": "<key>"}` dict per Phase 3 D-04 mapping.
- **OptionsFlow that doesn't reload coordinator** — defeats COORD-03 / OPT-04. `OptionsFlowWithReload` does this automatically; vanilla `OptionsFlow` requires the (now deprecated) `add_update_listener` plumbing.
- **Reauth that asks for URL or account_type** — defeats AUTH-05 spec. Per D-01 only username + password fields.
- **Tests that pickle `pronotepy.Client`** — Use `MagicMock` per Phase 3 C-05. Existing `tests/conftest.py` `mock_pronote_client` fixture (reused by Phase 3-5) is the canonical surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reload entry on options change | hand-roll `entry.add_update_listener(_async_reload_entry)` (D-12) | `OptionsFlowWithReload` base class | Deprecated 2026-05-07, removed 2026.12. Single import change. |
| Look up reauth config entry | `self.hass.config_entries.async_get_entry(self.context["entry_id"])` | `self._get_reauth_entry()` | Helper exists since HA 2024.10 specifically to eliminate this verbose lookup. |
| Look up reconfigure config entry | same verbose lookup | `self._get_reconfigure_entry()` | same |
| Commit reauth/reconfigure data | `hass.config_entries.async_update_entry(...)` + `await hass.config_entries.async_reload(...)` + `self.async_abort(reason="reauth_successful")` | `return self.async_update_reload_and_abort(entry, data_updates=...)` | One atomic helper. The May 2026 deprecation only flags it when *combined* with `add_update_listener` — calling it from a flow step is and remains the idiom. |
| Prefill form fields with current values | manually `vol.Optional(KEY, default=current_value): ...` | `add_suggested_values_to_schema(SCHEMA, current_dict)` | Cleaner, supports nested schemas, mirrors `entry.options` shape directly. Used by HA Core integrations. |
| Render a bool in OptionsFlow form | `cv.boolean` (renders as checkbox) | `BooleanSelector()` (toggle widget) | UX consistency with rest of HA UI. |
| Render a numeric field (1..1440 minutes) | `vol.All(int, vol.Range(min=1, max=1440))` | `NumberSelector(NumberSelectorConfig(min=1, max=1440, mode=BOX, unit_of_measurement="min"))` | Client-side bounds + unit label; HA UI standard. |
| Render a time field (HH:MM) | `cv.time` | `TimeSelector()` | Browser-native time picker. |
| Multi-child entry creation | new "add child" sub-flow | Phase 3 D-05 already ships this via `async_set_unique_id` + `_abort_if_unique_id_configured`. User re-runs "Add Integration" with a different `child_index`. | Already shipped. Phase 6 only verifies coexistence post-reload (one test). |
| Trigger reauth from test code | manually `hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_REAUTH, ...}, data=entry.data)` | `entry.start_reauth_flow(hass)` from PHACC's `MockConfigEntry` | Helper exists in HA core's `tests/common.py`; PHACC re-exports. |

**Key insight:** Phase 6 is small because HA gives us so much. Resist the temptation to "improve" the patterns — every shortcut HA provides has been battle-tested across hundreds of integrations.

## Runtime State Inventory

Phase 6 is NOT a rename/refactor in the classic sense, but it DOES mutate `entry.data` keys at runtime (reauth changes `username`/`password`/`session`; reconfigure changes `url`/`account_type`/`session`). Several categories of state need consideration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **HA's `.storage/core.config_entries` file** stores `entry.data` and `entry.options` for every entry. Phase 6's reauth/reconfigure flows MUTATE these via `async_update_reload_and_abort(data_updates=...)` — HA's storage layer debounces the disk write. Existing entries from Phase 3-5 have the locked `entry.data` D-08 shape; Phase 6 adds new `entry.options` keys (forward-compat per `get(key, default)`). | No data migration. `entry.options` keys are forward-compat by virtue of `.get(KEY, DEFAULT)` reads in `_resolve_options` (Phase 5) and the new `_options_schema_defaults` (Phase 6 D-11). |
| Live service config | **HA's `device_registry`** and **`entity_registry`** persist the `DeviceInfo.name` and entity_id. Phase 6's nickname (D-13) affects `DeviceInfo.name` (display only) but NOT entity_id (which keys off `unique_id`, ENT-02 frozen). | After reload triggered by OptionsFlowWithReload, HA's device_registry picks up the new `DeviceInfo.name` from `PronoteEntity.device_info` automatically. No registry manipulation in Phase 6 code. |
| OS-registered state | **None.** Phase 6 doesn't register systemd units, cron jobs, or HA service definitions. The OptionsFlow surface is purely UI + data. | None. |
| Secrets/env vars | **`entry.data["password"]`** mutated by reauth (D-01). Continues to live in `.storage/core.config_entries` — HA encrypts at rest in some installations but NOT all (PROJECT.md Phase 3 specifics ¶4). Phase 6 does NOT add new credential storage. Phase 7 DIAG-01 will redact this in diagnostics dumps. | None. The mutation honors Phase 3 D-08 storage shape — same JSON key, same trust boundary. |
| Build artifacts / installed packages | **None.** Phase 6 adds no new manifest dependencies. `OptionsFlowWithReload` is bundled with HA 2024.11+ — the existing HA 2026.4 floor already supplies it. | None. The manifest stays at `pronotepy==2.14.6`, `python-slugify==8.0.4`, `holidays==<pin from Phase 5>`. |

**The canonical question:** After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?

- A dev who installed v0.0.x → v0.0.6 (Phase 5) and then updates to v0.0.7 (Phase 6) inherits `entry.data` keys identical to Phase 3 D-08. **Their existing `entry.options` (8 Phase 5 keys) are forward-compat with the 11-key Phase 6 schema by `.get(KEY, DEFAULT)`.** They will not lose entity history.
- Same dev who then opens OptionsFlow for the first time: the form shows the 11-key schema with **suggested defaults** drawn from the existing 8 Phase 5 keys + the 3 new defaults. Submitting writes all 11 keys to `entry.options`.
- Recorder history continues unchanged because `unique_id` is frozen per ENT-02 — Phase 6 never recomputes it.

## Environment Availability

Phase 6 is a pure code/config change with no new external dependencies. **Step 2.6: SKIPPED (no external dependencies identified beyond what Phase 5 already required).**

[VERIFIED: `pip show pronotepy` → 2.14.6 matches manifest.json. No new package needed for `OptionsFlowWithReload` — bundled with HA since 2024.11.]

## Common Pitfalls

### Critical Gotcha #1: D-12 is deprecated in May 2026

**What goes wrong:** Implementing D-12 verbatim (`entry.async_on_unload(entry.add_update_listener(_async_reload_entry))`) will emit a HA log warning today, throw a deprecation error in HA 2026.6 (next release after 2026.4), and break completely in 2026.12. The HA-Pronote v0.1.0 release will likely ship into a HA version where this pattern is already gone.

**Why it happens:** The 2026-05-07 HA dev blog (TWELVE days before Phase 6 was discussed) deprecates the combination of `add_update_listener` + any reloading method. The replacement is `OptionsFlowWithReload`, a base class HA shipped 18 months earlier specifically for this use case.

**How to avoid:**
1. Change CONTEXT.md D-12 from "naïve add_update_listener" to "subclass `OptionsFlowWithReload`".
2. `from homeassistant.config_entries import OptionsFlowWithReload`.
3. Make `HaPronoteOptionsFlow(OptionsFlowWithReload)` instead of `(OptionsFlow)`.
4. **Delete** `entry.async_on_unload(entry.add_update_listener(_async_reload_entry))` from `__init__.py:async_setup_entry` — `OptionsFlowWithReload` does the reload itself.
5. **Delete** `_async_reload_entry` helper — not needed.

**Warning signs:**
- Deprecation warning in `ha core logs`: `Deprecated config entry listener combined with reloading method...`
- Two reloads firing on a single options save (the listener + the reloading-method reload — explicitly called out in the deprecation blog).
- Race conditions where the coordinator's polling loop interleaves with the reload teardown.

[CITED: developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/]

### Critical Gotcha #2: `vol.Strip` doesn't exist

**What goes wrong:** CONTEXT.md D-16 says `vol.All(cv.string, vol.Length(max=40), vol.Strip)`. This will raise `AttributeError: module 'voluptuous' has no attribute 'Strip'` at import time of the OptionsFlow schema — the entire integration fails to load.

**Why it happens:** `vol.Strip` is a phantom — it sounds like it should exist (HA's templating has a `trim` filter; some 3rd-party voluptuous extensions add `Strip`), but the upstream `voluptuous` package never shipped it.

**How to avoid:** Replace `vol.Strip` with a lambda. Two equally good options:

```python
# Option A: lambda in the vol.All chain
vol.All(cv.string, vol.Length(max=NICKNAME_MAX_LEN), lambda v: v.strip())

# Option B: strip inside the handler post-validation
# (schema only does cv.string + Length; the handler does .strip())
opts["nickname"] = (user_input.get("nickname") or "").strip()
```

Recommended: **Option A** — keeps the strip in the schema layer so test assertions on `entry.options["nickname"]` see the stripped value without per-test fix-ups.

**Warning signs:**
- `AttributeError: module 'voluptuous' has no attribute 'Strip'` at import time.
- `hassfest` validation failing with schema error.

[VERIFIED: voluptuous source — `voluptuous/validators.py` ships `vol.All`, `vol.Any`, `vol.Length`, `vol.Range`, `vol.In`, `vol.Coerce`, `vol.Match`, `vol.Url`, but no `Strip`.]

### Critical Gotcha #3: `OptionsFlow.__init__(config_entry)` deprecation

**What goes wrong:** Older HA tutorials show `def __init__(self, config_entry): self.config_entry = config_entry`. This is deprecated since HA 2024.12 with warning, and the `config_entry` property became read-only in HA 2025.12 — assignment raises `AttributeError: property 'config_entry' of 'HaPronoteOptionsFlow' object has no setter`.

**Why it happens:** HA 2024.12 changelog explicitly deprecated explicit `config_entry` assignment in OptionsFlow. Many community integrations (LocalTuya, HACS itself, better_thermostat, etc.) were caught.

**How to avoid:**
- DO NOT assign `self.config_entry = config_entry` in `__init__`.
- DO NOT take `config_entry` as `__init__` parameter (the `async_get_options_flow(config_entry)` API still passes one, but `OptionsFlow` / `OptionsFlowWithReload` no longer needs you to store it).
- USE `self.config_entry` (HA injects automatically) inside step methods.

**Sample broken code:**

```python
# BROKEN
class HaPronoteOptionsFlow(OptionsFlowWithReload):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry      # AttributeError on HA 2025.12+
```

**Sample correct code:**

```python
# CORRECT
class HaPronoteOptionsFlow(OptionsFlowWithReload):
    def __init__(self) -> None:
        self._step1_data: dict[str, Any] = {}       # OK: own attribute
        # NB: self.config_entry is injected by HA — do not set.

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HaPronoteOptionsFlow()           # no config_entry arg
```

**Warning signs:**
- `AttributeError: property 'config_entry' ... has no setter` at flow creation time.
- HA log warning: `Detected that custom integration ... sets option flow config_entry explicitly, which is deprecated...`

[CITED: github.com/hacs/integration/issues/4314, github.com/rospogrigio/localtuya/issues/1931, HA 2024.12 changelog]

### Pitfall #4: `set_active_child` on reauth/reconfigure must wrap typed errors

**What goes wrong:** Phase 3 carefully wrapped `pronotepy.set_child` calls behind `api/client.py:set_active_child` so `CryptoError` becomes `AuthError`, etc. The Phase 6 reconfigure step calls `set_active_child` for D-06 (re-derive child_identifier). If you forget to wrap with the same typed-error catch, you'll surface a raw `pronotepy.CryptoError` traceback in the flow.

**How to avoid:** Mirror the existing pattern in `config_flow.py:_create_entry` and `__init__.py:async_setup_entry` — wrap `set_active_child` calls in the same `try/except (AuthError, RateLimitedError, CommunicationError, PronoteIntegrationError):` block, map each to the corresponding `errors["base"]` key per Phase 3 D-04.

**Warning signs:**
- A reconfigure attempt fails and the UI shows "Unknown error" with a Python traceback in the logs instead of "Invalid credentials".

### Pitfall #5: `school_tz` validation must happen INSIDE the form handler, not at coordinator setup

**What goes wrong:** If you only validate `school_tz` at coordinator setup time (in `__init__.py:async_setup_entry`), a user typing `"Pacific/NotARealZone"` in the OptionsFlow will see the form succeed → coordinator reload triggers → setup fails with `ZoneInfoNotFoundError` → entry stuck in error state. Bad UX.

**How to avoid:** Validate inside `async_step_display` BEFORE calling `async_create_entry`. The Pattern 3 example above shows this — try `ZoneInfo(user_input["school_tz"])` and set `errors["school_tz"] = "invalid_school_tz"` on failure. The form re-renders with the error inline; user types again.

**Warning signs:**
- Entry flips to "Failed to setup" state right after OptionsFlow submission.
- Coordinator logs a `ZoneInfoNotFoundError` traceback every poll attempt.

### Pitfall #6: Reauth that drops `entry.data` keys instead of merging

**What goes wrong:** If you write `return self.async_update_reload_and_abort(entry, data={"username": ..., "password": ..., "session": None})`, the `data=` kwarg REPLACES `entry.data` entirely — you just deleted `url`, `account_type`, `child_identifier`, `child_index`, `child_name`. The entry resets to invalid state.

**How to avoid:** Use `data_updates=` (merge), NEVER `data=` (replace), per the May 2024 HA dev blog: "reduces the risk of data loss if the schema is updated."

```python
# CORRECT (merge — preserves url, account_type, child_*)
return self.async_update_reload_and_abort(
    entry,
    data_updates={
        "username": new_username,
        "password": new_password,
        "session": None,
    },
)

# BROKEN (replace — loses url, account_type, child_*)
return self.async_update_reload_and_abort(
    entry,
    data={"username": ..., "password": ..., "session": None},
)
```

[CITED: developers.home-assistant.io/blog/2024/04/25/always-reload-after-successful-reauth-flow/]

### Pitfall #7: `description_placeholders` interpolation forgotten

**What goes wrong:** Multi-child users with two entries reauthing simultaneously: the reauth dialog says "Re-authenticate Pronote" with no context for which child. User panics.

**How to avoid:** Pass `description_placeholders={"child_name": entry.data["child_name"]}` to every `async_show_form` call in reauth + reconfigure + OptionsFlow steps. Reference `{child_name}` in `strings.json`'s `config.step.reauth_confirm.description` and similar.

**Warning signs:** Two-entries UAT confused user trying to figure out which Pronote login to refresh.

### Pitfall #8: Hardcoding "fr"/"en" in flow strings (NOT HA's pattern)

**What goes wrong:** Phase 5 deliberately hardcoded notification body text in Python (Phase 5 D-15 C-05) because `persistent_notification.async_create` doesn't accept translation keys. Phase 6 flows are DIFFERENT — config flows fully support strings.json keys. Don't carry Phase 5's pattern into Phase 6.

**How to avoid:** Every Phase 6 flow string lives in `strings.json` and `translations/{en,fr}.json` — `config.step.reauth_confirm.title`, `config.step.reauth_confirm.description`, `config.step.reauth_confirm.data.username`, etc. The flow code references the dotted key only via `async_show_form(step_id="reauth_confirm", ...)` — HA core does the lookup.

**Warning signs:** Untranslated English strings appearing in the HA UI when the user's locale is French.

## Code Examples

Verified patterns from official sources. All examples below are HIGH confidence (Context7 unavailable; verified via HA dev docs + 2026-05-07 deprecation blog cross-reference).

### Example 1: Trigger from coordinator (already shipped — no change needed)

```python
# Source: existing custom_components/ha_pronote/coordinator.py:294
# Phase 3 already raises ConfigEntryAuthFailed; Phase 6 adds the receiver flow.

except AuthError as err:
    # Real auth failure on the retry — credentials genuinely invalid.
    self._handle_failure(err, kind=AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX)
    raise ConfigEntryAuthFailed(f"[{err.reason}] {redact(err.message)}") from err
```

No Phase 6 change. HA's reauth machinery hooks `ConfigEntryAuthFailed` automatically once `async_step_reauth` exists in `config_flow.py`.

### Example 2: Strings.json keys added by Phase 6

```jsonc
// strings.json — additions only; existing keys preserved.
{
  "config": {
    "step": {
      // existing keys preserved
      "user": { ... },
      "pick_child": { ... },

      // NEW
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
    },
    "error": {
      // existing keys preserved
      "invalid_auth": "...",
      "cannot_connect": "...",
      "ip_suspended": "...",
      "unknown": "..."
    },
    "abort": {
      "already_configured": "...",
      // NEW
      "reauth_successful": "Re-authentication successful — Pronote credentials updated.",
      "reconfigure_successful": "Configuration successful — Pronote settings updated.",
      "child_identifier_changed": "The new URL/account exposes a different child. Delete this entry and re-add it to track the new child."
    }
  },
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
}
```

Mirror in `translations/fr.json` per existing Phase 5 pattern.

### Example 3: const.py additions

```python
# const.py — APPEND to Phase 5 surface (no rename, no removal).

# Phase 6 additions.
DEFAULT_ADAPTIVE_POLLING_ENABLED: Final = True  # D-09 — OPT-02 default
NICKNAME_MAX_LEN: Final = 40                    # D-16
```

No other `const.py` change — `DEFAULT_SCHOOL_TZ` already exists from Phase 2 (`Pacific/Noumea`), `DEFAULT_REFRESH_INTERVAL` already exists from Phase 3, all 8 Phase 5 keys already present.

### Example 4: `PolitesseOptions` extension

```python
# politesse.py — ADD adaptive_enabled field.

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
    adaptive_enabled: bool = True   # NEW — Phase 6 OPT-02


def compute_interval(now: datetime, options: PolitesseOptions, *, rng: Any = random) -> timedelta:
    """Phase 6 — short-circuit if user disabled adaptive polling."""
    if not options.adaptive_enabled:
        # Skip the 17h–20h tighten branch; always return refresh_interval + jitter.
        jittered = options.refresh_interval + timedelta(
            seconds=rng.uniform(-options.jitter_seconds, options.jitter_seconds)
        )
        return max(jittered, timedelta(minutes=1))
    # ... existing branch logic unchanged ...
```

### Example 5: `coordinator._resolve_options` extension

```python
# coordinator.py — _resolve_options EXTEND.

return PolitesseOptions(
    school_tz=self._school_tz,
    refresh_interval=_read_minutes("refresh_interval", DEFAULT_REFRESH_INTERVAL),
    # ... existing 7 keys unchanged ...
    jitter_seconds=JITTER_SECONDS,
    adaptive_enabled=bool(opts.get("adaptive_polling_enabled", True)),   # NEW
)
```

### Example 6: `__init__.py:async_setup_entry` `school_tz` per-entry override

```python
# __init__.py — change ONE line.

# OLD (Phase 3/5):
school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)

# NEW (Phase 6):
school_tz_name = entry.options.get("school_tz", DEFAULT_SCHOOL_TZ)
try:
    school_tz = ZoneInfo(school_tz_name)
except (ZoneInfoNotFoundError, ValueError) as err:
    # If a bad tz somehow lands in entry.options (manual JSON edit, broken migration),
    # raise ConfigEntryNotReady — user can fix via OptionsFlow.
    raise ConfigEntryNotReady(f"Invalid school_tz {school_tz_name!r}") from err
```

Note: the OptionsFlow `async_step_display` validates `school_tz` before commit (Pitfall #5), so a bad value should never reach `async_setup_entry`. This is the belt-and-braces guard.

### Example 7: `entity.py:DeviceInfo.name` nickname fallback

```python
# entity.py — D-14 nickname fallback.

@property
def device_info(self) -> DeviceInfo:
    # ... existing class_label resolution unchanged ...

    # D-14: nickname fallback.
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `entry.add_update_listener(_async_reload_entry)` + manual `async_reload` | `OptionsFlowWithReload` base class | HA 2024.11 (introduced); HA 2026.5 (deprecation warning); HA 2026.6 (error); HA 2026.12 (removed) | Phase 6 MUST use `OptionsFlowWithReload`. CONTEXT.md D-12 reflects an outdated pattern. |
| `self.hass.config_entries.async_get_entry(self.context["entry_id"])` | `self._get_reauth_entry()` / `self._get_reconfigure_entry()` | HA 2024.10 | Cleaner; recommended; old form still works but is verbose |
| `self.config_entry = config_entry` in OptionsFlow `__init__` | `self.config_entry` injected by HA (read-only) | Deprecated HA 2024.12; setter removed HA 2025.12 | DO NOT assign. Use HA's injected value. |
| `data=` kwarg in `async_update_reload_and_abort` | `data_updates=` kwarg | HA 2024 docs explicitly recommend `data_updates` over `data` | Use `data_updates` to merge; never `data` (replaces and loses keys). |
| Single-step OptionsFlow with all fields | Multi-step OptionsFlow via `async_step_init` → step-named redirects | Always possible; documented in `data_entry_flow_index.md` | CONTEXT.md D-10 is fine. The "options only has init" line in some docs is outdated. |
| `cv.boolean` for booleans in flow | `BooleanSelector()` selector | HA 2023+ (selectors became the modern approach) | Better UX; use `BooleanSelector`. |
| `cv.time` | `TimeSelector()` selector | HA 2023+ | Same. |

**Deprecated/outdated:**
- `entry.add_update_listener(_async_reload_entry)` together with reloading methods — deprecated 2026-05-07, error 2026.6, removed 2026.12. [CITED: developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/]
- `OptionsFlow.__init__(config_entry)` storing `self.config_entry = config_entry` — deprecated HA 2024.12; setter removed HA 2025.12. [CITED: HA 2024.12 changelog]
- `vol.Url()` as a config flow schema validator — already replaced in Phase 3 D-03 by `TextSelector(TextSelectorConfig(type=URL))`. No Phase 6 regression.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `OptionsFlowWithReload` is available in HA 2026.4 (introduced 2024.11) — never removed | Critical Gotcha #1, Pattern 3 | LOW — both sources confirm. Plan can call `python -c "from homeassistant.config_entries import OptionsFlowWithReload"` as a probe step to be safe. |
| A2 | `_get_reauth_entry()` and `_get_reconfigure_entry()` exist in HA 2026.4 (introduced 2024.10) — never removed | Pattern 1, Pattern 2 | LOW — explicitly documented in the 2024-10-21 dev blog. |
| A3 | `async_update_reload_and_abort(entry, data_updates=...)` is the canonical commit idiom and stays so even after the May 2026 deprecation | Pattern 1, Pattern 2 | LOW — the May 2026 deprecation flags only the combination with `add_update_listener`. The flow-step usage stays canonical. |
| A4 | `entry.start_reauth_flow(hass)` / `start_reconfigure_flow(hass)` are available on `MockConfigEntry` via PHACC | Pattern 5 | MEDIUM — verified via HA core tests/common.py source (search result hit); PHACC mirrors common.py daily so the helper is exposed. Plan should `grep MockConfigEntry.start_reauth_flow` in `tests/common.py` of the installed PHACC version on first plan execution. |
| A5 | `description_placeholders` interpolation works in HA 2026.4 strings.json `description` and `data_description` fields | Code Examples, Pitfall #7 | LOW — long-standing HA feature, used throughout HA Core integrations. |
| A6 | `add_suggested_values_to_schema` is available on both `OptionsFlow` and `OptionsFlowWithReload` instances | Pattern 3, Pattern 2 | LOW — it's a method on `ConfigEntryBaseFlow` (the shared base), inherited by all flow types. |
| A7 | `NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX))` renders as a text input with min/max enforcement, not a slider | Don't Hand-Roll | LOW — confirmed via existing Phase 5 patterns; mode=BOX is the standard text-input mode. |
| A8 | `description_placeholders={"child_name": entry.data["child_name"]}` reaches the OptionsFlow steps the same way as ConfigFlow steps | Pitfall #7 | MEDIUM — confirmed for ConfigFlow steps; for OptionsFlow this is symmetric per HA core source but not explicitly documented. Plan should verify in test. |
| A9 | The reauth + reconfigure flows MUST end with `async_update_reload_and_abort` (NOT `async_create_entry`) | Pattern 1, Pattern 2, Anti-Patterns | LOW — explicitly stated in dev docs: "reauth flows are expected to update the current entry and abort; they should not create a new entry." |

**If this table is empty:** Not empty — flagged for plan-level confirmation. None of these assumptions need user clarification; they need a one-line probe at plan execution time (e.g. `python -c "from homeassistant.config_entries import OptionsFlowWithReload"` in plan 06-01 Wave 0).

## Validation Architecture

Required by Phase 6 — the integration's quality target is HA Bronze (already met by Phase 3) + Silver `reauthentication-flow` + Gold `reconfiguration-flow` (both shipped by Phase 6).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest-homeassistant-custom-component==0.13.326` (tracks HA `2026.5.0b0`; backward-compat with 2026.4.x) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` (Phase 1 D-29) |
| Quick run command | `uv run pytest tests/test_config_flow.py -x` |
| Full suite command | `uv run pytest --cov=custom_components.ha_pronote --cov-fail-under=90` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| AUTH-03 | Two ConfigEntries with independent options coexist post-reload | integration (`hass` fixture + 2 MockConfigEntries) | `pytest tests/test_config_flow.py::test_two_children_options_are_independent -x` | ❌ Wave 0 (new test, Pattern 4) |
| AUTH-05 | Reauth flow happy path — new password persisted, session cleared | integration | `pytest tests/test_config_flow.py::test_reauth_flow_happy_path -x` | ❌ Wave 0 (Pattern 5) |
| AUTH-05 | Reauth form-level error mapping (invalid_auth, ip_suspended, cannot_connect, unknown) | integration parametrized | `pytest tests/test_config_flow.py::test_reauth_error_mapping -x` | ❌ Wave 0 |
| AUTH-05 | Reauth username + password BOTH updated (not just password) | integration | `pytest tests/test_config_flow.py::test_reauth_updates_username_and_password -x` | ❌ Wave 0 |
| AUTH-05 | Reauth preserves URL + account_type + child_identifier (data_updates merge, not replace) | integration assertion on `entry.data` keys | `pytest tests/test_config_flow.py::test_reauth_preserves_url_account_type_child_id -x` | ❌ Wave 0 |
| AUTH-05 | Reauth triggers entry reload (coordinator re-instantiated) | integration | `pytest tests/test_config_flow.py::test_reauth_triggers_reload -x` | ❌ Wave 0 |
| AUTH-06 | Reconfigure flow happy path — URL change committed | integration | `pytest tests/test_config_flow.py::test_reconfigure_flow_happy_path -x` | ❌ Wave 0 |
| AUTH-06 | Reconfigure aborts when child_identifier resolves differently under new URL | integration | `pytest tests/test_config_flow.py::test_reconfigure_aborts_on_child_id_mismatch -x` | ❌ Wave 0 |
| AUTH-06 | Reconfigure clears session only when URL or account_type changed (D-08) | integration parametrized | `pytest tests/test_config_flow.py::test_reconfigure_session_clear_conditional -x` | ❌ Wave 0 |
| AUTH-06 | Reconfigure form-level error mapping | integration parametrized | `pytest tests/test_config_flow.py::test_reconfigure_error_mapping -x` | ❌ Wave 0 |
| AUTH-06 | Reconfigure preserves username + password + child_identifier | integration | `pytest tests/test_config_flow.py::test_reconfigure_preserves_credentials -x` | ❌ Wave 0 |
| COORD-03 | OptionsFlow polling step accepts refresh_interval 15/30/60 | integration parametrized | `pytest tests/test_config_flow.py::test_options_polling_refresh_interval -x` | ❌ Wave 0 |
| OPT-01 | refresh_interval value reaches `entry.options` post-commit | integration | (same as COORD-03) | ❌ Wave 0 |
| OPT-02 | adaptive_polling_enabled toggle persists; `PolitesseOptions.adaptive_enabled` reflects it | integration + politesse pure unit | `pytest tests/test_config_flow.py::test_options_adaptive_polling_toggle -x && pytest tests/test_politesse_tz_matrix.py::test_compute_interval_respects_adaptive_disabled -x` | ❌ Wave 0 (politesse unit test new; flow test new) |
| OPT-03 | Nickname strip + empty-to-None semantics | integration parametrized over `"  "`, `""`, `"Jeannot"`, `"  Jeannot  "` | `pytest tests/test_config_flow.py::test_options_nickname_strip -x` | ❌ Wave 0 |
| OPT-03 | Nickname propagates to `DeviceInfo.name` after reload | integration (sensor state via device_registry) | `pytest tests/test_sensor.py::test_nickname_propagates_to_device_name -x` | ❌ Wave 0 |
| OPT-04 | OptionsFlow commit triggers coordinator reload (no add_update_listener needed) | integration | `pytest tests/test_config_flow.py::test_options_change_triggers_reload -x` | ❌ Wave 0 |
| OPT-04 (D-09) | school_tz override reaches coordinator (compute_interval uses it) | integration | `pytest tests/test_config_flow.py::test_options_school_tz_override_takes_effect -x` | ❌ Wave 0 |
| OPT-04 (D-09) | school_tz invalid IANA name → form error, NOT coordinator setup failure | integration | `pytest tests/test_config_flow.py::test_options_invalid_school_tz_shows_form_error -x` | ❌ Wave 0 |
| (cross-cutting) | OptionsFlowWithReload import surfaces correctly | smoke test | `pytest tests/test_config_flow.py::test_options_flow_subclasses_options_flow_with_reload -x` | ❌ Wave 0 |
| (cross-cutting) | No deprecated `entry.add_update_listener` call in __init__.py | grep test | `pytest tests/test_init.py::test_no_deprecated_add_update_listener -x` | ❌ Wave 0 (small AST/grep assertion) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_config_flow.py -x` (fast, ≤ 30s typical)
- **Per wave merge:** `uv run pytest --cov=custom_components.ha_pronote --cov-fail-under=90`
- **Phase gate:** Full suite green before `/gsd-verify-work`. Includes TZ matrix unchanged from Phase 5 (Phase 6 doesn't extend the matrix per CONTEXT.md Claude's Discretion).

### Wave 0 Gaps

- [ ] `tests/test_config_flow.py` already exists — Phase 6 EXTENDS with ~17 new test functions per the table above.
- [ ] `tests/conftest.py` — `mock_pronote_client` fixture from Phase 3 is reused. No new fixtures required.
- [ ] No new framework install — PHACC 0.13.326 already installed; supplies `MockConfigEntry.start_reauth_flow` / `start_reconfigure_flow` helpers.
- [ ] Optional probe step in plan 06-01: `python -c "from homeassistant.config_entries import OptionsFlowWithReload; from pytest_homeassistant_custom_component.common import MockConfigEntry; mce = MockConfigEntry; assert hasattr(mce, 'start_reauth_flow') and hasattr(mce, 'start_reconfigure_flow')"` — confirms A1 + A4 assumptions in one shot.

## Security Domain

`security_enforcement` is enabled (default — no explicit `false` in `.planning/config.json`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | pronotepy `Client(...)` and `Client.token_login(...)` perform the auth handshake; HA-Pronote never hand-rolls auth crypto. Reauth flow surfaces credential rotation via the standard HA `ConfigEntryAuthFailed` → `async_step_reauth` machinery. |
| V3 Session Management | yes | Session token stored in `entry.data["session"]` (Phase 3 D-06); cleared on reauth (D-02) and on URL/account_type change (D-08). Token lifecycle owned by pronotepy. |
| V4 Access Control | no | HA-Pronote is per-entry per-child; no cross-entry data exposure. The unique_id format `url_host:username:child_identifier` enforces 1 ConfigEntry = 1 child boundary. AUTH-03 verifies. |
| V5 Input Validation | yes | All flow inputs validated via voluptuous schema. URL: `TextSelector(URL)` + `urllib.parse.urlparse` (Phase 3 D-03). Account type: `vol.In(["eleve", "parent"])`. Nickname: `vol.All(cv.string, vol.Length(max=40), .strip())`. school_tz: `ZoneInfo(...)` raises on invalid IANA name. |
| V6 Cryptography | no | All crypto inside pronotepy (RSA + AES via pycryptodome — exact-pinned in pronotepy's deps). HA-Pronote never imports a crypto primitive directly. |

### Known Threat Patterns for HA-Pronote Phase 6

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored credentials exfiltrated via debug log | Information Disclosure | Phase 3 `redact()` helper strips URL/password/token/uuid from every error message that hits a log line. Phase 6 inherits — no new credentials enter logs. |
| Stored credentials exfiltrated via diagnostics dump | Information Disclosure | DEFERRED — Phase 7 DIAG-01 with `async_redact_data`. Phase 6 does NOT add a diagnostics surface, so the attack surface stays Phase 3-equivalent. |
| Reauth flow accepting credentials from a different user (CSRF / session-jacking) | Spoofing | HA's flow_id token-protected; flow is bound to `self.context["entry_id"]` set by HA core. User must be HA-admin to access the flow URL. Not in Phase 6 scope — HA's auth gate is sufficient. |
| User-supplied `school_tz` triggering arbitrary code via ZoneInfo | Tampering | `ZoneInfo(...)` from stdlib — raises `ZoneInfoNotFoundError` on invalid name; cannot execute arbitrary code. Validated inside `async_step_display` (Pitfall #5). |
| User-supplied nickname containing path traversal / template injection | Tampering / Information Disclosure | Nickname is consumed ONLY by `DeviceInfo.name` (display string) — HA escapes for display. Length-capped at 40 chars. No path/eval surface. |
| User-supplied URL pointing to internal-only host (SSRF) | Tampering | pronotepy makes the HTTP call from the HA host, but the school server discriminator (Pronote-specific response shape) means a non-Pronote URL returns `CommunicationError`. User cannot use the integration as a generic outbound HTTP proxy. |
| Race condition between reload and active poll | Tampering | `OptionsFlowWithReload` triggers `async_unload_entry` (which Phase 3 plan 02 `await coordinator.async_shutdown()`s) → THEN `async_setup_entry`. The shutdown step waits for in-flight polls. No race. |

## Sources

### Primary (HIGH confidence)
- [HA Developer Docs: Config flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) — reauth + reconfigure idioms, `_get_reauth_entry`, `async_update_reload_and_abort`
- [HA Developer Docs: Options flow](https://developers.home-assistant.io/docs/config_entries_options_flow_handler/) — `OptionsFlowWithReload`, `add_suggested_values_to_schema`, multi-step pattern
- [HA Developer Docs: Data entry flow index](https://developers.home-assistant.io/docs/data_entry_flow_index/) — multi-step redirect from `async_step_init`, `description_placeholders`
- [HA Dev Blog 2024-10-21: New helpers for reauth and reconfigure](https://developers.home-assistant.io/blog/2024/10/21/reauth-reconfigure-helpers/) — `_get_reauth_entry()`, `_get_reconfigure_entry()`, `_abort_if_unique_id_mismatch()`, source check `if self.source == SOURCE_REAUTH`
- [HA Dev Blog 2024-04-25: Always reload after a successful re-auth flow](https://developers.home-assistant.io/blog/2024/04/25/always-reload-after-successful-reauth-flow/) — `data_updates=` preferred over `data=`
- [HA Dev Blog 2024-03-21: Config Entries reconfigure step](https://developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step/) — `async_step_reconfigure` introduction
- [HA Dev Blog 2026-05-07: Deprecating config entry listener with reloading methods](https://developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/) — **D-12 deprecation**; warning 2026.5+, error 2026.6, removed 2026.12
- [HA Quality Scale: Reauthentication-flow rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/) — Silver requirement
- [HA Quality Scale: Reconfiguration-flow rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/) — Gold requirement
- [HA Quality Scale: Config-flow-test-coverage rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage/) — Phase 6 test breadth target
- [HA 2024.11 changelog (`OptionsFlowWithReload` introduction)](https://www.home-assistant.io/changelogs/core-2024.11/)
- [HA 2024.12 changelog (deprecation of explicit `OptionsFlow.config_entry` assignment)](https://www.home-assistant.io/changelogs/core-2024.12/)

### Secondary (MEDIUM confidence)
- [HA Core common test helpers](https://github.com/home-assistant/home-assistant/blob/dev/tests/common.py) — `MockConfigEntry.start_reauth_flow` / `start_reconfigure_flow` (PHACC mirrors)
- [HA Core config entries source](https://github.com/home-assistant/core/blob/dev/homeassistant/config_entries.py) — `OptionsFlowWithReload` class definition, `async_update_reload_and_abort` signature
- [delphiki/hass-pronote](https://github.com/delphiki/hass-pronote) — prior art (still on Phase 5-era patterns; their `add_update_listener` is the deprecated form Phase 6 avoids)
- [hacs/integration#4314](https://github.com/hacs/integration/issues/4314) — concrete case of `config_entry` setter removal breaking integrations on HA 2025.x
- [rospogrigio/localtuya#1931](https://github.com/rospogrigio/localtuya/issues/1931) — same pattern, different integration
- [rospogrigio/localtuya#2132](https://github.com/rospogrigio/localtuya/issues/2132) — `config_entry` setter removed entirely in HA 2025.12

### Tertiary (LOW confidence)
- [Community Q&A: reauthentication config flow implementation](https://community.home-assistant.io/t/help-with-reauthentication-config-flow-implementation/586196) — useful for trip-wires; treated as advisory only
- [Aaron Godfrey tutorial part 4: Options Flow](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_4/) — pre-`OptionsFlowWithReload` patterns; cite only for the basic schema mechanics; do not follow the listener pattern verbatim

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `OptionsFlowWithReload`, `_get_reauth_entry`, `async_update_reload_and_abort`, `add_suggested_values_to_schema` all directly cited from official HA dev docs + dev blogs
- Architecture: HIGH — Phase 3 D-05 unique_id format + Phase 5 D-17 options shape already lock the structure; Phase 6 only adds UI + 3 keys
- Pitfalls: HIGH — three critical gotchas (D-12 deprecation, `vol.Strip` non-existence, `OptionsFlow.__init__` deprecation) verified across multiple sources
- Validation Architecture: HIGH on test framework; MEDIUM on PHACC `start_reauth_flow` helper (A4 — verify at plan execution time)
- Security: HIGH — Phase 6 attack surface is a strict subset of Phase 3/5; no new credentials, no new HTTP

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (the HA 2026.6 release that turns the listener+reload deprecation into an error — re-verify D-12 commentary before this date if Phase 6 has not landed)
