---
phase: 03-coordinator-first-sensor
reviewed: 2026-05-07T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - custom_components/ha_pronote/__init__.py
  - custom_components/ha_pronote/api/__init__.py
  - custom_components/ha_pronote/api/client.py
  - custom_components/ha_pronote/config_flow.py
  - custom_components/ha_pronote/const.py
  - custom_components/ha_pronote/coordinator.py
  - custom_components/ha_pronote/data.py
  - custom_components/ha_pronote/entity.py
  - custom_components/ha_pronote/sensor.py
  - custom_components/ha_pronote/strings.json
  - tests/conftest.py
  - tests/test_config_flow.py
  - tests/test_coordinator.py
  - tests/test_init.py
  - tests/test_sensor.py
  - tests/test_token_persistence.py
findings:
  blocker: 5
  warning: 8
  total: 13
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-07
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 3 implements the real `ConfigEntry` setup, the `TimestampDataUpdateCoordinator`, the first sensor (`PronoteLessonsTodaySensor`), and the full HA-side test surface. The async/sync isolation contract is honoured at every observed call-site (every `pronotepy` call goes through `hass.async_add_executor_job`), the `runtime_data` pattern is correctly used, and `_attr_unique_id` is locked per D-13.

However, the review surfaced **5 BLOCKER-class defects** that must be fixed before this phase ships:

1. The password input on the user step is **not masked** — the credential is rendered in plain text in the HA UI.
2. The `_recover_from_auth_error` flow incorrectly maps **non-auth failures** (`CommunicationError`, `RateLimitedError`) to `ConfigEntryAuthFailed`, which would trigger a spurious user-facing reauth flow on a transient network blip or IP suspension.
3. `_capture_session` runs **before** `_previous_snapshot` is updated, so an `export_credentials()` failure causes the freshly-fetched snapshot to be discarded and the diff baseline to drift out of sync.
4. `client.set_child(...)` in both `__init__.py` and `_recover_from_auth_error` is invoked **without error mapping** — a `pronotepy.PronoteAPIError` from this call escapes our typed-exception layer and surfaces as a raw stack trace.
5. The `_capture_session` write to `entry.data` lacks defensive handling — if `export_credentials()` raises, the snapshot is silently lost even though the fetch succeeded.

Eight further WARNING-class issues degrade robustness, maintainability, or HA UX quality and should be addressed in this phase or the immediate follow-up.

---

## BLOCKER

### CR-01: Password field rendered in plain text in HA UI

**Class:** BLOCKER (security / UX)
**File:** `custom_components/ha_pronote/config_flow.py:45-52`
**Issue:** The `_USER_SCHEMA` declares `vol.Required("password"): str`. Without a `selector.TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` (or the legacy `vol.Required("password"): str` with a `cv.string` + `password=True` hint), the HA frontend renders the password field as a normal text input. Users typing their Pronote password will see it on screen, and screenshots, screen-shares, browser history, and HA OS auto-screenshot recovery may all leak the credential. CLAUDE.md mandates "Identifiants Pronote stockés via mécanisme de stockage HA standard, jamais en clair dans les logs" — the same intent extends to UI rendering.
**Fix:**
```python
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required("url"): vol.Url(),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)
```
Add a regression test that asserts the password field is wrapped in a TextSelector with `type=password`.

---

### CR-02: Silent-recovery path mis-classifies non-auth failures as auth failures

**Class:** BLOCKER (incorrect behavior)
**File:** `custom_components/ha_pronote/coordinator.py:106-144` (specifically the `except (AuthError, PronoteIntegrationError)` arm at line 141)
**Issue:** D-22 mandates the following mapping:
- `AuthError` → `ConfigEntryAuthFailed` (HA fires reauth)
- `RateLimitedError` → `UpdateFailed` (HA retries on the next poll)
- `CommunicationError` → `UpdateFailed` (HA retries)

In `_recover_from_auth_error`, the retry's `fetch_all` may raise `RateLimitedError` (server now returns "IP suspended" mid-recovery) or `CommunicationError` (network blip during retry). The current code catches the entire `PronoteIntegrationError` family and re-raises as `ConfigEntryAuthFailed`, which:
1. Triggers a spurious user-facing reauth flow even though credentials are valid.
2. Swallows the original `RateLimitedError.reason = IP_SUSPENDED` signal that Phase 5's circuit-breaker is supposed to read.
3. Discards `_previous_snapshot`, breaking Phase 4's diff baseline.

The `RateLimitedError` is the more dangerous case — a user gets logged out because pronotepy banned their IP for 24h.
**Fix:**
```python
async def _recover_from_auth_error(
    self,
    original_err: AuthError,
    today: date,
) -> Snapshot:
    """D-09: single fresh re-login + retry; on second failure raise the right thing."""
    entry = self.config_entry
    if entry is None:
        raise ConfigEntryAuthFailed(str(original_err)) from original_err

    try:
        new_client = await self.hass.async_add_executor_job(
            partial(
                build_or_resume_client,
                entry.data["url"],
                entry.data["account_type"],
                entry.data["username"],
                entry.data["password"],
                None,
                f"home-assistant-{entry.entry_id[:8]}",
            )
        )
        if self._child_index is not None and hasattr(new_client, "set_child"):
            await self.hass.async_add_executor_job(new_client.set_child, self._child_index)
        self._client = new_client
        snapshot = await self.hass.async_add_executor_job(
            partial(fetch_all, self._client, today, self._school_tz, self._child_index)
        )
    except AuthError as err:
        # Real auth failure on the retry — credentials genuinely invalid.
        raise ConfigEntryAuthFailed(f"[{err.reason}] {err.message}") from err
    except RateLimitedError as err:
        # IP suspended during recovery — Phase 5 reads .reason for backoff.
        raise UpdateFailed(f"[{err.reason}] {err.message}") from err
    except (CommunicationError, PronoteIntegrationError) as err:
        # Transient — HA will retry on next poll.
        raise UpdateFailed(f"[{err.reason}] {err.message}") from err

    return snapshot
```
Add tests covering each retry-failure class:
- `test_recovery_rate_limited_raises_update_failed`
- `test_recovery_network_error_raises_update_failed`
- `test_recovery_auth_failed_again_raises_config_entry_auth_failed`

---

### CR-03: `_capture_session` runs before `_previous_snapshot` update — fetch result lost on token write failure

**Class:** BLOCKER (data loss / state drift)
**File:** `custom_components/ha_pronote/coordinator.py:80-104`
**Issue:** The current order in `_async_update_data` is:
```python
snapshot = await ... fetch_all ...
await self._capture_session()      # may raise
self._previous_snapshot = snapshot # never reached on raise
return snapshot                    # never reached on raise
```
`_capture_session` calls `client.export_credentials()` in the executor and `hass.config_entries.async_update_entry()` on the event loop. Either may raise (executor errors propagate; `async_update_entry` validates schema and could conceivably reject a malformed `entry.data`). When that happens:
1. The freshly-fetched `snapshot` is discarded — coordinator marks the poll as failed.
2. Every entity flips to `unavailable` despite Pronote having returned valid data.
3. `self._previous_snapshot` stays stuck on the prior poll's value, so Phase 4's diff layer will eventually compare a current snapshot against an out-of-date baseline (when the next successful poll finally lands), producing phantom "changed lessons" notifications.

Token persistence is a side-effect — it must NOT block returning the data we already have.
**Fix:**
```python
async def _async_update_data(self) -> Snapshot:
    today = dt_util.now(self._school_tz).date()
    try:
        snapshot = await self.hass.async_add_executor_job(
            partial(fetch_all, self._client, today, self._school_tz, self._child_index)
        )
    except AuthError as err:
        snapshot = await self._recover_from_auth_error(err, today)
    except RateLimitedError as err:
        raise UpdateFailed(f"[{err.reason}] {err.message}") from err
    except (CommunicationError, PronoteIntegrationError) as err:
        raise UpdateFailed(f"[{err.reason}] {err.message}") from err

    # State updates BEFORE side-effects that may fail.
    self._previous_snapshot = snapshot

    # Token capture is best-effort: log and continue on failure so a token
    # write hiccup never invalidates a successful poll.
    try:
        await self._capture_session()
    except Exception:  # noqa: BLE001 — defensive: any failure is non-fatal.
        _LOGGER.warning("Failed to persist session token; will retry next poll", exc_info=True)

    return snapshot
```
Add a regression test: patch `client.export_credentials` to raise, assert `coordinator.data` is the fetched snapshot and `last_update_success is True`.

---

### CR-04: `client.set_child(...)` invoked without error mapping — pronotepy exceptions leak

**Class:** BLOCKER (incorrect error handling)
**File:**
- `custom_components/ha_pronote/__init__.py:69-70`
- `custom_components/ha_pronote/coordinator.py:129-130`
- `custom_components/ha_pronote/config_flow.py:123`

**Issue:** `set_child` is a pronotepy method that performs an authenticated request. It can raise `pronotepy.PronoteAPIError` (e.g. session expired between login and child selection) or `OSError` (network blip). All three call-sites invoke it via `async_add_executor_job` directly, bypassing the typed-exception facade in `api/client.py`. The raw pronotepy exception then:
1. In `__init__.py:async_setup_entry` — escapes setup, logged as an unhandled traceback, and the user sees an opaque "Setup failed" with a Python error in their logs (instead of a clean `ConfigEntryNotReady` retry).
2. In `coordinator._recover_from_auth_error` — escapes the recovery's `try/except (AuthError, PronoteIntegrationError)` (PronoteAPIError is NOT one of our typed exceptions), bubbles up to `_async_update_data`, which does NOT catch it, propagates to `DataUpdateCoordinator._async_refresh`, gets wrapped in a generic `UpdateFailed` (HA's safety net), and credentials in `repr(args)` may end up in HA logs.
3. In `config_flow._create_entry` — escapes the flow, HA shows a generic "Unknown error" abort to the user.

**Fix:** Wrap every `set_child` call in a helper that maps to the typed-exception facade. Add to `api/client.py`:
```python
def set_active_child(client: pronotepy.ParentClient, child_index: int) -> None:
    """Apply a parent's child selection with our typed-error mapping."""
    try:
        client.set_child(child_index)
    except pronotepy.exceptions.CryptoError as err:
        raise AuthError(str(err)) from err
    except pronotepy.PronoteAPIError as err:
        if _IP_SUSPENDED_LITERAL in str(err):
            raise RateLimitedError(str(err)) from err
        raise CommunicationError(str(err), reason=ErrorReason.PROTOCOL_BROKEN) from err
    except OSError as err:
        raise CommunicationError(str(err)) from err
```
Then replace each `client.set_child` call site with `set_active_child(client, child_index)` (still wrapped in `async_add_executor_job`). The coordinator's recovery path then naturally catches the typed exception in its existing `except (AuthError, PronoteIntegrationError)` arm (which itself needs the CR-02 split).

---

### CR-05: `_capture_session` swallows pronotepy errors and races with `entry.data` writes

**Class:** BLOCKER (correctness)
**File:** `custom_components/ha_pronote/coordinator.py:146-153`
**Issue:** Two distinct problems compound:

1. **No exception handling on the executor call.** `client.export_credentials()` can raise (pronotepy 2.14.6 `Client.export_credentials` is a thin getter today, but it iterates internal state — any KeyError on a half-initialized client surfaces as an unhandled exception). Combined with CR-03's ordering bug, this is the most likely real-world trigger.
2. **Race-prone equality check.** `if new_session != entry.data.get("session")` reads `entry.data` without a lock. If a user just edited the entry through the UI between fetch start and this point (rare but possible), the comparison and subsequent `async_update_entry` could clobber the user's change. More concretely, `entry.data` is a `MappingProxyType` — `entry.data.get("session")` is safe to read but the `{**entry.data, "session": new_session}` spread loses any sibling key the UI just added.

The second issue is theoretical for v1 (no OptionsFlow yet), but the first is likely.

**Fix:**
```python
async def _capture_session(self) -> None:
    """D-06: persist export_credentials() to entry.data; non-fatal on failure."""
    entry = self.config_entry
    if entry is None:
        return
    try:
        new_session = await self.hass.async_add_executor_job(
            self._client.export_credentials
        )
    except Exception:  # noqa: BLE001 — token capture must never break a successful poll.
        _LOGGER.warning("export_credentials() failed; keeping prior session token", exc_info=True)
        return
    if new_session != entry.data.get("session"):
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, "session": new_session}
        )
```
This dovetails with CR-03's outer try/except.

---

## WARNING

### WR-01: `entity.py` `available` property breaks the `Entity._attr_available` contract

**File:** `custom_components/ha_pronote/entity.py:62-64`
**Issue:** The override
```python
@property
def available(self) -> bool:
    return self.coordinator.last_update_success
```
shadows `CoordinatorEntity.available`, whose own implementation is
```python
return super().available and self.coordinator.last_update_success
```
By dropping the `super().available` term, this entity ignores any future `_attr_available = False` set by Phase 4+ subclasses (e.g. when a specific data slice is missing but the coordinator overall succeeded). The bug is latent today (no subclass uses `_attr_available`), but becomes a silent correctness break the moment one does.
**Fix:** Either delete the override entirely (CoordinatorEntity already does what we want) or preserve the chain:
```python
@property
def available(self) -> bool:
    return super().available and self.coordinator.last_update_success
```
Deleting the override is cleaner — strictly equivalent to today's behaviour and free of the latent bug.

---

### WR-02: `__init__.py:async_setup_entry` reads required keys with `[]` — no graceful failure on malformed entry

**File:** `custom_components/ha_pronote/__init__.py:53-56,76,86`
**Issue:** `entry.data["url"]`, `entry.data["account_type"]`, `entry.data["username"]`, `entry.data["password"]`, `entry.data["child_identifier"]` — five direct subscripts. Any user with a corrupted entry (manual JSON edit, stale Phase 1 placeholder, future migration regression) gets a raw `KeyError` traceback in HA logs instead of `ConfigEntryNotReady("entry data missing required key 'url'")`. The `async_migrate_entry` skeleton at `__init__.py:100-107` deliberately doesn't validate the shape (D-26 — "no-op in v1"), so this is the only line of defence at setup time.
**Fix:** Validate up front and fail with a clean `ConfigEntryNotReady`:
```python
required = ("url", "account_type", "username", "password", "child_identifier", "child_name")
missing = [k for k in required if k not in entry.data]
if missing:
    raise ConfigEntryNotReady(f"entry.data missing required keys: {missing}")
```

---

### WR-03: `build_or_resume_client` fast-path swallows ALL `pronotepy.PronoteAPIError` — including IP-suspension

**File:** `custom_components/ha_pronote/api/client.py:97-110`
**Issue:** The token-login fast path catches `pronotepy.PronoteAPIError` indiscriminately at line 107 and falls through to fresh login. If pronotepy raises "Your IP address is suspended" during `token_login`, the code immediately retries with `Client(url, username, password, ...)` — which makes a second HTTP request to the SAME suspended IP and triggers a SECOND ban-extending request. Per Pronote's documented behaviour, repeated requests during a suspension extend the suspension window.

The `_IP_SUSPENDED_LITERAL` check exists in the fresh-login path (line 123) but not in the token_login fast-path's exception handler.
**Fix:**
```python
if session is not None:
    try:
        return cls.token_login(url, username=username, device_name=device_name, **session)
    except pronotepy.exceptions.CryptoError:
        pass  # stale session — fall through.
    except pronotepy.PronoteAPIError as err:
        if _IP_SUSPENDED_LITERAL in str(err):
            # Don't hammer a banned IP with a fresh-login retry.
            raise RateLimitedError(str(err)) from err
        pass  # other API error — fresh login may still work.
    except OSError:
        pass
```

---

### WR-04: `_recover_from_auth_error` makes a third request to a possibly-banned IP

**File:** `custom_components/ha_pronote/coordinator.py:106-144`
**Issue:** If a poll fails with `AuthError` and the underlying cause is "your session WAS valid, but pronote banned your IP and replied with a junk auth response that pronotepy decoded as a CryptoError" (this happens — Pitfall 2 in the spec acknowledges the AuthError↔RateLimited overlap), then immediately calling `build_or_resume_client(...)` triggers another login HTTP request to the banned IP. The CLAUDE.md "politesse polling" requirement explicitly calls out "éviter bannissement IP du serveur école" — the silent-recovery path violates this when the original error was actually a soft-rate-limit.
**Fix:** Add a short cooldown gate (in-process, no persistence) before invoking the recovery's network call:
```python
# Before calling _recover_from_auth_error in _async_update_data:
now = dt_util.utcnow()
if self._last_recovery_at is not None and now - self._last_recovery_at < timedelta(minutes=5):
    raise UpdateFailed("Auth recovery rate-limited; skipping this poll")
self._last_recovery_at = now
snapshot = await self._recover_from_auth_error(err, today)
```
This is also a hedge against an aliased exception loop where every poll attempts a fresh login.

---

### WR-05: Pronotepy error messages logged verbatim — potential credential leakage

**File:** `custom_components/ha_pronote/coordinator.py:98,100,142`; `custom_components/ha_pronote/api/client.py:48,50-55,121,123-128`
**Issue:** Every typed exception wraps `str(err)` from pronotepy. Pronotepy's exception messages are not strictly redacted — a future pronotepy version (or current edge cases like a 500 with the request URL echoed back) could include the user's URL, username, or partial token in the message. That message ends up in HA logs as:
- `_LOGGER` debug from coordinator (default WARNING level for UpdateFailed includes the message via HA's standard formatting).
- The `[reason] message` string in `UpdateFailed` and `ConfigEntryAuthFailed`, which HA logs with the entry's metadata.

CLAUDE.md's "jamais en clair dans les logs" applies here.
**Fix:** Add a redaction helper in `api/errors.py`:
```python
_REDACT_PATTERNS = (
    re.compile(r"(?i)password=\S+"),
    re.compile(r"(?i)token=[A-Za-z0-9+/=]+"),
)

def redact(message: str) -> str:
    for pattern in _REDACT_PATTERNS:
        message = pattern.sub("<redacted>", message)
    return message
```
Apply at every `str(err)` call site. Add a unit test that constructs an exception with `password=secret` in the message and asserts the wrapped exception drops it.

---

### WR-06: `config_flow._create_entry` does not bubble `set_child` errors back as form errors

**File:** `custom_components/ha_pronote/config_flow.py:113-170`
**Issue:** `_create_entry` calls `await self.hass.async_add_executor_job(self._client.set_child, child_index)` (line 123) and `await self.hass.async_add_executor_job(self._client.export_credentials)` (line 156) without try/except. If either raises (CR-04 covers the typed-error mapping), the user sees an opaque "Unknown error" abort with no way to recover except restarting the flow. This degrades the D-04 error-mapping contract (`AuthError → invalid_auth`, etc.) silently — D-04 is honoured only on the user step, not on subsequent steps.
**Fix:** Wrap the executor calls in `_create_entry` with the same error-mapping pattern as `async_step_user`, and route failures back to either `pick_child` (with `errors=`) or `user` (with a state reset). At minimum:
```python
try:
    if isinstance(self._client, pronotepy.ParentClient):
        ...
        await self.hass.async_add_executor_job(set_active_child, self._client, child_index)
    ...
    session = await self.hass.async_add_executor_job(self._client.export_credentials)
except AuthError:
    return self.async_abort(reason="invalid_auth")
except RateLimitedError:
    return self.async_abort(reason="ip_suspended")
except (CommunicationError, PronoteIntegrationError):
    return self.async_abort(reason="cannot_connect")
```

---

### WR-07: `async_unload_entry` does not stop the coordinator's polling loop

**File:** `custom_components/ha_pronote/__init__.py:95-97`
**Issue:** `async_unload_platforms` removes the entities, but the `TimestampDataUpdateCoordinator` keeps its `_async_refresh` schedule alive until garbage-collected. While `runtime_data` references the coordinator (and is itself dropped on unload — HA convention), the coordinator's internal `_unsub_refresh` callback can still fire one more time, hitting Pronote with a request after unload. For an integration whose top-level constraint is "politesse polling", this is observable.
**Fix:**
```python
async def async_unload_entry(hass: HomeAssistant, entry: PronoteConfigEntry) -> bool:
    coordinator = entry.runtime_data.coordinator
    coordinator.async_shutdown()  # cancels the scheduled refresh
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```
Add a test that asserts no `fetch_all` calls occur after `async_unload_entry`.

---

### WR-08: Test `test_no_blocking_calls_during_poll` does not actually exercise the blocking-call detector

**File:** `tests/test_coordinator.py:144-170`
**Issue:** The test patches `fetch_all` to a synchronous `MagicMock` return — the actual pronotepy `requests` calls never run. HA's blocking-call detector triggers ONLY on real `socket.connect` / `time.sleep` / `requests.*` calls inside the event loop. By patching `fetch_all` away, the detector has nothing to catch, so the assertion `"Detected blocking call" not in caplog.text` is trivially true regardless of whether the production code wrapped the call in `async_add_executor_job`. The test gives false confidence on COORD-02 / ROADMAP SC#3.
**Fix:** Replace the patch with one that lets `fetch_all` execute against a `MagicMock` `client` whose methods perform `time.sleep(0.001)` (a real blocking call). The mocked client's `lessons()` etc. become genuine sync functions; the production code's `async_add_executor_job` wrapping is what protects the loop. Asserting clean caplog under that condition is meaningful.

Alternatively: use HA's `block_async_io` test helper if `pytest-homeassistant-custom-component` exposes it (`hass.async_add_executor_job` is the only way blocking I/O is allowed during tests when block_async_io is enabled).

---

_Reviewed: 2026-05-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
