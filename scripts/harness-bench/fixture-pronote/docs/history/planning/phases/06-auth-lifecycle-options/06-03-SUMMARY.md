---
phase: 06-auth-lifecycle-options
plan: 03
requirements:
  - AUTH-05
status: complete
---

# Plan 06-03 Summary — Reauth Flow (AUTH-05)

## Files Modified
- `custom_components/ha_pronote/config_flow.py` — added `_REAUTH_SCHEMA`, `async_step_reauth` (trampoline), `async_step_reauth_confirm` (form + 4-arm typed-exception mapping + `async_update_reload_and_abort(data_updates=...)` merge). `Mapping` moved into `TYPE_CHECKING` block (ruff TC003).
- `custom_components/ha_pronote/strings.json` — added `config.step.reauth_confirm` + `config.abort.reauth_successful`.
- `custom_components/ha_pronote/translations/en.json` — mirror of strings.json.
- `custom_components/ha_pronote/translations/fr.json` — French translations with accents (`Ré-authentification`).
- `tests/test_config_flow.py` — added `_REAUTH_ENTRY_DATA` constant + 4 test functions (1 happy-path, 1 parametrised over 4 exception types, 1 username-update, 1 password-masking) = 7 test invocations.

## Key Decisions Honored
- **D-01** — Two-field schema (`username` + `password`). URL + account_type preserved from `entry.data`, never re-asked.
- **D-02** — Commit via `async_update_reload_and_abort(data_updates={...})` (MERGE). `session: None` forces fresh-login branch on next setup. URL/account_type/child_identifier/child_name/child_index preserved untouched.
- **D-03** — `device_name = f"home-assistant-{entry.entry_id[:8]}"` stable across reauth.
- **D-04** — Four-arm typed exception mapping (`AuthError → invalid_auth`, `RateLimitedError → ip_suspended`, `CommunicationError → cannot_connect`, `PronoteIntegrationError → unknown`). HA-native `ConfigEntryAuthFailed` trigger (Phase 3 `__init__.py` + Phase 5 `coordinator._recover_from_auth_error` already raise it).

## RESEARCH Pitfalls Addressed
- **Pitfall #6 (data= replace bug)**: explicit `data_updates=` only. Negative grep guard `! grep -E '_reload_and_abort\([^)]*,\s*data='` clean.
- **Pitfall #7 (missing description_placeholders)**: `description_placeholders={"child_name": entry.data["child_name"]}` on `async_show_form`.

## Verification Results
- JSON validity: 3/3 i18n files parse.
- Ruff format + check: clean (TC003 fixed via TYPE_CHECKING block).
- `! grep -E '_reload_and_abort\([^)]*,\s*data=' custom_components/ha_pronote/config_flow.py` → clean (no `data=` replace).
- `grep -c description_placeholders` → ≥ 1.
- Reauth test breakdown:
  - `test_reauth_flow_happy_path` PASSED
  - `test_reauth_error_mapping[raised0-invalid_auth]` PASSED
  - `test_reauth_error_mapping[raised1-ip_suspended]` PASSED
  - `test_reauth_error_mapping[raised2-cannot_connect]` PASSED
  - `test_reauth_error_mapping[raised3-unknown]` PASSED
  - `test_reauth_updates_username_and_password` PASSED
  - `test_reauth_schema_masks_password_field` PASSED
- Full suite: **451 passed, 7 skipped, 0 failed** (was 444 pre-Wave-2 baseline; +7 new reauth invocations).

## key-files.created
- `.planning/phases/06-auth-lifecycle-options/06-03-SUMMARY.md` (this file)

## key-files.modified
- `custom_components/ha_pronote/config_flow.py`
- `custom_components/ha_pronote/strings.json`
- `custom_components/ha_pronote/translations/en.json`
- `custom_components/ha_pronote/translations/fr.json`
- `tests/test_config_flow.py`

## Note for Plan 06-04
`_REAUTH_ENTRY_DATA` constant in `tests/test_config_flow.py` is reusable for reconfigure tests. Plan 06-04 should add reconfigure tests in the same file using the same constant + the established `start_reauth_flow` / equivalent helper pattern.

## Self-Check: PASSED
- AUTH-05 covered: reauth flow ships, password rotation recoverable in one click.
- entry.data merge contract proven by test_reauth_flow_happy_path (URL/account_type/child_* preserved).
- Session cleared per D-02.
- Four-arm error mapping reuses the `_map_error` helper from baseline fix (no duplication).
- No regressions (full suite green).
