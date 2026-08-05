---
phase: 02-api-diff-layer-ha-free
plan: 03
subsystem: diff
tags: [pronotepy, diff, identity-key, content-key, change-type, bain3-311, ha-free]

# Dependency graph
requires:
  - phase: 02-api-diff-layer-ha-free / 02-01
    provides: |
      api/__init__ + api/models (Snapshot, Lesson, Grade, Information frozen
      dataclasses with from_dict/to_dict round-trip and lessons_today/tomorrow
      slice properties).
  - phase: 02-api-diff-layer-ha-free / 02-02
    provides: |
      tests/fixtures/SPIKE-FINDINGS-bain3-311.md (S-04 acknowledged gap +
      identity-vs-content split locked) and 6 anonymized real-Pronote fixture
      pairs at tests/fixtures/real/.
provides:
  - "diff/events.py: ChangeType (4-value Literal) + DayLabel (2-value Literal) + 3 frozen dataclasses (LessonChange, NewGrade, NewInformation) with JSON-serializable to_payload() (ARCHITECTURE.md Pattern 3)."
  - "diff/lessons.py: identity-vs-content algorithm (D-08, D-09) -- discriminates canceled / room / teacher / modified, honours first-poll invariant + reorder no-op + day-window filter."
  - "diff/grades.py + diff/notifications.py: type-locked stubs (D-02) raising NotImplementedError; Phase 4 fills the bodies."
  - "diff/__init__.py: single import surface (C-01) re-exporting types + 3 functions."
  - "tests/fixtures/synthetic/{empty_to_empty,reorder_no_op,multi_change,first_poll_after_restart,lesson_removed,lesson_added}*.json + _README.md -- 11 round-trip-clean combinatorics fixtures (D-10, D-11, D-23)."
  - "tests/test_diff/{conftest,test_events,test_stubs,test_fixtures_roundtrip,test_lessons,test_lessons_synthetic}.py -- 65 tests (60 pass + 5 documented skips)."
affects:
  - 02-04-tz-matrix-and-coverage-gates
  - 04-sensors-events
  - 07-quality-distribution-diagnostics

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single import surface (C-01): diff/__init__.py re-exports the full Phase 4 contract from one path."
    - "Identity-vs-content split for diff: identity = (date, start_time, end_time, subject); content = (canceled, classroom, teacher). Status excluded from content (drift without cause)."
    - "Frozen 4-value taxonomy gated by a one-line typing.get_args(ChangeType) test -- adding a 5th value fails CI."
    - "Real-fixture diff tests skip with explicit S-04 message when T0 vs T1 lessons are byte-identical -- the scaffolding stays ready for the day a real schedule change is captured (Phase 4 gate)."
    - "Synthetic-fixture authoring as Python code -> json.dumps round-trip: every fixture is generated from typed Lesson constructors, so a refactor of the dataclass forces a fixture refresh in CI."

key-files:
  created:
    - "custom_components/ha_pronote/diff/__init__.py"
    - "custom_components/ha_pronote/diff/events.py"
    - "custom_components/ha_pronote/diff/lessons.py"
    - "custom_components/ha_pronote/diff/grades.py"
    - "custom_components/ha_pronote/diff/notifications.py"
    - "tests/fixtures/synthetic/_README.md"
    - "tests/fixtures/synthetic/empty_to_empty_T0.json"
    - "tests/fixtures/synthetic/empty_to_empty_T1.json"
    - "tests/fixtures/synthetic/reorder_no_op_T0.json"
    - "tests/fixtures/synthetic/reorder_no_op_T1.json"
    - "tests/fixtures/synthetic/multi_change_T0.json"
    - "tests/fixtures/synthetic/multi_change_T1.json"
    - "tests/fixtures/synthetic/first_poll_after_restart.json"
    - "tests/fixtures/synthetic/lesson_removed_T0.json"
    - "tests/fixtures/synthetic/lesson_removed_T1.json"
    - "tests/fixtures/synthetic/lesson_added_T0.json"
    - "tests/fixtures/synthetic/lesson_added_T1.json"
    - "tests/test_diff/__init__.py"
    - "tests/test_diff/conftest.py"
    - "tests/test_diff/test_events.py"
    - "tests/test_diff/test_stubs.py"
    - "tests/test_diff/test_fixtures_roundtrip.py"
    - "tests/test_diff/test_lessons.py"
    - "tests/test_diff/test_lessons_synthetic.py"
  modified: []

key-decisions:
  - "Diff layer cancel/room/teacher classification is built against documented pronotepy model + synthetic fixtures only -- no empirical T0->T1 lessons-diff in Phase 2 (S-04). Phase 4's first real schedule change is the verification gate."
  - "Algorithm decision step 4 (lesson disappeared from day's slice): SILENT. Frozen 4-value taxonomy has no `removed`. SPIKE-FINDINGS S-04 ambiguity ('cannot empirically distinguish a real removal from a polling race') plus the api/ Snapshot.lessons_today filter (D-16) means period-rollover noise never reaches the diff."
  - "Algorithm decision step 5 (lesson appeared in day's slice): SILENT. Mid-week scheduling additions are normal and not change events from a parent's perspective."
  - "bain3#311 paired-lesson case (Option A/B/C): chose the SIMPLE dict-by-identity approach (Option B/C). SPIKE-FINDINGS could not empirically verify Option A; defensive coding is reserved for the day duplicates surface."
  - "Status field excluded from the content key. SPIKE-FINDINGS S-04 documents that pronotepy maps Pronote's indicateurAbsence onto Lesson.canceled, while status is a free-form label that drifts without a material change. Using it would produce noisy modified events with no actionable cause."
  - "True->False on canceled emits `modified`, not `canceled`. The latter is reserved for the False->True flip. Locked by tests/test_diff/test_lessons_synthetic.py::test_lesson_uncanceled_emits_modified_change."
  - "Real-fixture tests skip (rather than fail) when T0/T1 lessons are byte-identical. Plan 02-02 captured 6 PII-clean fixtures whose lessons arrays match exactly (S-04). The scaffolding remains in place for Phase 4."

patterns-established:
  - "Spike-findings-driven implementation: the algorithm cites SPIKE-FINDINGS-bain3-311.md sections in code comments + summary frontmatter. Future plans MUST update SPIKE-FINDINGS first if a refinement lands; the diff code amends to match."
  - "Coverage-as-acceptance: ≥90% coverage on diff/lessons.py is a plan-level gate, verified by `pytest --cov=...lessons --cov-fail-under=90` at execution time. Achieved 100%."
  - "Per-test-tree autouse override: tests/test_diff/conftest.py defines a no-op `auto_enable_custom_integrations` fixture to neutralise the root PHACC autouse, mirroring tests/test_api/conftest.py. Pure-Python tests run without the HA harness."

requirements-completed: [EVENT-05]

# Metrics
duration: ~45min
completed: 2026-05-06
---

# Phase 2 Plan 03: Diff Layer Summary

**Identity-vs-content diff algorithm produced over Snapshot, with frozen 4-value `change_type` taxonomy, 100% coverage, and 11 synthetic fixtures backing the combinatorics edge cases.**

## Performance

- **Duration:** ~45 min (3 TDD cycles + ruff/format passes + coverage verification + summary)
- **Started:** 2026-05-06T08:00:00Z (orchestrator handoff)
- **Completed:** 2026-05-06T08:42:00Z
- **Tasks:** 3 (each in TDD RED -> GREEN, 6 commits total)
- **Files created:** 24 (5 production .py + 11 synthetic fixtures + 1 _README.md + 7 test files)
- **Files modified:** 0 (no existing api/ or root-level files touched)

## Accomplishments

- **`diff_lessons(previous, new, day) -> list[LessonChange]`** -- pure function honouring D-08 first-poll invariant, Pitfall 10 reorder no-op, frozen D-09 taxonomy, day-window filter via `Snapshot.lessons_today` / `lessons_tomorrow` (D-16). 100% line coverage on the module.
- **3 frozen event dataclasses** (`LessonChange`, `NewGrade`, `NewInformation`) with JSON-serializable `to_payload()` matching ARCHITECTURE.md Pattern 3 -- the exact shape Phase 4's coordinator forwards onto `hass.bus.async_fire`.
- **11 hand-crafted synthetic fixtures + _README.md** covering every combinatorics edge case the real spike (Plan 02-02 S-04) cannot reproduce on demand. All round-trip cleanly through `Snapshot.from_dict` / `to_dict`.
- **65-test diff suite** (60 pass + 5 documented skips). The 4 real-fixture skips are the explicit S-04 carryover; the 1 missing-fixture skip is the safety net for partial spikes.

## Task Commits

1. **Task 1 RED: `15f49dd`** -- failing tests for `diff/events.py` + stubs.
2. **Task 1 GREEN: `5869b1f`** -- scaffold `diff/` package (events + stubs + lessons placeholder).
3. **Task 2 RED: `24fa2b2`** -- failing fixture round-trip + structural gates.
4. **Task 2 GREEN: `37fab97`** -- 11 synthetic fixtures + `load_fixture` conftest.
5. **Task 3 RED: `01b29bc`** -- failing `diff_lessons` tests.
6. **Task 3 GREEN: `d8d9953`** -- identity-vs-content algorithm.

**Plan metadata:** committed alongside this SUMMARY.md.

## Files Created

### Production code (`custom_components/ha_pronote/diff/`)

- `__init__.py` -- single import surface (C-01) re-exporting `ChangeType`, `DayLabel`, `LessonChange`, `NewGrade`, `NewInformation`, `diff_lessons`, `diff_grades`, `diff_notifications`.
- `events.py` -- `ChangeType = Literal["canceled", "modified", "teacher", "room"]`, `DayLabel = Literal["today", "tomorrow"]`, and 3 frozen dataclasses with `to_payload()`.
- `lessons.py` -- the diff algorithm (88 lines, 33 statements, 100% covered).
- `grades.py` -- type-locked stub (D-02) raising `NotImplementedError("diff_grades body lands in Phase 4 (D-02)...")`.
- `notifications.py` -- mirror stub for informations.

### Synthetic fixtures (`tests/fixtures/synthetic/`)

- `empty_to_empty_T{0,1}.json` -- vacation: zero lessons in both polls.
- `reorder_no_op_T{0,1}.json` -- 3 identical lessons, reversed order.
- `multi_change_T{0,1}.json` -- 3 lessons exercising canceled + room + teacher in one poll (Europe/Paris timezone, +02:00 offset -- D-25 matrix probe).
- `first_poll_after_restart.json` -- 5 lessons + 3 grades + 2 informations; used as `new` with `previous=None` to assert the D-08 invariant on a fully-populated snapshot.
- `lesson_removed_T{0,1}.json` -- a J-1 (yesterday) lesson present in T0, absent in T1; the `lessons_today` filter (D-16) ensures `events == []` for `day="today"`.
- `lesson_added_T{0,1}.json` -- 2 lessons in T0, the same 2 + a new 14:00 lesson in T1; algorithm decision is silent on additions.
- `_README.md` -- documents every fixture's intent, the algorithm decisions, and the regression-sentinel role of `lesson_removed`.

### Tests (`tests/test_diff/`)

- `__init__.py` (empty package marker).
- `conftest.py` -- per-tree autouse override + `load_fixture` / `load_raw_fixture` helpers with `pytest.skip` on missing real fixtures.
- `test_events.py` -- 10 tests on the dataclasses + Literal taxonomy.
- `test_stubs.py` -- 2 tests asserting `diff_grades` / `diff_notifications` raise `NotImplementedError`.
- `test_fixtures_roundtrip.py` -- 27 tests (11 round-trip + 11 tz-aware + 1 dir-count + 1 readme + 3 helper).
- `test_lessons.py` -- 22 tests on the diff algorithm including 6 real-fixture tests (4 skip per S-04, 2 round-trip `Snapshot.from_dict` checks pass).
- `test_lessons_synthetic.py` -- 4 combinatorics-only tests (silent on removal, silent on addition, modified on uncancel, day-tomorrow window).

## Decisions Made

- **S-04 acknowledged in code, not just docs.** The diff layer's docstring cites SPIKE-FINDINGS-bain3-311.md by name and section, and the real-fixture tests print "Plan 02-02 S-04 acknowledged gap" in their skip messages. A future maintainer running `pytest -v` reads this directly.
- **Step 4 silent / step 5 silent.** The frozen 4-value taxonomy (D-09) has no `removed` or `added` value, and SPIKE-FINDINGS S-04 documents the empirical ambiguity. Both lesson-disappeared and lesson-appeared paths are silent. Phase 4 verification logs every such transition for one month before deciding to revisit.
- **bain3#311 Option B/C.** The dict-by-identity-key approach is sufficient given the empirical gap. If a future spike captures duplicate identity tuples (Option A — pronotepy emitting both the canceled and the room-changed lesson at the same `(date, start, end, subject)`), the dict swaps for `defaultdict(list)` and the consolidator picks the canceled-as-`before` / non-canceled-as-`after` per-tuple.
- **Status field excluded from content key.** Listing `status` would emit `modified` events on every poll where pronotepy refreshes the free-form label, drowning out the actionable canceled/room/teacher signals. The SPIKE-FINDINGS S-04 mention of `indicateurAbsence` -> `Lesson.canceled` confirms `canceled` is the load-bearing flag.
- **True->False on `canceled` emits `modified`.** The frozen taxonomy has no "uncancellation" word; emitting another `canceled` would be misleading. Locked by `test_lesson_uncanceled_emits_modified_change`.
- **Test infrastructure: per-tree autouse override.** `tests/test_diff/conftest.py` redefines `auto_enable_custom_integrations` as a no-op, neutralising the root `tests/conftest.py` PHACC autouse for the HA-free test surface. Mirror of `tests/test_api/conftest.py`. Lets the diff suite run without the HA harness installed.

## Phase 4 Hand-off

The `LessonChange.to_payload()` shape **is** the bus event payload contract:

```python
{
    "change_type": "canceled" | "modified" | "teacher" | "room",
    "day": "today" | "tomorrow",
    "lesson_date": "YYYY-MM-DD",
    "subject": str,
    "before": dict | None,   # Lesson.to_dict() of the T0 entry
    "after": dict | None,    # Lesson.to_dict() of the T1 entry
}
```

Phase 4's coordinator routes this verbatim into `hass.bus.async_fire("pronote_schedule_changed", payload)`. No additional shaping is needed.

The same applies to `NewGrade.to_payload()` and `NewInformation.to_payload()` once Phase 4 fills the diff function bodies.

## Deviations from Plan

### Auto-fixed Issues (Rule 3 -- Plan path)

**1. Real-fixture tests changed from "must emit" to "skip when no diff present"**
- **Found during:** Task 3 (test_lessons.py implementation).
- **Issue:** The plan as written assumes the 6 real fixtures contain detectable changes. Plan 02-02 SUMMARY.md explicitly records the S-04 acknowledged gap: T0/T1 lessons arrays are byte-identical. The real-fixture tests would have failed with `assert any(e.change_type == "canceled" for e in events)` on a guaranteed-empty list.
- **Fix:** Added a `_real_pair_has_lesson_change(load_raw_fixture, scenario)` helper that returns `False` when T0/T1 lessons are byte-identical, and `pytest.skip("...Plan 02-02 S-04 acknowledged gap...")` in each real-fixture test when the helper returns `False`. The plan itself anticipates this branch ("real fixtures may pytest.skip if Plan 02-02 was `partial:`").
- **Files modified:** `tests/test_diff/test_lessons.py`.
- **Verification:** 4 real-fixture tests skip with clear S-04 messages; the synthetic `multi_change` pair (which DOES have a diff) covers the same algorithm branches.
- **Committed in:** `01b29bc` (Task 3 RED) + `d8d9953` (Task 3 GREEN).

### Acknowledged Gaps (carried forward)

**2. SPIKE-FINDINGS does not record an explicit verdict on Algorithm decision steps 4 and 5.**
- **Plan expectation:** the executor reads the verdict and writes a single uncommented branch (PC-02-06).
- **Reality:** SPIKE-FINDINGS S-04 records the empirical gap and recommends building against the documented `Lesson` model. Steps 4 and 5 verdicts are documented in `tests/fixtures/synthetic/_README.md` ("silent on both") and in this SUMMARY's "Decisions Made" section, with the rationale tied to (a) frozen 4-value taxonomy excluding `removed`/`added`, (b) `lessons_today` filter as period-rollover safety net, (c) ambiguity between real removal and polling race. No commented-out alternative branches survive in the production code (PC-02-06 holds: `grep -rE "(# Uncomment|# TODO: spike|# pragma:.* spike|EXECUTOR DECISION POINT)"` returns nothing).

---

**Total deviations:** 1 auto-fixed (Rule 3 -- plan path), 1 acknowledged gap (carried forward to Phase 4).
**Impact on plan:** Both adjustments are explicit in the SPIKE-FINDINGS S-04 carry-over and the plan's own "real fixtures may pytest.skip" phrasing. No scope creep.

## Issues Encountered

- **Pre-existing tests/test_init.py + tests/test_manifest.py errors.** The root `tests/conftest.py` autouse PHACC fixture requires `enable_custom_integrations`, which only loads when the HA test harness is installed. Plan 02-04 owns the resolution (CI workflow + matrix). Verified pre-change: those tests were already error-collecting before any Plan 02-03 commit; not introduced here.
- **`pyproject.toml` ruff `required-version = ">=0.15.1"`.** The system ruff (0.14.5) was rejected. Resolved by `pip install ruff==0.15.1` into the project venv (one-shot bootstrap; not a `requirements_test.txt` change since Plan 02-04 owns the CI venv contract).
- **Cosmetic: ruff applied I001 (import sort) + UP037 (quoted-annotation removal) autofixes during the first lint pass.** All rewrites accepted without semantic change. Listed here for traceability since they touched files I had just authored.

## Next Plan Readiness (02-04: tz-matrix and coverage gates)

- **diff/ subpackage HA-free** (verified: no `homeassistant` imports anywhere).
- **`pytest tests/test_api/ tests/test_diff/ tests/test_scripts/` exits 0** (134 pass + 5 skip). Plan 02-04's pytest matrix can wrap this in the `(Europe/Paris, Pacific/Noumea)` parametrization without touching the underlying tests.
- **Coverage on `custom_components.ha_pronote.diff.lessons` is 100%** -- Plan 02-04's `--cov-fail-under=90` gate has 10 percentage points of slack.
- **`tests/test_fixtures.py` schema gate** (Plan 02-04 owns) can run `Snapshot.from_dict / to_dict` round-trip on every committed `tests/fixtures/**/*.json`; the 11 synthetic + 6 real fixtures are all guaranteed clean by Plan 02-03's verification.

## Threat Flags

None. The 5 STRIDE threats in the plan's `<threat_model>` are all mitigated:

- **T-02-03-01** (Tampering / Information Disclosure on bus payload) — `LessonChange.before`/`.after` are produced via `Lesson.to_dict()` (Plan 02-01); `test_event_payload_is_json_serializable` asserts JSON cleanliness on the multi_change fixture.
- **T-02-03-02** (Tampering: 5th change_type value) — `test_change_type_taxonomy_is_exactly_four_values` locks the set.
- **T-02-03-03** (bain3#311 phantom canceled) — `test_real_room_change_does_not_emit_phantom_canceled` skips on byte-identical fixtures but the assertion shape is in place; the synthetic `multi_change` pair exercises the room branch and passes.
- **T-02-03-04** (Synthetic fixture authoring drift) — every committed fixture round-trips through `Snapshot.from_dict / to_dict` (`test_synthetic_fixture_round_trips`).
- **T-02-03-05** (Period rollover noise -> false-positive flood) — `test_lesson_removed_outside_today_window_is_silent` covers the synthetic case; the day-window filter is the primary defense.

## Self-Check: PASSED

- All 5 production `.py` files exist (`__init__`, `events`, `lessons`, `grades`, `notifications`).
- All 11 synthetic fixtures + `_README.md` exist.
- All 7 test files exist (`__init__`, `conftest`, `test_events`, `test_stubs`, `test_fixtures_roundtrip`, `test_lessons`, `test_lessons_synthetic`).
- All 6 task commits present in git log: `15f49dd` (T1 RED), `5869b1f` (T1 GREEN), `24fa2b2` (T2 RED), `37fab97` (T2 GREEN), `01b29bc` (T3 RED), `d8d9953` (T3 GREEN).
- 134 HA-free tests pass + 5 documented skips; zero ruff violations under py314 target; 100% line coverage on `diff/lessons.py`; zero `homeassistant.*` imports anywhere in `diff/` or `tests/test_diff/`.

## TDD Gate Compliance

Each of the 3 tasks shipped a `test(02-03):` RED commit followed by a `feat(02-03):` GREEN commit. Plan-level type is `execute` (not `tdd`), but per-task `tdd="true"` was honoured.

---
*Phase: 02-api-diff-layer-ha-free*
*Completed: 2026-05-06*
