---
phase: 03-coordinator-first-sensor
plan: 03
subsystem: entity
tags: [entity, sensor, has_entity_name, translation_key, device_info, coordinator_entity, lessons_today, frozen_unique_id, mdi_school, measurement, ENT-02, ENT-03, TIME-01]

# Dependency graph
requires:
  - phase: 03-coordinator-first-sensor
    plan: 01
    provides: "strings.json entity.sensor.lessons_today.name translation_key + ConfigEntry data['child_name'] + frozen child_identifier slug (ENT-02 anchor)"
  - phase: 03-coordinator-first-sensor
    plan: 02
    provides: "PronoteData runtime payload (entry.runtime_data.coordinator + .child_identifier), PronoteDataUpdateCoordinator (coordinator.data: Snapshot, last_update_success, last_update_success_time), PLATFORMS=(Platform.SENSOR,) const"
  - phase: 02-pure-python-api-fetcher
    provides: "api.models.Snapshot.lessons_today property (subset of lessons whose date == self.today)"
provides:
  - "PronoteEntity base class — CoordinatorEntity[PronoteDataUpdateCoordinator] subclass with _attr_has_entity_name=True, device_info, available; the seam Phase 4's calendar/grades/notifications subclass without circular-dep risk (C-01)"
  - "PronoteLessonsTodaySensor — first concrete sensor (D-15 inheritance order: PronoteEntity, SensorEntity)"
  - "Frozen unique_id format anchor: f'pronote_{child_identifier}_lessons_today' — locked v1, Phase 6 OPT-03 nickname change must not touch it (D-13, ENT-02)"
  - "translation_key contract: 'lessons_today' -> strings.json entity.sensor.lessons_today.name (ENT-03)"
  - "DeviceInfo shape (D-17): identifiers={(DOMAIN, child_identifier)}, name=entry.data['child_name'], manufacturer='Pronote' — NO model/sw_version/configuration_url (Phase 4 owns model)"
  - "available semantic: self.coordinator.last_update_success — coordinator failure flips every entity to unavailable (D-15)"
  - "sensor.async_setup_entry platform callback reading entry.runtime_data.coordinator (D-21, D-25)"
affects: [03-04-tests, 04-calendar-and-diff, 04-grades-sensor, 04-notifications-sensor, 06-options-and-reauth, 06-nickname-rename]

# Tech tracking
tech-stack:
  added:
    - "homeassistant.helpers.update_coordinator.CoordinatorEntity (subclass — first use)"
    - "homeassistant.helpers.device_registry.DeviceInfo (first use in this project)"
    - "homeassistant.components.sensor.SensorEntity + SensorStateClass.MEASUREMENT (first use)"
    - "homeassistant.helpers.entity_platform.AddEntitiesCallback (TYPE_CHECKING-only)"
  patterns:
    - "Separate entity.py base file (C-01) — calendar.py / grades / notifications subclass without importing sensor.py (avoids circular dep)"
    - "_attr_has_entity_name = True on the base + _attr_translation_key on each subclass (D-15) — display name comes from strings.json"
    - "DeviceInfo via @property reading self._entry.runtime_data.child_identifier and self._entry.data['child_name'] (D-17)"
    - "available delegates to self.coordinator.last_update_success (D-15) — single line; HA inherits CoordinatorEntity baseline"
    - "unique_id locked in __init__ from entry.runtime_data.child_identifier — never re-derived after construction (D-13, T-03-17)"
    - "native_value reads coordinator.data.lessons_today property (D-14, D-16) — never iterates raw coordinator.data.lessons"
    - "Platform setup forwards a single sensor instance — Phase 4's grades/notifications extend by appending to async_add_entities([...]) (D-25)"

key-files:
  created:
    - "custom_components/ha_pronote/entity.py (64 lines) — PronoteEntity base"
    - "custom_components/ha_pronote/sensor.py (69 lines) — async_setup_entry + PronoteLessonsTodaySensor"
  modified: []

key-decisions:
  - "C-01 implemented verbatim: PronoteEntity ships in entity.py (NEW dedicated file), NOT in sensor.py. Phase 4's calendar.py and additional sensors will subclass entity.PronoteEntity without sensor.py becoming the import target."
  - "D-13/ENT-02 unique_id format frozen as f'pronote_{child_identifier}_lessons_today' — set ONCE in __init__ from entry.runtime_data.child_identifier. Plan 04's test will assert the exact byte-for-byte string."
  - "D-14 deferral: PronoteLessonsTodaySensor SHIPS WITHOUT extra_state_attributes — the J/J+1 lesson list payload (TIME-02) is Phase 4's deliberate add, NOT a refactor of this sensor."
  - "D-17 DeviceInfo locked to {identifiers, name, manufacturer} only — NO model field in Phase 3 (ROADMAP Phase 4 SC#2 explicitly assigns model=<class level> to Phase 4)."
  - "D-15 inheritance order: class PronoteLessonsTodaySensor(PronoteEntity, SensorEntity) — PronoteEntity first so its _attr_has_entity_name and device_info take precedence; SensorEntity second so SensorEntity attributes (state_class, native_unit_of_measurement) resolve via MRO."
  - "D-16 sensor metadata: _attr_state_class = MEASUREMENT, _attr_icon = 'mdi:school', _attr_native_unit_of_measurement = 'lessons'. Explicitly NO _attr_device_class — none of the SensorDeviceClass enum members fit a count-of-lessons metric."

patterns-established:
  - "Pattern: base class lives in dedicated entity.py (C-01) — Phase 4 ADD entities by adding new <Kind>Sensor classes that subclass PronoteEntity directly. No new files in sensor.py beyond declaring the class."
  - "Pattern: unique_id is computed ONCE in __init__ from frozen entry.runtime_data.child_identifier and assigned to self._attr_unique_id — never re-derived. Nickname options (Phase 6 OPT-03) only mutate display name, never the unique_id."
  - "Pattern: native_value via @property reads the Snapshot semantic property (lessons_today / lessons_tomorrow), NOT the raw lessons list — every future sensor consumes a typed property on Snapshot."
  - "Pattern: import discipline — runtime imports limited to homeassistant.* + .const + .entity. TYPE_CHECKING-only imports for HomeAssistant, AddEntitiesCallback, PronoteDataUpdateCoordinator, PronoteConfigEntry."

requirements-completed: [TIME-01, ENT-02, ENT-03]

# Metrics
duration: 4min
completed: 2026-05-07
---

# Phase 03 Plan 03: PronoteEntity Base + lessons_today Sensor Summary

**PronoteEntity base class (CoordinatorEntity[PronoteDataUpdateCoordinator]) in dedicated entity.py + first concrete sensor PronoteLessonsTodaySensor with frozen unique_id `pronote_{child_identifier}_lessons_today`, MEASUREMENT state class, and Snapshot.lessons_today native_value (state-only — TIME-02 J/J+1 attributes deliberately deferred to Phase 4).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-07T01:46:14Z
- **Completed:** 2026-05-07T01:51:08Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments

- ROADMAP Phase 3 SC#3 surface in place: `sensor.pronote_<child>_lessons_today` registers under `coordinator.data.lessons_today` and refreshes on the configured 30-min cadence (Plan 02's `DEFAULT_REFRESH_INTERVAL`). Phase 4 will add the J/J+1 attribute payload on this same sensor without a refactor (D-14).
- ROADMAP Phase 3 SC#4 / ENT-02 anchor frozen: the unique_id format `pronote_{child_identifier}_lessons_today` is hardcoded in `sensor.py:65` and Plan 04's test will assert the exact byte-for-byte string.
- C-01 adopted: `PronoteEntity` lives in a dedicated `entity.py` (NEW), not in `sensor.py`. Phase 4's calendar.py and grades / notifications sensors will subclass `entity.PronoteEntity` directly — no circular-dep risk.
- D-15 modern naming convention live: `_attr_has_entity_name = True` on the base, `_attr_translation_key = "lessons_today"` on the concrete sensor, display name resolved from strings.json's `entity.sensor.lessons_today.name` (Plan 01).
- D-17 DeviceInfo shape locked: `identifiers={(DOMAIN, child_identifier)}`, `name=entry.data["child_name"]`, `manufacturer="Pronote"` — explicitly NO `model` / `sw_version` / `configuration_url` (Phase 4 owns the class-level model attribute per ROADMAP Phase 4 SC#2).
- `available` semantic delegates to `self.coordinator.last_update_success` — a poll failure flips every entity (this one + every Phase 4 entity) to `unavailable` until the next successful refresh.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create entity.py — PronoteEntity base** — `6bdf2bb` (feat)
2. **Task 2: Create sensor.py — async_setup_entry + PronoteLessonsTodaySensor** — `a94423b` (feat)

## Files Created/Modified

- `custom_components/ha_pronote/entity.py` (NEW, 64 lines) — `PronoteEntity(CoordinatorEntity["PronoteDataUpdateCoordinator"])`. Module docstring cites C-01, D-15, D-17, ENT-03. `_attr_has_entity_name = True` class attribute, `__init__(coordinator, entry)` binding `self._entry`, `device_info` property returning `DeviceInfo(identifiers={(DOMAIN, child_identifier)}, name=entry.data["child_name"], manufacturer="Pronote")`, `available` property returning `self.coordinator.last_update_success`. TYPE_CHECKING imports of `PronoteDataUpdateCoordinator` and `PronoteConfigEntry` keep runtime imports limited to `homeassistant.*` and `.const`.
- `custom_components/ha_pronote/sensor.py` (NEW, 69 lines) — `async_setup_entry(hass, entry, async_add_entities)` reads `entry.runtime_data.coordinator` and registers a single `PronoteLessonsTodaySensor`. Class declares `_attr_translation_key = "lessons_today"`, `_attr_icon = "mdi:school"`, `_attr_state_class = SensorStateClass.MEASUREMENT`, `_attr_native_unit_of_measurement = "lessons"`. `__init__` locks `self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_lessons_today"`. `native_value` returns `len(self.coordinator.data.lessons_today)`. NO `extra_state_attributes`, NO `_attr_device_class`.

## Hand-off Shape (Plan 04 + Phase 4 read)

```python
# Plan 04 imports
from custom_components.ha_pronote.entity import PronoteEntity
from custom_components.ha_pronote.sensor import (
    PronoteLessonsTodaySensor,
    async_setup_entry as sensor_async_setup_entry,
)
```

Plan 04's PHACC test will assert (under the `hass` fixture):
- `sensor.pronote_<child_slug>_lessons_today` registers
- `state == str(len(coordinator.data.lessons_today))`
- `entity.unique_id == f"pronote_{child_identifier}_lessons_today"` (byte-for-byte)
- `entity.device_info["identifiers"] == {(DOMAIN, child_identifier)}`
- `entity.device_info["name"] == entry.data["child_name"]`
- `entity.device_info["manufacturer"] == "Pronote"`
- `entity.device_info` does NOT contain a `model` key
- `entity.available is True` after a successful first refresh, `False` after a forced failed refresh

Phase 4 grades / notifications sensors will:
- Add a new `<Kind>Sensor(PronoteEntity, SensorEntity)` class in `sensor.py` (or a separate `grades.py` if scope grows)
- Append the new instance(s) to `async_setup_entry`'s `async_add_entities([...])` call
- Subclass `entity.PronoteEntity` directly — `entity.py` is the seam, NOT `sensor.py`
- Add `extra_state_attributes` to `PronoteLessonsTodaySensor` for TIME-02 J/J+1 payload (deliberate ADD per D-14)
- Add `_attr_model` (or per-instance `model=` in DeviceInfo) for the class-level attribute (ROADMAP Phase 4 SC#2)

## Decisions Made

None new — all cited decisions (C-01, D-13, D-14, D-15, D-16, D-17, D-21, D-25, ENT-02, ENT-03, TIME-01) were already locked in `03-CONTEXT.md` and `03-PATTERNS.md`. This plan implements them verbatim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Docstring `model=<class level>` token clash with grep gate**
- **Found during:** Task 1 (entity.py creation)
- **Issue:** The plan's docstring template (lines 168-170 of 03-03-PLAN.md) literally contains `model=<class level>` to document the Phase 4 anti-pattern guard, but the plan's own acceptance criterion `grep -c "model=" custom_components/ha_pronote/entity.py == 0` then matches that docstring. The grep is correct (we want NO `model=` literal in the file, including docstrings), the plan template is the source of the conflict.
- **Fix:** Reworded the docstring from `` ``model=<class level>`` lands in Phase 4 `` to `the class-level model attribute lands in Phase 4`. Intent (banning the field in Phase 3) preserved with non-literal wording — the future reader still sees the anti-pattern callout.
- **Files modified:** `custom_components/ha_pronote/entity.py`
- **Verification:** `grep -c "model=" custom_components/ha_pronote/entity.py` exits with `0`; ruff (lint + format) clean; all other Task 1 acceptance criteria still pass.
- **Committed in:** `6bdf2bb` (Task 1 commit, autocorrection applied before commit)

**2. [Rule 3 — Blocking] Docstring `extra_state_attributes` token clash with grep gate**
- **Found during:** Task 2 (sensor.py creation)
- **Issue:** Same pattern as #1. The plan's docstring template (lines 263, 306 of 03-03-PLAN.md) literally contains `` ``extra_state_attributes`` `` twice to document the D-14 deferral, but the plan's acceptance criterion `grep -c "extra_state_attributes" custom_components/ha_pronote/sensor.py == 0` then matches both occurrences.
- **Fix:** Reworded both docstrings:
  - Module docstring: `` no ``extra_state_attributes`` `` → `no extra state attribute payload`.
  - Class docstring: `State-only in Phase 3 (no ``extra_state_attributes``)` → `State-only in Phase 3 (no extra state attribute payload)`.
- **Files modified:** `custom_components/ha_pronote/sensor.py`
- **Verification:** `grep -c "extra_state_attributes" custom_components/ha_pronote/sensor.py` exits with `0`; ruff (lint + format) clean; all other Task 2 acceptance criteria still pass.
- **Committed in:** `a94423b` (Task 2 commit, autocorrection applied before commit)

**3. [Rule 3 — Blocking] `ruff format` collapsed multi-line `_attr_unique_id` assignment**
- **Found during:** Task 2 (sensor.py creation, after first ruff format)
- **Issue:** The plan's code template wrote the unique_id as a multi-line assignment:
  ```python
  self._attr_unique_id = (
      f"pronote_{entry.runtime_data.child_identifier}_lessons_today"
  )
  ```
  The line fits within ruff's `line-length = 88` budget after the `self._attr_unique_id = ` prefix is consumed, so `ruff format` legitimately collapses it to a single line.
- **Fix:** Accepted the format change. The file's behaviour is byte-identical (the f-string content is unchanged) and the plan's grep gate (`grep -c 'f"pronote_{entry.runtime_data.child_identifier}_lessons_today"' ...`) still matches because the f-string substring is intact.
- **Files modified:** `custom_components/ha_pronote/sensor.py`
- **Verification:** `ruff format --check` reports `1 file already formatted`; the unique_id grep gate still exits with `1`.
- **Committed in:** `a94423b` (Task 2 commit, format applied before commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 3 — blocking)

**Impact on plan:** All three are mechanical conformance fixes (docstring tokens vs strict grep gates, formatter line-collapse). Behaviour is byte-identical to the plan's intent; no scope creep. Pattern carries over from Plan 02's similar comment-strip grep clashes.

## Issues Encountered

### Verification environment limitations (NOT code defects)

Same baseline limitation as Plan 02: this worktree's local Python 3.13.9 venv lacks Home Assistant 2026.4.x (which requires Python 3.14.2). Consequence:

| Gate | Status in this worktree | CI status |
|------|-------------------------|-----------|
| `ruff check` (entity.py + sensor.py) | PASS | PASS expected |
| `ruff format --check` (entity.py + sensor.py) | PASS | PASS expected |
| `pyright` (entity.py + sensor.py) | 5 `reportMissingImports` errors on `homeassistant.*` only — type signatures sound otherwise | PASS expected (HA 2026.4.x installed) |
| `pytest tests/test_no_ha_imports.py` | PASS — 27 tests passed in 0.05s (D-19 invariant preserved; AST-only, no HA needed) | PASS expected |
| Anti-pattern grep gates (4 patterns × `grep -v '^#'`) | PASS | PASS expected |
| Plan-level translation_key + strings.json key-shape | PASS | PASS expected |
| Plan-level unique_id format anchor | PASS | PASS expected |

The pyright errors are import-resolution warnings only (no signature mismatches, no attribute errors). CI on `main` runs against Python 3.14 + HA 2026.4.x via the workflows shipped in Phase 1.

**Tooling fix applied:** Installed `ruff==0.15.1` via `pip install --user` (PYENV_VERSION=3.13.5 picks the user-site binary up automatically since pyenv 3.14 is unavailable locally) and `pyright@1.1.409` via `npm install --no-save` so the local feedback loop matches the CI gates. These are environment-only; no project files were modified.

### TDD Gate Compliance

Plan type is `execute` (not `tdd`); no RED/GREEN/REFACTOR gate sequence is required. Plan 04 owns the test-side TDD work for this entity + sensor.

## End-of-plan invariants

| Invariant | Result |
|-----------|--------|
| `git diff --name-only` since Plan 02 lists exactly `entity.py` + `sensor.py` | PASS |
| `wc -l entity.py` between 35 and 80 | PASS (64) |
| `wc -l sensor.py` between 50 and 90 | PASS (69) |
| Importability sanity (requires HA) | NOT-RUNNABLE locally (no HA in venv); pyright clean (apart from import resolution) stands in. CI will exercise full import chain. |

## Threat Surface Scan

No new security-relevant surface introduced beyond the plan's `<threat_model>`. Threats T-03-16 through T-03-20 are addressed exactly as specified:
- T-03-16 (DeviceInfo.name discloses child name): accepted per plan — single-tenant HA install, intentional user-facing identity.
- T-03-17 (unique_id stability): unique_id computed ONCE in `__init__` from `entry.runtime_data.child_identifier` (frozen at flow time per Plan 01 D-11). Phase 6 OPT-03 nickname change must NOT touch unique_id.
- T-03-18 (logging): `entity.py` and `sensor.py` contain ZERO `_LOGGER.*` calls. The sensor only renders `len(coordinator.data.lessons_today)` (an integer); no credentials / URLs / session tokens flow through this code path.
- T-03-19 (DoS via failed first poll): handled by `available` returning `False` when `self.coordinator.last_update_success` is False — sensor visible but `unavailable` until next successful refresh. First-poll failure is handled by Plan 02's `async_config_entry_first_refresh` raising before the platform forward fires.
- T-03-20 (DeviceInfo identifier collision): `(DOMAIN, child_identifier)` is namespaced by `DOMAIN = "ha_pronote"` and Plan 01's D-12 collision-suffix prevents same-slug different-child ConfigEntries from colliding.

No threat flags raised — the implemented surface matches the planned threat register exactly.

## User Setup Required

None — no external service configuration required for this plan. Users will see the sensor appear once Plan 02 + 03 + a first config flow setup complete. Plan 04's PHACC tests exercise the entity / sensor under a mocked `build_or_resume_client` seam.

## Next Phase Readiness

- **Plan 04 (PHACC tests)**: ready. The `PronoteEntity` and `PronoteLessonsTodaySensor` symbols are importable; the unique_id format, device_info shape, translation_key, and native_value semantic are all locked and grep-asserted.
- **Phase 4 (calendar + diff + grades + notifications)**: ready. Subclass `entity.PronoteEntity` for new sensors, add `extra_state_attributes` to `PronoteLessonsTodaySensor` for TIME-02 (deliberate ADD per D-14), add `model=` to `DeviceInfo` (or `_attr_model` on subclasses) for the Phase 4 class-level model attribute.
- **Phase 6 (options + reauth + nickname)**: the unique_id is locked — OPT-03 nickname change must mutate display name only, never unique_id. The `_attr_translation_key` mechanism cleanly separates display name from entity_id.

## Symbols Plan 04 + Phase 4 will import

```python
from custom_components.ha_pronote.entity import PronoteEntity
from custom_components.ha_pronote.sensor import (
    PronoteLessonsTodaySensor,
    async_setup_entry,
)
```

The unique_id format is the contract: `f"pronote_{child_identifier}_lessons_today"`.

## Self-Check

**Verifying claims before proceeding.**

Files claimed created:
- `custom_components/ha_pronote/entity.py`: FOUND (64 lines, ruff-clean)
- `custom_components/ha_pronote/sensor.py`: FOUND (69 lines, ruff-clean)

Commits claimed:
- `6bdf2bb` (Task 1): FOUND in `git log`
- `a94423b` (Task 2): FOUND in `git log`

End-of-plan invariants:
- `entity.py` LOC in [35, 80]: 64 — PASS
- `sensor.py` LOC in [50, 90]: 69 — PASS
- `git diff --name-only` since `c7df8e6` lists exactly `entity.py` + `sensor.py`: PASS

Plan-level verification gates:
- `ruff check`: PASS (both files)
- `ruff format --check`: PASS (both files)
- `pyright`: errors limited to `reportMissingImports` on `homeassistant.*` (pre-existing local venv limitation; CI clean)
- Anti-pattern grep gates (`import requests`, `import pytz`, `async_timeout`, `pronotepy.ent`): PASS (0 matches under `grep -v '^#'`)
- translation_key matches strings.json `entity.sensor.lessons_today.name`: PASS
- unique_id format anchor `f"pronote_{entry.runtime_data.child_identifier}_lessons_today"`: PASS
- D-19 invariant via `tests/test_no_ha_imports.py`: PASS (27 tests, 0.05s)

## Self-Check: PASSED

---
*Phase: 03-coordinator-first-sensor*
*Completed: 2026-05-07*
