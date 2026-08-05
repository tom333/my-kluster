---
phase: 03-coordinator-first-sensor
fixed_at: 2026-05-07T00:00:00Z
review_path: .planning/phases/03-coordinator-first-sensor/03-REVIEW.md
iteration: 3
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report — Cycle 3

**Fixed at:** 2026-05-07
**Source review:** `.planning/phases/03-coordinator-first-sensor/03-REVIEW.md` (cycle 2)
**Iteration:** 3 (final cycle of `--auto` fix loop)

**Summary:**
- Findings in scope: 2 (1 BLOCKER + 1 WARNING; the 3 INFO findings were intentionally out of default `--fix` scope)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-06: `api/fetcher.py:54` calls raw `client.set_child` — CR-04 fix is incomplete

**Files modified:** `custom_components/ha_pronote/api/client.py`, `custom_components/ha_pronote/api/fetcher.py`, `tests/test_api/test_fetcher.py`
**Commit:** `f41b15f`
**Applied fix:** Replaced the raw `client.set_child(child_index_or_identifier)` call inside `fetch_all` with `set_active_child(client, child_index_or_identifier)` (already exported from `api/__init__.py` since cycle-1 CR-04). The wrapper produces typed exceptions (`AuthError` / `RateLimitedError` / `CommunicationError`) that the coordinator's `_async_update_data` already catches — so a stale parent session's `CryptoError` now correctly enters D-09 silent recovery instead of leaking through HA's safety net as a generic `UpdateFailed`. Three companion changes:

1. Added `from .client import set_active_child` to `api/fetcher.py`.
2. Widened `set_active_child`'s second parameter type from `int` to `int | str` to match `fetch_all`'s `child_index_or_identifier: int | str | None` surface — pronotepy's `set_child` accepts either form, and existing tests (`test_fetch_all_calls_set_child_for_parent_client_with_string_identifier`) already covered the string path. No behavioural change for current callers (all pass `int`).
3. Added a long inline comment at the call site documenting *why* the wrapped call is OUTSIDE the existing `try: ... except pronotepy.PronoteAPIError` block — the typed wrapper does its own error mapping, so reusing the inner try would be dead code.
4. Updated `fetch_all`'s `Raises:` docstring to enumerate the three new typed exception classes that can now propagate out of the function.

**Regression tests added** in `tests/test_api/test_fetcher.py`:
- `test_fetch_all_set_child_crypto_error_surfaces_as_auth_error` — `pronotepy.exceptions.CryptoError` from `set_child` now surfaces as `AuthError` with `reason == AUTH_FAILED`.
- `test_fetch_all_set_child_ip_suspended_surfaces_as_rate_limited` — IP-suspended literal in a `PronoteAPIError` from `set_child` surfaces as `RateLimitedError` (D-22 / Pitfall 1).
- `test_fetch_all_set_child_other_api_error_surfaces_as_communication_error` — generic `PronoteAPIError` surfaces as `CommunicationError(PROTOCOL_BROKEN)`.
- `test_fetch_all_set_child_does_not_leak_raw_pronote_api_error` — explicit negative assertion that the raw pronotepy class does not escape.

### WR-09: `_last_recovery_at` is never reset, so a successful recovery still blocks the NEXT poll's recovery

**Files modified:** `custom_components/ha_pronote/coordinator.py`, `tests/test_coordinator.py`
**Commit:** `e960daa`
**Applied fix:** Added `self._last_recovery_at = None` immediately after the successful return of `_recover_from_auth_error(err, today)` in `_async_update_data`. The placement is deliberate: if `_recover_from_auth_error` raises (`ConfigEntryAuthFailed`, `UpdateFailed` for rate-limit / communication failure), the new line is skipped and the WR-04 cooldown timestamp set on line 125 stays in effect to block the next aliased-loop recovery attempt. Only a successful recovery — which proves the AuthError was real auth, not the Pitfall-2 aliased rate-limit the cooldown was hedging against — clears the gate.

A multi-paragraph comment was added explaining the contract so future readers understand both the "why clear" (WR-09) and the "why this exact line, not earlier" (WR-04 still owns the failure-arm timestamp) interactions.

**Regression tests added** in `tests/test_coordinator.py`:
- `test_successful_recovery_clears_cooldown` — direct assertion: after a poll with `[AuthError, success]`, `coordinator._last_recovery_at is None`.
- `test_genuine_auth_failure_after_successful_recovery_is_not_swallowed` — behavioural proof: poll N with `[AuthError, success]` is followed by poll N+1 with `[AuthError, AuthError]`. Without WR-09, the cooldown gate would short-circuit poll N+1 to `UpdateFailed` before recovery started; with WR-09 in place, `build_or_resume_client` IS called a second time and `ConfigEntryAuthFailed` propagates so HA's reauth flow fires.

## Skipped Issues

None — both in-scope findings were fixable as described in the review's Fix sections, and verification (Tier 1 re-read + Tier 2 ruff/py_compile) passed cleanly for both.

## Verification Notes

- **Local environment:** Python 3.13.9. The HA-importing test suite (PHACC) is not installed locally, so verification was restricted to:
  1. **Tier 1** re-read of every modified file region.
  2. **Tier 2** `ruff check` (passed: "No issues found" for both fix sets) and `python -m py_compile` (passed for all 5 touched source files).
  3. **AST guard** — manually re-ran the `tests/test_no_ha_imports.py` walk against `custom_components/ha_pronote/api/` and `tests/test_api/`: zero `homeassistant.*` imports. D-19 invariant preserved.
- **`ruff format` skipped on `coordinator.py` and `api/fetcher.py`** per the cycle-3 guidance: both contain `except (X, Y):` tuples that ruff 0.15.1 strips parens on, which produces a downstream syntax change unrelated to the fix. `ruff format --check` was used (read-only) where applicable. Test files have no `except` tuples and were format-checked: `tests/test_coordinator.py` is already-formatted; `tests/test_api/test_fetcher.py` had pre-existing formatting drift unrelated to this change (verified by stashing and re-checking on the pre-fix tree).
- **HA-fixture-dependent tests** (`tests/test_coordinator.py`, `tests/test_api/test_fetcher.py` partially) were not run locally — they require `pytest_homeassistant_custom_component`. The cycle-3 verifier phase will execute them in CI / the HA dev container.

## Logic-Verification Tag

Both fixes carry semantic correctness risk that the verifier should hand-confirm:

- **CR-06**: the call-site swap is straightforward, but the *placement* (outside the existing `try: ... except pronotepy.PronoteAPIError`) is intentional. A careful reader might be tempted to fold `set_active_child` *inside* the try — that would be wrong (the typed wrapper does its own mapping and would never raise `pronotepy.PronoteAPIError`, so the `except` arm could never fire on it). The comment at lines 50-64 of fetcher.py documents this.
- **WR-09**: the cleared-on-success-only contract is what makes the cooldown meaningful. If a future refactor moves `self._last_recovery_at = None` *before* the recovery call (or to a `finally:` block), WR-04's protection collapses. The new test `test_genuine_auth_failure_after_successful_recovery_is_not_swallowed` is the load-bearing guard against that drift.

Both are flagged as `fixed: requires human verification` on the verifier's checklist for cycle 3.

---

_Fixed: 2026-05-07_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3 of 3 (final cycle)_
