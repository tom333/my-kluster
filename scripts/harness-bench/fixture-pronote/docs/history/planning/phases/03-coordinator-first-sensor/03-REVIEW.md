---
phase: 03-coordinator-first-sensor
reviewed: 2026-05-07T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - custom_components/ha_pronote/__init__.py
  - custom_components/ha_pronote/api/__init__.py
  - custom_components/ha_pronote/api/client.py
  - custom_components/ha_pronote/api/errors.py
  - custom_components/ha_pronote/api/fetcher.py
  - custom_components/ha_pronote/config_flow.py
  - custom_components/ha_pronote/const.py
  - custom_components/ha_pronote/coordinator.py
  - custom_components/ha_pronote/data.py
  - custom_components/ha_pronote/entity.py
  - custom_components/ha_pronote/sensor.py
  - custom_components/ha_pronote/strings.json
  - tests/conftest.py
  - tests/test_api/test_client.py
  - tests/test_api/test_errors.py
  - tests/test_api/test_fetcher.py
  - tests/test_config_flow.py
  - tests/test_coordinator.py
  - tests/test_init.py
  - tests/test_sensor.py
  - tests/test_token_persistence.py
findings:
  blocker: 0
  warning: 0
  info: 3
  total: 3
status: clean
---

# Phase 3: Code Review Report — Cycle 3 (final)

**Reviewed:** 2026-05-07
**Depth:** standard
**Files Reviewed:** 21 (production + tests; cycle-1 + cycle-2 review artifacts read as context)
**Cycle:** 3 of 3 (final — `--auto` fix loop complete)
**Status:** clean

## Summary

All cycle-1 findings (5 BLOCKER `CR-01..CR-05` + 8 WARNING `WR-01..WR-08`) and the cycle-2 escalations (1 BLOCKER `CR-06` + 1 WARNING `WR-09`) are RESOLVED at the working-tree level. The cycle-3 fixes (commits `f41b15f`, `e960daa`) introduce no new defects.

The 3 INFO items surfaced in cycle 2 (`IN-01`, `IN-02`, `IN-03`) are intentionally NOT fixed — they fall outside the `--fix` default scope and are carried forward verbatim below for future-phase visibility.

This phase is shippable.

---

## Cycle-3 Working-Tree Verification

The orchestrator stashed cycle-3 phantom reverts left in the working tree by gsd-code-fixer's worktree cleanup. Direct file reads (NOT just `git status`) confirm the fixes are present in the source files actually executed by Python:

| Cycle ID | Anchor | Verified at |
|---|---|---|
| `CR-06` | `from .client import set_active_child` | `api/fetcher.py:21` |
| `CR-06` | `set_active_child(client, child_index_or_identifier)` (NOT raw `client.set_child`) | `api/fetcher.py:73` |
| `WR-09` | `self._last_recovery_at = None` on the recovery success path | `coordinator.py:134` |

The cycle-3 commits are present in HEAD (`f41b15f`, `e960daa`) and the working tree mirrors HEAD for these files.

---

## Cycle-1 + Cycle-2 Regression Re-Check

Re-verified by direct file read at the line numbers cycle 2 named:

| ID | Class | Status | Evidence |
|---|---|---|---|
| CR-01 | password masking | RESOLVED | `config_flow.py:59` — `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))`. Test `test_user_schema_masks_password_field` (`test_config_flow.py:160-165`) introspects the schema. |
| CR-02 | recovery error routing | RESOLVED | `coordinator.py:203-211` splits the catch into `AuthError` → `ConfigEntryAuthFailed`, `RateLimitedError` → `UpdateFailed`, `(CommunicationError, PronoteIntegrationError)` → `UpdateFailed`. Three named regression tests cover each branch (`test_coordinator.py:274-370`). |
| CR-03 | snapshot lost on token-write failure | RESOLVED | `coordinator.py:147` writes `_previous_snapshot` BEFORE `_capture_session`; `coordinator.py:152-155` wraps the capture in best-effort try. `test_export_credentials_failure_does_not_invalidate_poll` (`test_coordinator.py:378-411`) asserts `last_update_success is True` AND `_previous_snapshot is snapshot`. |
| CR-04 | set_child error mapping (3 sites) | RESOLVED | `set_active_child` helper at `api/client.py:143-183` applied to `__init__.py:93`, `coordinator.py:186`, `config_flow.py:137`. Five regression tests in `test_api/test_client.py:141-172`. |
| CR-05 | `_capture_session` exception swallowing | RESOLVED | `coordinator.py:225-229` wraps `export_credentials` in `try/except Exception` with a warning log. `test_export_credentials_failure_does_not_invalidate_poll` exercises the path. |
| CR-06 | fetcher.py 4th set_child site | RESOLVED | `api/fetcher.py:73` now calls `set_active_child(client, child_index_or_identifier)`. Regression tests `test_fetch_all_set_child_*` (`test_api/test_fetcher.py:391-439`) lock the mapping for CryptoError → AuthError, IP-suspended → RateLimitedError, other API error → CommunicationError, and a negative test asserting raw `pronotepy.PronoteAPIError` never escapes. |
| WR-01 | available property override | RESOLVED | `entity.py` no longer defines `available`; comment block at lines 19-23 and 63-67 documents the deletion. CoordinatorEntity's chained behaviour preserved. |
| WR-02 | missing entry.data keys | RESOLVED | `__init__.py:58-60` validates the 6 required keys upfront and raises `ConfigEntryNotReady`. `test_setup_entry_missing_required_key_raises_config_entry_not_ready` (`test_init.py:45-66`) asserts setup returns False. |
| WR-03 | token_login fast-path swallows IP-suspended | RESOLVED | `api/client.py:108-117` checks `_IP_SUSPENDED_LITERAL` in the `token_login` exception handler and raises `RateLimitedError` before falling through. `test_build_or_resume_client_token_login_ip_suspended_raises_rate_limited` (`test_token_persistence.py:89-119`) asserts fresh-login init was NEVER called. |
| WR-04 | recovery cooldown gate | RESOLVED | `coordinator.py:120-125` gates `_recover_from_auth_error` on a 5-minute cooldown. `test_recovery_cooldown_skips_back_to_back_auth_errors` (`test_coordinator.py:421-470`) asserts the second AuthError within the window does NOT call `build_or_resume_client`. |
| WR-05 | credential redaction | RESOLVED | `api/errors.py:14-38` defines `redact()` with 5 patterns. Five unit tests in `test_api/test_errors.py:102-128`. The coordinator and `api/client.py` wrap every `str(err)` in `redact()` before constructing `UpdateFailed` / `ConfigEntryAuthFailed` / typed exceptions. |
| WR-06 | config_flow set_child / export_credentials errors | RESOLVED | `config_flow.py:132-151` wraps the `set_active_child` path in the D-04 mapping; `config_flow.py:180-183` wraps `export_credentials` and aborts with `cannot_connect`. Four parametrized regression tests in `test_config_flow.py:174-214`. |
| WR-07 | unload does not stop coordinator | RESOLVED | `__init__.py:130-131` calls `await coordinator.async_shutdown()` BEFORE `async_unload_platforms`. `test_unload_entry_shuts_down_coordinator` (`test_init.py:69-90`) asserts the call. (Note: the assertion shape itself is INFO-level scope — see IN-03 below.) |
| WR-08 | blocking-call test was vacuous | RESOLVED | `test_no_blocking_calls_during_poll` (`test_coordinator.py:146-195`) no longer patches `fetch_all` away. The mock client's `lessons` and `information_and_surveys` perform real `time.sleep(0.001)` calls, so HA's blocking-call detector now has actual sync I/O to catch on the loop thread. |
| WR-09 | `_last_recovery_at` not cleared on success | RESOLVED | `coordinator.py:134` (`self._last_recovery_at = None` on the recovery success path). Two regression tests in `test_coordinator.py:482-585` (`test_successful_recovery_clears_cooldown` + `test_genuine_auth_failure_after_successful_recovery_is_not_swallowed`) lock both the state and the behavioural contract. |

**Outcome:** all 15 prior findings RESOLVED. No regressions introduced by cycle-3 fixes.

---

## Adversarial Pass on Cycle-3 Diff

I examined the cycle-3 changes for new defects:

1. **`set_active_child` is called BEFORE `fetcher.py`'s try/except (line 73 vs. try at line 78).** This is correct by design: `set_active_child` does its own typed-exception mapping (`AuthError` / `RateLimitedError` / `CommunicationError`). Wrapping it in the inner `try/except pronotepy.PronoteAPIError` would be redundant — and worse, would re-wrap a typed exception (which is NOT a `pronotepy.PronoteAPIError`) so the inner try is irrelevant. The coordinator's `_async_update_data` catches all three typed-exception classes (`coordinator.py:111, 135, 138`), so the propagation contract is preserved. The fetcher docstring at lines 48-56 documents this contract correctly.

2. **`self._last_recovery_at = None` placement (`coordinator.py:134`)** is reached only if `_recover_from_auth_error` returns without raising. The fix's own comment at lines 127-133 explains the contract correctly: a successful recovery proves the AuthError was real auth (not aliased rate-limit), so the cooldown should clear. If recovery raises, the `None` assignment is skipped and the timestamp set at line 125 remains in place to block the next aliased-loop attempt — exactly the WR-04 contract.

3. **Both fixes preserve the `redact(err.message)` calls** in the surrounding error-mapping arms. WR-05 stays satisfied for the new code paths.

4. **No new imports or attributes leak HA types into `api/`.** `api/fetcher.py` adds only `from .client import set_active_child` — same package, no `homeassistant.*` import. D-19/D-20 (api/ stays HA-free) preserved.

5. **No new dead code, type mismatches, or unhandled paths** in the cycle-3 diff.

---

## INFO (carried forward from cycle 2 — intentionally not fixed)

These were surfaced in cycle 2 and deferred because they fall outside the `--fix` default scope. They remain valid concerns for a future hardening pass; carried verbatim with their original cycle-2 framing.

### IN-01: `redact()` URL-with-credentials pattern not covered

**Origin:** cycle 2.
**File:** `custom_components/ha_pronote/api/errors.py:16-24`
**Issue:** The redact patterns cover `password=`, `pwd=`, `token=`, `session=`, and `Authorization:` — but NOT `https://user:pass@host/...` URL-embedded credentials. If pronotepy or upstream Pronote echoes the request URL back in an exception message and the user configured a URL with embedded credentials (rare but valid per RFC 3986), the credentials would leak into HA logs.
**Fix (low-priority, defense-in-depth):**
```python
re.compile(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@"),  # strip user:pass@ from URLs
```
And replace with `\1<redacted>@`. Unit test:
```python
def test_redact_strips_userinfo_from_url():
    assert "secret" not in redact("connect failed: https://alice:secret@pronote.example.com/")
```

### IN-02: `redact()` `password=\S+` greedily captures across a single space

**Origin:** cycle 2.
**File:** `custom_components/ha_pronote/api/errors.py:17`
**Issue:** `password=\S+` matches one whitespace-delimited token. A message like `password=foo bar` redacts `password=foo` to `<redacted>` but leaves ` bar` exposed. Pronote passwords don't contain spaces in practice, but the pattern's brittleness is worth noting. Same caveat for `pwd=\S+`. Not exploitable today; documented as a known scope.
**Fix:** Bound the match to a stop class (e.g. `[^\s&]+` to also handle URL query separators) or use a longer lookahead. Acceptable to defer.

### IN-03: `tests/test_init.py:90` mock-shutdown assertion uses a fragile fallback

**Origin:** cycle 2.
**File:** `tests/test_init.py:90`
**Issue:** `assert mock_shutdown.await_count + mock_shutdown.call_count >= 1` — the `+ call_count` term is dead code IF `patch.object` correctly auto-detects `async_shutdown` as a coroutine function (which it does for `TimestampDataUpdateCoordinator.async_shutdown`, returning an `AsyncMock`). The assertion still passes if a future HA refactor changes `async_shutdown` to a sync method, masking a real regression where the production code is no longer awaiting the coordinator shutdown. A tighter assertion is `mock_shutdown.assert_awaited_once()`.
**Fix:**
```python
with patch.object(coordinator, "async_shutdown", new_callable=AsyncMock) as mock_shutdown:
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_shutdown.assert_awaited_once()
```

---

## Known TODOs (not flagged)

- **`except (X, Y):` ruff 0.15.1 formatting regression.** `config_flow.py:144-151` uses 4 separate `except` arms instead of a tuple, per the cycle-1 reviewer's note that ruff reformats the tuple form unstably. Tracked as a tooling cleanup for a later phase. NOT a defect of the implementation.

---

_Reviewed: 2026-05-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Cycle: 3 of 3 — final_
