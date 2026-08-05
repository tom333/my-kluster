# Diagnostics & Repair Issues — Design Spec

**Date:** 2026-06-11
**Sub-domain of:** Phase 7 (Quality, Diagnostics & Distribution)
**Requirements:** DIAG-01, DIAG-02, DIAG-03
**Status:** approved, ready for implementation planning

## Goal

Ship three HA-native diagnostics surfaces:

1. **DIAG-01** — `async_get_config_entry_diagnostics`: a downloadable JSON dump that is PII-safe by default (no credentials, no establishment URL), paste-able into a GitHub issue.
2. **DIAG-02** — IP-suspended Repair Issue: replaces the Phase 5 persistent notification with HA's native Repair card.
3. **DIAG-03** — Auth-circuit Repair Issue: replaces the Phase 5 auth persistent notification with a fixable Repair card whose fix-flow launches the Phase 6 reauth flow.

This also **completes the migration** away from `persistent_notification` (the Phase 5 stand-in) to Repair Issues as the single source of truth for actionable problems.

## Non-Goals

- i18n exhaustive sweep (I18N-01/02) — owned by the i18n sub-spec. This spec ships only the `issues.*` translation keys it needs.
- README / CI / release workflow (DIST-04/07/09) — owned by the Distribution sub-spec.
- New runtime failure modes — this spec only re-surfaces existing Phase 5 breaker signals through better UI.

## Architecture

Three units, each independently testable:

| Unit | File | Responsibility | Depends on |
|------|------|----------------|------------|
| Diagnostics dump | `diagnostics.py` (new) | Serialize entry + runtime + data summary, redact secrets | `async_redact_data`, coordinator public attrs |
| Repair issue lifecycle | `coordinator.py` (modify `_handle_failure` + `_reset_breaker_on_success`) | Create/delete Repair Issues on breaker tick / reset | `homeassistant.helpers.issue_registry` |
| Auth repair fix-flow | `repairs.py` (new) | Confirm dialog → launch reauth flow | `entry.async_start_reauth` |

HA auto-discovers `diagnostics.py` and `repairs.py` by filename — no manifest key needed.

## Component 1 — Diagnostics dump (DIAG-01)

### Interface

```python
# diagnostics.py
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PronoteConfigEntry
) -> dict[str, Any]:
    ...
```

### Output shape (post-redact)

```python
{
  "entry": {
    "title": entry.title,
    "version": entry.version,
    "options": dict(entry.options),          # all 11 option keys — no secrets here
    "data": async_redact_data(dict(entry.data), TO_REDACT),
  },
  "runtime": {
    "last_update_success": coordinator.last_update_success,
    "last_update_success_time": <ISO or None>,
    "backoff_until": <ISO or None>,           # from _backoff_until
    "consecutive_failures": coordinator._consecutive_failures,
    "last_recovery_at": <ISO or None>,        # from _last_recovery_at
  },
  "data_summary": {
    "lessons_today": <len or None>,
    "grades": <len or None>,
    "notifications": <len or None>,
    "has_previous_snapshot": bool,            # _previous_snapshot is not None
  },
}
```

`runtime` reads coordinator attributes directly (read-only). `data_summary` derives counts from `coordinator.data` (the current `Snapshot`) — never dumps lesson/grade content (could contain a child's full schedule).

### Redaction (the critical decision)

```python
TO_REDACT = {"password", "username", "uuid", "qr_code_uuid", "token", "url", "session"}
```

**Why `session` wholesale:** `entry.data["session"]` is the opaque dict returned by `pronotepy.export_credentials()`. It nests credential-bearing keys under names that differ from the top level — notably `pronote_url` (NOT `url`), plus `client_identifier`, `uuid`, `qr_code_uuid`, `token`, `username`, `password`. `async_redact_data` matches keys recursively *by exact name*, so a bare `TO_REDACT={"url"}` would scrub the top-level URL but leak the establishment URL via the session blob's `pronote_url`. Redacting the whole `session` key → `**REDACTED**`:
- closes the `pronote_url` leak,
- is future-proof (pronotepy 2.15 adding a new session key stays scrubbed),
- loses nothing useful (session internals are opaque; "session present" is still inferable from the redaction marker).

### Kept keys (intentionally NOT redacted)

`account_type`, `child_identifier` (slug), `child_name`, `child_index`, all `entry.options`, all `runtime`, all `data_summary`. These identify the child by the name the user themselves typed into their own HA instance — already visible in entity names and the Devices panel. Not a new exposure surface.

## Component 2 — IP-suspended Repair Issue (DIAG-02)

### Migration

In `coordinator._handle_failure(kind=IP_SUSPENDED_NOTIFICATION_ID_SUFFIX)`:
- **Remove:** `persistent_notification.async_create(...)`
- **Add:** `ir.async_create_issue(hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING, translation_key="ip_suspended", translation_placeholders={...})`

In `coordinator._reset_breaker_on_success`:
- **Remove:** `persistent_notification.async_dismiss(... ip_suspended ...)`
- **Add:** `ir.async_delete_issue(hass, DOMAIN, ip_issue_id)`

### Issue identity

```python
issue_id = f"{entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}"
```

`ir` scopes by `(DOMAIN, issue_id)`; embedding `entry_id` keeps multi-child isolation (two children → two distinct issues).

### Placeholders → i18n

The inline FR/EN string-building in `_format_notification` is replaced by `translation_placeholders`:
```python
{"strike_count": str(n), "retry_at": retry_str, "detail": redact(err.message), "help_url": troubleshooting_url}
```
HA localizes via `strings.json` → `issues.ip_suspended.{title,description}`. `is_fixable=False` — the only user action is "wait"; the card carries strike count, retry time, and troubleshooting link.

### Auto-clear

Next successful poll → `_reset_breaker_on_success` → `ir.async_delete_issue`. Idempotent (delete on a non-existent issue is a no-op).

## Component 3 — Auth-circuit Repair Issue + fix-flow (DIAG-03)

### The redundancy decision

A surviving `AuthError` already does two things today in `_recover_from_auth_error`:
1. raises `ConfigEntryAuthFailed` → HA's **native** reauth notification fires (sidebar);
2. calls `_handle_failure(kind=AUTH_CIRCUIT)` → persistent notification.

DIAG-03's Repair Issue is a *third* reauth-adjacent surface. **Decision: accept the minor redundancy.** The Repair card is more discoverable than HA's easy-to-miss native notification, carries troubleshooting context (strike count, why it happened), and its fix-flow launches the *same* reauth flow (no data divergence). This is the standard HA "auth broken, click to fix" pattern.

### Issue creation

In `_handle_failure(kind=AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX)`:
```python
ir.async_create_issue(
    hass, DOMAIN, issue_id,
    is_fixable=True,
    severity=ir.IssueSeverity.ERROR,
    translation_key="auth_circuit",
    translation_placeholders={...},
    data={"entry_id": entry.entry_id},   # passed to the fix-flow
)
```

### Fix-flow

```python
# repairs.py (new) — HA auto-discovers
async def async_create_fix_flow(hass, issue_id, data) -> RepairsFlow:
    return PronoteAuthRepairFlow(data["entry_id"])

class PronoteAuthRepairFlow(RepairsFlow):
    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(self, user_input=None) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is not None:
                entry.async_start_reauth(self.hass)   # launches Phase 6 reauth
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))
```

### Auto-clear

Two paths both converge on `_reset_breaker_on_success`:
- direct: any later successful poll clears the breaker → `ir.async_delete_issue`;
- post-reauth: successful reauth → entry reload → fresh `async_setup_entry` → first successful poll → `_reset_breaker_on_success`.

## i18n keys shipped by this spec

In `strings.json`, `translations/en.json`, `translations/fr.json`, under a new top-level `issues` block:

```
issues.ip_suspended.title / .description        (placeholders: strike_count, retry_at, detail, help_url)
issues.auth_circuit.title / .description        (placeholders: strike_count, retry_at, detail, help_url)
issues.auth_circuit.fix_flow.step.confirm.title / .description
```

The i18n sub-spec later audits completeness; this spec ships the minimum needed for the two issues to render + the fix-flow confirm dialog. FR written natively, EN mirrors.

## Plan slicing (3 plans)

| Plan | Scope | Files | Tests |
|------|-------|-------|-------|
| **A — diag dump** | `diagnostics.py` + redaction | `diagnostics.py` (new) | `test_diagnostics.py`: populated entry (with session blob) → assert no `password`/`pronote_url`/`token`/`uuid` anywhere (recursive scan), `session == "**REDACTED**"`, kept keys present |
| **B — IP-ban issue** | migrate IP-ban notif → Repair Issue | `coordinator.py`, `strings.json`, `en.json`, `fr.json` | issue created on IP-ban (severity WARNING, is_fixable False); cleared on successful poll |
| **C — auth issue + fix-flow** | migrate auth-circuit notif → fixable Repair Issue | `coordinator.py`, `repairs.py` (new), `strings.json`, `en.json`, `fr.json` | issue created (ERROR, is_fixable True); fix-flow confirm → reauth flow started; cleared on breaker reset |

Each plan = atomic commits. Plan B + C remove the corresponding `persistent_notification` calls and the now-dead `_format_notification` branches (or repoint them to placeholder dicts).

## Testing strategy

- **Redaction (Plan A):** recursive walk of the dump dict asserting forbidden substrings absent (`pronote_url`, the test password, the test token, the uuid). Positive assertions on kept keys.
- **Issue lifecycle (Plan B/C):** `ir.async_get(hass).async_get_issue(DOMAIN, issue_id)` present after trigger; `is None` after successful poll. Severity + `is_fixable` asserted.
- **Fix-flow (Plan C):** drive `hass.config_entries... ` repair flow init→confirm; assert a reauth flow exists for the entry afterward (`hass.config_entries.flow.async_progress_by_handler(DOMAIN)` contains a `reauth` source flow).
- **Regression:** full suite stays green (currently 477 passed, 7 skipped).

## Risks / open items

- `entry.async_start_reauth(hass)` from within a RepairsFlow — verify the HA 2026.4 signature at execution time (Plan C Wave 0 probe). Fallback: `hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": ...}, data=entry.data)`.
- Removing `_format_notification` branches: confirm no other caller depends on them before deleting (grep first).
- `persistent_notification` import becomes unused in `coordinator.py` after both migrations → remove the import (ruff F401 will flag).
