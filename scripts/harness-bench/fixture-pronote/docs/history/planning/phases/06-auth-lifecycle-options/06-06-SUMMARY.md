---
phase: 06-auth-lifecycle-options
plan: 06
requirements:
  - AUTH-03
status: complete
---

# Plan 06-06 Summary — Multi-Child Isolation (AUTH-03)

## Files Modified
- `tests/test_config_flow.py` — added `_make_entry` factory + 5 multi-child isolation tests. `date` import promoted to top-level.

## Tests Added (5)
- `test_two_children_options_are_independent` — AUTH-03 / D-17: OptionsFlow on entry A does NOT mutate entry B's options.
- `test_two_children_reauth_a_does_not_affect_b` — reauth on entry A only mutates A's credentials.
- `test_two_children_reconfigure_a_does_not_affect_b` — reconfigure on entry A only mutates A's URL; both unique_ids preserved (SC#4).
- `test_reconfigure_url_change_preserves_unique_id` — dedicated SC#4 invariant test (single-entry). Asserts unique_id frozen across host change.
- `test_two_children_two_distinct_coordinators_after_setup` — each entry gets its own coordinator instance after setup.

## Key Decisions Honored
- **AUTH-03 / D-17** — no new production code. Phase 3 D-05 unique_id pattern + `_abort_if_unique_id_configured` already supports multi-entry. Phase 6 ONLY verifies non-regression across the new mutation flows.
- **SC#4** — unique_id frozen across reconfigure (host change is happy path). Explicit `assert entry_a.unique_id == original_unique_id_a` after host-change reconfigure.

## Test Harness Adjustments
- Multi-entry setup pattern: `add_to_hass` + `async_setup(entry_id)` + `async_block_till_done` per entry, sequentially (HA refuses double-setup if MockConfigEntry auto-loaded).

## Verification Results
- Ruff format + check: clean.
- 5 new multi-child tests + 1 SC#4 invariant test (also matched by "url_change_preserves_unique_id" pattern; this test was added in Plan 06-04 revision and stays as the dedicated SC#4 invariant gate).
- Full suite: **477 passed, 7 skipped, 0 failed** (+5 since Plan 06-05's 472).

## key-files.created
- `.planning/phases/06-auth-lifecycle-options/06-06-SUMMARY.md` (this file)

## key-files.modified
- `tests/test_config_flow.py`

## Self-Check: PASSED
- AUTH-03 covered: 4 mutation flows tested for isolation (options/reauth/reconfigure/runtime coordinator).
- SC#4 invariant proven by `test_reconfigure_url_change_preserves_unique_id` + the multi-child reconfigure test's `assert entry_a.unique_id == original_unique_id_a`.
- No regressions.
- Phase 6 complete — all 6 plans landed.
