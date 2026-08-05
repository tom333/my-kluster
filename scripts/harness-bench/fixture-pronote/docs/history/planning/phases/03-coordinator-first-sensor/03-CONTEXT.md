# Phase 3: Coordinator & First Sensor - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end runtime loop that proves the executor boundary, `runtime_data` plumbing, token persistence, and entity identity work against real Pronote — without any of the diff/event firing or full sensor suite that Phase 4 will add.

**Phase 3 ships:**

1. **Real `config_flow.py`** replacing Phase 1's `not_implemented` placeholder — `async_step_user` (URL + account_type + username + password) plus `async_step_pick_child` (only when `ParentClient.children` count > 1). Validates credentials by calling `api.client.build_client(...)` (executor-wrapped); creates a config entry only on success. Per-invocation = per-child entry.
2. **`coordinator.py` — `PronoteDataUpdateCoordinator`** subclass of `TimestampDataUpdateCoordinator` (HA modern). One coordinator per `ConfigEntry`. `_async_update_data` wraps `api.fetcher.fetch_all(...)` in `hass.async_add_executor_job(partial(...))`, captures `client.export_credentials()` after every successful poll, writes it to `entry.data['session']`, maps typed `api/errors.py` exceptions to `ConfigEntryAuthFailed` / `UpdateFailed`. Hardcoded `update_interval = timedelta(minutes=30)` (Phase 5 makes it adaptive, Phase 6 makes it Options-Flow-driven).
3. **`__init__.py` — real `async_setup_entry` / `async_unload_entry` / `async_migrate_entry`** with the `runtime_data` typed pattern (`type PronoteConfigEntry = ConfigEntry[PronoteData]`). On setup: try `Client.token_login(stored_session)` (executor) first; on `AuthError` fallback to fresh `Client(url, username, password)`; coordinator's `async_config_entry_first_refresh()` awaited; sensor platform forwarded.
4. **`data.py` — `PronoteData` dataclass** (the typed `runtime_data` payload): coordinator reference, `child_identifier`, `school_tz`, plus a slot for the live pronotepy client used between polls (so the coordinator can call `export_credentials()` without rebuilding).
5. **`sensor.py` — one `PronoteLessonsTodaySensor`** + a base class `PronoteEntity(CoordinatorEntity[PronoteDataUpdateCoordinator])` Phase 4 will subclass. State = `len(coordinator.data.lessons_today)`, no extra_state_attributes, `state_class=measurement`, `icon=mdi:school`, `has_entity_name=True`, `_attr_translation_key="lessons_today"`. Device per child: `DeviceInfo(identifiers={(DOMAIN, child_identifier)}, name=client.info.name, manufacturer="Pronote")` — no `model` field yet (Phase 4 adds it).
6. **`unique_id` freeze** — at config-flow time, derive `child_identifier = slugify(client.info.name)` (eleve) or `slugify(client.children[i].name)` (parent) and STORE it in `entry.data['child_identifier']`. Coordinator/sensor never re-derive. Collisions with existing entries get a 2-char hex suffix from `pronotepy.children[i].identifier`. Sensor `unique_id = f"pronote_{child_identifier}_lessons_today"` — frozen v1, never altered by nickname.
7. **`async_migrate_entry` skeleton** — present, returns `True`. Phase 6+ fills the body when shapes change (ENT-04).
8. **AUTH-07 Pronote-side device label** — `home-assistant-{entry_id[:8]}` passed into `pronotepy.Client` (or `ParentClient`) constructor as the `device_name` kwarg so the user can see the integration in the Pronote app and revoke it manually.
9. **Tests** — full PHACC coverage: ConfigFlow happy path (eleve), ConfigFlow happy path (parent + pick_child), ConfigFlow `invalid_auth` / `cannot_connect` error mapping, coordinator first-refresh + token-capture roundtrip, restart with stored session uses `token_login` first, restart with stale session falls back to fresh login, sensor state reads from coordinator, unique_id format assertion, `async_migrate_entry` returns True, blocking-call detector clean during a poll. Pronotepy mocked at the `requests.Session` level via `requests-mock` (Phase 2 D-26 dep).

**In scope (Phase 3 only):**

- `custom_components/ha_pronote/__init__.py` — replace Phase 1 no-op stub with real `async_setup_entry`/`async_unload_entry`/`async_migrate_entry`
- `custom_components/ha_pronote/data.py` — NEW (`PronoteData`, `type PronoteConfigEntry = ConfigEntry[PronoteData]`)
- `custom_components/ha_pronote/coordinator.py` — NEW (`PronoteDataUpdateCoordinator`)
- `custom_components/ha_pronote/config_flow.py` — REPLACE placeholder with real flow (`async_step_user`, `async_step_pick_child`)
- `custom_components/ha_pronote/sensor.py` — NEW (`PronoteEntity` base + `PronoteLessonsTodaySensor`)
- `custom_components/ha_pronote/strings.json` — extend with config-flow / sensor / error strings
- `custom_components/ha_pronote/manifest.json` — flip `quality_scale` only if hassfest demands; bump `version` placeholder if needed
- `custom_components/ha_pronote/const.py` — append `DEFAULT_REFRESH_INTERVAL = timedelta(minutes=30)`, platform list, etc.
- `custom_components/ha_pronote/api/client.py` — extend with a `token_login_or_build(...)` helper that takes the stored session dict and falls back to fresh login (or wire that fallback in `__init__.py:async_setup_entry`)
- `tests/test_config_flow.py` — NEW
- `tests/test_coordinator.py` — NEW
- `tests/test_sensor.py` — NEW
- `tests/test_init.py` — extend with `async_setup_entry` happy path + `async_migrate_entry` skeleton check
- `tests/test_token_persistence.py` — NEW (or fold into test_coordinator.py)
- `tests/conftest.py` — may add a `mock_pronote_client` fixture for HA-side tests

**Out of scope (deferred to later phases):**

- Bus events (`pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_information`) — Phase 4
- Full sensor suite (grades, notifications) + Calendar entity — Phase 4
- J / J+1 attribute payload on the lessons sensor — Phase 4 (TIME-02, TIME-03)
- Adaptive 17h–20h polling, quiet hours, week-end suspension, vacation suspension, jitter, circuit breaker, IP-suspended long backoff — Phase 5
- Reauth flow (`async_step_reauth`), reconfigure flow (`async_step_reconfigure`), Options Flow (refresh_interval, nickname, school_tz override) — Phase 6
- Diagnostics platform (`async_get_config_entry_diagnostics` with `async_redact_data`) — Phase 7
- Repair issues (`ir.async_create_issue`) for IP-ban / auth-fail — Phase 7
- Translations (`fr.json`, `en.json` full coverage) — Phase 7. Phase 3 ships `strings.json` only.
- Daily cron CI against `pronotepy@main` — Phase 7
- README install / configuration docs — Phase 7

</domain>

<decisions>
## Implementation Decisions

### Config Flow shape & ParentClient handling (Area 1)
- **D-01:** `async_step_user` is a single-step form with all four fields: `URL`, `account_type` (Literal["eleve","parent"]), `username`, `password`. Submission triggers `await hass.async_add_executor_job(partial(build_client, url, account_type, username, password))`. On success: if eleve, jump straight to entry creation; if parent and `len(client.children) == 1`, also straight to entry creation; if parent and `len(client.children) > 1`, transition to `async_step_pick_child`.
- **D-02:** `async_step_pick_child` shows a single-select dropdown of `client.children` (display: each child's `name`; value: index `0..n-1`). Selection triggers `client.set_child(idx)`, then a fresh `client.export_credentials()` capture, then entry creation with the chosen `child_identifier`. Re-running "Add Integration" lets the user add the second child as a separate entry — AUTH-03 (one entry per child) ships effectively in Phase 3 by virtue of this flow; Phase 6 adds reconfigure UX and per-child auth-fail isolation tests but does NOT migrate entries.
- **D-03:** URL validation is `voluptuous.Url()` schema only — instant form-level rejection of malformed URLs. Real reachability is verified by the `build_client(...)` call: a wrong host raises `CommunicationError` (mapped to `errors={"base": "cannot_connect"}` in the form). No HEAD probe before auth (overkill for Phase 3; CLAUDE.md's anti-pattern table specifically calls out `voluptuous.Url()` as the right tool).
- **D-04:** Error mapping in `async_step_user`:
  - `AuthError` → `errors={"base": "invalid_auth"}` (form re-presented; no entry created)
  - `RateLimitedError(IP_SUSPENDED)` → `errors={"base": "ip_suspended"}` (form re-presented with localized explanation; Phase 5's circuit breaker is for the runtime path, not the flow)
  - `CommunicationError` → `errors={"base": "cannot_connect"}` (typo / network / Pronote down)
  - Any other `PronoteIntegrationError` → `errors={"base": "unknown"}`
- **D-05:** `ConfigEntry` unique_id format: `f"{url_host}:{username}:{child_identifier}"` where `url_host = urllib.parse.urlparse(url).hostname.lower()`. Set via `await self.async_set_unique_id(...)` before entry creation; `_abort_if_unique_id_configured()` rejects the second add of the same child. AUTH-03 (parent with multiple children) creates *different* unique_ids per child, so re-running the flow with a different `child_index` adds a new entry cleanly.

### Token persistence trigger (Area 2)
- **D-06:** `client.export_credentials()` is called **after every successful poll** in `coordinator._async_update_data` (executor-wrapped). On success the coordinator updates `entry.data["session"]` via `self.hass.config_entries.async_update_entry(self.config_entry, data={**entry.data, "session": new_session})`. HA's storage layer debounces the flush — the disk-write cost is negligible. This ensures: if Pronote rotates the session token, we capture the rotation; the AUTH-04 "one login per lifetime" contract holds even under rotation; restart-after-rotation uses fresh stored creds.
- **D-07:** `async_setup_entry` restart strategy: read `entry.data.get("session")`. If present → call `pronotepy.Client.token_login(url, username, **session_dict)` (executor-wrapped) inside an `api/client.py` helper. On `AuthError` → fall back to `pronotepy.Client(url, username=username, password=password)` (executor-wrapped). On success of the fallback → immediately capture the new `export_credentials()` and write to `entry.data["session"]` so the next restart hits the fast path. On failure of *both* paths → raise `ConfigEntryAuthFailed` (HA fires reauth — Phase 6's owner; until Phase 6 ships, the entry visibly fails with a clear error).
- **D-08:** Storage shape — `entry.data` keys after Phase 3:
  - `url: str` (the Pronote space URL the user entered)
  - `account_type: Literal["eleve","parent"]`
  - `username: str`
  - `password: str` (kept for the AUTH-04 fallback path; Phase 7 diagnostics redacts it; "drop after first token_login" was rejected because it breaks the silent-recovery branch)
  - `session: dict[str, Any]` (opaque pronotepy-owned blob from `export_credentials()`; treated as transparent — no introspection)
  - `child_identifier: str` (frozen child id derived at flow time per D-15)
  - `child_index: int | None` (the integer index pronotepy needs for `set_child(idx)`; `None` for eleve)
  - `child_name: str` (the original pronotepy `name` so DeviceInfo.name can use it without re-fetching)
- **D-09:** Mid-poll session-expired recovery: when the coordinator catches `AuthError` from `fetcher.fetch_all`, the api/coordinator path attempts a single fresh re-login (`Client(url, username, password)` in executor) with the stored password; on success, capture the new `export_credentials()`, replace `entry.data["session"]`, and retry the original fetch once; on failure of either step, raise `ConfigEntryAuthFailed`. This is the silent-recovery branch — the user sees no reauth UI for a routine Pronote session rotation.

### child_identifier source (ENT-02 freeze, Area 3)
- **D-10:** `child_identifier` source: `slugify(name)` via `python-slugify` (already declared in `manifest.json` requirements per Phase 1 D-14). For eleve account → `slugify(client.info.name)`. For parent account → `slugify(client.children[child_index].name)`. Readable in HA entity_ids (e.g. `sensor.pronote_jean_dupont_lessons_today`).
- **D-11:** **Frozen at flow time, never re-derived.** The slug is computed once in `async_step_user` (or `async_step_pick_child`) and stored in `entry.data["child_identifier"]`. Coordinator and sensor read from there — they never call `slugify(client.info.name)` against the live pronotepy data. ENT-02's "frozen v1, never altered by nickname" is enforced literally: a Pronote-side name change (typo fix, married-name change) updates `DeviceInfo.name` (display) but never `unique_id` (entity history preserved).
- **D-12:** Collision handling: in `async_set_unique_id` precheck, if the slug would collide with another existing entry's `child_identifier` within the same HA install (different parent account, same child name), append a 2-char hex suffix derived from the first 2 hex chars of `pronotepy.children[child_index].identifier` — e.g. `jean_dupont_a3`. Caught at flow time so the user sees the final entity name in the confirmation step before commit. Edge case for twins / blended families.
- **D-13:** Sensor `unique_id` format (frozen): `f"pronote_{child_identifier}_lessons_today"`. Generally `f"pronote_{child_identifier}_{sensor_kind}"`. The `sensor_kind` strings get added as Phase 4 ships more sensors (`grades`, `notifications`, `calendar`) — Phase 3 only locks `lessons_today`.

### Sensor design (TIME-01, Area 4)
- **D-14:** Phase 3 ships **state-only** — `native_value = len(coordinator.data.lessons_today)`. NO `extra_state_attributes`. Phase 4 adds J / J+1 attributes (TIME-02) as a deliberate add, not a refactor.
- **D-15:** Class hierarchy:
  - `PronoteEntity(CoordinatorEntity[PronoteDataUpdateCoordinator])` base in `custom_components/ha_pronote/entity.py` (NEW, or co-located in `sensor.py` if the planner prefers single-file in Phase 3) — owns `_attr_has_entity_name = True`, `device_info` property reading from `runtime_data`, `available` reading from coordinator's `last_update_success`. Phase 4 subclasses this base for `PronoteGradesSensor`, `PronoteNotificationsSensor`, `PronoteCalendar`.
  - `PronoteLessonsTodaySensor(PronoteEntity, SensorEntity)` — declares `_attr_translation_key = "lessons_today"`, `_attr_icon = "mdi:school"`, `_attr_state_class = SensorStateClass.MEASUREMENT`, `_attr_native_unit_of_measurement = "lessons"`. `native_value` returns the count.
- **D-16:** Sensor metadata: `state_class = SensorStateClass.MEASUREMENT` (graphable in long-term statistics). NO `device_class` (no fitting `SensorDeviceClass`). `icon = "mdi:school"`. Unit of measurement: `"lessons"` — translation_key drives the display string (`"cours"` in fr).
- **D-17:** Device shape: `DeviceInfo(identifiers={(DOMAIN, child_identifier)}, name=entry.data["child_name"], manufacturer="Pronote")`. **NO `model` field** — ROADMAP Phase 4 success criterion #2 explicitly says `model=<class level>` lands in Phase 4. **NO `sw_version`, NO `configuration_url`** in Phase 3.
- **D-18:** AUTH-07 Pronote-side device label = `home-assistant-{entry_id[:8]}` is passed to `pronotepy.Client` (or `ParentClient`) constructor as the `device_name` kwarg in `api/client.py:build_client(...)`. This label appears in the user's Pronote app under "connected devices" and is how they'd manually revoke the integration's session. Distinct from HA's `DeviceInfo.name` (which is the *child's* name shown in HA).

### Cross-cutting (Coordinator, runtime_data, error mapping)
- **D-19:** `coordinator.py` subclasses `homeassistant.helpers.update_coordinator.TimestampDataUpdateCoordinator` (NOT plain `DataUpdateCoordinator`) — gives `last_update_success_time` for free, used by Phase 4's diff layer ("EDT changed since last poll" payload). Confirmed by `delphiki/hass-pronote/coordinator.py` and CLAUDE.md/SUMMARY.md "TimestampDataUpdateCoordinator subclass" recommendation.
- **D-20:** Coordinator data shape: `coordinator.data: Snapshot` directly (the `Snapshot` dataclass from `api/models.py`). NOT wrapped in another typed layer. Sensor reads `self.coordinator.data.lessons_today` directly. Phase 4's diff layer reads `self.coordinator.data` + the *previous* snapshot which the coordinator stashes on `self._previous_snapshot` (or similar) for the diff comparison — Phase 3 just exposes the current Snapshot; the previous-snapshot bookkeeping lands in Phase 4 alongside the diff trigger.
- **D-21:** `runtime_data` shape — `PronoteData` dataclass in `data.py`:
  ```python
  @dataclass
  class PronoteData:
      coordinator: PronoteDataUpdateCoordinator
      client: pronotepy.Client | pronotepy.ParentClient   # live, between polls
      child_identifier: str
      child_index: int | None
      school_tz: ZoneInfo
  type PronoteConfigEntry = ConfigEntry[PronoteData]
  ```
  The live `client` is held so the coordinator can call `client.export_credentials()` and (in Phase 4) reuse it across polls without rebuilding. Phase 5 may grow the dataclass for circuit-breaker state.
- **D-22:** Coordinator error mapping (locks the contract Phase 5/6 build on):
  - `AuthError` → `raise ConfigEntryAuthFailed` (HA fires reauth — Phase 6 ships the flow; Phase 3 just raises so the entry visibly auths-failed)
  - `RateLimitedError(IP_SUSPENDED)` → `raise UpdateFailed` with the literal pronotepy message (Phase 5 inspects `.reason` to enter long-backoff; Phase 3 just propagates so the integration stays alive but stale)
  - `CommunicationError` / any other `PronoteIntegrationError` → `raise UpdateFailed`
  - First refresh in `async_setup_entry` uses `coordinator.async_config_entry_first_refresh()` so a setup-time auth fail aborts setup cleanly (the right HA pattern for cloud-polling integrations).
- **D-23:** `school_tz` resolution in Phase 3 = `ZoneInfo(const.DEFAULT_SCHOOL_TZ)` (i.e. `Pacific/Noumea`). Phase 6 OPT-04 lets the user override per entry. Coordinator passes `today=dt_util.now(self._school_tz).date(), school_tz=self._school_tz` into `fetch_all(...)` on each poll (Phase 2 D-17/D-18 keep `api/` pure; coordinator owns the `dt_util` call).
- **D-24:** Hardcoded Phase 3 polling: `update_interval = timedelta(minutes=30)`. Defined as `const.DEFAULT_REFRESH_INTERVAL` in `const.py` for Phase 6 to read. NO jitter, NO adaptive switching, NO quiet hours (Phase 5).
- **D-25:** Platform forwarding in `__init__.py:async_setup_entry`: `await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])`. Phase 4 will add `Platform.CALENDAR`. `const.py:PLATFORMS = (Platform.SENSOR,)`.
- **D-26:** `async_migrate_entry` skeleton: `async def async_migrate_entry(hass, entry) -> bool: return True`. Comment notes "Phase 6+ fills the body when entry shapes change." `entry.version = 1` for v1.

### Claude's Discretion
The user delegated these sub-decisions to the planner. Recommended defaults to apply unless the planner finds a stronger argument:

- **C-01:** Whether to put `PronoteEntity` in a new `entity.py` or co-locate in `sensor.py` (D-15) — RECOMMEND `entity.py` (single source of truth that Phase 4's `calendar.py` imports without circular dep risk). Cost: one extra file, ~25 LOC.
- **C-02:** How to expose the `token_login_or_build` helper (D-07) — RECOMMEND a single `api/client.py:build_or_resume_client(url, account_type, username, password, session)` function that internally tries `token_login` first then falls back to fresh login. Coordinator and `async_setup_entry` both call it. Single seam for Phase 6 reauth to also reuse.
- **C-03:** Whether the coordinator captures the `previous_snapshot` already in Phase 3 (D-20) — RECOMMEND yes (`self._previous_snapshot: Snapshot | None = None` updated at end of each poll). Costs nothing in Phase 3 (no diff is fired) but Phase 4 just reads it. If the planner finds it cleaner to add in Phase 4, that's also fine.
- **C-04:** Where the `device_name` for AUTH-07 is stored — RECOMMEND derive on the fly in `api/client.py:build_or_resume_client` from `entry.entry_id[:8]`. The `entry_id` is stable across restarts, so the Pronote-side label stays the same. No `entry.data` slot needed.
- **C-05:** Mock strategy for HA-side tests (`tests/test_config_flow.py`, `tests/test_coordinator.py`) — RECOMMEND `MagicMock` of `pronotepy.Client` / `pronotepy.ParentClient` rather than `requests-mock` at the HTTP layer. The `requests-mock` strategy stays for `tests/test_api/` (pure-python). HA-side tests should patch `custom_components.ha_pronote.api.client.build_or_resume_client` to return the mock client. Faster + decouples HA-side tests from pronotepy internal HTTP shape.
- **C-06:** Plan decomposition / wave structure — RECOMMEND 4 plans across 3 waves: Wave 1 = (data.py + coordinator.py + __init__.py wiring) ‖ (config_flow.py + strings.json); Wave 2 = (sensor.py + entity.py); Wave 3 = (full HA-side test suite). Planner may prefer a different cut — e.g. a single ConfigFlow-first wave to land the auth path before the runtime, then a coordinator wave, then a sensor+test wave. The dependency that matters: ConfigFlow can land before coordinator if `async_setup_entry` raises `ConfigEntryNotReady` until the coordinator ships, but it's tighter to ship them in one wave.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Core value, "From scratch (not fork)", "Pronote direct only in v1 (no ENT)", "Polling adaptatif fin de journée", session-reuse / no-IP-ban discipline
- `.planning/REQUIREMENTS.md` — Phase 3 covers AUTH-01, AUTH-02, AUTH-04, AUTH-07, COORD-01, COORD-02, TIME-01, ENT-02, ENT-03, ENT-04 (10 requirements). Cross-cutting trackers: AUTH-03 (multi-child UX, Phase 6 owner — Phase 3 supports it via the pick_child step), AUTH-05 (reauth flow, Phase 6), AUTH-06 (reconfigure flow, Phase 6), COORD-03 (Options Flow refresh interval, Phase 6 — Phase 3 hardcodes the default), COORD-04..09 (politesse, Phase 5)
- `.planning/ROADMAP.md` §"Phase 3: Coordinator & First Sensor" — Goal, 4 success criteria, "depends on Phase 2" gate, cross-cutting invariants in ROADMAP Overview (executor wrap, tz-aware via dt_util, PronoteIntegrationError(reason=...) hierarchy, sensor size limits enforced on heavy-class fixture (Phase 4), Paris+Noumea pytest matrix carrying forward from Phase 2)
- `CLAUDE.md` — Tech stack (Python 3.14.2, HA 2026.4+, pronotepy 2.14.6 EXACT pin, ruff/pyright/uv); the "What NOT to Use" table is binding (NO `async_timeout`, NO `pytz`, NO direct `requests` outside pronotepy, NO `pronotepy.ent.*`, NO monkey-patching, NO hardcoded URL); cross-cutting invariants (executor boundary, tz-aware via dt_util, typed error hierarchy)

### Prior phase context
- `.planning/phases/01-foundations-skeleton/01-CONTEXT.md` — Phase 1 decisions still binding in Phase 3:
  - **D-01:** `domain = "ha_pronote"` (frozen)
  - **D-02 [informational]:** `unique_id` pattern `pronote_{child_identifier}_{sensor_kind}` (Phase 3 implements; ENT-02)
  - **D-12:** `iot_class: "cloud_polling"` — Phase 3 must respect HA's polling semantics
  - **D-13:** `quality_scale: "bronze"` — Phase 3 must satisfy Bronze (handled-failure, async-only, etc.)
  - **D-14:** `pronotepy==2.14.6` exact pin, `python-slugify==8.0.4` (Phase 3 *uses* slugify for D-10)
  - **D-15:** `integration_type: "hub"` — Phase 3 ships the per-child entry pattern this declares
  - **D-16:** `config_flow: true` — Phase 3 fills the placeholder
  - **D-30..D-35:** anti-pattern hard locks (no async_timeout, no pytz, no direct requests, no pronotepy.ent, no hardcoded URL, no monkey-patching) — every one applies in Phase 3
  - **D-29:** `pytest-homeassistant-custom-component` already wired with `asyncio_mode = "auto"` — Phase 3 HA-side tests use the `hass` fixture + `MockConfigEntry` directly
- `.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md` — Phase 2 decisions still binding in Phase 3:
  - **D-15..D-18:** `api/fetcher.fetch_all(client, today, school_tz, child_index_or_identifier)` signature is the contract Phase 3's coordinator calls — DO NOT modify the signature in Phase 3. `today` and `school_tz` injected (no `dt_util` in `api/`).
  - **D-19, D-20:** Zero `homeassistant.*` imports in `api/` or `diff/` — `tests/test_no_ha_imports.py` already enforces. Phase 3's coordinator/sensor/config_flow IS allowed to import HA, of course.
  - **D-21:** `api/client.py:build_client(url, account_type, username, password)` returns `pronotepy.Client | pronotepy.ParentClient`. Child selection (`set_child(...)`) lives in `api/fetcher.py`'s `child_index_or_identifier` parameter — Phase 3's coordinator passes the stored `entry.data["child_index"]` on each poll. NO `pronotepy.ent.*`.
  - **D-22:** Typed error hierarchy in `api/errors.py` (AuthError / RateLimitedError / CommunicationError / ParseError, ErrorReason StrEnum) — Phase 3 maps these to ConfigEntryAuthFailed / UpdateFailed (D-22 of *this* CONTEXT.md).
  - **D-23, D-24:** All datetimes tz-aware (TIME-04 satisfied by Phase 2's localize-at-fetch); pronotepy back-refs already stripped — Phase 3 doesn't touch the wire format.
  - **D-25:** Pytest matrix `Europe/Paris` + `Pacific/Noumea` carries into Phase 3 — HA-side tests parameterize over both axes when datetime-sensitive.
- `.planning/phases/01-foundations-skeleton/01-PLAN.md` and `01-{01..05}-PLAN.md` — Phase 1 plans for surrounding-file context (the actual `manifest.json`, `pyproject.toml`, `tests/conftest.py` Phase 3 will extend live there)
- `.planning/phases/02-api-diff-layer-ha-free/02-{01..04}-PLAN.md` — Phase 2 plans for the api/ + diff/ surface Phase 3 consumes; especially `02-01-api-skeleton-and-spike-tooling-PLAN.md` (api/ shape) and `02-02-real-pronote-spike-PLAN.md` (anonymized fixtures Phase 3 HA-side tests can reuse)

### Research already done
- `.planning/research/STACK.md` — Why `TimestampDataUpdateCoordinator` (D-19), why `runtime_data` over `hass.data[DOMAIN]` (D-21), why `requests-mock` at the api/ layer + MagicMock at the HA-side layer
- `.planning/research/ARCHITECTURE.md` — **Critical for Phase 3 planning:**
  - §"Recommended Project Structure" — `custom_components/ha_pronote/{__init__,coordinator,data,config_flow,sensor,entity,const}.py` exact layout
  - §"Pattern 1" — sync library + `async_add_executor_job` (Phase 3's executor boundary)
  - §"Pattern 6" — `runtime_data` not `hass.data[DOMAIN]` (D-21)
  - §"Pattern 7" — `TimestampDataUpdateCoordinator` subclass (D-19)
  - §"Pattern 8" — single-step `async_step_user` for cloud-polling integrations with auth (D-01)
  - §"Suggested Build Order — Phase C (coordinator) and Phase E (config_flow + sensor)" — directly maps to Phase 3 plan slices
  - §"Anti-Pattern 1" (executor wrap), §"Anti-Pattern 5" (no pronotepy refs leaking out — Phase 2 already prevented in `api/`; Phase 3 must not re-introduce them in `coordinator.py` data dict)
  - §"Anti-Pattern 7" (storing the `client` in `coordinator.data` — RECOMMENDED in `runtime_data` instead per D-21)
- `.planning/research/PITFALLS.md` — **Critical for Phase 3 planning:**
  - §"Pitfall 1" (IP suspension) — Phase 3 propagates `RateLimitedError(IP_SUSPENDED)` as `UpdateFailed`; long-backoff is Phase 5's job
  - §"Pitfall 2" (pronotepy breakage) — Phase 3 maps every typed exception path
  - §"Pitfall 3" (blocking calls) — every pronotepy call in Phase 3 goes through `hass.async_add_executor_job` (COORD-02 enforcement)
  - §"Pitfall 4" (timezone NC) — Phase 3 sources `school_tz` from `const.DEFAULT_SCHOOL_TZ`, passes to `fetch_all`. PHACC tests parameterize across `Europe/Paris` + `Pacific/Noumea` axes for any datetime-sensitive test.
  - §"Pitfall 5" (session reuse) — Phase 3's D-06 / D-07 / D-09 directly implement the "one login per lifetime" recipe
  - §"Pitfall 6" (config-flow blocking IO) — `build_or_resume_client` in `async_step_user` is executor-wrapped (D-01)
  - §"Pitfall 7" (multi-child / set_child)— Phase 3's `async_step_pick_child` (D-02) implements the recipe; `child_index` stored in entry.data (D-08)
  - §"Pitfall 8" (unique_id stability) — Phase 3's D-10 / D-11 / D-13 are the literal mitigation — `child_identifier` captured once at flow time, never re-derived
  - §"Pitfall 9" (entity rename on Pronote name change) — D-11 enforces capture-once semantics; DeviceInfo.name updates display while unique_id stays frozen
- `.planning/research/FEATURES.md` §"Cloud-polling Config Flow with reauth + reconfigure" — locks the form-shape grammar Phase 3 starts (Phase 6 finishes); §"Numeric overall_average sensor" (Phase 4 — Phase 3 establishes the entity hierarchy)
- `.planning/research/SUMMARY.md` — High-level synthesis (read once for orientation)

### External references (URL — no local copy)
- `delphiki/HomeAssistant-Pronote/coordinator.py` — reference implementation:
  - 26 `async_add_executor_job` call sites (Phase 3's coordinator should match the pattern even if the call count differs — fewer for Phase 3, full count by Phase 4)
  - The export_credentials capture-on-success pattern is delphiki's; Phase 3 reuses the *idea*, not the literal code (delphiki uses `hass.data[DOMAIN]` legacy; we use `runtime_data`)
  - The auth-fail → ConfigEntryAuthFailed mapping is delphiki's
- `delphiki/HomeAssistant-Pronote/config_flow.py` — reference implementation:
  - Single-step async_step_user shape (D-01 mirrors)
  - Multi-child handling — delphiki picks first child silently; Phase 3 explicitly improves with `async_step_pick_child` (D-02)
- `bain3/pronotepy/clients.py` — `Client.__init__(url, username, password, **kwargs)` and `Client.token_login(url, username, **session)` and `ParentClient.set_child(...)` and `Client.export_credentials()` and `Client(..., device_name=...)` kwarg surface — Phase 3 wraps these via `api/client.py`. Source: `https://github.com/bain3/pronotepy/blob/main/pronotepy/clients.py`
- HA Developer Docs §"Integration Quality Scale: Bronze" — `https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/` — Phase 3 must satisfy Bronze (handled-failure on auth, async-only, no blocking I/O, has-tests). Phase 7 chases Silver.
- HA Developer Docs §"Config Flow" — `https://developers.home-assistant.io/docs/config_entries_config_flow_handler/` — async_step_user, async_set_unique_id, _abort_if_unique_id_configured, errors dict shape, async_show_form
- HA Developer Docs §"DataUpdateCoordinator" — `https://developers.home-assistant.io/docs/integration_fetching_data` — coordinator pattern, async_config_entry_first_refresh, UpdateFailed
- HA Developer Docs §"DeviceInfo" — `https://developers.home-assistant.io/docs/device_registry_index/` — identifiers, manufacturer, model, has_entity_name + translation_key

### Phase 1 / Phase 2 shipped code (relevant Phase 3 reads)
- `custom_components/ha_pronote/__init__.py` — Phase 1 no-op stub. Phase 3 REPLACES with real `async_setup_entry`/`async_unload_entry`/`async_migrate_entry`.
- `custom_components/ha_pronote/const.py` — Phase 1 + Phase 2 contributions: `DOMAIN`, `DEFAULT_SCHOOL_TZ`, `DEFAULT_LOOKBACK_DAYS`, `DEFAULT_LOOKAHEAD_DAYS`. Phase 3 APPENDS `DEFAULT_REFRESH_INTERVAL = timedelta(minutes=30)`, `PLATFORMS = (Platform.SENSOR,)`.
- `custom_components/ha_pronote/manifest.json` — Phase 1 declares `pronotepy==2.14.6`, `python-slugify==8.0.4`, `iot_class: "cloud_polling"`, `quality_scale: "bronze"`, `integration_type: "hub"`, `config_flow: true`, `version: "0.0.1"`. Phase 3 does NOT modify (unless hassfest demands).
- `custom_components/ha_pronote/config_flow.py` — Phase 1 placeholder (`async_step_user` aborts with `not_implemented`). Phase 3 REPLACES with real flow.
- `custom_components/ha_pronote/strings.json` — Phase 1 minimal. Phase 3 EXTENDS with config-flow data labels, error keys (`invalid_auth`, `cannot_connect`, `ip_suspended`, `unknown`), abort keys (`already_configured`, `not_implemented` removed), and the `lessons_today` sensor translation_key.
- `custom_components/ha_pronote/api/__init__.py`, `api/client.py`, `api/fetcher.py`, `api/models.py`, `api/errors.py`, `api/_strip.py` — Phase 2 shipped surface. Phase 3 may EXTEND `api/client.py` with `build_or_resume_client(url, account_type, username, password, session)` (per C-02) but does NOT change Phase 2's existing functions.
- `custom_components/ha_pronote/diff/{events,lessons,grades,notifications}.py` — Phase 2 shipped surface. Phase 3 IMPORTS the types but does NOT call `diff_lessons` (Phase 4 ships the firing).
- `tests/conftest.py` — Phase 1 PHACC autouse fixture wiring. Phase 3 may EXTEND with HA-side fixtures (`mock_pronote_client`, `mock_config_entry`).
- `tests/test_init.py`, `tests/test_manifest.py`, `tests/test_no_ha_imports.py`, `tests/test_fixtures.py` — Phase 1+2 already shipped. Phase 3 EXTENDS `tests/test_init.py` with real `async_setup_entry` happy path; does NOT modify the others.
- `pyproject.toml`, `requirements_test.txt`, `.github/workflows/test.yml` — Phase 1+2 shipped surface. Phase 3 likely does NOT modify (PHACC already pulls everything Phase 3 needs).

### SPEC.md
None — `/gsd-spec-phase` was not run for Phase 3. Requirements live in REQUIREMENTS.md (10 reqs listed above) and ROADMAP.md success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **From Phase 2 (api/ shipped surface):**
  - `api/client.py:build_client(url, account_type, username, password)` returns `pronotepy.Client | pronotepy.ParentClient`. Phase 3 wraps in executor; extends with `build_or_resume_client(...)` (C-02) that takes optional session dict.
  - `api/fetcher.py:fetch_all(client, today, school_tz, child_index_or_identifier=None) -> Snapshot`. Phase 3 coordinator calls this on every poll. Signature LOCKED.
  - `api/errors.py:{AuthError, RateLimitedError, CommunicationError, ParseError, PronoteIntegrationError, ErrorReason}` — Phase 3's coordinator/setup map AuthError → ConfigEntryAuthFailed, all others → UpdateFailed (with optional ip_suspended-aware messaging).
  - `api/models.py:Snapshot` — has `.lessons_today` and `.lessons_tomorrow` slice properties (D-16 of Phase 2). Sensor reads `snapshot.lessons_today` directly.
- **From Phase 1 (skeleton):**
  - `const.py:DOMAIN = "ha_pronote"` — Phase 3 imports.
  - `manifest.json` already declares `python-slugify==8.0.4` — Phase 3 imports `slugify` for D-10.
  - `tests/conftest.py` PHACC autouse + `enable_custom_integrations` — Phase 3 HA-side tests (`tests/test_config_flow.py`, `tests/test_coordinator.py`, `tests/test_sensor.py`) use the `hass` fixture and `MockConfigEntry` directly.
  - `pyproject.toml` `[tool.pytest.ini_options]` `asyncio_mode = "auto"` already set (Phase 1 D-29).

### Established Patterns
- **From Phase 1 / Phase 2:**
  - Exact-pin discipline on `pronotepy==2.14.6` (Phase 1 D-14) — Phase 3 doesn't touch.
  - All planner-level reads of CLAUDE.md "What NOT to Use" before any tooling call (Phase 1 / Phase 2 set the precedent).
  - Frozen `@dataclass(frozen=True)` for value types (Phase 2 `api/models.py`, `diff/events.py`) — Phase 3's `PronoteData` is mutable (holds the live `client` between polls), so use plain `@dataclass`.
  - tz-aware datetime everywhere via `zoneinfo.ZoneInfo` (Phase 2 D-23) — Phase 3's `dt_util.now(school_tz)` mirrors at the HA layer.
- **External patterns to mirror (idea, not code):**
  - `delphiki/HomeAssistant-Pronote/coordinator.py` — `_async_update_data` shape: executor fetch → diff → bus fire → store. Phase 3 implements the executor fetch + store; Phase 4 adds the diff + fire.
  - `delphiki/HomeAssistant-Pronote/config_flow.py` — single-step async_step_user; Phase 3 improves with explicit pick_child step.
  - `pronotepy/clients.py` — `Client.token_login(url, username, **session_dict)` and `Client(url, username=..., password=..., device_name=...)` — Phase 3's `build_or_resume_client` calls these.

### Integration Points
- **Phase 3 → Phase 4 interface:**
  - `coordinator.data: Snapshot` and `coordinator._previous_snapshot: Snapshot | None` (per C-03) — Phase 4's diff layer reads both, computes `LessonChange` events, fires `pronote_schedule_changed` via `hass.bus.async_fire`.
  - `PronoteEntity` base class (D-15) — Phase 4 subclasses for `PronoteGradesSensor`, `PronoteNotificationsSensor`, `PronoteCalendar`.
  - `runtime_data: PronoteData` (D-21) — Phase 4 may extend the dataclass with diff-state fields (last_fired_event_ids, etc.).
- **Phase 3 → Phase 5 interface:**
  - `coordinator.update_interval` (D-24) — Phase 5 mutates this on each poll based on `compute_interval(now, options)`.
  - `RateLimitedError(IP_SUSPENDED)` mapping (D-22) — Phase 5's circuit breaker reads `.reason` to enter long-backoff.
  - `runtime_data: PronoteData` — Phase 5 may grow with `circuit_breaker_state`.
- **Phase 3 → Phase 6 interface:**
  - `entry.data` shape (D-08) — Phase 6's reauth flow updates `entry.data["password"]` + `entry.data["session"]` (cleared so token_login re-runs); reconfigure flow updates `entry.data["url"]` / `entry.data["account_type"]` while preserving `entry.data["child_identifier"]`.
  - `async_migrate_entry` skeleton (D-26) — Phase 6 fills the body for any data-shape changes.
  - The Phase 3 `async_step_pick_child` already implements AUTH-03 effectively; Phase 6 adds reconfigure UX, multi-child auth-fail isolation tests, and OptionsFlow (refresh_interval, nickname, school_tz, adaptive toggle).
- **Phase 3 → Phase 7 interface:**
  - `entry.data` keys (D-08) — Phase 7's `async_get_config_entry_diagnostics` redacts `password`, `session`, `username` per DIAG-01.
  - `PronoteIntegrationError(reason=...)` propagation — Phase 7's repair issues key on `.reason` to render the right user-facing card (DIAG-02 / DIAG-03).

</code_context>

<specifics>
## Specific Ideas

- The author's real Pronote instance is `katiramona.ac-noumea.nc` (PROJECT.md context). The first end-to-end UAT for Phase 3 will be: "user enters that URL + parent credentials + picks the one child + sees `sensor.pronote_<slug>_lessons_today` populate within 30 min". Anonymized fixtures from Phase 2's spike (`tests/fixtures/real/cancellation_T0.json` etc.) can drive the HA-side tests via mocked pronotepy clients — no need to recapture.
- "EDT" stays the user-facing French term in `strings.json` translations; the API surface (entity_id, sensor_kind) uses English (`lessons_today`).
- The Pronote-side device label `home-assistant-{entry_id[:8]}` (AUTH-07) is what the user sees in their Pronote app's "connected devices" list — meaningful enough to recognize, opaque enough to be safe to show on someone else's screen.
- Token persistence is a SECURITY surface as much as a UX one — `entry.data["session"]` and `entry.data["password"]` are stored in HA's `.storage/core.config_entries` plain JSON file; HA encrypts the storage layer at rest in some setups but not all. Phase 7's diagnostics redaction is the user-visible mitigation; Phase 3 just stores carefully (no logging of credentials, no echoing in repr).
- Phase 3's "first end-to-end" is the integration's first real proof of life — every subsequent phase rests on this loop being clean. If anything in the executor boundary, runtime_data plumbing, or token persistence is wrong, every phase after compounds the bug. Plan accordingly: HA-side tests for Phase 3 should be more thorough than Phase 4+ proportionally.

</specifics>

<deferred>
## Deferred Ideas

These came up during the discussion but belong in later phases or post-v1:

- **Reauth flow (`async_step_reauth`)** — Phase 6 (AUTH-05). Phase 3 raises `ConfigEntryAuthFailed` when both token_login and fresh-login fail; HA shows the entry as needing attention but Phase 6 ships the actual reauth UX.
- **Reconfigure flow (`async_step_reconfigure`)** — Phase 6 (AUTH-06). Phase 3 stores `entry.data` keys in a shape that preserves `child_identifier` across reconfigure (D-08); Phase 6 implements the flow.
- **Options Flow (`async_step_init` / `async_step_user`)** — Phase 6 (OPT-01..04). Phase 3 hardcodes `update_interval = 30 min` and `school_tz = Pacific/Noumea`; Phase 6 makes both editable.
- **Adaptive 17h–20h polling, weekend / vacation suspension, jitter, circuit breaker, IP-ban long-backoff** — Phase 5 (COORD-04..09, DIST-06).
- **`pronote_schedule_changed` / `pronote_new_grade` / `pronote_new_information` bus events** — Phase 4. Phase 3 produces no events.
- **TIME-02 / TIME-03 J + J+1 attributes on the lessons sensor + 16 KiB enforcement on heavy-class fixture** — Phase 4. Phase 3 ships state-only.
- **Grades sensor (GRADE-01..03), Notifications sensor (NOTIF-01..02), Calendar entity (CAL-01..02)** — Phase 4.
- **DeviceInfo.model = `<class level>`** — Phase 4 (ROADMAP success criterion #2 explicitly).
- **Diagnostics platform (DIAG-01)** — Phase 7. Phase 3 stores credentials carefully but ships no redactor.
- **Repair Issues (DIAG-02, DIAG-03)** — Phase 7.
- **Translations (`fr.json`, `en.json` complete)** — Phase 7. Phase 3 ships `strings.json` only, with all keys present so Phase 7's translation work is mechanical.
- **Daily cron CI against `pronotepy@main`** — Phase 7 (DIST-04).
- **Dropping `entry.data["password"]` after first successful token_login** — explicitly rejected for Phase 3 because it breaks the silent-recovery branch (D-09). Reconsider in Phase 7 alongside diagnostics redaction.
- **Pre-emptive child-select nickname field at flow time** — explicitly rejected (scope creeps Phase 6 OPT-03 nickname into Phase 3). Phase 3 uses raw slugified name; Phase 6 OPT-03 adds editable nickname WITHOUT touching unique_id.
- **Pronotepy upgrade beyond 2.14.6** — only when a real bug forces it (Phase 2 D-anchor); Phase 3 commits to 2.14.6 as the spike-validated version.
- **HEAD probe before auth in Config Flow** — explicitly rejected (D-03); pronotepy's connect failure is enough signal.

</deferred>

---

*Phase: 3-Coordinator & First Sensor*
*Context gathered: 2026-05-06*
