---
phase: 05-politesse-adaptive-polling-quiet-hours-circuit-breaker
plan: 01
subsystem: politesse
tags: [politesse, pure-module, ha-free, tz-matrix, jitter, backoff, predicates]

# Dependency graph
requires:
  - phase: 02-api-diff-layer-ha-free
    provides: HA-free module pattern (api/_strip.py + diff/lessons.py docstring/shape precedent) and the AST guard (tests/test_no_ha_imports.py) which is now extended
  - phase: 03-coordinator-first-sensor
    provides: DEFAULT_REFRESH_INTERVAL const (mirrored as PolitesseOptions.refresh_interval default)
provides:
  - PolitesseOptions frozen dataclass — the resolved-per-entry options snapshot every politesse function consumes
  - compute_interval(now, options, *, rng) — D-04 4-branch adaptive cadence with jitter + clamp
  - should_poll(now, options) — D-05 weekend/vacation/férié gate with D-06 primer exception
  - should_fire_event(now, options) — D-09 quiet-hours event suppression predicate
  - next_backoff(strike_index, schedule=...) — D-11 fixed-schedule backoff helper (V-09 anchor)
  - is_school_day / is_quiet_hours / is_afternoon_window / is_primer_window — the four predicates used by the algorithm
  - tests/test_politesse_tz_matrix.py — 84 tz-matrixed unit tests (file name carries the `tz_matrix` substring for V-14)
  - Extended tests/test_no_ha_imports.py GUARDED_PATHS (politesse.py + holiday_dates.py + test_politesse_tz_matrix.py)
affects:
  - 05-02 (holiday_dates.py): the AST guard's sanity check is now a tripwire for that plan
  - 05-03 (coordinator wiring): imports compute_interval / should_poll / should_fire_event / next_backoff verbatim from this module

# Tech tracking
tech-stack:
  added: []  # stdlib only — no new runtime dependency
  patterns:
    - "Pure HA-free module pattern (D-16): stdlib + dataclass-frozen options, every function takes `now`/`options` as args, no module state"
    - "Injectable RNG pattern (D-19): `rng: random.Random | random = random` keyword-only param duck-types `.uniform`"
    - "TZ-matrix pure-pytest pattern (D-20): module-level `pytestmark = pytest.mark.parametrize(\"school_tz\", [...])` with local autouse-fixture overrides so the file runs without `hass`/PHACC"
    - "File-name-driven `pytest -k` selector pattern: file name carries `tz_matrix` substring so V-14 selector resolves all collected cases (precedent: tests/test_diff/test_lessons_tz_matrix.py)"

key-files:
  created:
    - "custom_components/ha_pronote/politesse.py (348 LOC) — pure HA-free predicates + compute_interval + next_backoff"
    - "tests/test_politesse_tz_matrix.py (487 LOC) — 42 named tests × 2 timezones = 84 collected"
    - ".planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/05-01-SUMMARY.md"
  modified:
    - "tests/test_no_ha_imports.py — GUARDED_PATHS extended with politesse.py + holiday_dates.py + test_politesse_tz_matrix.py; `_python_files` generalized to accept file roots (Option B)"

key-decisions:
  - "Followed D-16: politesse.py imports stdlib only (datetime, random, dataclasses, typing) — no homeassistant.*, no holidays, no const.py. Defaults for vacation_ranges / holiday_dates flow in via PolitesseOptions injected by the coordinator."
  - "Followed D-04 branch ordering verbatim: quiet > suspended > afternoon > base. The afternoon branch (3) ANDs `is_afternoon_window` with `is_school_day(tomorrow)` — the Fri-18h-with-Sat-off case correctly falls through to the base interval."
  - "Followed D-06 primer unification: `is_primer_window` returns True iff today is non-school AND tomorrow is school AND now is in the afternoon window. `should_poll` short-circuits to True via the primer exception so the afternoon branch in `compute_interval` then evaluates True for Sun-19h and last-day-of-vacation-19h."
  - "Followed D-19 RNG injection: `rng: random.Random | random = random` keyword-only; tests pass `rng=random.Random(seed=42)` for V-13 reproducibility."
  - "Followed D-20 test layout verbatim: pure pytest, module-level `pytestmark` parametrizing every test on Europe/Paris + Pacific/Noumea; no freezegun (functions take `now` as arg); no hass; local autouse-fixture overrides for the two HA-bound conftest autouse fixtures."

patterns-established:
  - "Pure HA-free predicate module (D-16): @dataclass(frozen=True) options snapshot + free functions taking `now` + options, no module state, no I/O, no try/except (re-raise discipline per memory/feedback_no_silent_exceptions.md)"
  - "Naive-datetime gate: every predicate accepting `now: datetime` raises `ValueError(\"now must be tz-aware\")` if `now.tzinfo is None` — uniform error message string asserted by 5 dedicated tests"
  - "Half-open time-window convention: `[start, end)` for both afternoon_window (D-07) and the degenerate quiet-hours branch (D-08); cross-midnight branch handled separately when `quiet_start > quiet_end`"
  - "AST guard sanity-check tripwire: extending GUARDED_PATHS with files that another (parallel-wave) plan must ship makes the test_guarded_paths_are_not_empty assertion a forcing function for wave-merge ordering"

requirements-completed: [COORD-04, COORD-05, COORD-06, COORD-07, COORD-09, DIST-06]

# Metrics
duration: ~25 min
completed: 2026-05-25
---

# Phase 05 Plan 01: Politesse Pure-Module Summary

**Pure HA-free `politesse.py` shipping the D-04 4-branch adaptive cadence, D-11 backoff schedule, D-03/05/06/07/08/09 predicates, and the D-19 injectable-RNG jitter — backed by 84 tz-matrixed unit tests (Europe/Paris + Pacific/Noumea).**

## Performance

- **Duration:** ~25 min (plus ~5 min spent bootstrapping the worktree's `.venv` because the wave-spawned worktree branch did not include the Phase 5 phase docs created on `main` — rebase onto `main` resolved that without history rewrites)
- **Started:** 2026-05-25T02:09:00Z (approx — first execution tool call after worktree rebase)
- **Completed:** 2026-05-25T02:34:09Z
- **Tasks:** 3 (Task 1 — politesse.py; Task 2 — test_politesse_tz_matrix.py; Task 3 — AST guard extension)
- **Files modified:** 3 (`politesse.py` created, `test_politesse_tz_matrix.py` created, `test_no_ha_imports.py` modified)
- **Total LOC delivered:** 835 (348 source + 487 tests)
- **Test cases delivered:** 84 collected (42 named tests × 2 timezones) — all green

## Accomplishments

- `custom_components/ha_pronote/politesse.py` (348 LOC) — 9 public exports (`PolitesseOptions` + 8 functions), zero `homeassistant.*` imports, zero `holidays` imports (D-16 satisfied), zero `try/except` blocks (re-raise discipline)
- `tests/test_politesse_tz_matrix.py` (487 LOC) — 7 `TestXxx` classes, 42 named tests, module-level pytestmark on `["Europe/Paris", "Pacific/Noumea"]`, two local autouse-fixture overrides keep the file hermetic (no `hass`, no PHACC, no `freezegun`)
- `tests/test_no_ha_imports.py` — `GUARDED_PATHS` extended with the three new Phase 5 entries; `_python_files` generalized to accept both directory and file roots via the Option B change-set from PATTERNS.md
- All 12 V-XX-named tests pass individually on both timezones: V-01, V-02, V-03, V-04, V-05, V-06, V-07, V-09, V-12, V-13, V-18, V-19
- V-14 selector resolves: `pytest -k "tz_matrix" tests/test_politesse_tz_matrix.py -q` collects and passes 84 cases
- V-22 AST guard: `politesse.py` and `test_politesse_tz_matrix.py` both individually pass the `homeassistant.*` import check

## V-XX Coverage Map

| V-ID | Test name(s) | Anchor |
|------|--------------|--------|
| V-01 | `test_compute_interval_weekday_afternoon` | D-04 afternoon branch |
| V-02 | `test_compute_interval_base_weekday_morning` | D-04 base branch |
| V-03 | `test_should_poll_weekend_suspended` | D-05 weekend |
| V-04 | `test_should_poll_vacation_suspended` | D-05 vacation |
| V-05 | `test_should_poll_ferie_suspended` | D-05 férié |
| V-06 | `test_should_fire_event_false_in_quiet_hours` | D-09 |
| V-07 | `test_compute_interval_quiet_hours_cadence` | D-04 branch 1 |
| V-09 | `test_next_backoff_schedule_clamps_at_24h` | D-11 / COORD-07 helper driver |
| V-12 | `test_jitter_within_pm_30s_bounds` | D-19 jitter bounds |
| V-13 | `test_jitter_seeded_rng_reproducible` | D-19 reproducibility |
| V-14 | (implicit) — file name `tz_matrix` + module pytestmark | DIST-06 anchor |
| V-18 | `test_compute_interval_sunday_evening_primer` | D-06 Sun-evening primer |
| V-19 | `test_compute_interval_last_day_of_vacation_evening_primer` | D-06 last-vacation-evening primer |
| V-22 | AST guard tests on politesse.py + test_politesse_tz_matrix.py | D-16 |

## Task Commits

Each task was committed atomically (worktree branch `worktree-agent-a5f76eef748c8c55e`, off `main`):

1. **Task 1: politesse.py source** — `9aba6db` (feat) — `feat(05-01): add politesse.py — pure HA-free predicates + compute_interval + next_backoff`
2. **Task 2: tz-matrix tests** — `73199c8` (test) — `test(05-01): add tz-matrixed politesse unit tests — V-01..V-09, V-12..V-14, V-18, V-19`
3. **Task 3: AST guard extension** — `95c55ab` (test) — `test(05-01): extend AST guard to politesse.py + holiday_dates.py + test_politesse_tz_matrix.py`

Plan metadata commit (this SUMMARY) will be added by the orchestrator's post-wave merge.

_Note: Plan 05-01 has `tdd="true"` on Tasks 1 and 2 but the plan's own ordering puts source before tests; the discipline was preserved by validating each acceptance check inline as the source was written (e.g. running `next_backoff` clamp checks via `uv run python -c …` immediately after Task 1's Write) and by holding Task 2's commit until every named test passed on both timezones. No RED-only commit was created — the plan's verify blocks are themselves the GREEN gates._

## Files Created/Modified

- `custom_components/ha_pronote/politesse.py` — **created**, 348 LOC. Pure HA-free predicates + compute_interval + next_backoff. Stdlib-only imports. `@dataclass(frozen=True)` PolitesseOptions. No `try/except`. Naive datetime → ValueError.
- `tests/test_politesse_tz_matrix.py` — **created**, 487 LOC. 7 TestClass groups (TestIsSchoolDay, TestIsQuietHours, TestIsAfternoonWindow, TestIsPrimerWindow, TestShouldPoll, TestShouldFireEvent, TestComputeInterval, TestNextBackoff, TestNaiveDatetimeRejection). Module-level pytestmark parametrizing every test on `["Europe/Paris", "Pacific/Noumea"]`. Local autouse-fixture overrides shadow `tests/conftest.py`'s HA-dependent autouse fixtures.
- `tests/test_no_ha_imports.py` — **modified**, +9 / -1. GUARDED_PATHS extended with three Phase 5 entries. `_python_files` generalized to accept file roots.

## Decisions Made

- **Followed D-04 branch ordering** exactly as specified (quiet > suspended > afternoon > base). Added an explicit "Sat 23h quiet wins over suspended" test (`test_compute_interval_saturday_23h_quiet_wins_over_suspended`) to lock the ordering.
- **Followed D-06 primer unification**: the `is_primer_window` predicate is a single check (`not is_school_day(today) AND is_school_day(tomorrow) AND is_afternoon_window(now)`); both Sun-19h and last-day-of-vacation-19h cases collapse to this one predicate, which `should_poll` uses as its exception clause and `compute_interval`'s afternoon branch picks up via the same `is_school_day(tomorrow) AND is_afternoon_window(now)` AND.
- **Re-raise discipline**: zero `try/except` in `politesse.py`. Naive `datetime` input raises `ValueError("now must be tz-aware")` with a static error message (no caller-input interpolation — closes T-05-01-06 log-injection threat).
- **Backoff schedule baked into politesse.py** (`_DEFAULT_BACKOFF_SCHEDULE`) so `next_backoff(0)` works standalone in tests, but the function signature accepts a `schedule=` kwarg so the coordinator (Plan 05-03) can pass `BACKOFF_SCHEDULE` from `const.py` explicitly without forcing politesse.py to import const (preserving D-16).
- **`_build_options` helper, not a fixture**: fixtures pull `tests/conftest.py` (per PATTERNS.md §"2. tests/test_politesse.py" anti-pattern); a module-level helper function dodges that and keeps the file hermetic.
- **EN DASH (`–`) replaced by HYPHEN (`-`) in docstrings** to satisfy ruff RUF002 (ambiguous-character lint).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Worktree branch lacked Phase 5 phase docs**
- **Found during:** Plan loading (before Task 1)
- **Issue:** The worktree's per-agent branch `worktree-agent-a5f76eef748c8c55e` was forked from an older `main` HEAD and did not contain `.planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/` (including this plan's own PLAN.md, CONTEXT.md, RESEARCH.md, PATTERNS.md). The phase docs lived on local `main` only.
- **Fix:** `git fetch && git rebase main` from inside the worktree. Resulted in fast-forward (no conflicts) bringing in the 5 Phase 5 doc-commits on top of the worktree branch.
- **Files modified:** None in repo state — just bringing the worktree branch up to date with `main`.
- **Verification:** `ls .planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/` shows the 8 phase doc files; the rebase preserved the HEAD assertion (still on `worktree-agent-a5f76eef748c8c55e`).
- **Committed in:** N/A (rebase only — no new commit).

**2. [Rule 3 — Blocking] Local `.venv` was not bootstrapped for test execution**
- **Found during:** Initial verification attempts
- **Issue:** The worktree's `.venv` had no `pytest`, no `homeassistant`, no `pronotepy`. CI installs via `uv pip install --system -r requirements_test.txt` but local execution needs a venv.
- **Fix:** `uv venv --python 3.14 .venv` then a targeted install of `homeassistant==2026.5.0b0` (the version PHACC 0.13.326 actually requires per its `Requires-Dist` — `requirements_test.txt` pins `homeassistant==2026.4.4` which is mutually unsatisfiable; this is a pre-existing requirements-pinning bug unrelated to Plan 05-01, but install needed to resolve), `pytest-homeassistant-custom-component==0.13.326`, `pronotepy==2.14.6`, `requests-mock==1.12.1`, `aiohttp`, `syrupy`. Without these, `tests/conftest.py` imports fail before any politesse test can run.
- **Files modified:** None in repo state — `.venv/` is in `.gitignore`.
- **Verification:** `uv run --no-sync pytest tests/test_no_ha_imports.py -q` passes; `uv run --no-sync pytest tests/test_politesse_tz_matrix.py -q` runs all 84 cases green.
- **Committed in:** N/A.
- **Recommendation:** A future "infra" mini-plan should fix the `requirements_test.txt` vs PHACC version-pinning mismatch. Logging to `.planning/phases/05-.../deferred-items.md` is out of scope for Plan 05-01 (only the politesse module + its tests + AST guard).

**3. [Rule 1 — Ruff lint cleanup on new files] Minor ruff fixes applied to source + test files**
- **Found during:** Tasks 1 and 2 (post-Write, before commit)
- **Issue:** Ruff's `I001` import-sort and `SIM103` "return condition directly" and `RUF002` "EN DASH in docstring" flagged the freshly written files.
- **Fix:** Re-ordered imports per ruff's isort block (`random` before `from dataclasses ...`), collapsed the trailing two-line `if/return False/return True` to `return d not in holiday_dates`, replaced two EN-DASH occurrences (`22h–6h` → `22h-6h`) in docstrings.
- **Files modified:** `custom_components/ha_pronote/politesse.py`, `tests/test_politesse_tz_matrix.py`.
- **Verification:** `uv run --no-sync ruff check custom_components/ha_pronote/politesse.py tests/test_politesse_tz_matrix.py` → All checks passed!
- **Committed in:** Folded into the original task commits (Task 1 → `9aba6db`, Task 2 → `73199c8`).

### Intentional Deviation (NOT auto-fixed — by design per the plan)

**4. [Plan-mandated tripwire] `test_guarded_paths_are_not_empty` fails for `holiday_dates.py`**
- **Found during:** Task 3 verification
- **Issue:** Plan 05-01 Task 3 appends `custom_components/ha_pronote/holiday_dates.py` to `GUARDED_PATHS`, but Plan 05-02 (parallel Wave 1) is the plan that ships the file. In this isolated worktree, `holiday_dates.py` does not exist, so the sanity check at lines 76-88 of `test_no_ha_imports.py` fires: `AssertionError: guarded path custom_components/ha_pronote/holiday_dates.py has no .py files`.
- **Why this is correct:** The PLAN.md `<action>` block explicitly states "**Note on Plan ordering**: `holiday_dates.py` is shipped by Plan 05-02 Task 1 (WR-2)... If Plan 05-01 Task 3 runs BEFORE Plan 05-02 has merged, `test_guarded_paths_are_not_empty` will fail because the file doesn't exist yet. This is the intended behavior — the AST guard is a tripwire that forces Plan 05-02 to land before Phase 5 declares itself green. Plan 05-03 (Wave 2) depends on both Wave 1 plans, so by Wave 2 entry the guard is satisfied."
- **Confirmation tests:** The two AST-walker tests that DO matter for Plan 05-01 — `test_no_homeassistant_import[custom_components/ha_pronote/politesse.py]` and `test_no_homeassistant_import[tests/test_politesse_tz_matrix.py]` — both pass cleanly (V-22 satisfied for this plan's own deliverables).
- **Files modified:** `tests/test_no_ha_imports.py` (the tripwire-adding change).
- **Committed in:** `95c55ab` (Task 3 commit).

---

**Total deviations:** 4 — 3 auto-fixed (1 worktree-rebase, 1 venv bootstrap, 1 ruff cleanup) and 1 intentional plan-mandated tripwire.
**Impact on plan:** Zero scope creep. The three auto-fixes were execution-environment setup; the tripwire is the plan's own forcing-function for the Plan 05-02 dependency.

## Issues Encountered

- **`requirements_test.txt` vs PHACC version mismatch** (pre-existing, not introduced by this plan): `requirements_test.txt` pins `homeassistant==2026.4.4` but `pytest-homeassistant-custom-component==0.13.326` declares `Requires-Dist: homeassistant==2026.5.0b0`. Locally resolved by installing `homeassistant==2026.5.0b0` explicitly. CI runs `uv pip install --system` which resolves transitively and likely picks up the same version; the conflict only surfaces when uv tries to satisfy both pins simultaneously. Not fixed in Plan 05-01 (out of scope).

## Self-Check

Created files verified to exist:
- `[FOUND] custom_components/ha_pronote/politesse.py`
- `[FOUND] tests/test_politesse_tz_matrix.py`
- `[FOUND] .planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/05-01-SUMMARY.md` (this file)

Modified file verified:
- `[FOUND] tests/test_no_ha_imports.py` (3 new GUARDED_PATHS entries, `_python_files` generalized)

Commits verified in `git log`:
- `[FOUND] 9aba6db` — Task 1 feat
- `[FOUND] 73199c8` — Task 2 test
- `[FOUND] 95c55ab` — Task 3 test

## Self-Check: PASSED

## Next Plan Readiness

- **Plan 05-02** (`holiday_dates.py` neutral helper module, parallel Wave 1) can land independently. When it merges, the `test_guarded_paths_are_not_empty` tripwire on `holiday_dates.py` is resolved and the AST guard runs fully green.
- **Plan 05-03** (Wave 2 — coordinator wiring) can `from custom_components.ha_pronote.politesse import PolitesseOptions, compute_interval, should_poll, should_fire_event, next_backoff` verbatim; the exported surface is locked.
- **Phase 6 OptionsFlow** (future): the `PolitesseOptions` field set is the schema source-of-truth — the voluptuous schema is the inverse projection.

---
*Phase: 05-politesse-adaptive-polling-quiet-hours-circuit-breaker*
*Plan: 01*
*Completed: 2026-05-25*
