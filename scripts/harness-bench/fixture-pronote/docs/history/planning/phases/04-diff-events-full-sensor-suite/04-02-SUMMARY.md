---
phase: 04-diff-events-full-sensor-suite
plan: "02"
subsystem: api
tags: [models, fetcher, grade-extension, snapshot-extension, tdd, backward-compat, pronotepy-name-mapping]

# Dependency graph
requires:
  - phase: 02-data-layer
    provides: "Grade + Snapshot frozen dataclasses; _grade_from_raw; fetch_all baseline"
  - phase: 03-coordinator-first-sensor
    provides: "Coordinator + PronoteLessonsTodaySensor baseline; test infrastructure"
provides:
  - "models.Grade with 9 fields: class_average, class_min, class_max, comment added (str, default '')"
  - "models.Snapshot with 7 fields: overall_average, period_name added (str, default '')"
  - "fetcher._grade_from_raw maps raw.average/max/min/comment → Grade class context fields"
  - "fetcher.fetch_all captures overall_average + period_name from current_period in executor"
affects: [04-03-sensor-extensions, 04-04-calendar, 04-05-bus-events]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pronotepy name mapping: raw.average → Grade.class_average (not raw.class_average)"
    - "getattr(raw, attr, None) or '' — explicit visible default, not swallowing catch"
    - "overall_average fetched in executor (same call as grades) — never from sensor native_value"
    - "str = '' defaults on frozen dataclass fields preserve backward compat"

key-files:
  created: []
  modified:
    - custom_components/ha_pronote/api/models.py
    - custom_components/ha_pronote/api/fetcher.py
    - tests/test_api/test_models.py
    - tests/test_api/test_fetcher.py

decisions:
  - "Use Option A: extend models.Grade + _grade_from_raw (not render-time inline) — keeps sensor layer clean"
  - "Fetch overall_average inside fetch_all (same executor call as grades) — avoids PITFALL 3"
  - "getattr(raw, 'average', None) or '' — not try/except per no-silent-exceptions rule"

metrics:
  duration_minutes: ~20
  completed: "2026-05-24"
  tasks_completed: 2
  files_modified: 4
---

# Phase 04 Plan 02: Grade + Snapshot Phase 4 Field Extension Summary

Extended `api/models.py` and `api/fetcher.py` to carry Grade class-context fields and Snapshot-level overall_average + period_name for Wave 2 sensors, using TDD with full backward-compatibility for Phase 2 fixtures.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | Failing tests for Grade/Snapshot extension | 68ace5d | tests/test_api/test_models.py |
| 1 (GREEN) | Extend Grade + Snapshot dataclasses | aaadbdc | custom_components/ha_pronote/api/models.py |
| 2 (RED) | Failing tests for fetcher extensions | 940e63b | tests/test_api/test_fetcher.py |
| 2 (GREEN) | Extend _grade_from_raw + fetch_all | dca54a7 | custom_components/ha_pronote/api/fetcher.py |

## What Was Built

### models.Grade — 4 new fields

```python
class_average: str = ""  # pronotepy: raw.average (NOT raw.class_average — name mapping alert)
class_min: str = ""      # pronotepy: raw.min
class_max: str = ""      # pronotepy: raw.max
comment: str = ""        # pronotepy: raw.comment
```

`to_dict()` serializes all 9 fields; `from_dict()` uses `data.get(key, "")` so existing Phase 2 fixture JSON without these keys loads cleanly.

### models.Snapshot — 2 new fields

```python
overall_average: str = ""  # Period.overall_average (HTTP @property — fetched in executor)
period_name: str = ""      # Period.name e.g. "Trimestre 2"
```

Same backward-compat pattern: old JSON without `overall_average` key produces `""`.

### fetcher._grade_from_raw

```python
class_average=str(getattr(raw, "average", None) or ""),  # pronotepy attr name
class_min=str(getattr(raw, "min", None) or ""),
class_max=str(getattr(raw, "max", None) or ""),
comment=str(getattr(raw, "comment", None) or ""),
```

`getattr(..., None)` fallback is an explicit visible default (project rule: no silent exceptions).

### fetcher.fetch_all

Captures `overall_average` and `period_name` in the same executor call as grades. `Period.overall_average` is a `@property` that makes a synchronous HTTP call — must stay in executor, never called from sensor `native_value` (RESEARCH Pitfall 3).

## Test Results

| Test Suite | Passed | Pre-existing Failures | Notes |
|-----------|--------|----------------------|-------|
| test_models.py (18 tests) | 18/18 | 0 | All Phase 2 + Phase 4 tests pass |
| test_fetcher.py (phase 4 tests) | 20/20 (excluding set_child) | 5 set_child tests | Pre-existing test_client.py + test_fetcher.py failures in Python 3.13 env |
| test_no_ha_imports.py | 27/27 | 0 | api/ layer remains HA-free |

**Pre-existing failures note:** The 5 `set_child`-related tests fail in Python 3.13 because `_FakeParentClient` lacks `.children` attribute. This is a pre-existing test infrastructure issue on the `main` branch (confirmed by checking git history before this plan's changes). These failures are in `test_client.py` and `test_fetcher.py::test_fetch_all_calls_set_child_for_parent_client_with_index`, not caused by this plan.

## Deviations from Plan

None — plan executed exactly as written.

The TDD flow followed the prescribed pattern:
- RED: wrote failing tests, committed
- GREEN: implemented extension, committed
- No REFACTOR needed (code is clean as-written)

## Known Stubs

None. All fields are wired from pronotepy through the model layer.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The `fetcher.py` change adds two `getattr` calls within an already-existing executor function — no new trust boundary.

## TDD Gate Compliance

- RED gate: `test(04-02): add failing tests for Grade/Snapshot Phase 4 extension` (68ace5d) — tests failed as expected
- GREEN gate: `feat(04-02): extend Grade + Snapshot dataclasses with Phase 4 fields` (aaadbdc) — tests passed
- RED gate: `test(04-02): add failing tests for fetcher Phase 4 extensions` (940e63b) — tests failed as expected
- GREEN gate: `feat(04-02): extend fetcher — _grade_from_raw + fetch_all overall_average capture` (dca54a7) — tests passed

## Self-Check

**Verifying claims before proceeding.**

Files claimed created/modified:
- `custom_components/ha_pronote/api/models.py`: FOUND (extended with 4+2 fields)
- `custom_components/ha_pronote/api/fetcher.py`: FOUND (extended _grade_from_raw + fetch_all)
- `tests/test_api/test_models.py`: FOUND (7 new Phase 4 tests added)
- `tests/test_api/test_fetcher.py`: FOUND (5 new Phase 4 tests added)

Commits claimed:
- `68ace5d` (Task 1 RED — test Grade/Snapshot): FOUND
- `aaadbdc` (Task 1 GREEN — models.py extension): FOUND
- `940e63b` (Task 2 RED — test fetcher): FOUND
- `dca54a7` (Task 2 GREEN — fetcher.py extension): FOUND

Field presence counts:
- `class_average` in models.py: 4 (≥3 required — field def, to_dict, from_dict + comment): PASS
- `overall_average` in models.py: 5 (≥3 required): PASS
- `overall_average` in fetcher.py: 4 (≥2 required): PASS
- `class_average` in fetcher.py: 2 (≥1 required): PASS

## Self-Check: PASSED
