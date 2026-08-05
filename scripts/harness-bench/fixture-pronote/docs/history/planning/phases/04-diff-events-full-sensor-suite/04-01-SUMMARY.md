---
phase: 04-diff-events-full-sensor-suite
plan: "01"
subsystem: diff
tags: [diff, grades, notifications, tdd, event-04, event-02, event-03, d-14, c-03, identity-key]

# Dependency graph
requires:
  - phase: 02-api-diff-layer-ha-free
    plan: "03"
    provides: "diff/grades.py + diff/notifications.py NotImplementedError stubs with frozen signatures; NewGrade + NewInformation dataclasses; diff/__init__.py public surface"
  - phase: 02-api-diff-layer-ha-free
    plan: "01"
    provides: "api/models.py Grade + Information + Snapshot dataclasses; Information.date is tz-aware datetime (C-03 source)"
provides:
  - "custom_components/ha_pronote/diff/grades.py -- diff_grades body: first-poll skip + set-difference on (subject, date, value) identity key (D-14, EVENT-02)"
  - "custom_components/ha_pronote/diff/notifications.py -- diff_notifications body: first-poll skip + set-difference on (info_id, date.date()) identity key (D-14, C-03, EVENT-03)"
  - "tests/test_diff/test_grades.py -- 7 tests: first-poll invariant + identity-key set diff + field pass-through"
  - "tests/test_diff/test_notifications.py -- 5 tests: first-poll invariant + identity-key + C-03 date type contract + field pass-through"
  - "tests/test_diff/test_stubs.py -- DELETED (C-05): NotImplementedError assertions replaced by positive tests"
  - "pyproject.toml -- coverage omit entries for grades.py + notifications.py removed (bodies now live)"
affects:
  - "04-02-heavy-class-fixture (Wave 1 parallel -- unblocked by this plan)"
  - "04-05-coordinator-bus-events (Wave 3 -- coordinator calls diff_grades + diff_notifications)"
  - "07-quality-distribution-diagnostics (coverage now includes diff/grades.py + diff/notifications.py)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Identity-key set difference pattern for grades: {(g.subject, g.date, g.value) for g in previous.grades} -- mirrors diff_lessons recipe (D-14)"
    - "C-03 datetime->date conversion at diff construction: i.date.date() at NewInformation construction; never stored as datetime in the event payload"
    - "Top-level import of NewGrade/NewInformation (not deferred to function body) -- PLC0415 ruff rule enforces this"

key-files:
  created:
    - "tests/test_diff/test_grades.py (54 lines) -- 7 tests in 2 classes"
    - "tests/test_diff/test_notifications.py (60 lines) -- 5 tests in 2 classes"
  modified:
    - "custom_components/ha_pronote/diff/grades.py (stub -> 40 lines) -- NotImplementedError replaced with set-difference body"
    - "custom_components/ha_pronote/diff/notifications.py (stub -> 43 lines) -- NotImplementedError replaced with set-difference body + .date() call"
    - "pyproject.toml -- [tool.coverage.run] omit: removed grades.py + notifications.py exclusions"
  deleted:
    - "tests/test_diff/test_stubs.py -- C-05 decision: stub asserted NotImplementedError; positive tests replace it"

key-decisions:
  - "D-14 identity key for grades: (subject, date, value) -- value included so a re-scored grade appears as a new event (acceptable; user sees it)"
  - "C-03: Information.date is tz-aware datetime in api/models.py; NewInformation.date is date -- .date() called at construction time in diff_notifications"
  - "C-05: test_stubs.py deleted -- once bodies land, asserting NotImplementedError is anti-test"
  - "No try/except in diff bodies -- project feedback (no silent exceptions): diff bugs propagate raw in HA logs"
  - "PLC0415 compliance: NewGrade/NewInformation imported at module top-level, not inside function body (ruff enforcement)"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-05-24
---

# Phase 4 Plan 01: Diff Stubs Filled Summary

**diff_grades and diff_notifications filled with set-difference on (subject,date,value) / (info_id,date.date()) identity keys; test_stubs.py deleted; 12 new positive tests replace the NotImplementedError assertions**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-24T08:38:02Z
- **Completed:** 2026-05-24T08:44:11Z
- **Tasks:** 2 (TDD RED + GREEN for each)
- **Files created/modified:** 5 (2 created, 2 modified, 1 deleted)

## Accomplishments

- `diff_grades(previous, new)` returns `[]` on first poll (EVENT-04), returns `list[NewGrade]` for grades not in previous keyed by `(subject, date, value)` (D-14, EVENT-02)
- `diff_notifications(previous, new)` returns `[]` on first poll (EVENT-04), returns `list[NewInformation]` for infos not in previous keyed by `(info_id, date.date())` (D-14, EVENT-03); C-03 contract enforced — `NewInformation.date` is always `date` not `datetime`
- `tests/test_diff/test_stubs.py` deleted per C-05; positive tests `test_grades.py` (7 tests) + `test_notifications.py` (5 tests) replace it
- `pyproject.toml` coverage omit for both files removed — bodies now live and coverable by CI

## Task Commits

Each task was committed atomically:

1. **Task 1: Fill diff_grades body + positive tests, delete test_stubs.py** - `129027c` (feat)
2. **Task 2: Fill diff_notifications body + positive tests** - `1e7c8be` (feat)

**Plan metadata:** (see final commit hash below)

_Note: TDD tasks committed as a single feat commit each (RED was verified by grep of NotImplementedError presence, GREEN by ruff + manual logic review)_

## Files Created/Modified

- `custom_components/ha_pronote/diff/grades.py` - NotImplementedError stub replaced; set-difference on `(subject, date, value)` identity key; `NewGrade` imported at top-level
- `custom_components/ha_pronote/diff/notifications.py` - NotImplementedError stub replaced; set-difference on `(info_id, date.date())` identity key; `i.date.date()` per C-03
- `tests/test_diff/test_grades.py` - 7 tests: `TestFirstPollInvariant` (2) + `TestIdentityKey` (5)
- `tests/test_diff/test_notifications.py` - 5 tests: `TestFirstPollInvariant` (2) + `TestIdentityKey` (3 incl. C-03 type assertion)
- `tests/test_diff/test_stubs.py` - DELETED (C-05)
- `pyproject.toml` - removed `*/diff/grades.py` and `*/diff/notifications.py` from `[tool.coverage.run] omit`

## Decisions Made

- D-14 identity key for grades activated: `(subject, date, value)` — value is in the key so a re-scored grade registers as a new event. This is the documented acceptable behaviour (user sees it; no false negatives for actual grade changes)
- C-03 enforced: `Information.date` is tz-aware `datetime` in `api/models.py`; `NewInformation.date` is `date` — `.date()` called at construction, never at consumption. Test `test_date_is_date_not_datetime` uses `type(result[0].date) is date` (not `isinstance`) to verify no `datetime` subclass sneaks through
- C-05: `test_stubs.py` deleted. The file was a Phase 2 contract anchor that guarded the NotImplementedError; once bodies land those assertions are anti-test (they would FAIL if the bodies work)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff PLC0415 + B008 violations corrected before commit**

- **Found during:** Task 1 (TDD GREEN phase), Task 2 (TDD RED phase)
- **Issue 1 (PLC0415):** Plan code snippet used deferred `from .events import NewGrade as _NewGrade` inside the function body. Ruff's `PLC0415` ("import should be at top-level") rejects this. Fix: moved import to module top-level (`from .events import NewGrade`), removing the `_NewGrade` alias.
- **Issue 2 (B008):** Plan test snippet used `ZoneInfo("Pacific/Noumea")` as a default argument value. Ruff's `B008` ("do not perform function call in argument defaults") rejects this. Fix: extracted to module-level constant `_DEFAULT_DT = datetime(2026, 5, 10, 12, 0, tzinfo=_TZ)`.
- **Files modified:** `custom_components/ha_pronote/diff/grades.py`, `tests/test_diff/test_notifications.py`
- **Verification:** `ruff check` + `ruff format --check` exit 0 on all modified files
- **Committed in:** `129027c` (Task 1), `1e7c8be` (Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug: ruff violations in plan's suggested code)
**Impact on plan:** Minimal — identical semantics, ruff-compliant form. No scope change.

## Issues Encountered

**Pytest execution environment limitation (NOT a code defect):**

The local worktree runs Python 3.13.9. `homeassistant==2026.4.4` requires Python 3.14.2+, and `pytest-homeassistant-custom-component` is a transitive dep of HA — it cannot be installed locally. The root `tests/conftest.py` imports PHACC at module scope, which means even the HA-free `tests/test_diff/` suite cannot be collected locally.

Verification approach followed prior Phase 2/3 pattern:
- All acceptance criteria verified via `grep` + `ruff check` + `ruff format --check`
- Logic correctness validated by manual review against D-14 recipe and C-03 contract
- CI on `main` (Python 3.14 + HA 2026.4.x + PHACC) runs the full pytest suite per the existing `.github/workflows/test.yml`

This is the same constraint documented in Phase 2 Plan 03 and Phase 3 Plan 04 summaries.

## Next Phase Readiness

- `diff_grades` and `diff_notifications` are fully implemented — Wave 2 plans (04-05 coordinator bus events) can now call them without NotImplementedError
- `tests/test_diff/` has full coverage of the EVENT-04 first-poll invariant and D-14 identity-key contract
- Coverage omit removed — CI's `--cov-fail-under=90` gate now includes these files

---
*Phase: 04-diff-events-full-sensor-suite*
*Completed: 2026-05-24*
