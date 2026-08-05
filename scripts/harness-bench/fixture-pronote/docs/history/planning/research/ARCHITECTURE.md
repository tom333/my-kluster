# Architecture Research

**Domain:** Home Assistant custom_component integrating a third-party scraping library (`pronotepy`) for Pronote (French school management system)
**Researched:** 2026-05-03
**Confidence:** HIGH

Sources verified against the official Home Assistant developer documentation,
the canonical `ludeeus/integration_blueprint` template, and the existing
`delphiki/hass-pronote` integration (which already wraps `pronotepy` in a HA
coordinator and is a near-direct prior art for our scope).

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Home Assistant Core (asyncio)                  │
│                                                                      │
│  ┌────────────────────┐     ┌──────────────────────────────────┐     │
│  │   Config Flow      │────▶│         Config Entry             │     │
│  │  (config_flow.py)  │     │  (UI-created, holds credentials  │     │
│  │  user / reauth /   │     │   + options for polling)         │     │
│  │  reconfigure /     │     └──────────────┬───────────────────┘     │
│  │  options           │                    │                         │
│  └────────────────────┘                    ▼                         │
│                                ┌──────────────────────────┐          │
│                                │   __init__.py            │          │
│                                │   async_setup_entry()    │          │
│                                │   builds runtime_data    │          │
│                                └──────┬───────────────────┘          │
│                                       │                              │
│                                       ▼                              │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │               PronoteDataUpdateCoordinator                 │      │
│  │               (coordinator.py — one per child)             │      │
│  │                                                            │      │
│  │  _async_update_data():                                     │      │
│  │    1. await async_add_executor_job(api.fetch_all)          │      │
│  │    2. diff vs self.data (previous snapshot)                │      │
│  │    3. emit hass.bus.async_fire(...) for each change        │      │
│  │    4. return new dict → CoordinatorEntity refresh          │      │
│  │                                                            │      │
│  │  _adjust_interval():  17h–20h ⇒ tighter; else default      │      │
│  └──────────────┬──────────────────────────────┬──────────────┘      │
│                 │ (sync, in thread executor)   │                     │
│                 ▼                              ▼                     │
│   ┌──────────────────────────┐    ┌──────────────────────────────┐   │
│   │  api/ (sync facade over  │    │     diff/ (pure functions)   │   │
│   │  pronotepy)              │    │  - lessons_diff(old, new)    │   │
│   │  - login()               │    │  - grades_diff(old, new)     │   │
│   │  - fetch_lessons(d)      │    │  - notifs_diff(old, new)     │   │
│   │  - fetch_grades()        │    │   → list of change events    │   │
│   │  - fetch_info()          │    └──────────────────────────────┘   │
│   │  - export_credentials()  │                                       │
│   │  Raises typed exceptions │                                       │
│   └──────────┬───────────────┘                                       │
│              │ blocking IO                                           │
│              ▼                                                       │
│   ┌──────────────────────────┐                                       │
│   │  pronotepy (3rd party)   │                                       │
│   │  sync, requests-based    │                                       │
│   └──────────────────────────┘                                       │
│                                                                      │
│  Coordinator output ─┬─▶ sensor.py    (CoordinatorEntity per data)   │
│                      ├─▶ binary_sensor (optional, e.g. "has change") │
│                      └─▶ HA event bus  (pronote_*, automations)      │
│                                                                      │
│  diagnostics.py ─▶ redacted dump for support tickets                 │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `manifest.json` | Declare domain, version, requirements (`pronotepy==X`), `iot_class=cloud_polling`, `config_flow=true`, codeowners, issue tracker | Static JSON, validated by HA + HACS |
| `hacs.json` (repo root) | Declare HACS metadata: `name`, minimum `homeassistant`, minimum `hacs`, `content_in_root=false`, `zip_release` (optional) | Static JSON at repo root |
| `__init__.py` | `async_setup_entry`, `async_unload_entry`, `async_reload_entry`, optional `async_migrate_entry` for schema bumps. Builds `runtime_data` dataclass and calls `coordinator.async_config_entry_first_refresh()` | Thin orchestration |
| `const.py` | `DOMAIN`, `PLATFORMS`, default polling intervals, event type names, config keys | Constants only |
| `data.py` (typed runtime) | `dataclass` holding `client`, `coordinator`, references; `type ConfigEntry[ProjectData]` alias | Modern HA pattern (post-2024.x) for `entry.runtime_data` |
| `api/` (sync) | All `pronotepy` calls; pure sync; typed exceptions (`AuthError`, `CommunicationError`, `ParseError`, `RateLimitedError`) | Plain Python, no HA imports — keeps it unit-testable in isolation |
| `coordinator.py` | One `DataUpdateCoordinator` subclass per child config entry. Owns adaptive interval, executor wrapping, diff computation, event firing, `ConfigEntryAuthFailed`/`UpdateFailed` translation | Inherits `DataUpdateCoordinator[CoordinatorData]` |
| `diff/` (pure) | Pure functions: `(old_snapshot, new_snapshot) -> list[ChangeEvent]` for lessons J/J+1, grades, notifs. No HA imports. | Plain dataclasses + functions |
| `entity.py` | Base `CoordinatorEntity` providing `device_info`, `attribution`, unique-id prefix shared by all platforms | One small class |
| `sensor.py`, `binary_sensor.py`, `calendar.py` (later) | One `async_setup_entry` per platform; declarative `EntityDescription` tuples; entity classes derive `coordinator.data[...]` lazily | Pure presentation |
| `config_flow.py` | `ConfigFlow` (user/reauth/reconfigure steps) + `OptionsFlow` (polling intervals, nickname, etc.) | One file, multi-step async methods |
| `diagnostics.py` | `async_get_config_entry_diagnostics` returning `async_redact_data(...)` of config + last coordinator snapshot | ~30 lines |
| `services.yaml` + service handlers in `__init__.py` | Optional: `pronote.refresh`, `pronote.refresh_all` for manual pulls | Registers `hass.services.async_register` |
| `strings.json` + `translations/{en,fr}.json` | UI strings for config flow & options | JSON, English `strings.json` is source of truth |

---

## Recommended Project Structure

```
ha-pronote/
├── README.md                                # User-facing install + config
├── hacs.json                                # HACS metadata (repo root)
├── pyproject.toml                           # uv project (dev deps, ruff, pytest)
├── uv.lock
├── .github/
│   └── workflows/
│       ├── validate.yml                     # hassfest + HACS validation
│       └── tests.yml                        # ruff + pytest + coverage
│
├── custom_components/
│   └── pronote/                             # = DOMAIN (matches manifest.json)
│       ├── __init__.py                      # async_setup_entry / unload / reload / migrate
│       ├── manifest.json                    # version, requirements=[pronotepy], iot_class
│       ├── const.py                         # DOMAIN, PLATFORMS, EVENT_TYPE_*, CONF_*, default intervals
│       ├── data.py                          # @dataclass PronoteData; ConfigEntry alias
│       ├── api/
│       │   ├── __init__.py                  # facade re-exports
│       │   ├── client.py                    # build pronotepy client (login, qr, parent/eleve)
│       │   ├── fetcher.py                   # high-level fetch_all() returning typed snapshot
│       │   ├── models.py                    # plain dataclasses: Lesson, Grade, Info, Snapshot
│       │   └── errors.py                    # AuthError, CommunicationError, ParseError, RateLimitedError
│       ├── diff/
│       │   ├── __init__.py
│       │   ├── lessons.py                   # diff_lessons(old, new, day) -> list[ChangeEvent]
│       │   ├── grades.py                    # diff_grades(old, new) -> list[NewGrade]
│       │   └── notifications.py             # diff_notifications(old, new) -> list[NewNotif]
│       ├── coordinator.py                   # PronoteDataUpdateCoordinator (executor + diff + events + adaptive interval)
│       ├── entity.py                        # PronoteBaseEntity (CoordinatorEntity)
│       ├── sensor.py                        # schedule, grades, notifications sensors
│       ├── binary_sensor.py                 # optional: "schedule changed today" flag
│       ├── config_flow.py                   # user / reauth / reconfigure / options
│       ├── diagnostics.py                   # redacted snapshot
│       ├── services.yaml                    # optional manual refresh service
│       ├── strings.json
│       └── translations/
│           ├── fr.json
│           └── en.json
│
└── tests/
    ├── conftest.py                          # pytest-homeassistant-custom-component fixtures
    ├── fixtures/
    │   ├── pronote_snapshot_T0.json         # baseline scrape
    │   ├── pronote_snapshot_T1_changed.json # for diff tests
    │   └── pronote_login_response.json
    ├── test_api/
    │   ├── test_client.py                   # mocks pronotepy
    │   └── test_fetcher.py
    ├── test_diff/
    │   ├── test_lessons_diff.py             # pure logic — fastest to write, highest value
    │   ├── test_grades_diff.py
    │   └── test_notifications_diff.py
    ├── test_coordinator.py                  # adaptive interval, executor wiring, event firing
    ├── test_config_flow.py                  # user/reauth/options
    ├── test_init.py                         # setup/unload/migrate
    └── test_diagnostics.py
```

### Structure Rationale

- **`custom_components/pronote/`** is mandatory and HACS-validated; the folder name MUST match `manifest.json`'s `domain`.
- **`api/` as a subpackage** (not a single `api.py`): isolates `pronotepy` so the rest of the integration imports our own typed dataclasses. Keeps coordinator readable, makes mocking trivial in tests, and gives a clean seam if we later swap the underlying lib.
- **`diff/` as a separate subpackage**: diff logic is the highest-value, most-tested code in this project (it's the source of the alerts that justify the integration's existence). It must be **pure Python with no HA imports** so it runs in plain pytest with millisecond test times. Coordinator imports and orchestrates; it does not implement diff.
- **`data.py` for runtime types**: aligns with the modern HA pattern (`entry.runtime_data` typed via `type ConfigEntry[YourData]` alias, used in `ludeeus/integration_blueprint`). Replaces the old `hass.data[DOMAIN][entry_id]` dictionary pattern (still seen in `delphiki/hass-pronote` but officially deprecated direction).
- **`hacs.json` at repo root, not inside `custom_components/`**: HACS scans the repo root.
- **`tests/` outside `custom_components/`**: the standard `pytest-homeassistant-custom-component` layout; HA hassfest validation does not look in `tests/`.

---

## Architectural Patterns

### Pattern 1: Sync library wrapped via `async_add_executor_job`

**What:** `pronotepy` is fully synchronous (built on `requests`). Every call MUST be marshalled to HA's executor thread pool — running it directly on the event loop would block all of Home Assistant.

**When to use:** Always, for every `pronotepy` method call (login, get_lessons, get_grades, session.close, export_credentials, ...).

**Trade-offs:**
- (+) Standard HA pattern, well-documented, supported by HA core.
- (+) Single shared executor — no need to manage our own thread pool.
- (−) One blocking call holds an executor thread for its duration; with multiple children polling concurrently, login storms could starve the pool. Mitigation: serialize logins per coordinator (one coordinator = one child = one inflight call at a time, which `DataUpdateCoordinator` already enforces).
- (−) `functools.partial` needed for kwargs (HA's `async_add_executor_job` only takes positional args).

**Decision:** Use the **default executor** (`hass.async_add_executor_job`). Do **NOT** spawn a dedicated `ThreadPoolExecutor` — `delphiki/hass-pronote` doesn't, the blueprint doesn't, and there's no evidence we need it for ≤5 children polling every 15–60 minutes.

**Example:**
```python
# coordinator.py
from functools import partial

async def _async_update_data(self) -> CoordinatorData:
    try:
        client = await self.hass.async_add_executor_job(
            partial(build_client, self.config_entry.data)
        )
        snapshot = await self.hass.async_add_executor_job(
            partial(fetch_all, client, today=date.today())
        )
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (CommunicationError, RateLimitedError) as err:
        raise UpdateFailed(str(err)) from err
    finally:
        await self.hass.async_add_executor_job(client.session.close)
    return snapshot
```

### Pattern 2: One coordinator per account (per child)

**What:** Each Pronote account = one HA `ConfigEntry` = one `DataUpdateCoordinator` instance. All sensors for a given child consume from that single coordinator. Multi-child families = multiple config entries, each independent.

**When to use:** Always, for this domain. Pronote credentials are per-account and the API surface is small enough that one coordinator can fetch lessons + grades + notifications in a single update cycle.

**Trade-offs:**
- (+) Simple mental model: one entry → one coordinator → many entities.
- (+) Each child polls independently; one child's auth failure doesn't break another's data.
- (+) HA's existing reload/unload/reauth machinery works per-entry without custom plumbing.
- (−) Single coordinator means lessons + grades + notifs share the same `update_interval`. Acceptable: the 30-minute default is appropriate for all three. If we ever needed independent intervals (e.g. notifs every 5 min, grades every hour) we'd split into multiple coordinators per entry — defer that decision.

**Rejected alternative:** "Multiple coordinators per entry, one per data type." Adds complexity (cross-coordinator coordination, separate auth state, separate session lifetime), and `delphiki/hass-pronote` ships in production with a single coordinator pulling everything. Don't pre-optimize.

### Pattern 3: Diff-as-pure-function, fired from coordinator

**What:** The coordinator stores `self.data` (the previous snapshot) automatically across runs. At each update, it compares old vs new via pure functions in `diff/`, then fires HA bus events for each detected change before returning the new snapshot.

**When to use:** Whenever a state change matters as an automation trigger, not just as an attribute update — i.e. lesson cancellations, new grades, new notifications. (Sensor state changes alone trigger `state_changed` events, but those are too noisy and structurally weak for our use case; users want a typed `pronote_schedule_changed` event with a clean payload.)

**Trade-offs:**
- (+) Diff logic is pure → trivially unit-testable with JSON fixtures, no HA in the loop.
- (+) Coordinator stays thin: orchestrates fetch, calls diff, fires events.
- (+) `delphiki/hass-pronote` validates this exact pattern in production (`compare_data` + `trigger_event` + `hass.bus.async_fire`).
- (−) Snapshot must be deep-copied or immutable to avoid mutation aliasing. Use plain dataclasses (frozen=True where possible).
- (−) On first run `previous_data` is `None` — must handle that and skip event emission for the first cycle.

**Example:**
```python
# coordinator.py (excerpt)
async def _async_update_data(self) -> Snapshot:
    previous: Snapshot | None = self.data  # HA stores it for us
    new = await self._fetch_snapshot()

    if previous is not None:
        for change in diff_lessons(previous.lessons_today, new.lessons_today, day="today"):
            self._fire_event(EVENT_SCHEDULE_CHANGED, change.to_payload())
        for change in diff_lessons(previous.lessons_tomorrow, new.lessons_tomorrow, day="tomorrow"):
            self._fire_event(EVENT_SCHEDULE_CHANGED, change.to_payload())
        for grade in diff_grades(previous.grades, new.grades):
            self._fire_event(EVENT_NEW_GRADE, grade.to_payload())

    return new

def _fire_event(self, event_type: str, payload: dict) -> None:
    self.hass.bus.async_fire(event_type, {
        "child_slug": self.child_slug,
        "child_name": self.child_name,
        "config_entry_id": self.config_entry.entry_id,
        **payload,
    })
```

**Event payload schema (suggested, stable across versions):**
```python
# pronote_schedule_changed
{
    "child_slug": "alice_dupont",
    "child_name": "Alice Dupont",
    "config_entry_id": "abc123",
    "change_type": "cancelled" | "modified" | "added",
    "day": "today" | "tomorrow",
    "lesson": {
        "subject": "Mathématiques",
        "teacher": "M. Martin",
        "room": "B204",
        "start": "2026-05-04T08:00:00+11:00",
        "end": "2026-05-04T09:00:00+11:00",
    },
    "previous": { ... } | None,  # only for "modified"
}
```

### Pattern 4: Adaptive `update_interval` mutated in-place

**What:** HA does not provide a first-class API for time-of-day-dependent polling. The accepted community pattern is to mutate `self.update_interval` from inside `_async_update_data()` (or via a separate `async_track_time_change` listener registered in `async_setup_entry`).

**When to use:** When polling cadence depends on conditions (time of day, last-update activity, day of week). Our case: tighten to 5–10 min between 17h–20h local time on weekdays to catch late J+1 schedule edits; relax to 30 min otherwise.

**Trade-offs:**
- (+) Direct mutation of `self.update_interval` is supported (the attribute is public and HA reads it on each cycle).
- (+) No new HA primitive needed; works on every supported HA version.
- (−) Not a documented API contract — confidence MEDIUM on long-term stability, but the pattern is widespread in core integrations.
- (−) Two implementation choices, with a clear winner:

**Option A (recommended):** Compute the next interval at the END of `_async_update_data()` based on current time. Single source of truth, deterministic, tested in pure pytest.

**Option B:** Register `async_track_time_change` listeners in `async_setup_entry` to flip the interval at 17h and 20h. Two sources of truth, harder to test, more moving parts.

**Decision:** **Option A.** Implement as a pure function `compute_interval(now: datetime, options: dict) -> timedelta` and call it at the end of `_async_update_data` and in `__init__`.

**Example:**
```python
# coordinator.py
def _compute_interval(self, now: datetime) -> timedelta:
    base = timedelta(minutes=self.options.refresh_interval)  # default 30
    if not self.options.adaptive_polling:
        return base
    # Weekday afternoons: tighter polling for J+1 changes
    if now.weekday() < 5 and 17 <= now.hour < 20:
        return timedelta(minutes=self.options.afternoon_interval)  # default 10
    return base

async def _async_update_data(self) -> Snapshot:
    snapshot = ...
    self.update_interval = self._compute_interval(dt_util.now())
    return snapshot
```

### Pattern 5: Politesse polling — circuit breaker on the API client

**What:** Belt-and-suspenders to prevent IP banning. The coordinator alone is not enough — if `pronotepy` itself raises rate-limit-shaped errors (HTTP 429, 503, repeated auth failures), the API client must enter a backoff state independently of the polling cadence.

**When to use:** Critical for this project. The school server is shared, fragile, and its admin can ban us with no recourse. Conservative defaults required.

**Implementation:**
- API client tracks consecutive failure count.
- After N=3 consecutive `CommunicationError`s, raise a typed `RateLimitedError` and skip the next M cycles (exponential backoff: 1× then 2× then 4× normal interval, capped at 4h).
- Coordinator surfaces this as `UpdateFailed` to HA; entities go to `unavailable` until backoff clears.
- Logged at WARNING level so users can see it in the HA log without DEBUG.

**Trade-offs:**
- (+) Defense in depth: even a misconfigured 1-minute polling interval can't hammer the school server.
- (+) Self-healing once the server recovers.
- (−) More code paths to test; need fixtures simulating rate-limit responses.

### Pattern 6: Modern `runtime_data` over `hass.data[DOMAIN]`

**What:** Recent HA versions (post-2024.x) prefer attaching integration runtime objects to `entry.runtime_data` (a typed attribute) instead of stuffing them into `hass.data[DOMAIN][entry_id]`.

**When to use:** Always for new integrations.

**Why:**
- (+) Type-safe via `type MyConfigEntry = ConfigEntry[MyData]` alias.
- (+) Lifecycle is automatic — `runtime_data` is cleared on unload.
- (+) No nested dict lookups.

**Adoption note:** `ludeeus/integration_blueprint` uses this pattern exclusively. `delphiki/hass-pronote` still uses the older `hass.data[DOMAIN]` dict — we should not copy that detail.

---

## Data Flow

### Setup Flow (one-shot, on integration load)

```
User clicks "Add Integration" in HA UI
        │
        ▼
config_flow.async_step_user()
        │ collects URL, account_type, credentials
        │ calls api.client.test_login() in executor
        ▼
config_flow.async_create_entry()  ──────▶  ConfigEntry persisted in HA storage
        │
        ▼
__init__.async_setup_entry(hass, entry):
        1. Build PronoteApiClient from entry.data
        2. Build PronoteDataUpdateCoordinator(hass, entry, client)
        3. entry.runtime_data = PronoteData(client, coordinator)
        4. await coordinator.async_config_entry_first_refresh()
              ├─ on auth error  → ConfigEntryAuthFailed → triggers reauth flow
              └─ on net error   → ConfigEntryNotReady   → HA retries with backoff
        5. await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
              ├─ sensor.async_setup_entry → creates schedule, grades, notifs sensors
              └─ binary_sensor.async_setup_entry → creates "has_change" sensors
        6. entry.async_on_unload(entry.add_update_listener(reload_on_options_change))
```

### Update Flow (every `update_interval`, the hot path)

```
HA scheduler ticks (every update_interval seconds)
        │
        ▼
coordinator._async_update_data()       [running on event loop]
        │
        ├─ previous = self.data        (None on first run)
        │
        ├─ await hass.async_add_executor_job(api.fetch_all, ...)
        │       ┌────────────────────────────────────────┐
        │       │  [executor thread]                     │
        │       │   pronotepy.Client.refresh()           │
        │       │   pronotepy.Client.lessons(today)      │
        │       │   pronotepy.Client.lessons(tomorrow)   │
        │       │   pronotepy.Client.current_period.grades │
        │       │   pronotepy.Client.information_and_surveys │
        │       │   → returns Snapshot(...)              │
        │       └────────────────────────────────────────┘
        │
        ├─ if previous is not None:
        │     events = diff_all(previous, snapshot)        [pure, fast]
        │     for ev in events: hass.bus.async_fire(ev.type, ev.payload)
        │
        ├─ self.update_interval = compute_interval(dt_util.now())
        │
        └─ return snapshot
                │
                ▼
        CoordinatorEntity._handle_coordinator_update() fires for every linked entity
                │
                ▼
        Each entity's native_value / extra_state_attributes properties read from
        coordinator.data → HA state machine updates → frontend refreshes
                │
                ▼
        Automations triggered by:
          - state_changed (sensor numeric value flips)
          - pronote_schedule_changed (typed bus event from diff)
          - pronote_new_grade (typed bus event)
          - pronote_new_information (typed bus event)
```

### State Storage

```
ConfigEntry.data        → credentials (encrypted at rest by HA storage layer)
ConfigEntry.options     → polling interval, adaptive_polling flag, afternoon_interval, nickname
ConfigEntry.runtime_data → PronoteData(client, coordinator)   [in-memory, cleared on unload]
Coordinator.data        → last Snapshot                        [in-memory, persists across cycles]
```

No custom persistence layer needed. HA handles config entry storage; coordinator state is transient (we accept losing the snapshot on restart — first cycle after restart simply skips diff emission).

### Key Data Flows

1. **First-time login:** UI → config_flow → executor(`pronotepy.Client(url, user, pwd)`) → token exchange → success → ConfigEntry created.
2. **Token refresh:** Each `_async_update_data` exports refreshed credentials via `client.export_credentials()` and stores them back into `entry.data` (Pronote tokens rotate frequently). Standard pattern from `delphiki/hass-pronote`.
3. **Auth failure mid-session:** `pronotepy` raises → API layer converts to `AuthError` → coordinator raises `ConfigEntryAuthFailed` → HA fires reauth flow → user re-enters password → entry updated → entry reloaded.
4. **Schedule change detection:** old snapshot + new snapshot → `diff_lessons()` → list of `LessonChange` → coordinator fires `pronote_schedule_changed` events on bus → user automations trigger notifications.

---

## Suggested Build Order

The sequence is dictated by **what must work for the next thing to be testable**. Each step ends in a runnable, demonstrable artifact.

### Phase A — Skeleton you can install
1. `manifest.json` + `hacs.json` + empty `__init__.py` with a no-op `async_setup_entry` returning `True`.
2. `const.py` with `DOMAIN`, `PLATFORMS=[]`, defaults.
3. `config_flow.py` with single `async_step_user` collecting URL + credentials, NO validation yet.
4. **Exit criterion:** integration loads in a HA dev container, "Add Integration" UI shows the form, entry can be created and removed without errors.

### Phase B — API layer (sync, isolated)
5. `api/errors.py` with `AuthError`, `CommunicationError`, `RateLimitedError`, `ParseError`.
6. `api/models.py` with `Snapshot`, `Lesson`, `Grade`, `Information` dataclasses.
7. `api/client.py` — sync `pronotepy` wrapper with `login()`, `test_login()`, `export_credentials()`. Pure Python, importable in plain pytest.
8. `api/fetcher.py` — `fetch_all(client, today) -> Snapshot`, returning fully serializable plain objects (strip pronotepy back-references; see the `_strip_client_refs` pattern in `delphiki/hass-pronote` — non-trivial gotcha worth budgeting for).
9. `tests/test_api/` with fixtures from real (anonymized) Pronote responses.
10. **Exit criterion:** `pytest tests/test_api/` passes. We can fetch a snapshot from a real Pronote instance via a local CLI script.

### Phase C — Coordinator + first sensor
11. `data.py` with `PronoteData` dataclass and `PronoteConfigEntry` type alias.
12. `coordinator.py` v0: just executor-wraps `fetch_all`, no diff yet, no adaptive interval. Translates errors to `ConfigEntryAuthFailed` / `UpdateFailed`.
13. `entity.py` base class.
14. `sensor.py` with ONE sensor (lessons today count) to validate end-to-end.
15. `__init__.py` properly wired: builds coordinator, calls `async_config_entry_first_refresh`, forwards platforms.
16. Update `config_flow.py` to actually call `client.test_login()` and surface auth errors.
17. **Exit criterion:** integration installed against real Pronote shows a working sensor whose value updates on the polling interval. Reauth works on wrong password.

### Phase D — Diff + events (the core value)
18. `diff/lessons.py` — `diff_lessons(old, new, day) -> list[LessonChange]` with comprehensive unit tests (cancelled, modified room/teacher/time, added, removed).
19. Coordinator integrates diff: stores previous snapshot (already automatic via `self.data`), calls diff functions, fires `pronote_schedule_changed` on bus.
20. `tests/test_coordinator.py` validates that events fire with correct payloads given two snapshots.
21. `diff/grades.py` + `diff/notifications.py` — same pattern.
22. **Exit criterion:** modifying a lesson in Pronote (or replaying a fixture) results in a `pronote_schedule_changed` event visible in HA's Developer Tools → Events. This is the moment the project demonstrates its core value.

### Phase E — Adaptive polling + politesse
23. `compute_interval()` pure function + tests for time-of-day branches.
24. Coordinator mutates `self.update_interval` at end of `_async_update_data`.
25. Circuit breaker in `api/client.py` (consecutive failure counter + exponential backoff).
26. `tests/` for both: time-mocked tests for interval computation; mock-injected failures for circuit breaker.
27. **Exit criterion:** logs show interval shrinking 17h–20h on weekdays; simulated rate-limit responses cause exponential backoff observable in logs.

### Phase F — Multi-account, options, reauth, reconfigure
28. Verify two config entries with different credentials run independent coordinators (mostly free thanks to HA's design, but test it).
29. `OptionsFlow` for refresh_interval, adaptive_polling toggle, afternoon_interval, nickname.
30. `async_step_reauth` in `config_flow.py` for password expiry.
31. `async_step_reconfigure` for changing URL or account type without losing entity history.
32. **Exit criterion:** option changes propagate to coordinator without HA restart; reauth flow triggers automatically on invalid credentials.

### Phase G — Quality + distribution
33. `diagnostics.py` with `TO_REDACT = [CONF_PASSWORD, CONF_USERNAME, "qr_code_*", "session"]`.
34. `strings.json` + `translations/fr.json` + `translations/en.json`.
35. GitHub Actions: `validate.yml` (hassfest + HACS validation actions) + `tests.yml` (ruff + pytest + coverage gate).
36. README with HACS install instructions, automation examples for the events.
37. Tag v0.1.0 — declare HACS custom-repo readiness.

### Build-order dependencies summary

```
Phase A (skeleton)
        │
        ▼
Phase B (api/) ─── independent, no HA imports, tested in plain pytest
        │
        ▼
Phase C (coordinator + first sensor) ─── needs A + B
        │
        ▼
Phase D (diff + events) ─── needs C; THIS IS THE PRODUCT
        │
        ├──▶ Phase E (adaptive polling + politesse) ─── needs D for testing
        │
        └──▶ Phase F (multi-account, options, reauth) ─── needs C
                │
                ▼
        Phase G (diagnostics, i18n, CI, packaging) ─── needs all above
```

Phases E and F can proceed in parallel once D is done. Phase G starts as soon as D is complete (CI can be set up earlier, but its full quality gate makes sense once the code is meaningful).

---

## Scaling Considerations

This is a **single-household integration**, not a server-side system. The relevant scale dimension is "how many children in the family" — typically 1–4, hard cap maybe 8.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 child | Default config works. ~1 executor thread used per cycle. |
| 2–4 children | Each is a separate config entry → 2–4 coordinators ticking independently. HA's executor pool (default 10 threads) absorbs this comfortably. |
| 5+ children | Theoretical limit: HA's default executor pool. In practice, since each child polls every 30 minutes, simultaneous executor occupancy is rare. No code changes needed. |
| Many HACS users (community scale) | Each user's HA instance is independent — no shared backend. The only "scaling" concern is the **shared school server**: if many users from the same school install this, polling could constitute DDoS against the school. Mitigation: conservative defaults (30 min, jittered start time), prominent README warning. |

### Scaling Priorities

1. **First bottleneck (if any): IP ban from the school server.** Already addressed by Pattern 5 (circuit breaker) and conservative polling defaults.
2. **Second bottleneck: pronotepy memory leaks.** `delphiki/hass-pronote` ships with a `_strip_client_refs` and a `PronotePeriod.instances.clear()` call after every fetch — these are real production fixes, not premature optimization. Bake them in from day one.
3. **Third bottleneck (theoretical): pronotepy parsing performance on huge schedules.** Not relevant at our scale.

---

## Anti-Patterns

### Anti-Pattern 1: Calling `pronotepy` directly on the event loop

**What people do:** Forget the `async_add_executor_job` wrapper for "small" calls, e.g. `client.session_check()`.

**Why it's wrong:** Even a single sync call of a few hundred milliseconds blocks the entire HA event loop — every entity, every automation, every websocket — and shows up as `Updating state takes >X seconds, the system may be overloaded` warnings in the log.

**Do this instead:** Wrap **every** `pronotepy` call without exception. If unsure, follow the rule: anything that touches `client.*` goes through the executor.

### Anti-Pattern 2: Multiple coordinators per config entry to "parallelize" data types

**What people do:** Build separate `LessonsCoordinator`, `GradesCoordinator`, `NotificationsCoordinator` per child, thinking it's more modular.

**Why it's wrong:** Each coordinator opens its own `pronotepy` session → triple the login traffic to the school server (the exact thing we want to avoid). Coordination of cross-data-type diffs becomes painful. No real benefit at our scale.

**Do this instead:** One coordinator per child, fetches everything in one cycle, calls multiple diff functions on the result.

### Anti-Pattern 3: Diff logic embedded in entity classes

**What people do:** Compute "what changed" inside the `SensorEntity.native_value` or in `_handle_coordinator_update`.

**Why it's wrong:** Entities can be created/destroyed on reload — they have no reliable history. They're also untestable without spinning up the full HA test harness.

**Do this instead:** Diff is computed in the coordinator's `_async_update_data` (which has stable access to `self.data` from the previous cycle) using pure functions in `diff/`. Entities are read-only views over `coordinator.data`.

### Anti-Pattern 4: Firing HA bus events from inside an executor job

**What people do:** Inside `api.fetch_all` (running in a thread), call `hass.bus.async_fire(...)` after detecting a change.

**Why it's wrong:** `hass.bus.async_fire` is **not thread-safe**. It must be called from the event loop. Calling it from a thread leads to subtle race conditions and intermittent crashes. (Use `hass.bus.fire` for thread-safe firing — but our diff happens on the event loop anyway, so the issue shouldn't arise.)

**Do this instead:** Diff and event firing live in the **coordinator** (event loop). Executor-side code only fetches and parses; it never touches `hass.*`.

### Anti-Pattern 5: Storing `pronotepy` client objects on entity instances

**What people do:** Hand the `pronotepy.Client` to each sensor as a convenience.

**Why it's wrong:** `pronotepy` clients hold a `requests.Session`, large parsed XML trees, and mutable internal state. Aliasing the client across entities makes lifecycle management impossible (when do we close the session?) and prevents the GC from reclaiming memory.

**Do this instead:** The client lives in `runtime_data.client` (single owner) and is used only inside the coordinator. The coordinator publishes plain dataclasses (the `Snapshot`) — entities only ever see those. This is exactly why `delphiki/hass-pronote` had to add the explicit `_strip_client_refs` workaround to GC sessions; we avoid the whole problem by never letting `pronotepy` objects escape the coordinator.

### Anti-Pattern 6: Aggressive default polling interval

**What people do:** Default to 5–10 min polling because "users want fresh data."

**Why it's wrong:** Pronote servers are school-administered, often underpowered, and can ban our IP with no recourse. A 5-min default × thousands of HACS installs = effectively a DDoS.

**Do this instead:** Default 30 min, document the tradeoff in README, allow user-tightening to 15 min minimum (NOT 5). Adaptive afternoon polling is the primary mechanism for catching late J+1 changes — not a globally tight interval.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Pronote server (HTTP) | Through `pronotepy` only — never speak HTTP directly | API is unofficial, undocumented; subject to break with each Pronote update. Pin `pronotepy` version in `manifest.json` and watch upstream releases. |
| Home Assistant Core | Through HA's documented integration APIs (`ConfigEntries`, `DataUpdateCoordinator`, `bus`, `services`) | No direct DB or filesystem access; persist via `ConfigEntry.data`/`options` only. |
| HACS | Repository-level metadata in `hacs.json` at repo root + tagged GitHub releases | For v1, custom repository; for v2+, submission to default HACS index requires Quality Scale compliance. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `config_flow.py` ↔ `api/client.py` | Direct call to `test_login()`; runs in executor | Config flow methods are async, so they wrap the sync API call themselves. |
| `__init__.py` ↔ `coordinator.py` | Constructs coordinator, calls `async_config_entry_first_refresh` | Errors there decide between `ConfigEntryAuthFailed` (→reauth) and `ConfigEntryNotReady` (→retry). |
| `coordinator.py` ↔ `api/` | Sync calls wrapped in `async_add_executor_job` | API layer must NOT import HA — keeps it unit-testable. |
| `coordinator.py` ↔ `diff/` | Direct sync function calls (pure functions, fast) | Diff layer must NOT import HA — pure pytest tests. |
| `coordinator.py` ↔ `hass.bus` | `hass.bus.async_fire(EVENT_TYPE, payload)` | The only place we touch the bus. |
| `sensor.py` / `binary_sensor.py` ↔ `coordinator` | Inheritance via `CoordinatorEntity`; reads `self.coordinator.data` | Entities are pure projections. No business logic. |
| `diagnostics.py` ↔ `coordinator` + `entry` | Reads `entry.runtime_data.coordinator.data` and `entry.data`, redacts | Standalone, called by HA's diagnostics download. |

---

## Sources

- [Home Assistant Developer Docs — Integration file structure](https://developers.home-assistant.io/docs/creating_integration_file_structure/) — HIGH confidence (official)
- [Home Assistant Developer Docs — Fetching data / DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) — HIGH confidence (official)
- [Home Assistant Developer Docs — Working with Async](https://developers.home-assistant.io/docs/asyncio_working_with_async/) — HIGH confidence (official)
- [Home Assistant Developer Docs — Config flow handler](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) — HIGH confidence (official)
- [Home Assistant Developer Docs — Firing events](https://developers.home-assistant.io/docs/integration_events/) — HIGH confidence (official)
- [Home Assistant Quality Scale — Diagnostics rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/) — HIGH confidence (official)
- [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint) — HIGH confidence (canonical template, files read directly: `__init__.py`, `coordinator.py`, `config_flow.py`, `data.py`, `entity.py`, `sensor.py`)
- [delphiki/hass-pronote](https://github.com/delphiki/hass-pronote) — HIGH confidence (existing Pronote integration, files read directly: `__init__.py`, `coordinator.py`, `pronote_helper.py`, `manifest.json`). Validates the executor-wrapping + diff + bus-event pattern in production.
- [HACS — Integration publishing requirements](https://hacs.xyz/docs/publish/integration/) — HIGH confidence (official)
- [Home Assistant community — Dynamic update_interval discussions](https://community.home-assistant.io/t/change-the-update-interval-in-an-existing-coordinator/341635) — MEDIUM confidence (community pattern, not officially documented but widely used)
- [Home Assistant core source — `update_coordinator.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/update_coordinator.py) — HIGH confidence (source-verified that `update_interval` is a public mutable attribute)

---
*Architecture research for: Home Assistant custom_component wrapping pronotepy*
*Researched: 2026-05-03*
