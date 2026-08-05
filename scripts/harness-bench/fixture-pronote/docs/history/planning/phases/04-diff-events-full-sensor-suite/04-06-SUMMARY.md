---
phase: "04"
plan: "06"
subsystem: calendar
tags:
  - calendar
  - ha-entity
  - tdd
  - ci-gate
dependency_graph:
  requires:
    - "04-02"  # heavy_class.json fixture + conftest heavy_class_snapshot
    - "04-03"  # PronoteEntity base with DeviceInfo.model
    - "04-04"  # PLATFORMS includes CALENDAR in const.py
  provides:
    - PronoteCalendar CalendarEntity
    - calendar platform async_setup_entry
    - test_calendar.py green
    - D-17 calendar CI gate in test_attribute_size.py
  affects:
    - custom_components/ha_pronote/strings.json
    - tests/test_attribute_size.py
tech_stack:
  added:
    - homeassistant.components.calendar.CalendarEntity (dual-inherit base)
    - homeassistant.components.calendar.CalendarEvent (dataclass)
    - homeassistant.util.slugify.slugify (uid stability — NOT python-slugify)
    - homeassistant.util.dt.now() (event property current-time gate)
  patterns:
    - "PronoteEntity + CalendarEntity dual inheritance (D-07)"
    - "object.__new__ pure-Python test pattern (revision fix — no hass dependency)"
    - "asyncio.get_event_loop().run_until_complete for sync test of async method"
key_files:
  created:
    - custom_components/ha_pronote/calendar.py
    - tests/test_calendar.py
  modified:
    - custom_components/ha_pronote/strings.json
    - tests/test_attribute_size.py
decisions:
  - "event property implemented (not deferred): RESEARCH confirmed CalendarEntity raises NotImplementedError if absent — mandatory"
  - "slugify from homeassistant.util.slugify (not python-slugify): HA entity-id consistency, A5 contract"
  - "end <= start degenerate guard: T-04-06c mitigation, Pitfall 6 — end forced to start + 1h"
  - "empty classroom → None: HA hides the location row; empty string causes confusing empty display"
  - "HA-integration tests skip via pytest.skip if entity_component unavailable — not load-bearing; pure-Python tests are the hard gates"
metrics:
  duration: "~20 min"
  completed: "2026-05-24"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 4 Plan 06: PronoteCalendar Entity Summary

**One-liner:** CalendarEntity with HA's slugify-based stable UIDs, cancelled-lesson ❌ prefix, and pure-Python D-17 size CI gate.

## Tasks Completed

| Task | Name | Files |
|------|------|-------|
| 1 (TDD) | Create calendar.py + extend strings.json + tests/test_calendar.py | `calendar.py`, `strings.json`, `tests/test_calendar.py` |
| 2 | Extend test_attribute_size.py with calendar size gate | `tests/test_attribute_size.py` |

## Implementation

### calendar.py

`PronoteCalendar(PronoteEntity, CalendarEntity)` — dual inheritance per D-07. Key design choices:

- `event` property: iterates `coordinator.data.lessons` sorted by start, returns first where `lesson.end > dt_util.now()`. Returns `None` for all-past windows. **Required** — CalendarEntity raises `NotImplementedError` if absent (RESEARCH Pitfall 1).
- `async_get_events(hass, start_date, end_date)`: date-level boundary comparison `start_date.date() <= lesson.date <= end_date.date()`. Pure in-memory, no I/O.
- `_lesson_to_event(lesson)`: maps Lesson → CalendarEvent. Summary has `❌ ` prefix when `lesson.canceled`. Description = `"Professeur: {teacher}"` + `"\nStatut: annulé"` when canceled. Location = `lesson.classroom or None`. UID = `pronote_{child_id}_{date}_{start.isoformat()}_{slugify(subject)}` — deterministic, stable across polls.

### strings.json

Added `entity.calendar.calendar.name = "Emploi du temps"` inside the `entity` block alongside the existing `sensor` block.

### tests/test_calendar.py

10 test functions covering:
- Pure-Python (no hass): `test_lesson_to_event_uid_stability`, `test_lesson_to_event_cancelled_description`, `test_lesson_to_event_active_description`, `test_lesson_to_event_empty_classroom_becomes_none`, `test_lesson_to_event_non_empty_classroom_preserved`, `test_async_get_events_returns_empty_for_no_lessons`, `test_event_property_returns_none_for_past_lessons`, `test_event_property_returns_next_lesson`
- HA-integration (with hass): `test_calendar_entity_created`, `test_async_get_events_range_filter`, `test_cancelled_lesson_has_x_prefix`

Revision-fix tests use `object.__new__(PronoteCalendar)` pattern to avoid hass dependency for correctness-critical paths.

### tests/test_attribute_size.py

Added two functions:
1. `test_calendar_event_size_pure_python` — **D-17 HARD GATE**: no hass, no `pytest.skip`, iterates all 128+ lessons through `_lesson_to_event`, asserts summary ≤ 255 chars, description ≤ 1024 chars, location ≤ 255 chars.
2. `test_calendar_events_within_limits_integration` — complementary HA-integration check (skip allowed — not the D-17 enforcer).

## Deviations from Plan

### Auto-implemented: event property (D-08 deferred → REQUIRED)

- **Found during:** Task 1 design
- **Issue:** CONTEXT.md D-08 said "No `event` property override in v1" but RESEARCH.md Pitfall 1 confirms CalendarEntity raises `NotImplementedError` if `event` is not implemented. Omitting it would crash any HA integration that instantiates the entity.
- **Fix:** Implemented `event` property returning first lesson where `end > now()` per the plan's interface spec in `<interfaces>` block. This matches the PLAN.md `must_haves` truth: "PronoteCalendar.event property returns current/next lesson as CalendarEvent or None (CalendarEntity base class requirement)".
- **Files modified:** `calendar.py`
- **Note:** The CONTEXT.md D-08 deferred section was superseded by the PLAN.md spec and RESEARCH Pitfall 1. The plan itself (must_haves) took precedence.

## Known Stubs

None — calendar.py is fully wired. All CalendarEvent fields populated from real Lesson data. The J-7→J+14 fetch window is hardcoded in the fetcher (Phase 2 lock); `async_get_events` returns `[]` for ranges outside that window — this is documented behavior, not a stub.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns beyond what the plan's `<threat_model>` already covers (T-04-06a, T-04-06b, T-04-06c all mitigated in implementation).

## Self-Check: PASSED

Files confirmed created/modified:
- `custom_components/ha_pronote/calendar.py` — CREATED (class PronoteCalendar with event property, async_get_events, _lesson_to_event, slugify import)
- `custom_components/ha_pronote/strings.json` — MODIFIED (entity.calendar.calendar.name added)
- `tests/test_calendar.py` — CREATED (10 tests, all required functions present)
- `tests/test_attribute_size.py` — MODIFIED (test_calendar_event_size_pure_python added without pytest.skip; MagicMock import added)
