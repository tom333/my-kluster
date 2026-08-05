---
phase: 06-auth-lifecycle-options
plan: "01"
subsystem: politesse + const
tags:
  - phase-6
  - politesse
  - foundation
  - adaptive-polling
dependency_graph:
  requires:
    - custom_components/ha_pronote/politesse.py  # Phase 5 PolitesseOptions base
    - custom_components/ha_pronote/const.py      # Phase 5 constants base
  provides:
    - DEFAULT_ADAPTIVE_POLLING_ENABLED symbol in const.py
    - NICKNAME_MAX_LEN symbol in const.py
    - PolitesseOptions.adaptive_enabled field
    - compute_interval adaptive bypass branch
  affects:
    - 06-02 coordinator _resolve_options (reads adaptive_polling_enabled from entry.options)
    - 06-05 OptionsFlow schema (NICKNAME_MAX_LEN used by vol.Length validator)
tech_stack:
  added: []
  patterns:
    - "frozen dataclass field with default (backward-compat extension)"
    - "early-return short-circuit before branch tree in pure function"
    - "module-level pytestmark parametrize with school_tz for DIST-06 coverage"
key_files:
  created: []
  modified:
    - custom_components/ha_pronote/const.py
    - custom_components/ha_pronote/politesse.py
    - tests/test_politesse_tz_matrix.py
decisions:
  - "D-09 Phase 6: adaptive_enabled defaults True to preserve Phase 5 behavior unchanged"
  - "D-16 Phase 6: NICKNAME_MAX_LEN=40 const owns only length cap; strip is OptionsFlow schema concern"
  - "Test parametrize uses module-level school_tz (not separate tz_name) to match Phase 5 DIST-06 convention"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-25"
  tasks_completed: 2
  files_modified: 3
---

# Phase 06 Plan 01: Foundation Constants + PolitesseOptions Extension Summary

**One-liner:** Two const additions (`DEFAULT_ADAPTIVE_POLLING_ENABLED=True`, `NICKNAME_MAX_LEN=40`) and `PolitesseOptions.adaptive_enabled: bool = True` field with `compute_interval` short-circuit bypass, covered by 4 new TZ-matrix tests (Phase 5 DIST-06 style).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Append DEFAULT_ADAPTIVE_POLLING_ENABLED and NICKNAME_MAX_LEN to const.py | fabbd87 | `custom_components/ha_pronote/const.py` |
| 2 | Add adaptive_enabled field to PolitesseOptions + short-circuit branch + tests | 2070d78 | `custom_components/ha_pronote/politesse.py`, `tests/test_politesse_tz_matrix.py` |

## Verification Output

### V1: Full politesse TZ matrix suite

```
uv run pytest tests/test_politesse_tz_matrix.py -x -q
88 passed in 1.06s
```

All 88 tests pass (84 pre-existing + 4 new Phase 6 tests).

### V2: HA-free gate

```
uv run pytest tests/test_no_ha_imports.py -x -q
31 passed
```

`politesse.py` still imports only stdlib — no `homeassistant.*` leakage.

### V3: Symbol import verification

```
from custom_components.ha_pronote.const import DEFAULT_ADAPTIVE_POLLING_ENABLED, NICKNAME_MAX_LEN
DEFAULT_ADAPTIVE_POLLING_ENABLED=True, NICKNAME_MAX_LEN=40
```

### Acceptance Criteria Grep Output

```
grep -q "DEFAULT_ADAPTIVE_POLLING_ENABLED: Final = True" custom_components/ha_pronote/const.py  # exit 0
grep -q "NICKNAME_MAX_LEN: Final = 40" custom_components/ha_pronote/const.py                   # exit 0
grep -c "DEFAULT_REFRESH_INTERVAL" custom_components/ha_pronote/const.py                        # 1 (not deleted)
grep -c "BACKOFF_SCHEDULE" custom_components/ha_pronote/const.py                                # 1 (not deleted)
grep -q "adaptive_enabled: bool = True" custom_components/ha_pronote/politesse.py               # exit 0
grep -q "if not options.adaptive_enabled:" custom_components/ha_pronote/politesse.py            # exit 0
grep -c "adaptive_enabled" custom_components/ha_pronote/politesse.py                            # 2 (field + branch)
grep -q "test_compute_interval_respects_adaptive_disabled" tests/test_politesse_tz_matrix.py    # exit 0
grep -q "test_compute_interval_adaptive_enabled_default_preserves_phase5" tests/test_politesse_tz_matrix.py  # exit 0
```

All criteria satisfied.

## What Plans 06-02 and 06-05 Consume

- **Plan 06-02** (coordinator `_resolve_options` extension): reads `entry.options.get("adaptive_polling_enabled", DEFAULT_ADAPTIVE_POLLING_ENABLED)` and maps it to `PolitesseOptions(adaptive_enabled=bool(...))`.
- **Plan 06-05** (OptionsFlow schema): uses `NICKNAME_MAX_LEN` in `vol.All(cv.string, vol.Length(max=NICKNAME_MAX_LEN), lambda v: v.strip())` for the `nickname` field validation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test parametrize adapted to module-level pytestmark school_tz convention**

- **Found during:** Task 2, first test run
- **Issue:** The plan's spec used `@pytest.mark.parametrize("tz_name", [...])` with `tz_name` as parameter, but the file has `pytestmark = pytest.mark.parametrize("school_tz", [...])` which injects `school_tz` into ALL functions. A standalone function with `tz_name` instead of `school_tz` causes a pytest collection error ("function uses no argument 'school_tz'").
- **Fix:** Removed inner `@pytest.mark.parametrize("tz_name", ...)` decorator from both new test functions. Both functions accept `school_tz` (the module-level parametrize param) and use it both for `options.school_tz` and `now` creation — matching the Phase 5 `_build_options(school_tz)` DIST-06 pattern. The bypass test (adaptive=False) uses the same tz for both, which correctly validates that the bypass works regardless of the school timezone.
- **Files modified:** `tests/test_politesse_tz_matrix.py`
- **Commit:** 2070d78

## Known Stubs

None. The `TROUBLESHOOTING_DOC_URL_BASE` pre-existing stub (`<placeholder-owner>`) is from Phase 5 and is explicitly tracked for Phase 7 DIST-07 resolution. It is not in the const block added by this plan.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. Both new const symbols are immutable `Final` values (bool + int). The `adaptive_enabled` bool field is internal to `PolitesseOptions` — no untrusted input traverses this boundary; the coordinator (Plan 06-02) coerces via `bool(opts.get(..., True))`.

## Self-Check: PASSED

- `custom_components/ha_pronote/const.py` — FOUND
- `custom_components/ha_pronote/politesse.py` — FOUND
- `tests/test_politesse_tz_matrix.py` — FOUND
- `.planning/phases/06-auth-lifecycle-options/06-01-SUMMARY.md` — FOUND
- Commit fabbd87 — FOUND (feat(06-01): add DEFAULT_ADAPTIVE_POLLING_ENABLED and NICKNAME_MAX_LEN)
- Commit 2070d78 — FOUND (feat(06-01): add adaptive_enabled field to PolitesseOptions + compute_interval short-circuit)
- No accidental file deletions in commits
