---
phase: 04-diff-events-full-sensor-suite
plan: "05"
subsystem: sensor
tags:
  - sensor
  - grades
  - notifications
  - lessons
  - TIME-02
  - GRADE-01
  - GRADE-02
  - GRADE-03
  - NOTIF-01
  - NOTIF-02
dependency_graph:
  requires:
    - 04-02 (Snapshot.grades/information/overall_average/period_name model fields)
    - 04-03 (heavy_class.json fixture + PHASE-4-PROBE-NOTES.md)
    - 04-04 (const.py NOTIFICATIONS_WINDOW/GRADE_COMMENT_MAX_LEN + entity.py base)
  provides:
    - PronoteLessonsTodaySensor TIME-02 attributes (lessons_today/lessons_tomorrow)
    - PronoteGradesSensor (GRADE-01/02/03)
    - PronoteNotificationsSensor (NOTIF-01/02)
    - tests/test_attribute_size.py CI gate (D-17)
  affects:
    - sensor.py (all 3 sensors)
    - strings.json (2 new entity keys)
    - tests/test_sensor.py (TIME-02 attrs + grades + notifications coverage)
    - tests/test_attribute_size.py (new CI gate)
    - tests/conftest.py (heavy_class_snapshot fixture)
tech_stack:
  added: []
  patterns:
    - _to_float() typed conversion guard (comma->dot, ValueError->None)
    - extra_state_attributes with 16 KiB discipline (D-17)
    - Lessons sorted ascending, grades/infos sorted descending (D-06)
    - NOTIFICATIONS_WINDOW cap (top-20 slice on informations list)
    - GRADE_COMMENT_MAX_LEN truncation (200 chars)
    - str(title or "") for nullable str fields (probe STEP 7)
key_files:
  created:
    - tests/test_attribute_size.py
  modified:
    - custom_components/ha_pronote/sensor.py
    - custom_components/ha_pronote/strings.json
    - tests/conftest.py
    - tests/test_sensor.py
decisions:
  - _to_float returns None for empty string AND non-numeric (ValueError guard, not swallowing)
  - PronoteGradesSensor.native_value has explicit -1 sentinel guard separate from _to_float
  - Information.title serialised as str(title or "") in attributes (probe finding: title can be None)
  - entity_id fragments: "lessons_today" / "notes" / "notifications" (from strings.json name fields)
  - test_sensor_no_lessons_attribute_in_state replaced with test_time02_attrs_present (Phase 3->Phase 4 ownership transfer)
metrics:
  duration: ~25min
  completed: 2026-05-24
  tasks_completed: 2
  tasks_total: 2
  files_modified: 5
---

# Phase 04 Plan 05: Sensor Suite Summary

**One-liner:** Three-sensor suite with TIME-02 J/J+1 lesson attrs, PronoteGradesSensor (comma-decimal float + ApexCharts grades list), PronoteNotificationsSensor (unread count + top-20 informations), and D-17 CI gate asserting 16 KiB attribute discipline on the heavy_class fixture.

## What shipped

### Task 1 — Sensor extensions + conftest fixtures + strings.json

**`custom_components/ha_pronote/sensor.py`** — extended with:

1. **`_to_float(raw: str) -> float | None`** — module-level typed conversion guard. Comma-to-dot normalisation for Pronote's French decimal format ("14,50" → 14.5). Returns `None` for empty strings and non-numeric strings (`except ValueError`). This is a typed conversion guard, NOT a swallowing catch — per "no silent exceptions" memory, the ValueError is for the string→float conversion only.

2. **`PronoteLessonsTodaySensor.extra_state_attributes`** (TIME-02) — returns `{"lessons_today": [...], "lessons_tomorrow": [...]}`, each a sorted list of `Lesson.to_dict()` dicts (8 keys: date, start, end, subject, teacher, classroom, canceled, status). Sorted by `start` ascending (D-06).

3. **`PronoteGradesSensor`** (GRADE-01/02/03):
   - `translation_key = "grades"` → strings.json name "Notes" → entity_id `sensor.{child}_notes`
   - `native_value`: `float(overall_average.replace(",", "."))` with guards for `""` and `"-1"` → both return `None` (HA shows "unknown")
   - `extra_state_attributes`: `{"period_name": str, "grades": [{date, subject, grade, out_of, coefficient, class_average, class_min, class_max, comment(≤200)}, ...]}`, sorted newest-first (D-06)

4. **`PronoteNotificationsSensor`** (NOTIF-01/02):
   - `translation_key = "notifications"` → entity_id `sensor.{child}_notifications`
   - `native_value`: `sum(1 for i in information if not i.read)`
   - `extra_state_attributes`: `{"unread_count": int, "informations": [{info_id, title, sender, date, excerpt, read}, ...]}`, capped at `NOTIFICATIONS_WINDOW=20` most recent by date desc (D-05/D-06). `title` serialised as `str(title or "")` (probe STEP 7: title may be None)

5. **`async_setup_entry`** — updated to register all 3 sensors.

**`custom_components/ha_pronote/strings.json`** — `entity.sensor` block extended with:
- `"grades": {"name": "Notes"}`
- `"notifications": {"name": "Notifications"}`

**`tests/conftest.py`** — two new fixtures appended:
- `heavy_class_snapshot` — loads `tests/fixtures/synthetic/heavy_class.json` as `Snapshot.from_dict`. Used by CI gate.
- `mock_pronote_client_with_grades` — extends `mock_pronote_client` with `overall_average="14,50"`, `period_name="Trimestre 2"`, one synthetic grade (shape matches probe STEP 6 docs).

### Task 2 — CI gate `tests/test_attribute_size.py` (D-17)

New file: `tests/test_attribute_size.py`

Parametrised over all 3 sensors against `heavy_class_snapshot` (128 lessons, 100 grades, 30 infos). For each sensor:

1. `state not in (None, "unknown", "unavailable")` — verifies sensor has valid state on the heavy-class fixture
2. `len(str(state)) <= 255` — HA state machine limit
3. `len(json.dumps(attrs, default=str).encode("utf-8")) <= 16384` — HA recorder limit (MAX_ATTRS_BYTES = 16384)

**No `pytest.skip` paths.** HARD CI fail on any breach.

### `tests/test_sensor.py` extensions

- Replaced `test_sensor_no_lessons_attribute_in_state` (Phase 3 lock: "no attrs") with:
  - `test_time02_attrs_present` — lessons_today + lessons_tomorrow keys present
  - `test_time02_lessons_today_dict_shape` — 8-key schema per lesson (D-02)
- Added `_to_float` unit tests (4 tests)
- Added `PronoteGradesSensor` tests:
  - `test_grades_sensor_state_float` — "14,50" → state "14.5"
  - `test_grades_sensor_state_none_when_empty` — "" → "unknown"
  - `test_grades_sensor_state_none_when_minus_one` — "-1" → "unknown"
  - `test_grades_attrs_schema` — 9-key schema per grade (D-04)
  - `test_grades_attrs_comment_truncated` — 300-char comment → 200-char cap
  - `test_grades_sorted_newest_first` — D-06 sort order verified
- Added `PronoteNotificationsSensor` tests:
  - `test_notifications_sensor_state_unread_count` — 2 unread → state "2"
  - `test_notifications_sensor_state_all_read` — 0 unread → state "0"
  - `test_notifications_attrs_schema` — 6-key schema per info (D-05)
  - `test_notifications_attrs_capped_at_20` — 30 infos → only 20 in attrs
  - `test_notifications_attrs_sorted_newest_first` — D-06 sort order
  - `test_notifications_title_none_serialised_as_empty_string` — probe STEP 7 guard

## Deviations from Plan

### Deviation 1 (plan text vs implementation)

**Found during:** Task 1, implementing `_make_snapshot_with_grades` test helper.

**Issue:** Plan action says `from datetime import date` import "if not present" — the import was already there.

**Fix:** No action needed. Non-issue.

### Deviation 2 (test coverage — Rule 2: missing critical functionality)

**Added `test_to_float_minus_one`** to explicitly document that `_to_float("-1")` returns `-1.0` (NOT `None`) — and that the `-1` sentinel guard lives in `PronoteGradesSensor.native_value`, not in `_to_float`. This makes the separation of concerns explicit and prevents future confusion where someone might "fix" `_to_float` to return `None` for "-1" and break the dual-responsibility.

### Deviation 3 (test cleanup — Rule 1: Phase 3 lock removal)

**`test_sensor_no_lessons_attribute_in_state`** was a Phase 3 lock asserting "no TIME-02 attrs yet." Phase 4 delivers TIME-02 attrs, so this test would now fail. Replaced with `test_time02_attrs_present` + `test_time02_lessons_today_dict_shape` (positive Phase 4 assertions). This is the planned ownership transfer documented in 04-04-SUMMARY.md.

### No other deviations — plan executed as written.

## Known Stubs

None. All 3 sensors read from `coordinator.data` (the `Snapshot` object), which is populated by `fetch_all` in the executor. No hardcoded values, no placeholder states.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The sensor layer is read-only from coordinator data. The `_to_float` helper and `str(title or "")` guard are defensive normalisations at the HA boundary, not trust-boundary expansions.

## Self-Check

Bash not available in this agent context (permission denied). File verification via Read tool:

- [x] `custom_components/ha_pronote/sensor.py` — `PronoteGradesSensor`, `PronoteNotificationsSensor`, `_to_float`, `extra_state_attributes` on lessons sensor, 3-sensor `async_setup_entry` confirmed
- [x] `custom_components/ha_pronote/strings.json` — `grades` and `notifications` keys present
- [x] `tests/conftest.py` — `heavy_class_snapshot` and `mock_pronote_client_with_grades` fixtures present
- [x] `tests/test_sensor.py` — TIME-02, grades, notifications tests present; Phase 3 lock test removed
- [x] `tests/test_attribute_size.py` — new file, `MAX_ATTRS_BYTES = 16384`, 3 parametrized cases, no pytest.skip
- [x] No modifications to STATE.md or ROADMAP.md

## Self-Check: NOTE — NO BASH

Bash permission was denied for this agent. Commits and test runs could not be performed in-agent. The orchestrator must:

1. Run the HEAD assertion
2. Stage and commit changed files
3. Run `uv run pytest tests/test_sensor.py tests/test_attribute_size.py -x -q`
4. Create the final metadata commit

**Files to commit (Task 1):**
- `custom_components/ha_pronote/sensor.py`
- `custom_components/ha_pronote/strings.json`
- `tests/conftest.py`
- `tests/test_sensor.py`

**Files to commit (Task 2):**
- `tests/test_attribute_size.py`
