---
phase: 5
slug: politesse-adaptive-polling-quiet-hours-circuit-breaker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x via pytest-homeassistant-custom-component (PHACC) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1 D-29 — `asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/test_politesse.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~3-5 seconds for politesse module; ~30-40 seconds for full suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest <test files touched> -q`
- **After every plan wave:** Run `uv run pytest -q` (full suite + TZ matrix)
- **Before `/gsd-verify-work`:** Full suite must be green on BOTH `Europe/Paris` AND `Pacific/Noumea` (DIST-06)
- **Max feedback latency:** ~40 seconds (full suite)

---

## Per-Task Verification Map

> Per-plan/per-task IDs are placeholders pending PLAN.md creation (planner spawns next). The validation strategy itself is mapped 1:1 from RESEARCH.md `## Validation Architecture` to the 7 REQ-IDs + 4 ROADMAP success criteria. Planner MUST keep these test commands as the verification anchors for each task.

| Validation ID | Requirement | SC# | Plan (TBD) | Wave | Test Type | Automated Command | Status |
|---------------|-------------|-----|------------|------|-----------|-------------------|--------|
| V-01 | COORD-04 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_compute_interval_weekday_afternoon -q` | ⬜ pending |
| V-02 | COORD-04 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_compute_interval_base_weekday_morning -q` | ⬜ pending |
| V-03 | COORD-05 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_should_poll_weekend_suspended -q` | ⬜ pending |
| V-04 | COORD-05 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_should_poll_vacation_suspended -q` | ⬜ pending |
| V-05 | COORD-05 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_should_poll_ferie_suspended -q` | ⬜ pending |
| V-06 | COORD-06 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_should_fire_event_false_in_quiet_hours -q` | ⬜ pending |
| V-07 | COORD-06 | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_compute_interval_quiet_hours_cadence -q` | ⬜ pending |
| V-08 | COORD-07 | SC#2 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_3_consecutive_auth_failures_set_backoff_4h_and_notification -q` | ⬜ pending |
| V-09 | COORD-07 | SC#2 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_next_backoff_schedule_clamps_at_24h -q` | ⬜ pending |
| V-10 | COORD-08 | SC#2 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_ip_suspended_triggers_backoff_and_notification -q` | ⬜ pending |
| V-11 | COORD-08 | SC#2 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_recovery_resets_breaker_and_dismisses_notification -q` | ⬜ pending |
| V-12 | COORD-09 | SC#4 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_jitter_within_pm_30s_bounds -q` | ⬜ pending |
| V-13 | COORD-09 | SC#4 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_jitter_seeded_rng_reproducible -q` | ⬜ pending |
| V-14 | DIST-06 | SC#3 | 05-01 (pol.) | 1 | unit-matrix | `pytest tests/test_politesse_tz_matrix.py -q -k "tz_matrix"` (file name encodes the `tz_matrix` substring per BLOCKER-1 fix — module-level pytestmark parametrizes every test on `school_tz=[Europe/Paris, Pacific/Noumea]`) | ⬜ pending |
| V-15 | DIST-06 | SC#3 | 05-03 (coord.) | 2 | integration-matrix | `pytest tests/test_coordinator.py -q -k "tz_matrix"` | ⬜ pending |
| V-16 | COORD-04 + SC#1 (end-to-end) | SC#1 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_24h_synthetic_clock_tz_matrix_produces_at_least_5_distinct_intervals -q` (replays a synthetic 24h day across all branches; asserts cadence visibly adapts) | ⬜ pending |
| V-17 | COORD-06 (end-to-end) | SC#1 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_168h_synthetic_week_tz_matrix_zero_events_during_quiet_hours -q` (replays a synthetic 7-day week; asserts bus event count = 0 between 22h and 6h NC) | ⬜ pending |
| V-18 | COORD-04 / D-06 primer | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_compute_interval_sunday_evening_primer -q` | ⬜ pending |
| V-19 | COORD-04 / D-06 primer | SC#1 | 05-01 (pol.) | 1 | unit | `pytest tests/test_politesse_tz_matrix.py::test_compute_interval_last_day_of_vacation_evening_primer -q` | ⬜ pending |
| V-20 | D-10 suspension semantics | SC#1 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_async_update_data_skip_executor_during_suspension -q` (assert no pronotepy mock invocation when should_poll=False; assert sensors stay populated) | ⬜ pending |
| V-21 | D-15 notification body | SC#2 | 05-03 (coord.) | 2 | integration | `pytest tests/test_coordinator.py::test_notification_body_contains_next_retry_time_and_strike_count -q` (assert template substitution + redacted message) | ⬜ pending |
| V-22 | AST guard (D-16 invariant) | infra | 05-01 (pol.) | 1 | guard | `pytest tests/test_no_ha_imports.py -q` (extended to include politesse.py — zero homeassistant.* imports) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `custom_components/ha_pronote/politesse.py` — NEW pure HA-free module (Plan 05-01 ships)
- [ ] `tests/test_politesse_tz_matrix.py` — NEW pure unit test file with TZ matrix parametrization; file name encodes the `tz_matrix` substring per BLOCKER-1 fix (Plan 05-01 ships)
- [ ] `custom_components/ha_pronote/manifest.json` — APPEND `holidays==0.97` (Plan 05-02 ships, per research D-02 verified version)
- [ ] `custom_components/ha_pronote/const.py` — APPEND constants per CONTEXT.md D-18 + TROUBLESHOOTING_DOC_URL_BASE per BLOCKER-3 (Plan 05-02 ships)
- [ ] `custom_components/ha_pronote/holiday_dates.py` — NEW HA-free neutral helper module per WR-2 (Plan 05-02 ships)
- [ ] `scripts/check_translation_keys_phase5.py` — NEW recursive key-tree parity script per WR-5 (Plan 05-03 ships)
- [ ] `tests/conftest.py` — ADD `mock_persistent_notification` fixture (helper around patching `persistent_notification.async_create` / `async_dismiss`) for Plan 05-03 coordinator tests
- [ ] `tests/test_no_ha_imports.py` — APPEND `politesse.py` to the AST-guarded protected list (Plan 05-01 ships)
- [ ] `tests/test_coordinator.py` — EXTEND with circuit-breaker + suspension + event-gate scenarios (Plan 05-03 ships)

*No framework install needed — pytest + PHACC + freezegun + pytest-freezer all transitively present from Phase 1 install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live observability of cadence adapting over 24h in HA logs | COORD-04, SC#1 ("observable in the HA logs over a 24h window") | Requires installing the integration on a real HA instance and watching logs for ≥24h; not feasible in CI | (1) Install Phase 5 build on local HA. (2) Enable `logger.default: debug` for `custom_components.ha_pronote.*`. (3) Let it run for ≥24h including a Mon-Thu workday + Fri evening + Sat-Sun + a quiet-hours overnight period. (4) Grep logs for `update_interval` mutations, `Event suppressed during quiet hours`, `Skipping poll: should_poll=False`. (5) Confirm at least 5 distinct cadence values observed. |
| Persistent HA notification visible in UI on synthetic IP suspension | COORD-08 | Requires UI inspection; assertion on `persistent_notification.async_create` call args is in V-10/V-21 | (1) Force a synthetic `RateLimitedError(IP_SUSPENDED)` via dev-tools service call OR by temporarily breaking the URL to a 403-returning host. (2) Open HA Notifications panel (bell icon). (3) Confirm notification with title "[HA-Pronote] IP suspendue par Pronote" appears. (4) Confirm body includes the redacted next-retry time and strike count. (5) Force a successful poll. (6) Confirm notification auto-dismisses. |
| `holidays.France(subdiv='NC')` returns expected 2026 set | D-02 (probe step C-03) | One-off probe — output captured into `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`, becomes a fixture; not a recurring test | (1) Run `uv run --no-project --python 3.14 --with holidays==0.97 python scripts/probe_nc_holidays.py`. (2) Capture stdout into `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`. (3) Verify Fête de la citoyenneté (24/9/2026) appears in output. (4) If any expected NC-specific date is missing, populate `const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT` with the supplementing frozenset and re-run. (5) Commit the notes file + supplement. HUMAN-UAT sign-off required before release. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (politesse.py, test_politesse.py, holidays dep, const.py additions)
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter after planner finalizes per-task mapping

**Approval:** pending — planner spawns next; this strategy gets updated with concrete `{N}-XX-YY` task IDs once PLAN.md files exist.
