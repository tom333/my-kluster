---
phase: 06-auth-lifecycle-options
plan: 04
requirements:
  - AUTH-06
status: complete
---

# Plan 06-04 Summary — Reconfigure Flow (AUTH-06)

## Files Modified
- `custom_components/ha_pronote/config_flow.py` — added `_RECONFIGURE_SCHEMA` + `async_step_reconfigure` (D-05..D-08). Class-level block comment above method documents SC#4 rationale OUTSIDE the method body so `inspect.getsource` static-source check stays clean. Outer + inner try/except refactored to use `_map_error` helper (PLR0912 fix).
- `custom_components/ha_pronote/strings.json` — added `config.step.reconfigure` + `config.abort.reconfigure_successful` + `config.abort.child_identifier_changed`.
- `custom_components/ha_pronote/translations/en.json` — mirror.
- `custom_components/ha_pronote/translations/fr.json` — French translations (accents preserved).
- `tests/test_config_flow.py` — added 6 test functions, 9 invocations (1 form prefilled + 1 URL-change happy-path + 1 child-mismatch abort + 4 parametrised error mapping + 1 session-preserved + 1 session-cleared). `MagicMock` imported top-level.

## Key Decisions Honored
- **D-05** — URL + account_type editable. Username/password preserved (reauth flow owns them).
- **D-06** — Explicit `new_child_identifier != entry.data["child_identifier"]` comparison aborts with `reason="child_identifier_changed"`. THE ONLY guard.
- **D-07** — `build_or_resume_client(session=None)` re-validates BEFORE any persistence. On exception → form re-shown with `errors["base"]` mapped, NO entry mutation.
- **D-08** — `entry.data["session"]` cleared ONLY when URL or account_type changed (string-equal-after-strip). If just normalisation → session preserved.
- **ROADMAP SC#4** — `unique_id` PRESERVED across reconfigure. NO `async_set_unique_id`, NO `_abort_if_unique_id_mismatch` call-sites in method body. Entity history (Recorder, energy stats, automations) keyed on unique_id stays wired across host changes.
- **Pitfall #4** — `set_active_child` wrapped in same `_map_error`-driven typed except.
- **Pitfall #6** — `data_updates=` MERGE everywhere. Negative grep clean.

## Verification Results
- JSON validity: 3/3 i18n files parse.
- Ruff format + check: clean (refactored to use `_map_error` to satisfy PLR0912).
- `! grep -E '_reload_and_abort\([^)]*,\s*data=' custom_components/ha_pronote/config_flow.py` → clean.
- SC#4 invariant: `inspect.getsource(HaPronoteConfigFlow.async_step_reconfigure)` contains zero `self.async_set_unique_id(` / `self._abort_if_unique_id_mismatch(` call-sites.
- Reconfigure test breakdown (9 invocations):
  - `test_reconfigure_form_prefilled` PASSED
  - `test_reconfigure_flow_url_change_happy_path` PASSED (host change + unique_id preserved per SC#4)
  - `test_reconfigure_aborts_on_child_identifier_mismatch` PASSED (D-06)
  - `test_reconfigure_error_mapping[raised0-invalid_auth]` PASSED
  - `test_reconfigure_error_mapping[raised1-ip_suspended]` PASSED
  - `test_reconfigure_error_mapping[raised2-cannot_connect]` PASSED
  - `test_reconfigure_error_mapping[raised3-unknown]` PASSED
  - `test_reconfigure_session_preserved_when_no_change` PASSED (D-08 negative branch)
  - `test_reconfigure_session_cleared_when_account_type_changes` PASSED (D-08 positive branch)
- Full suite: **460 passed, 7 skipped, 0 failed** (+9 reconfigure since Plan 06-03's 451).

## key-files.created
- `.planning/phases/06-auth-lifecycle-options/06-04-SUMMARY.md` (this file)

## key-files.modified
- `custom_components/ha_pronote/config_flow.py`
- `custom_components/ha_pronote/strings.json`
- `custom_components/ha_pronote/translations/en.json`
- `custom_components/ha_pronote/translations/fr.json`
- `tests/test_config_flow.py`

## Note for Plan 06-05
OptionsFlow (`HaPronoteOptionsFlow(OptionsFlowWithReload)`) builds on the same `config_flow.py`. Plan 06-05 adds `async_get_options_flow` staticmethod + the OptionsFlow class. No interaction with reconfigure semantics.

## Self-Check: PASSED
- AUTH-06 covered: reconfigure flow ships, URL + account_type editable without losing entity history.
- SC#4 invariant proven by `test_reconfigure_flow_url_change_happy_path` (`entry.unique_id == original_unique_id` after host change).
- D-06 child-mismatch guard tested.
- D-08 session-clear conditional tested both branches (preserved + cleared).
- Pitfall #4 (set_active_child wrap) tested via the error_mapping parametrise.
- Pitfall #6 (merge contract) tested by happy-path's "credentials + child_* preserved" assertions.
- No regressions (full suite green).
