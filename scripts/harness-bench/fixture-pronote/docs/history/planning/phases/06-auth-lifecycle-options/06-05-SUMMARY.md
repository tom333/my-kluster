---
phase: 06-auth-lifecycle-options
plan: 05
requirements:
  - COORD-03
  - OPT-01
  - OPT-02
  - OPT-03
  - OPT-04
status: complete
---

# Plan 06-05 Summary — OptionsFlow (COORD-03 + OPT-01..04)

## Files Modified
- `custom_components/ha_pronote/config_flow.py` — added `_POLLING_SCHEMA` (9 fields, Number/Boolean/Time selectors), `_DISPLAY_SCHEMA` (nickname + school_tz, lambda strip), `_options_schema_defaults(entry)` (D-11 single source of truth), `HaPronoteOptionsFlow(OptionsFlowWithReload)` class + `async_get_options_flow` staticmethod. Critical Gotcha #2 comment refactored to avoid literal `vol.Strip` token so regression guard stays clean.
- `custom_components/ha_pronote/strings.json` — added top-level `"options"` block with `step.polling.*` + `step.display.*` + `error.invalid_school_tz`.
- `custom_components/ha_pronote/translations/en.json` — mirror.
- `custom_components/ha_pronote/translations/fr.json` — French translations with accents.
- `tests/test_config_flow.py` — added 5 test functions, 8 invocations (subclass smoke + multi-step commit + invalid_school_tz + nickname parametrize × 4 + defaults invariant). Imports promoted to top-level.
- `tests/test_coordinator.py` — added `test_options_change_triggers_reload` (OPT-04 / D-12 REVISED). `_timedelta` import promoted to top-level.
- `tests/test_init.py` — added 3 permanent regression guards (`test_no_deprecated_add_update_listener_in_production`, `test_no_vol_strip_in_production`, `test_no_options_flow_init_config_entry_assignment`). W-2 satisfied — all three Gotchas have equal coverage.

## Critical Gotchas Encoded
1. **Gotcha #1** — `HaPronoteOptionsFlow(OptionsFlowWithReload)` — NOT `OptionsFlow` + `entry.add_update_listener`. Production-tree grep clean. Permanent pytest guard in `test_init.py`.
2. **Gotcha #2** — `vol.All(cv.string, vol.Length(max=NICKNAME_MAX_LEN), lambda v: v.strip())` — NEVER `vol.Strip`. Production-tree grep clean. Permanent pytest guard.
3. **Gotcha #3** — `def __init__(self) -> None:` (no `config_entry` arg, no `self.config_entry = ...`). HA injects `self.config_entry`. Production-tree grep clean. Permanent pytest guard.

## Key Decisions Honored
- **D-09 / D-10** — 9-field Polling step + 2-field Display step; `async_step_init` trampolines to `async_step_polling`.
- **D-11** — `_options_schema_defaults` single source of truth. Invariant test `test_options_defaults_match_resolve_options` proves agreement with `coordinator._resolve_options`.
- **D-15** — `hass.config_entries.async_update_entry(entry, title=nickname)` when nickname truthy. Tested via nickname parametrize.
- **D-16 REVISED** — lambda strip (Gotcha #2).
- **Pitfall #5** — `ZoneInfo(user_input["school_tz"])` validates inside step 2; error key `invalid_school_tz` surfaces inline.
- **W-5** — device-registry round-trip asserted in `test_options_nickname_strip_and_title_update` (read-side Plan 06-02 × write-side Plan 06-05).

## Verification Results
- JSON validity: 3/3 i18n files parse.
- Ruff format + check: clean. PLR0913 noqa on 6-arg parametrised test.
- `! grep -rE "vol\.Strip|add_update_listener\(|self\.config_entry = config_entry|def __init__\(self,\s*config_entry" custom_components/ha_pronote/` → clean.
- OptionsFlow tests + reload test + regression guards: **12 new invocations all PASSED**.
- Full suite: **472 passed, 7 skipped, 0 failed** (+12 since Plan 06-04's 460).

## key-files.created
- `.planning/phases/06-auth-lifecycle-options/06-05-SUMMARY.md` (this file)

## key-files.modified
- `custom_components/ha_pronote/config_flow.py`
- `custom_components/ha_pronote/strings.json`
- `custom_components/ha_pronote/translations/en.json`
- `custom_components/ha_pronote/translations/fr.json`
- `tests/test_config_flow.py`
- `tests/test_coordinator.py`
- `tests/test_init.py`

## Note for Plan 06-06
OptionsFlow shipping unblocks multi-child isolation tests — Plan 06-06 can now drive OptionsFlow on entry A while verifying entry B's options stay unchanged. Phase 6 OptionsFlow ships D-09..D-16 with RESEARCH revisions encoded; Plan 06-06 verifies multi-child isolation on top.

## Self-Check: PASSED
- COORD-03 + OPT-01..04 covered.
- `OptionsFlowWithReload` re-instantiates coordinator on commit (proven by `test_options_change_triggers_reload`).
- 11-key commit shape verified.
- 3 regression guards permanent (CI-ready).
- D-15 title update + W-5 device.name round-trip both tested.
- D-11 single source of truth invariant locked.
- No regressions (full suite green).
