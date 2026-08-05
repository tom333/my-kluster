---
phase: 05-politesse-adaptive-polling-quiet-hours-circuit-breaker
plan: 04
subsystem: testing
tags: [test-fixture, freezegun, gap-closure, deterministic-time, pentecote-collision, nc-ferie, ascension-collision]

# Dependency graph
requires:
  - phase: 05-01-politesse-pure-python-module
    provides: politesse predicates (should_poll, compute_interval, is_school_day) that the coordinator short-circuit depends on
  - phase: 05-02-holiday-calendar-and-constants
    provides: NC_VACATION_RANGES_2026, holidays.France(subdiv='NC') wiring, JITTER_SECONDS const
  - phase: 05-03-coordinator-wiring-and-circuit-breaker
    provides: coordinator._async_update_data short-circuits at lines 154-169 (D-10 should_poll + D-10 backoff_until), _handle_failure breaker tick, _reset_breaker_on_success, persistent_notification create/dismiss
provides:
  - Module-level autouse `_frozen_school_day` fixture pinning dt_util.now() to Thu 2026-05-07 14:00 Pacific/Noumea in tests/test_coordinator.py, tests/test_sensor.py, tests/test_token_persistence.py
  - Widened jitter-envelope assertion in test_update_interval_is_30_minutes (`abs(.total_seconds() - 1800) <= JITTER_SECONDS + 5` per D-04)
  - Re-anchored V-08 t0 from Tue 2026-05-12 to Mon 2026-05-18 to dodge Ascension Day (2026-05-14 NC férié) in the 24h-stride loop
  - 14 previously-broken tests now green; regression delta = 0 against the documented 14-failure baseline; production code untouched
affects: [phase-06 auth-lifecycle, phase-07 distribution]

# Tech tracking
tech-stack:
  added: []  # No new dependencies — used existing pytest-freezer 0.4.9 (transitive via PHACC)
  patterns:
    - "Module-level autouse freezegun fixture for date-sensitive coordinator tests — pins INITIAL clock, tests override via own freezer.move_to(...) calls"
    - "Test-clock anchor selection rule: avoid 24h-stride landing on NC fériés (Ascension 2026-05-14, Pentecôte 2026-05-25, Fête de la Victoire 2026-05-08, Fête du Travail 2026-05-01)"

key-files:
  created: []  # Pure modifications — no new files
  modified:
    - tests/test_coordinator.py (autouse fixture + widened jitter assertion + V-08 t0 anchor)
    - tests/test_sensor.py (autouse fixture + added missing `import pytest`)
    - tests/test_token_persistence.py (autouse fixture)

key-decisions:
  - "Module-level autouse fixture (NOT conftest-level) — narrows blast radius; pure-Python test_politesse.py / test_holiday_dates.py / test_no_ha_imports.py keep their synthetic-now contracts intact (D-20)"
  - "Pin date 2026-05-07 14:00 NC chosen for 4 simultaneous properties: weekday=3, not in NC_VACATION_RANGES_2026, not in holidays.France(subdiv='NC'), 14:00 < afternoon-window 17:00, 14:00 ∉ quiet [22:00, 06:00)"
  - "Jitter assertion widened (per D-04) instead of disabling jitter — preserves Plan 05-01's compute_interval contract (±JITTER_SECONDS uniform jitter on every cadence)"
  - "Hypothesis 0 (Ascension collision in 24h-stride loop) confirmed as root cause of V-08 'DID NOT RAISE'; Hypotheses 1-5 (production-side _handle_failure / set_active_child / _format_notification) NOT invoked — no production code modified"
  - "Recovered from worktree-cwd-drift (#3097) by cherry-picking the drift-commit onto the worktree branch and `git revert`-ing the drift-commit on main; preserved audit trail without rewinding the protected `main` ref (#2924)"

patterns-established:
  - "Pattern 1: Autouse module-level freezegun pin — `@pytest.fixture(autouse=True)\\ndef _frozen_school_day(freezer): freezer.move_to(...)`. Future Phase 5/6 coordinator tests reuse this; tests with own clock override via freezer.move_to(...) at body top."
  - "Pattern 2: Jitter envelope assertion — `abs(actual.total_seconds() - expected_seconds) <= JITTER_SECONDS + 5`. Reused wherever compute_interval's deterministic envelope is asserted post-Plan 05-01."
  - "Pattern 3: Clean-week anchor for synthetic-stride tests — Mon 2026-05-18 → Thu 2026-05-21 (post-Ascension, pre-Pentecôte, outside vacation). Document in test docstring so future edits don't break the assumption."

requirements-completed: [COORD-04, COORD-05, COORD-06, COORD-07, COORD-08, COORD-09, DIST-06]

# Metrics
duration: 15min
completed: 2026-05-25
---

# Phase 5 Plan 04: Gap Closure (dt_util.now() freezegun fix + V-08 t0 anchor re-pin) Summary

**Module-level autouse freezegun fixture pinning dt_util.now() to Thu 2026-05-07 14:00 Pacific/Noumea in 3 test files + widened 30-min jitter assertion + V-08 t0 anchor re-pinned from Tue 2026-05-12 to Mon 2026-05-18 to dodge Ascension Day — closes 14 Plan 05-03 freezegun-collision failures with zero production-code modification.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-25T05:40:00Z (worktree spawn time)
- **Completed:** 2026-05-25T05:55:33Z
- **Tasks:** 2 (Task 1 = autouse fixture install + jitter widening; Task 2 = Hypothesis 0 contingency arm fired)
- **Files modified:** 3

## Accomplishments

- **14 of 14 previously-broken tests now pass.** 12 in test_coordinator.py, 1 in test_sensor.py, 1 in test_token_persistence.py (full list under "Task Commits → Acceptance").
- **Regression delta = 0** against the 14-failure baseline documented in `deferred-items.md`. The full suite shows exactly 14 failures, all of which are the same baseline failures (2x test_manifest.py URL spec, 10x test_config_flow.py PHACC drift, 1x test_coordinator.py::test_recovery_cooldown_skips_back_to_back_auth_errors, 1x test_token_persistence.py::test_build_or_resume_client_uses_token_login_when_session_present).
- **Zero production code modified.** `git diff --name-only --stat` against the plan's pre-execution tip (`2498e05`) shows only the 3 test files in `tests/` were touched. The Hypothesis 0 root cause of V-08's DID NOT RAISE was a TEST anchor (Tue 2026-05-12 + 24h stride lands on Ascension 2026-05-14) — Plan 05-03's `should_poll` short-circuit + `_handle_failure` breaker tick + `_format_notification` were all correct per D-10/D-13/D-15.
- **Validation IDs V-08, V-15, V-16, V-17, V-20, V-21 are now reachable from the test harness** (Phase 5 WR-6 closure precondition).

## Pin date and 4 verified properties

Target: **Thursday 2026-05-07 14:00:00+11:00 (Pacific/Noumea)**.

| Property | Verification |
|---|---|
| `weekday() == 3` (Thursday) | `is_school_day` returns True (weekday < 5) |
| NOT in `NC_VACATION_RANGES_2026` | April vac ends 2026-04-19, June vac starts 2026-06-06 |
| NOT in `holidays.France(subdiv='NC', years=2026)` | Verified via `import holidays`: NC fériés in May 2026 are {2026-05-01, 2026-05-08, 2026-05-14, 2026-05-25} — 2026-05-07 not in set |
| NOT in afternoon window [17:00, 20:00) | 14:00 < 17:00 → `is_afternoon_window` returns False → base 30-min cadence (matches `test_update_interval_is_30_minutes` expectation) |
| NOT in quiet hours [22:00, 06:00) | 14:00 ∉ window → `is_quiet_hours` returns False → `should_fire_event` returns True (matches the 4 event-firing tests' expectation) |

Net result: at this synthetic time, `should_poll == True`, `is_afternoon_window == False`, `is_quiet_hours == False`. The coordinator falls THROUGH the two short-circuits in `_async_update_data` and reaches the `fetch_all` executor call — exactly the assumption baked into the Phase 3/4-era tests.

## 14 tests closed by Plan 05-04

### test_coordinator.py (12)

1. `test_rate_limited_during_poll_raises_update_failed`
2. `test_communication_error_during_poll_raises_update_failed`
3. `test_update_interval_is_30_minutes` (post-assertion-widening per D-04)
4. `test_recovery_rate_limited_raises_update_failed`
5. `test_recovery_network_error_raises_update_failed`
6. `test_recovery_auth_failed_again_raises_config_entry_auth_failed`
7. `test_genuine_auth_failure_after_successful_recovery_is_not_swallowed`
8. `test_fires_schedule_changed_on_lesson_diff`
9. `test_fires_new_grade_on_grade_diff`
10. `test_fires_new_information_on_info_diff`
11. `test_event_payload_contains_child_context`
12. `test_3_consecutive_auth_failures_set_backoff_4h_and_notification` (V-08 — closed by Task 2's Hypothesis 0 fix)

### test_sensor.py (1)

13. `test_sensor_unavailable_when_coordinator_fails`

### test_token_persistence.py (1)

14. `test_coordinator_writes_new_session_after_silent_recovery`

## 14 baseline failures left untouched (deferred-items.md)

These were failing BEFORE Phase 5 started and remain failing — Plan 05-04 does NOT fix them. They are tracked in `.planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/deferred-items.md`:

### tests/test_manifest.py (2)

- `test_manifest_documentation_url` — expects `https://github.com/tom333/ha-pronote`, manifest has `ha_pronote` (underscore). Spec/manifest discrepancy.
- `test_manifest_issue_tracker_url` — same hyphen-vs-underscore discrepancy.

### tests/test_config_flow.py (10)

- 4× `test_user_step_error_mapping[*]` (invalid_auth / ip_suspended / cannot_connect / unknown)
- 3× `test_create_entry_set_active_child_error_aborts_with_mapped_reason[*]`
- 1× `test_create_entry_export_credentials_failure_aborts_cannot_connect`
- 1× `test_user_step_parent_two_children_transitions_to_pick_child`
- 1× `test_user_step_pick_child_creates_entry`

### tests/test_coordinator.py (1)

- `test_recovery_cooldown_skips_back_to_back_auth_errors`

### tests/test_token_persistence.py (1)

- `test_build_or_resume_client_uses_token_login_when_session_present`

## Task Commits

Each task was committed atomically on the worktree branch `worktree-agent-ab27a25fc94b70173`:

1. **Task 1: autouse `_frozen_school_day` fixture in 3 test files + widened jitter assertion** — `df9fafb` (test)
2. **Task 2: V-08 t0 anchor re-pinned Tue 2026-05-12 → Mon 2026-05-18 (Hypothesis 0 fix)** — `f1d36f4` (test)

**Plan metadata commit:** to be appended by execute-plan.md's `git_commit_metadata` step (SUMMARY.md + REQUIREMENTS.md only in worktree mode — STATE.md and ROADMAP.md owned by the orchestrator post-merge per the worktree contract).

## Files Created/Modified

### Modified (3)

- `tests/test_coordinator.py` (Task 1 + Task 2):
  - Added `import pytest` already-present check (no change — pytest was already imported at line 9)
  - Replaced module-level `from datetime import date, timedelta` with `from datetime import date, datetime as _datetime` (module-level `timedelta` was no longer used after the jitter assertion widening; F401 satisfied)
  - Added `from zoneinfo import ZoneInfo as _ZoneInfo` import (private alias to avoid shadowing the in-body `from zoneinfo import ZoneInfo` re-imports used by breaker tests)
  - Added module-level autouse `_frozen_school_day` fixture pinning to Thu 2026-05-07 14:00 Pacific/Noumea
  - Widened `test_update_interval_is_30_minutes` assertion: `coordinator.update_interval == timedelta(minutes=30)` → `abs(.total_seconds() - 1800) <= JITTER_SECONDS + 5`
  - Re-anchored V-08 test `t0` from `datetime(2026, 5, 12, 14, 0, ...)` (Tue) to `datetime(2026, 5, 18, 14, 0, ...)` (Mon) with a 6-line docstring comment documenting the Ascension dodge

- `tests/test_sensor.py` (Task 1):
  - Added missing `import pytest` (line 9 — was absent at planning time per the PLAN's pre-flight check)
  - Added module-level autouse `_frozen_school_day` fixture (reuses existing top-level `datetime` and `ZoneInfo` imports — no underscore aliasing needed because the file's existing imports cover the symbols)

- `tests/test_token_persistence.py` (Task 1):
  - Added `from datetime import datetime as _datetime` to existing import line (file already imported `date`)
  - Added `from zoneinfo import ZoneInfo as _ZoneInfo` (was not imported at all in this file)
  - Added module-level autouse `_frozen_school_day` fixture

### Created (0)

None. Pure modifications.

## Decisions Made

- **Module-level autouse over conftest-level (per plan):** Narrows blast radius. The pure-Python `test_politesse.py`, `test_holiday_dates.py`, `test_no_ha_imports.py` modules pass synthetic `now` arguments per D-20 / D-16; a globally-patched clock would silently corrupt their assertions about real `holidays.France(subdiv='NC')` calendar lookups.
- **`return freezer` instead of `yield freezer`:** Ruff PT022 ("No teardown in fixture") flagged the plan's recommended `yield freezer`. Since the fixture has no teardown (freezegun's move_to mutation is automatically rolled back by pytest-freezer's own teardown), `return freezer` is the cleaner pattern AND matches the existing `auto_enable_custom_integrations` autouse pattern in `tests/conftest.py:20-27`. Behavior identical.
- **Hypothesis 0 confirmed without invoking Hypotheses 1-5:** The V-08 failure log showed `DID NOT RAISE` precisely at the `2026-05-14 14:00:00 (Ascension)` freezer tick — diagnostic enough to confirm the test-setup root cause. Production code (`_handle_failure`, `_recover_from_auth_error`, `_format_notification`) was not investigated further. Per `feedback_no_silent_exceptions.md`, the raise propagation contract in `_recover_from_auth_error` is the correct shape; no try/except mutation needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Worktree cwd-drift recovery (#3097)**
- **Found during:** Task 1 (immediately after the first `git commit`)
- **Issue:** My initial Edit/Write calls used absolute paths starting with `/data/projets/perso/pronote/...` (the main repo root) instead of `/data/projets/perso/pronote/.claude/worktrees/agent-ab27a25fc94b70173/...` (the worktree root). The first commit (`4976b75`) landed on `main` instead of `worktree-agent-ab27a25fc94b70173`. The cwd-drift sentinel from `worktree-path-safety.md` was not set up before the first Bash call, so the `[ -f .git ]` worktree guard was bypassed (main repo's `.git` is a directory, not a file).
- **Fix:** (a) cherry-picked `4976b75` onto the worktree branch (preserving content), (b) `git revert --no-edit 4976b75` on main to nullify the accidental drift-commit (creating `728e261` — a NEW commit that undoes the drift, per `agents/gsd-executor.md`'s "Always create NEW commits rather than amending"), (c) wrote `gsd-spawn-toplevel` sentinel for future cwd-drift detection, (d) switched all subsequent Read/Edit/Write/Bash calls to operate from the worktree path explicitly. **Did NOT use `git update-ref refs/heads/main` or `git reset --hard` on the protected `main` ref** (per #2924).
- **Files modified:** None on disk in the worktree — only git history. The worktree-branch commit `df9fafb` is content-identical to the main-branch drift-commit `4976b75`; main now has `4976b75 + revert(728e261)` (net no-op since the test files there are back at baseline).
- **Verification:** `git log --oneline -3` on the worktree shows `f1d36f4 → df9fafb → 2498e05`; main shows `728e261 (revert) → 4976b75 → 2498e05`. Worktree `tests/test_coordinator.py` has the fixture; main's `tests/test_coordinator.py` is restored to baseline.
- **Committed in:** `df9fafb` (cherry-picked), `728e261` (revert on main).

**2. [Rule 3 — Blocking] Worktree venv missing `holidays` package**
- **Found during:** Task 1 (first pytest invocation in worktree)
- **Issue:** The worktree's `.venv/` was a uv-managed shadow venv missing the `holidays==0.97` package (declared in `manifest.json` as a runtime requirement, transitively pulled when the integration is loaded by HA's test harness). uv's `sync --frozen` reported "Audited in 0.00ms" but the package wasn't present. Attempting `uv pip install holidays==0.97` failed because uv tried to also install `pytest-homeassistant-custom-component==0.13.326` which requires `homeassistant==2026.5.0b0`, conflicting with the existing pinned `homeassistant==2026.4.4` per `requirements_test.txt`.
- **Fix:** Bypassed uv's environment resolution by invoking pytest directly through the main repo's already-bootstrapped venv: `/data/projets/perso/pronote/.venv/bin/python -m pytest ...`. The main venv has `holidays`, `pytest-freezer`, `pytest-homeassistant-custom-component`, and all other PHACC-transitive deps correctly installed.
- **Files modified:** None.
- **Verification:** `/data/projets/perso/pronote/.venv/bin/python -c "import holidays; print(holidays.__version__)"` → `0.97`. Full suite runs.
- **Committed in:** N/A (workflow adjustment, not a code change)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — Blocking, both meta-workflow not production)
**Impact on plan:** Both deviations were workflow recoveries (worktree cwd-drift + worktree venv bootstrap), neither affected the deliverables. Plan was executed exactly as written for the 3 test files + 1 t0 anchor; zero scope creep.

## Issues Encountered

- **V-08 still failed after Task 1's autouse fixture install** — caused by the test's own `freezer.move_to(t0)` at body top overriding the module pin. Diagnosed in <2 min via the captured pytest log: the "DID NOT RAISE" exception was logged at `2026-05-14 14:00:00` (Ascension Day). Resolved by Task 2's t0 anchor re-pin per the plan's Hypothesis 0 contingency arm. No production-code investigation needed (Hypotheses 1-5 not invoked).

## Threat Flags

None. The plan modifies test infrastructure only; no new production surface, no new I/O, no new credentials, no new attack surface. STRIDE register from PLAN.md (T-05.4-01 .. T-05.4-05) all hold as planned:

- T-05.4-01 (Tampering / fixture leak): mitigated — `git diff --name-only` shows only test files modified
- T-05.4-02 (Information Disclosure / pin date): accept — 2026-05-07 is a public calendar date
- T-05.4-03 (DoS / fixture slowdown): accept — freezegun move_to is ~ms per test
- T-05.4-04 (Repudiation / false confidence): mitigated — V-15/V-16 TZ-matrix tests at `test_politesse.py` + `test_24h_synthetic_clock_tz_matrix_produces_at_least_5_distinct_intervals` at `test_coordinator.py:1081` are the structural anti-repudiation gate, untouched
- T-05.4-05 (Elevation): N/A

## User Setup Required

None - this plan is pure test-infrastructure. No external service configuration, no secrets, no UAT step.

## Next Phase Readiness

- **Phase 5 WR-6 (test gate green) is now CLOSED.** Regression delta = 0 against the documented 14-failure baseline; all Plan 05-03 deliverables (atomic event gate, suspension short-circuit, circuit breaker, persistent notifications, jitter envelope) are now testable end-to-end.
- **Validation IDs V-08, V-15, V-16, V-17, V-20, V-21 are now reachable from the test harness** (running pytest no longer hits the férié-day short-circuit on real-clock dates like Pentecôte 2026-05-25).
- **Phase 6 (Auth Lifecycle) is unblocked:** the reauth flow tests it will add can confidently use this same `_frozen_school_day` autouse fixture pattern.
- **No blockers, no concerns.** The 14 pre-existing baseline failures remain tracked in `deferred-items.md` for a separate follow-up plan (Phase 7 DIST-07 for the test_manifest.py URL spec; a separate PHACC-drift plan for test_config_flow.py).

## Self-Check: PASSED

| Check | Result |
|---|---|
| SUMMARY.md file present | FOUND (236 lines) |
| Task 1 commit `df9fafb` reachable from worktree branch | FOUND |
| Task 2 commit `f1d36f4` reachable from worktree branch | FOUND |
| `_frozen_school_day` fixture present in all 3 test files | 1 + 1 + 1 = 3 matches |
| `import pytest` present in tests/test_sensor.py (BLOCKER-1) | 1 (was 0 at planning time) |
| Pin date `2026, 5, 7, 14, 0, 0` literal in all 3 test files | 1 + 1 + 1 = 3 matches |
| `JITTER_SECONDS` referenced in test_coordinator.py | 10 references |
| Old strict assertion `coordinator.update_interval == timedelta(minutes=30)` removed | 0 matches |
| V-08 new t0 anchor `datetime(2026, 5, 18, 14, 0` present | 1 match |
| Production code (`custom_components/ha_pronote/`) untouched | 0 files changed |
| `tests/conftest.py` untouched | 0 files changed |
| `tests/test_manifest.py` / `tests/test_config_flow.py` untouched | 0 files changed |
| Full pytest suite regression delta vs deferred-items.md baseline | 14 failed (exactly the baseline — delta 0) |

All checks pass. SUMMARY committed safely.

---

*Phase: 05-politesse-adaptive-polling-quiet-hours-circuit-breaker*
*Plan: 04 (gap closure)*
*Completed: 2026-05-25*
