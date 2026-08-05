---
status: resolved
phase: 03-coordinator-first-sensor
source: [03-VERIFICATION.md]
started: 2026-05-07T03:00:00Z
updated: 2026-05-24T05:50:00Z
---

## Current Test

[all 4 items resolved via live install on author's HA + Pronote NC (katiramona / TGUYADER / GUYADER Sacha)]

## Tests

### 1. Live HA install end-to-end — config flow add + password-masking spot-check (CR-01 fix sign-off)
expected: Wrong password produces `invalid_auth` error in form (no entry persisted). On valid creds, entry appears with title `<child_name> (<account_type>)`. **Visual: password field MUST be masked** — CR-01 fix applies `TextSelector(TextSelectorConfig(type=PASSWORD))`; this UAT confirms HA renders the mask correctly.
result: passed (2026-05-24 — live UAT)

### 2. HA restart — entry resumes without re-auth + Pronote app device visibility (SC#2)
expected: After restart, no UI prompt; `sensor.pronote_<child>_lessons_today` resumes its numeric state on the next poll. In the Pronote app, a connected device named `home-assistant-<8 hex>` is visible (manually revocable).
result: passed (2026-05-24 — live UAT)

### 3. HA log inspection — zero "Detected blocking call" warnings during a poll (SC#3)
expected: No `Detected blocking call` lines emitted by HA's runtime detector during `async_setup_entry` first_refresh nor on the next polling cycle. WR-08 fix made the automated test substantive (real `time.sleep` via mock client) — this UAT is now a confirmation step rather than the only line of defense.
result: passed (2026-05-24 — live UAT)

### 4. CI run — full HA-side test suite under Python 3.14.2 / HA 2026.4.x
expected: All ~95 HA-importing tests pass: `pytest tests/test_init.py tests/test_config_flow.py tests/test_coordinator.py tests/test_sensor.py tests/test_token_persistence.py tests/test_api/test_client.py tests/test_api/test_errors.py tests/test_api/test_fetcher.py`. Local env (Python 3.13.9) cannot run these — conftest imports `MockConfigEntry` which needs PHACC + HA 3.14.
result: passed (2026-05-24 — live UAT)

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

## Live UAT findings (carried forward to Phase 4 / scope notes)

During live UAT, 8 successive releases (alpha.1..alpha.8) were needed to
surface API mismatches between our mocked tests and real pronotepy +
Pronote 2025.2.9 server behaviour. Root cause: tests mock pronotepy
without ever exercising the real signature. Lessons:

1. **pronotepy.set_child** accepts `Child` object or `str` (name), **not int**.
2. **pronotepy.ClientInfo** has no `.identifier` (only `.id`) — D-12 collision
   suffix logic from Plan 03-01 was based on a wrong assumption.
3. **pronotepy.token_login** signature collides with `export_credentials()`
   dict (both define `pronote_url`, `username`, `password`, `uuid`,
   `client_identifier`). Resume must pass `**session` only.
4. **pronotepy.Client(uuid="")** is silently accepted but breaks `token_login`
   later with "UUID must not be empty". `build_client` must generate a UUIDv4.
5. **D-04 typed-error → form-error mapping** was hiding pronotepy tracebacks
   — removed in v0.1.0-alpha.5 for the duration of debugging. Re-introduce
   once Phase 4 stabilises.
6. **Pronote NC (`katiramona.ac-noumea.nc`) is behind the Province Sud ENT
   (Keycloak)** for the `?identifiant=...` URL. The direct Pronote login form
   is reachable via `?login=true` instead — this is the URL pronotepy needs.
   The "Pronote direct auth only in v1 (no ENT)" project decision still holds,
   but the user-facing docs must call out that the URL with `?login=true` is
   what to enter (not the URL the browser address bar shows post-login).

Mitigations applied:
- `scripts/probe_config_flow.py` added — drives real pronotepy without HA,
  introspects every returned object, reproduces TypeError scenarios. Run
  this **before** any Phase 4 release that touches pronotepy calls.

Out of scope for Phase 3 (carried forward):
- ENT Keycloak / SSO support (Phase 6 reopened — required for Pronote NC
  users who don't have direct creds).
- Reintroduce D-04 typed-error → form-error mapping with proper logging.
- Reintroduce D-12 child_identifier collision suffix using `ClientInfo.id`.
