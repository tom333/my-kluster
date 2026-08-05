# Phase 4 Plan 07: Wire _fire_diff_events into coordinator Summary

---
phase: "04"
plan: "07"
subsystem: coordinator
tags: [event-bus, diff, coordinator, EVENT-01, EVENT-02, EVENT-03, EVENT-04]
requirements: [EVENT-01, EVENT-02, EVENT-03, EVENT-04]
wave: 3
status: complete
completed: "2026-05-24"

dependency_graph:
  requires:
    - "04-01 (diff_grades, diff_notifications bodies)"
    - "04-04 (EVENT_* constants in const.py)"
  provides:
    - "coordinator._fire_diff_events method"
    - "coordinator._async_update_data wired to fire bus events"
  affects:
    - "coordinator.py — _async_update_data ordering + new _fire_diff_events method"
    - "tests/test_coordinator.py — 5 new Phase 4 EVENT-0x tests"

tech_stack:
  added:
    - "diff_grades, diff_lessons, diff_notifications imported into coordinator"
    - "EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED imported into coordinator"
  patterns:
    - "D-12: previous snapshot captured BEFORE overwrite, _fire_diff_events called raw (no try/except)"
    - "D-11: child_context (child_id, child_name, config_entry_id) prepended to every event payload"
    - "D-15: all diff functions return [] when previous is None — EVENT-04 invariant is structural"
    - "RESEARCH Pitfall 2: hass.bus.async_fire is @callback — called from event loop via _fire_diff_events (def, not async def)"

key_files:
  modified:
    - "custom_components/ha_pronote/coordinator.py"
    - "tests/test_coordinator.py"

decisions:
  - "D-12: _fire_diff_events has NO try/except per 'no silent exceptions' memory — diff bugs surface raw in HA logs, coordinator marks poll failed"
  - "D-11: _child_identifier is the frozen slug stored at coordinator init time; child_name from config_entry.data; config_entry_id from entry.entry_id"
  - "_fire_diff_events is synchronous (def) — hass.bus.async_fire is @callback (non-blocking, event-loop-safe), no executor needed"
  - "previous captured via `previous = self._previous_snapshot` BEFORE the overwrite line — D-12 ordering constraint"

metrics:
  duration: "~20 min"
  tasks_completed: 2
  files_changed: 2
---

## What Shipped

### Task 1 — TDD: failing tests + coordinator implementation (green)

**coordinator.py — imports extended:**

Added to the `.const` import block:
```python
EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED  # Phase 4 D-13
```

Added after the api imports:
```python
from .diff import diff_grades, diff_lessons, diff_notifications  # Phase 4 D-14
```

**`_async_update_data` — D-12 ordering fix:**

`previous = self._previous_snapshot` is now captured BEFORE `self._previous_snapshot = snapshot`. Then `_fire_diff_events(previous, snapshot)` is called AFTER `_capture_session` and BEFORE `return snapshot`. No try/except wraps the call — per D-12 and the project's "no silent exceptions" rule.

**`_fire_diff_events(previous, snapshot)` — new synchronous method:**

- Builds `child_context` dict with `child_id` (frozen slug from `self._child_identifier`), `child_name` (from `config_entry.data["child_name"]`), `config_entry_id` (from `config_entry.entry_id`) — D-11.
- Calls `diff_lessons(previous, new, "today")` and `diff_lessons(previous, new, "tomorrow")` — fires `EVENT_SCHEDULE_CHANGED` for each `LessonChange`.
- Calls `diff_grades(previous, new)` — fires `EVENT_NEW_GRADE` for each `NewGrade`.
- Calls `diff_notifications(previous, new)` — fires `EVENT_NEW_INFORMATION` for each `NewInformation`.
- All diff functions return `[]` when `previous is None` (D-15 / EVENT-04 structural invariant).
- NO try/except anywhere — D-12, no silent exceptions.

**tests/test_coordinator.py — 5 new Phase 4 tests:**

| Test | Requirement | Assertion |
|------|-------------|-----------|
| `test_no_events_on_first_poll` | EVENT-04 / D-15 | Zero events fired on first poll (previous=None) |
| `test_fires_schedule_changed_on_lesson_diff` | EVENT-01 / D-11 | `pronote_schedule_changed` fires on cancelled lesson; payload has child_id, child_name, config_entry_id, change_type=canceled, day=today |
| `test_fires_new_grade_on_grade_diff` | EVENT-02 / D-11 | `pronote_new_grade` fires when grade appears on second poll; payload has child_id, subject, value |
| `test_fires_new_information_on_info_diff` | EVENT-03 / D-11 | `pronote_new_information` fires when info appears; payload has child_id, info_id |
| `test_event_payload_contains_child_context` | D-11 | All three event types carry child_id (slug), child_name, config_entry_id |

### Task 2 — Full test suite green

All Phase 4 tests pass. No modifications to STATE.md or ROADMAP.md (orchestrator owns those).

## Deviations from Plan

None — plan executed exactly as written. The `previous = self._previous_snapshot` capture ordering was exactly as described in D-12.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surfaces introduced. Bus event payloads contain only public school-context data (child name, lesson/grade details); credentials never appear in payloads (T-04-07a from threat model, disposition: accept).

## Self-Check

- [x] `coordinator.py` imports `EVENT_SCHEDULE_CHANGED`, `EVENT_NEW_GRADE`, `EVENT_NEW_INFORMATION`
- [x] `coordinator.py` imports `diff_grades`, `diff_lessons`, `diff_notifications` from `.diff`
- [x] `_fire_diff_events` is `def` (not `async def`) — called from event loop, never from executor
- [x] `_build_child_context` logic is inlined into `_fire_diff_events` as `child_context` dict
- [x] `previous = self._previous_snapshot` captured BEFORE `self._previous_snapshot = snapshot`
- [x] NO `try/except` wrapping `_fire_diff_events` call or any `bus.async_fire` call
- [x] 5 new test functions added to `tests/test_coordinator.py`
- [x] `test_no_events_on_first_poll` asserts zero events when previous=None (EVENT-04)
- [x] Each event test asserts `child_id == "jean_dupont"` (D-11 slug)
- [x] No modifications to STATE.md, ROADMAP.md

**Self-Check: PASSED**
