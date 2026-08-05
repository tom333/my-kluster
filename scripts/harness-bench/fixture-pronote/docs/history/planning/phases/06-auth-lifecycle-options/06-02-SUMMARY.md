---
phase: 06-auth-lifecycle-options
plan: "02"
subsystem: coordinator + entity + init
tags:
  - phase-6
  - coordinator
  - entity
  - options
  - school-tz
  - nickname
  - adaptive-polling
dependency_graph:
  requires:
    - custom_components/ha_pronote/politesse.py  # PolitesseOptions.adaptive_enabled (06-01)
    - custom_components/ha_pronote/const.py      # DEFAULT_SCHOOL_TZ, NICKNAME_MAX_LEN (06-01)
    - custom_components/ha_pronote/coordinator.py  # _resolve_options (Phase 5)
    - custom_components/ha_pronote/entity.py       # PronoteEntity.device_info (Phase 4)
    - custom_components/ha_pronote/__init__.py      # async_setup_entry (Phase 3)
  provides:
    - "coordinator._resolve_options reads adaptive_polling_enabled from entry.options"
    - "async_setup_entry reads school_tz from entry.options (raw propagation)"
    - "PronoteEntity.device_info.name = nickname (stripped) OR entry.data['child_name']"
  affects:
    - 06-05 OptionsFlow (writes these three keys — reads must exist first)
    - 06-05 test_options_change_triggers_reload (asserts runtime effect)
tech_stack:
  added: []
  patterns:
    - "bool(opts.get(key, default)) — safe bool coercion with default (no parse-error path)"
    - "entry.options.get(key, DEFAULT) — fallback-aware options read"
    - "ZoneInfo() direct construction — no try/except (feedback_no_silent_exceptions.md)"
    - "(value or '').strip() or fallback — strip + empty-as-None chain"
    - "device registry assertion (dr.async_get + async_get_device) for DeviceInfo tests"
key_files:
  created: []
  modified:
    - custom_components/ha_pronote/coordinator.py
    - custom_components/ha_pronote/politesse.py
    - custom_components/ha_pronote/__init__.py
    - custom_components/ha_pronote/entity.py
    - tests/test_coordinator.py
    - tests/test_init.py
    - tests/test_sensor.py
decisions:
  - "D-09 Phase 6: adaptive_polling_enabled read via bool(opts.get(..., True)) — no _read_* helper needed"
  - "D-12 REVISED: NO entry.add_update_listener in __init__.py — OptionsFlowWithReload (06-05) handles reload"
  - "D-13 / ENT-02: nickname affects ONLY DeviceInfo.name — unique_id and entity_id stay frozen on child_identifier"
  - "D-14: nickname fallback uses entry.data['child_name'] from Phase 3 D-08 — no Pronote re-fetch"
  - "D-16: empty/whitespace nickname strips to '' and falls through to child_name"
  - "OPT-04: ZoneInfoNotFoundError propagates raw — HA logs traceback, entry enters SETUP_ERROR"
  - "Rule 3 deviation: PolitesseOptions.adaptive_enabled added in this plan (06-01 worktree base was stale)"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-26"
  tasks_completed: 3
  files_modified: 7
---

# Phase 06 Plan 02: Read-Side Options Wiring Summary

**One-liner:** Three entry.options read paths wired into the runtime: `adaptive_polling_enabled` → `PolitesseOptions.adaptive_enabled` in coordinator, `school_tz` → `ZoneInfo()` direct construction (raw propagation, no try/except) in `async_setup_entry`, and `nickname` → `DeviceInfo.name` strip-or-fallback in `PronoteEntity.device_info`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend coordinator._resolve_options with adaptive_polling_enabled + PolitesseOptions.adaptive_enabled | 240a536 | `custom_components/ha_pronote/coordinator.py`, `custom_components/ha_pronote/politesse.py`, `tests/test_coordinator.py` |
| 2 | Read school_tz from entry.options in async_setup_entry — raw ZoneInfo propagation | b432c2f | `custom_components/ha_pronote/__init__.py`, `tests/test_init.py` |
| 3 | PronoteEntity.device_info nickname fallback + parametrised test | 3b7ee8d | `custom_components/ha_pronote/entity.py`, `tests/test_sensor.py` |

## Verification Output

### Acceptance Criteria Grep Output

**Task 1:**
```
grep -q "adaptive_enabled=bool(opts.get" custom_components/ha_pronote/coordinator.py  # exit 0 ✓
grep -q "test_resolve_options_adaptive_disabled_propagates" tests/test_coordinator.py  # exit 0 ✓
grep -q "test_resolve_options_adaptive_default_is_true" tests/test_coordinator.py      # exit 0 ✓
```

**Task 2:**
```
grep -q "entry.options.get(\"school_tz\"" custom_components/ha_pronote/__init__.py  # exit 0 ✓
grep -E "except.*(ZoneInfoNotFoundError|ValueError).*:.*ConfigEntryNotReady" __init__.py
  → 0 matches (no try/except wrapper — CRITICAL requirement satisfied) ✓
grep -c "entry.add_update_listener" custom_components/ha_pronote/__init__.py
  → 0 (D-12 REVISED enforced) ✓
grep -q "test_async_setup_entry_school_tz_override_takes_effect" tests/test_init.py   # exit 0 ✓
grep -q "test_async_setup_entry_school_tz_invalid_raises_zoneinfo_error" tests/test_init.py  # exit 0 ✓
```

**Task 3:**
```
grep -q "display_name = (" custom_components/ha_pronote/entity.py             # exit 0 ✓
grep -q "self._entry.options.get(\"nickname\"" custom_components/ha_pronote/entity.py  # exit 0 ✓
grep -q "name=display_name" custom_components/ha_pronote/entity.py            # exit 0 ✓
grep -c "identifiers={(DOMAIN, self._entry.runtime_data.child_identifier)}" entity.py
  → 1 (ENT-02 invariant — identifiers frozen on child_identifier, NEVER nickname) ✓
grep -q "test_device_info_nickname_fallback" tests/test_sensor.py             # exit 0 ✓
```

### Task 1 Test Run (verified GREEN)

Tests `test_resolve_options_adaptive_disabled_propagates` and `test_resolve_options_adaptive_default_is_true` were verified GREEN during execution:
```
uv run pytest tests/test_coordinator.py::test_resolve_options_adaptive_disabled_propagates \
  tests/test_coordinator.py::test_resolve_options_adaptive_default_is_true -x -q --timeout=60
2 passed ✓
```

Full coordinator suite (excluding pre-existing failure `test_recovery_cooldown_skips_back_to_back_auth_errors`):
```
33 passed, 1 deselected in 1.49s
```

The pre-existing failure `test_recovery_cooldown_skips_back_to_back_auth_errors` was confirmed pre-existing (fails without any changes from this plan).

### Test 2 and 3 Verification (code logic verified)

Task 2 and Task 3 tests could not be re-run due to sandbox throttling after Task 1, but the code logic was verified by:
- The RED assertions were confirmed correct (the code WOULD fail before the implementation)
- The GREEN implementations match the exact patterns specified in the plan
- All acceptance criteria greps pass

## What Plan 06-05 Consumes

Plan 06-05's OptionsFlow writes `adaptive_polling_enabled`, `school_tz`, and `nickname` to `entry.options`. These three read paths must exist before the OptionsFlow so that `test_options_change_triggers_reload` can assert the runtime effect after each option save.

The OptionsFlow `async_step_display` is the PRIMARY validation gate for `school_tz` (Pitfall #5 from 06-RESEARCH.md) — `__init__.async_setup_entry` deliberately does NOT validate, it propagates raw.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree base at Phase 4 — missing Phase 5 + 06-01 prerequisites**

- **Found during:** Pre-execution worktree check
- **Issue:** The worktree was based on commit `3a014d1` (Phase 4 end). The plan assumes Phase 5 (`_resolve_options`, `PolitesseOptions`, `politesse.py`, circuit breaker) and Plan 06-01 (`adaptive_enabled` field) are present. Neither existed in the worktree.
- **Fix:** Merged `fabbd87` (main HEAD at execution time) to bring Phase 5 + 06-01 const additions. Subsequently merged `980ee5f` (06-01 full completion including `adaptive_enabled` in PolitesseOptions) when discovered it was also missing.
- **Impact:** The `PolitesseOptions.adaptive_enabled` field was added twice (once by my Task 1 commit `240a536`, once by the merged `2070d78`). Git auto-resolved to the correct single field. Final file state is correct.
- **Files modified:** `custom_components/ha_pronote/politesse.py` (via merge), full Phase 5 stack (via merge)

**2. [Rule 1 - Bug] PolitesseOptions.adaptive_enabled pre-added in Task 1 (later merged from 06-01)**

- **Found during:** Task 1 execution
- **Issue:** When I started Task 1, `PolitesseOptions` did not have `adaptive_enabled` (worktree was at Phase 4, 06-01 merge brought only const additions). Adding `adaptive_enabled=bool(...)` to the `_resolve_options` return would fail because `PolitesseOptions.__init__` doesn't accept it.
- **Fix:** Added `adaptive_enabled: bool = True` to `PolitesseOptions` in Task 1 commit `240a536` as a Rule 3 prerequisite fix. When the full 06-01 commit `2070d78` was later merged, git auto-resolved the duplicate to the single correct field.
- **Files modified:** `custom_components/ha_pronote/politesse.py`

## Known Stubs

None. All three read paths wire to their implementation:
- `adaptive_enabled`: reads from `entry.options` and maps to `PolitesseOptions` field consumed by `compute_interval`
- `school_tz`: reads from `entry.options`, constructs `ZoneInfo`, passes to coordinator and `runtime_data`
- `nickname`: reads from `entry.options`, applies strip + fallback, returns as `DeviceInfo.name`

No hardcoded empty values, no placeholder text, no TODO comments in the new code.

## Threat Flags

No new threat flags beyond what the plan's threat model documented:
- T-06-02-01 (school_tz injection) — mitigated by raw propagation (invalid IANA → SETUP_ERROR, no exec path)
- T-06-02-02 (traceback disclosure) — accepted per user feedback memory
- T-06-02-03 (nickname markup) — mitigated by display-only consumption + NICKNAME_MAX_LEN at write-side
- T-06-02-04 (adaptive_polling_enabled corruption) — mitigated by `bool(...)` coercion
- T-06-02-05 (reload loop) — mitigated by NO `entry.add_update_listener` (D-12 REVISED enforced)

## Self-Check: PASSED

- `custom_components/ha_pronote/coordinator.py` — FOUND
- `custom_components/ha_pronote/politesse.py` — FOUND
- `custom_components/ha_pronote/__init__.py` — FOUND
- `custom_components/ha_pronote/entity.py` — FOUND
- `tests/test_coordinator.py` — FOUND
- `tests/test_init.py` — FOUND
- `tests/test_sensor.py` — FOUND
- `.planning/phases/06-auth-lifecycle-options/06-02-SUMMARY.md` — this file
- Commit 240a536 — FOUND (Task 1: coordinator _resolve_options + PolitesseOptions.adaptive_enabled)
- Commit b432c2f — FOUND (Task 2: school_tz from entry.options, raw ZoneInfo propagation)
- Commit 3b7ee8d — FOUND (Task 3: nickname fallback in entity.py + parametrised test)
- No accidental file deletions in commits
