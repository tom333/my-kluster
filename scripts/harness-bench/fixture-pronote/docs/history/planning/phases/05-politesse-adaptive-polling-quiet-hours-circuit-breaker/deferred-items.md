# Phase 5 — Deferred Items

Out-of-scope discoveries logged during Plan execution. NOT fixed by Phase 5 plans.

---

## Pre-existing test failures (observed at Plan 05-02 Task 1 close, 2026-05-25)

The repo had 14 pre-existing pytest failures at `HEAD` BEFORE any Phase 5 plan
ran. They block on the WR-6 regression gate being interpreted strictly (full
suite green); we interpret WR-6 as "regression delta = 0" — confirmed via
baseline comparison (`git stash` + pytest run → identical 14 failures).

Each failure is unrelated to Plan 05-02's scope (manifest dep pin + const.py
additions + holiday_dates.py helper + probe). Listed for visibility:

### `tests/test_manifest.py` (2 failures)
- `test_manifest_documentation_url` — expects `https://github.com/tom333/ha-pronote`, manifest has `ha_pronote` (underscore). Spec/manifest discrepancy.
- `test_manifest_issue_tracker_url` — same hyphen-vs-underscore discrepancy.

### `tests/test_config_flow.py` (10 failures)
- 4× `test_user_step_error_mapping[*]` (invalid_auth / ip_suspended / cannot_connect / unknown)
- 3× `test_create_entry_set_active_child_error_aborts_with_mapped_reason[*]`
- 1× `test_create_entry_export_credentials_failure_aborts_cannot_connect`
- 1× `test_user_step_parent_two_children_transitions_to_pick_child`
- 1× `test_user_step_pick_child_creates_entry`

### `tests/test_coordinator.py` (1 failure)
- `test_recovery_cooldown_skips_back_to_back_auth_errors`

### `tests/test_token_persistence.py` (1 failure)
- `test_build_or_resume_client_uses_token_login_when_session_present`

These should be addressed in a separate Phase-3/4 follow-up plan (likely a
PHACC version drift since the last green CI run). They are NOT a Phase 5
deliverable. Plan 05-02 did not add or modify any of the affected modules.
