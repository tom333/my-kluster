---
phase: 06-auth-lifecycle-options
verified: 2026-05-30T06:33:59Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 6: Auth Lifecycle & Options — Verification Report

**Phase Goal:** A user whose password changes can recover in one click; a user with two children sees two independent integrations; every per-entry knob is editable from the UI without recreating the entry.
**Verified:** 2026-05-30T06:33:59Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Critical Environment Note

**Python version matters.** The project targets Python 3.14.2 (HA 2026.3+ requirement). The production `config_flow.py` at line 562 uses:

```python
except ZoneInfoNotFoundError, ValueError:
```

This is **Python 3.14 syntax** (bare tuple in except clause, valid per the 3.14 parser). It is a `SyntaxError` under Python 3.13 and earlier. Verification was run with `.venv/bin/python3` (Python 3.14.2) which is the project's required runtime — all results below reflect this correct environment.

**Full suite result (Python 3.14.2):** 477 passed, 7 skipped, 0 failed.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can add a second child via "Add Integration" — two coordinators run independently | VERIFIED | `test_two_children_two_distinct_coordinators_after_setup` passes: `coord_a is not coord_b`, each entry has its own `runtime_data.child_identifier`. Phase 3 D-05 `unique_id` format encodes multi-entry; `_abort_if_unique_id_configured()` in `async_step_user` prevents duplicates. |
| 2 | After password change, reauth flow asks ONLY for new password (URL/account_type preserved); entry resumes without losing entity history | VERIFIED | `async_step_reauth` + `async_step_reauth_confirm` present in `config_flow.py:279-337`. `_REAUTH_SCHEMA` = username + password only. `async_update_reload_and_abort(data_updates={...})` (merge, not replace). `test_reauth_flow_happy_path` asserts URL/account_type/child_* all preserved after success. |
| 3 | User can change refresh_interval, toggle adaptive polling, set nickname, override school_tz via Options — coordinator reloads automatically | VERIFIED | `HaPronoteOptionsFlow(OptionsFlowWithReload)` at line 518. 9-field polling step + 2-field display step. `_options_schema_defaults` single source of truth. `test_options_flow_polling_then_display_commit` asserts all 11 keys committed to entry.options. `test_options_change_triggers_reload` asserts coordinator re-instantiated after commit. |
| 4 | User can change URL or account_type via reconfigure without losing entity history (unique_id preserved) | VERIFIED | `async_step_reconfigure` at line 357. No `async_set_unique_id` or unique-id helper called inside the method body (confirmed by AST inspection). D-06 child_identifier guard present. `test_reconfigure_url_change_preserves_unique_id` asserts `entry.unique_id == original_unique_id` after host-change. |

**Score:** 4/4 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/ha_pronote/const.py` | DEFAULT_ADAPTIVE_POLLING_ENABLED + NICKNAME_MAX_LEN | VERIFIED | Lines 93–94: `DEFAULT_ADAPTIVE_POLLING_ENABLED: Final = True`, `NICKNAME_MAX_LEN: Final = 40` |
| `custom_components/ha_pronote/politesse.py` | PolitesseOptions.adaptive_enabled field + compute_interval short-circuit | VERIFIED | Line 80: `adaptive_enabled: bool = True`. Lines 323–327: `if not options.adaptive_enabled:` early-return with refresh_interval ± jitter. |
| `custom_components/ha_pronote/coordinator.py` | `_resolve_options` reads adaptive_polling_enabled | VERIFIED | Line 439: `adaptive_enabled=bool(opts.get("adaptive_polling_enabled", True))` |
| `custom_components/ha_pronote/__init__.py` | school_tz override from entry.options (raw ZoneInfo, no try/except) | VERIFIED | Lines 71–72: `school_tz_name = entry.options.get("school_tz", DEFAULT_SCHOOL_TZ)` then `school_tz = ZoneInfo(school_tz_name)` — no try/except, ZoneInfoNotFoundError propagates raw. |
| `custom_components/ha_pronote/entity.py` | DeviceInfo.name nickname fallback | VERIFIED | Lines 91–94: `(self._entry.options.get("nickname") or "").strip() or self._entry.data["child_name"]` |
| `custom_components/ha_pronote/config_flow.py` | async_step_reauth + async_step_reauth_confirm | VERIFIED | Lines 279–337. _REAUTH_SCHEMA (2 fields). async_update_reload_and_abort with data_updates= merge. |
| `custom_components/ha_pronote/config_flow.py` | async_step_reconfigure | VERIFIED | Lines 357–447. _RECONFIGURE_SCHEMA (2 fields). D-06 child_identifier guard. D-08 conditional session clear. |
| `custom_components/ha_pronote/config_flow.py` | HaPronoteOptionsFlow (OptionsFlowWithReload, multi-step) | VERIFIED | Lines 518–581. Inherits OptionsFlowWithReload. __init__ takes no config_entry arg. async_step_init trampolines to async_step_polling. |
| `custom_components/ha_pronote/strings.json` | reauth_confirm + reconfigure + options blocks | VERIFIED | config.step.reauth_confirm, config.step.reconfigure, config.abort.reauth_successful, config.abort.reconfigure_successful, config.abort.child_identifier_changed, options.step.polling, options.step.display, options.error.invalid_school_tz all present. |
| `custom_components/ha_pronote/translations/fr.json` | French translations for all Phase 6 keys | VERIFIED | Ré-authentification Pronote, Modifier l'URL..., Polling, Affichage, fuseau horaire... all present. |
| `tests/test_politesse_tz_matrix.py` | Adaptive bypass test at 18:00 school evening | VERIFIED | 88 tests pass. test_compute_interval_adaptive_disabled_bypasses_afternoon_window at lines 491+. |
| `tests/test_config_flow.py` | Reauth, reconfigure, OptionsFlow, multi-child tests | VERIFIED | 43 tests pass. test_reauth_flow_happy_path, test_reconfigure_flow_happy_path, test_options_flow_polling_then_display_commit, test_two_children_options_are_independent, test_two_children_reauth_a_does_not_affect_b, test_two_children_reconfigure_a_does_not_affect_b, test_reconfigure_url_change_preserves_unique_id, test_two_children_two_distinct_coordinators_after_setup — all present and passing. |
| `tests/test_init.py` | 3 permanent regression guards | VERIFIED | test_no_deprecated_add_update_listener_in_production, test_no_vol_strip_in_production, test_no_options_flow_init_config_entry_assignment — all pass (3 passed in 0.16s). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config_flow.py:async_step_reauth_confirm` | `api/client.py:build_or_resume_client` | `hass.async_add_executor_job(partial(...))` | WIRED | Line 302: `await self.hass.async_add_executor_job(partial(build_or_resume_client, ...))` |
| `config_flow.py:async_step_reauth_confirm` | `async_update_reload_and_abort(data_updates=...)` | merge pattern | WIRED | Lines 323–330: uses `data_updates=` (not `data=`). Session cleared, URL/account_type preserved. |
| `config_flow.py:async_step_reconfigure` | `api/client.py:build_or_resume_client` | `hass.async_add_executor_job(partial(...))` | WIRED | Lines 378–388: validates before persistence. |
| `config_flow.py:async_step_reconfigure` | `async_abort(reason="child_identifier_changed")` | D-06 explicit string comparison | WIRED | Line 414: `if new_child_identifier != entry.data["child_identifier"]: return self.async_abort(reason="child_identifier_changed")` |
| `config_flow.py:HaPronoteOptionsFlow` | `homeassistant.config_entries.OptionsFlowWithReload` | subclass | WIRED | `class HaPronoteOptionsFlow(OptionsFlowWithReload):` line 518. Auto-reloads on async_create_entry. |
| `config_flow.py:_options_schema_defaults` | `coordinator.py:_resolve_options` | shared DEFAULT_* constants from const.py (D-11) | WIRED | Both read the same `opts.get(key, DEFAULT_*)` pattern. Invariant tested by `test_options_defaults_match_resolve_options`. |
| `coordinator.py:_resolve_options` | `politesse.py:PolitesseOptions.adaptive_enabled` | `bool(opts.get("adaptive_polling_enabled", True))` | WIRED | Line 439. Propagates to PolitesseOptions then into compute_interval short-circuit. |
| `__init__.py:async_setup_entry` | `entry.options.get("school_tz")` | ZoneInfo direct construction | WIRED | Lines 71–72. No try/except per feedback_no_silent_exceptions.md. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `entity.py:device_info` | `display_name` | `entry.options.get("nickname")` then `entry.data["child_name"]` fallback | Yes — reads from live HA entry store | FLOWING |
| `coordinator.py:_resolve_options` | `adaptive_enabled` | `entry.options.get("adaptive_polling_enabled", True)` | Yes — reads from live HA options store | FLOWING |
| `__init__.py:async_setup_entry` | `school_tz` | `entry.options.get("school_tz", DEFAULT_SCHOOL_TZ)` | Yes — reads from live HA options store | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 477 tests pass with Python 3.14 | `.venv/bin/python3 -m pytest tests/ 2>&1 \| tail -1` | 477 passed, 7 skipped in 14.12s | PASS |
| Reauth test suite passes | `.venv/bin/python3 -m pytest tests/test_config_flow.py 2>&1 \| tail -1` | 43 passed | PASS |
| Regression guards pass | `.venv/bin/python3 -m pytest tests/test_init.py -k "no_deprecated or no_vol or no_options_flow" 2>&1 \| tail -1` | 3 passed | PASS |
| Adaptive politesse tests pass | `.venv/bin/python3 -m pytest tests/test_politesse_tz_matrix.py 2>&1 \| tail -1` | 88 passed | PASS |
| SC#4 unique_id immutability test passes | `.venv/bin/python3 -m pytest tests/test_config_flow.py::test_reconfigure_url_change_preserves_unique_id` | PASSED | PASS |
| compute_interval short-circuit with adaptive_enabled=False | Line 323 in politesse.py; test in tz_matrix passes | Returns refresh_interval ± jitter regardless of 18:00 match | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AUTH-03 | 06-06 | Multiple children — one ConfigEntry per child | SATISFIED | Phase 3 D-05 unique_id format encodes it. Plans 06-06 ships 5 isolation tests proving non-regression across all Phase 6 mutation flows. |
| AUTH-05 | 06-03 | Reauth flow (password-only) after password change | SATISFIED | async_step_reauth + async_step_reauth_confirm in config_flow.py. test_reauth_flow_happy_path passes. |
| AUTH-06 | 06-04 | Reconfigure flow (URL/account_type) without losing entity history | SATISFIED | async_step_reconfigure in config_flow.py. SC#4 unique_id preserved — confirmed by AST inspection and test_reconfigure_url_change_preserves_unique_id. |
| COORD-03 | 06-01, 06-05 | refresh_interval configurable via Options Flow | SATISFIED | _POLLING_SCHEMA includes refresh_interval field. _resolve_options reads it. test_options_flow_polling_then_display_commit asserts correct value committed. |
| OPT-01 | 06-05 | User can modify refresh_interval from Options Flow without recreating entry | SATISFIED | HaPronoteOptionsFlow(OptionsFlowWithReload) — no entry recreation needed. 11 keys committed in single flow. |
| OPT-02 | 06-01, 06-05 | User can enable/disable adaptive polling 17h-20h | SATISFIED | adaptive_polling_enabled field in _POLLING_SCHEMA. PolitesseOptions.adaptive_enabled field. compute_interval short-circuit. Full TZ-matrix test coverage. |
| OPT-03 | 06-02, 06-05 | User can set child nickname | SATISFIED | nickname field in _DISPLAY_SCHEMA with lambda strip. DeviceInfo.name fallback chain in entity.py. D-15 title update via async_update_entry. |
| OPT-04 | 06-05 | Coordinator reloads automatically when options change | SATISFIED | OptionsFlowWithReload base class handles reload automatically. test_options_change_triggers_reload asserts coord_before is not coord_after. |

All 8 Phase 6 requirements SATISFIED.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `config_flow.py` | 562 | `except ZoneInfoNotFoundError, ValueError:` | INFO | **Python 3.14 syntax only** — valid in 3.14 (bare tuple in except). Raises SyntaxError under Python 3.13. The project targets Python 3.14.2 per HA 2026.3+ requirement and the project venv. Not a blocker; may confuse contributors using older Python for linting. |

No TODO/FIXME/placeholder comments found in Phase 6 production code. No empty implementations. No `return null` stubs.

---

## Human Verification Required

None. All observable truths are verifiable programmatically and confirmed by the passing test suite.

---

## Gaps Summary

No gaps. All 4 ROADMAP success criteria verified, all 8 requirements satisfied, all key links wired, all artifacts substantive and wired.

**Note on Python version:** The one item worth human awareness (not a gap) is that `except ZoneInfoNotFoundError, ValueError:` on line 562 is Python 3.14 syntax. If a contributor runs ruff or tests with Python 3.13, they will see a SyntaxError. This is intentional — the project floor is Python 3.14.2. Recommend adding a note in CLAUDE.md or pyproject.toml that the dev environment must use Python 3.14+.

---

_Verified: 2026-05-30T06:33:59Z_
_Verifier: Claude (gsd-verifier)_
