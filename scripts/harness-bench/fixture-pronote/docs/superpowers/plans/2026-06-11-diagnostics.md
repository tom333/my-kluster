# Diagnostics & Repair Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship HA-native diagnostics dump (PII-safe) + two Repair Issues (IP-ban informational, auth-circuit fixable-with-reauth), replacing the Phase 5 persistent notifications.

**Architecture:** New `diagnostics.py` serializes entry+runtime+data-summary with wholesale `session` redaction. `coordinator.py`'s `_handle_failure` / `_reset_breaker_on_success` swap `persistent_notification` calls for `issue_registry` create/delete. New `repairs.py` hosts a `RepairsFlow` whose confirm step launches the Phase 6 reauth flow.

**Tech Stack:** Python 3.14.2, Home Assistant 2026.4+, `homeassistant.helpers.issue_registry` (`ir`), `homeassistant.components.diagnostics.async_redact_data`, `homeassistant.helpers.repairs.RepairsFlow`, pytest + PHACC.

**Spec:** `docs/superpowers/specs/2026-06-11-diagnostics-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `custom_components/ha_pronote/diagnostics.py` | Create | `async_get_config_entry_diagnostics` + `TO_REDACT` |
| `custom_components/ha_pronote/repairs.py` | Create | `async_create_fix_flow` + `PronoteAuthRepairFlow` |
| `custom_components/ha_pronote/coordinator.py` | Modify | `_handle_failure` + `_reset_breaker_on_success` → `ir.*`; drop `persistent_notification` import |
| `custom_components/ha_pronote/strings.json` | Modify | `issues.*` block |
| `custom_components/ha_pronote/translations/en.json` | Modify | mirror |
| `custom_components/ha_pronote/translations/fr.json` | Modify | FR |
| `tests/test_diagnostics.py` | Create | redaction + shape |
| `tests/test_coordinator.py` | Modify | issue lifecycle (both kinds) |
| `tests/test_repairs.py` | Create | fix-flow → reauth |

Run all tests with: `uv run pytest <path> -q` (project `.venv` is Python 3.14.2).

---

## Task 0: Wave-0 probe — confirm `entry.async_start_reauth` signature

**Files:** none (probe only)

- [ ] **Step 1: Probe the reauth-launch idiom available in this HA version**

Run:
```bash
uv run python -c "from homeassistant.config_entries import ConfigEntry; print('async_start_reauth' in dir(ConfigEntry))"
```
Expected: `True`.

If `False`: in Task 6 use the fallback
`self.hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": self._entry_id}, data=entry.data)`
(import `SOURCE_REAUTH` from `homeassistant.config_entries`) instead of `entry.async_start_reauth(self.hass)`. Record the choice; the rest of Task 6 is unchanged.

---

## Task 1: Diagnostics dump — redaction + shape (DIAG-01)

**Files:**
- Create: `custom_components/ha_pronote/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_diagnostics.py
"""DIAG-01 — config entry diagnostics dump is PII-safe by default."""

from __future__ import annotations

import json

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote.const import DOMAIN
from custom_components.ha_pronote.diagnostics import (
    async_get_config_entry_diagnostics,
)

# A populated entry whose session blob carries the nested credential keys that a
# bare {"url"} redact would miss — notably `pronote_url`.
_ENTRY_DATA = {
    "url": "https://example.com/pronote/eleve.html",
    "account_type": "eleve",
    "username": "alice",
    "password": "s3cr3t-pw",
    "session": {
        "pronote_url": "https://example.com/pronote/eleve.html",
        "username": "alice",
        "password": "s3cr3t-pw",
        "uuid": "deadbeef-uuid",
        "qr_code_uuid": "qr-deadbeef",
        "client_identifier": "client-deadbeef",
        "token": "tok-deadbeef",
    },
    "child_identifier": "jean_dupont",
    "child_index": None,
    "child_name": "Jean Dupont",
}


async def test_diagnostics_redacts_all_secrets(hass, mock_pronote_client) -> None:
    """No password / token / uuid / pronote_url / session internals anywhere in the dump."""
    from unittest.mock import patch

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data=_ENTRY_DATA,
        options={"refresh_interval": 15, "nickname": "Jeannot"},
        version=1,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)
    blob = json.dumps(diag)

    # Forbidden substrings must NOT appear anywhere in the serialized dump.
    for secret in ("s3cr3t-pw", "tok-deadbeef", "deadbeef-uuid", "qr-deadbeef", "client-deadbeef"):
        assert secret not in blob, f"leaked: {secret}"
    # The establishment URL must not leak via the top-level url NOR the session's pronote_url.
    assert "https://example.com/pronote/eleve.html" not in blob
    # session is redacted wholesale.
    assert diag["entry"]["data"]["session"] == "**REDACTED**"


async def test_diagnostics_keeps_safe_keys(hass, mock_pronote_client) -> None:
    """account_type / child_name / options / runtime / data_summary survive."""
    from unittest.mock import patch

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data=_ENTRY_DATA,
        options={"refresh_interval": 15, "nickname": "Jeannot"},
        version=1,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"]["data"]["account_type"] == "eleve"
    assert diag["entry"]["data"]["child_name"] == "Jean Dupont"
    assert diag["entry"]["data"]["child_identifier"] == "jean_dupont"
    assert diag["entry"]["options"]["refresh_interval"] == 15
    assert diag["entry"]["options"]["nickname"] == "Jeannot"
    assert "last_update_success" in diag["runtime"]
    assert "consecutive_failures" in diag["runtime"]
    assert "lessons_today" in diag["data_summary"]
    assert "has_previous_snapshot" in diag["data_summary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_diagnostics.py -q`
Expected: FAIL — `ModuleNotFoundError: ...diagnostics` (module not created yet).

- [ ] **Step 3: Write the implementation**

```python
# custom_components/ha_pronote/diagnostics.py
"""DIAG-01 — config entry diagnostics dump, PII-safe by default.

HA auto-discovers this platform by filename. The dump is downloadable from
Settings → Devices & Services → (entry) → ⋮ → Download diagnostics, and is
designed to be paste-able into a GitHub issue without leaking credentials or
the establishment URL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import PronoteConfigEntry

# `session` is redacted WHOLESALE (not by sub-key): the dict from
# pronotepy.export_credentials() nests `pronote_url`, `client_identifier`,
# `uuid`, `qr_code_uuid`, `token`, `username`, `password` under names that
# differ from the top level. A bare {"url"} would leak the establishment URL
# via `pronote_url`. Redacting the whole key is future-proof against new
# pronotepy session keys.
TO_REDACT = {"password", "username", "uuid", "qr_code_uuid", "token", "url", "session"}


def _iso(value: Any) -> str | None:
    """ISO-format a datetime-like attribute, or None."""
    return value.isoformat() if value is not None else None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PronoteConfigEntry
) -> dict[str, Any]:
    """Return a redacted diagnostics dump for one ConfigEntry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = coordinator.data

    data_summary: dict[str, Any] = {
        "lessons_today": len(snapshot.lessons_today) if snapshot is not None else None,
        "grades": len(snapshot.grades) if snapshot is not None else None,
        "notifications": len(snapshot.information) if snapshot is not None else None,
        "has_previous_snapshot": coordinator._previous_snapshot is not None,  # noqa: SLF001
    }

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "runtime": {
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": _iso(coordinator.last_update_success_time),
            "backoff_until": _iso(coordinator._backoff_until),  # noqa: SLF001
            "consecutive_failures": coordinator._consecutive_failures,  # noqa: SLF001
            "last_recovery_at": _iso(coordinator._last_recovery_at),  # noqa: SLF001
        },
        "data_summary": data_summary,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_diagnostics.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Lint**

Run: `uv run ruff format custom_components/ha_pronote/diagnostics.py tests/test_diagnostics.py && uv run ruff check custom_components/ha_pronote/diagnostics.py tests/test_diagnostics.py`
Expected: `All checks passed!` (the `# noqa: SLF001` markers permit private-attr access in the diagnostics reader).

- [ ] **Step 6: Commit**

```bash
git add custom_components/ha_pronote/diagnostics.py tests/test_diagnostics.py
git commit -m "feat(diag): add config entry diagnostics dump with session-wholesale redaction (DIAG-01)"
```

---

## Task 2: IP-ban Repair Issue — i18n keys first (DIAG-02 part 1)

**Files:**
- Modify: `custom_components/ha_pronote/strings.json`
- Modify: `custom_components/ha_pronote/translations/en.json`
- Modify: `custom_components/ha_pronote/translations/fr.json`

- [ ] **Step 1: Add the `issues` block to `strings.json`**

Add a new top-level `"issues"` key as a sibling of `"config"`, `"options"`, `"entity"`, `"notification"` (mind the trailing comma on whatever block currently ends the object — append `issues` last, before the closing `}`):

```json
  "issues": {
    "ip_suspended": {
      "title": "Pronote suspended your IP address",
      "description": "The Pronote server temporarily suspended this Home Assistant instance's IP (attempt #{strike_count}). Next retry at {retry_at}. If this recurs, increase your polling interval in the integration options. Technical detail: {detail}. Help: {help_url}"
    },
    "auth_circuit": {
      "title": "Pronote rejected your credentials",
      "description": "Authentication has failed repeatedly (attempt #{strike_count}). Next retry at {retry_at}. If your Pronote password changed, re-authenticate. Technical detail: {detail}. Help: {help_url}",
      "fix_flow": {
        "step": {
          "confirm": {
            "title": "Re-authenticate Pronote",
            "description": "Launch the re-authentication flow to enter your current Pronote credentials for {child_name}."
          }
        }
      }
    }
  }
```

- [ ] **Step 2: Mirror into `translations/en.json`**

Add the identical `"issues"` block (same English text) as the last top-level key.

- [ ] **Step 3: Add the French `issues` block to `translations/fr.json`**

```json
  "issues": {
    "ip_suspended": {
      "title": "Pronote a suspendu votre adresse IP",
      "description": "Le serveur Pronote a temporairement suspendu l'IP de cette instance Home Assistant (tentative N°{strike_count}). Prochaine tentative à {retry_at}. Si cela se reproduit, augmentez votre intervalle de polling dans les options de l'intégration. Détail technique : {detail}. Aide : {help_url}"
    },
    "auth_circuit": {
      "title": "Pronote a rejeté vos identifiants",
      "description": "L'authentification a échoué plusieurs fois (tentative N°{strike_count}). Prochaine tentative à {retry_at}. Si votre mot de passe Pronote a changé, ré-authentifiez-vous. Détail technique : {detail}. Aide : {help_url}",
      "fix_flow": {
        "step": {
          "confirm": {
            "title": "Ré-authentification Pronote",
            "description": "Lancez la procédure de ré-authentification pour saisir vos identifiants Pronote actuels pour {child_name}."
          }
        }
      }
    }
  }
```

- [ ] **Step 2 (verify) & Step 4: Validate JSON**

Run:
```bash
for f in custom_components/ha_pronote/strings.json custom_components/ha_pronote/translations/en.json custom_components/ha_pronote/translations/fr.json; do uv run python -m json.tool "$f" > /dev/null && echo "OK $f"; done
```
Expected: three `OK` lines.

- [ ] **Step 5: Commit**

```bash
git add custom_components/ha_pronote/strings.json custom_components/ha_pronote/translations/en.json custom_components/ha_pronote/translations/fr.json
git commit -m "feat(diag): add issues.* i18n keys for IP-ban + auth-circuit repair cards (DIAG-02/03)"
```

---

## Task 3: IP-ban Repair Issue — coordinator migration (DIAG-02 part 2)

**Files:**
- Modify: `custom_components/ha_pronote/coordinator.py` (`_handle_failure`, `_reset_breaker_on_success`)
- Modify: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_coordinator.py` (the file already imports `patch`, `MagicMock`, `dt_util`, `date`, `AuthError`, `RateLimitedError`):

```python
# ---------------------------------------------------------------------------
# Phase 7 DIAG-02 — IP-ban surfaces as a Repair Issue (replaces persistent notif).
# ---------------------------------------------------------------------------


async def test_ip_ban_creates_repair_issue(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """RateLimitedError(IP_SUSPENDED) → Repair Issue created (severity WARNING, not fixable)."""
    from homeassistant.helpers import issue_registry as ir

    from custom_components.ha_pronote.api import ErrorReason, RateLimitedError
    from custom_components.ha_pronote.const import (
        DOMAIN,
        IP_SUSPENDED_NOTIFICATION_ID_SUFFIX,
    )

    today = _datetime(2026, 5, 7, 14, 0, 0, tzinfo=_ZoneInfo("Pacific/Noumea")).date()
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = mock_config_entry.runtime_data.coordinator

        with patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
        ):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()  # noqa: SLF001

    reg = ir.async_get(hass)
    issue_id = f"{mock_config_entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}"
    issue = reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_successful_poll_clears_ip_ban_issue(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """A later successful poll deletes the IP-ban Repair Issue."""
    from homeassistant.helpers import issue_registry as ir

    from custom_components.ha_pronote.api import ErrorReason, RateLimitedError
    from custom_components.ha_pronote.const import (
        DOMAIN,
        IP_SUSPENDED_NOTIFICATION_ID_SUFFIX,
    )

    today = _datetime(2026, 5, 7, 14, 0, 0, tzinfo=_ZoneInfo("Pacific/Noumea")).date()
    mock_config_entry.add_to_hass(hass)
    issue_id = f"{mock_config_entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}"
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = mock_config_entry.runtime_data.coordinator

        with patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
        ):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()  # noqa: SLF001

        reg = ir.async_get(hass)
        assert reg.async_get_issue(DOMAIN, issue_id) is not None

        # backoff would block a real poll; clear it so the success path runs.
        coordinator._backoff_until = None  # noqa: SLF001
        with patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ):
            await coordinator._async_update_data()  # noqa: SLF001

    assert reg.async_get_issue(DOMAIN, issue_id) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -k "ip_ban or clears_ip_ban" -q`
Expected: FAIL — no Repair Issue created (still using `persistent_notification`).

- [ ] **Step 3: Add the issue_registry import to coordinator.py**

In `coordinator.py`, replace the line:
```python
from homeassistant.components import persistent_notification  # Phase 5 D-15
```
with:
```python
from homeassistant.helpers import issue_registry as ir  # Phase 7 DIAG-02/03
```

- [ ] **Step 4: Rewrite the notification-create tail of `_handle_failure`**

In `_handle_failure` (around line 462-479), replace the `notification_id` + `_format_notification` + `persistent_notification.async_create(...)` block with:

```python
        issue_id = f"{self.config_entry.entry_id}_{kind}"
        language = (
            self.hass.config.language if self.hass.config.language else "en"
        ).split("-")[0]
        retry_str = self._backoff_until.strftime(
            "%H:%M le %d/%m" if language == "fr" else "%H:%M on %d/%m"
        )
        anchor_kind = kind.replace("_", "-")
        help_url = f"{TROUBLESHOOTING_DOC_URL_BASE}#troubleshooting-{anchor_kind}"
        placeholders = {
            "strike_count": str(self._consecutive_failures),
            "retry_at": retry_str,
            "detail": redact(err.message),
            "help_url": help_url,
        }

        if kind == IP_SUSPENDED_NOTIFICATION_ID_SUFFIX:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="ip_suspended",
                translation_placeholders=placeholders,
            )
        else:  # AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX
            placeholders["child_name"] = self.config_entry.data["child_name"]
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="auth_circuit",
                translation_placeholders=placeholders,
                data={"entry_id": self.config_entry.entry_id},
            )
```

(This implements BOTH issue kinds now — Task 5 only adds the `repairs.py` fix-flow. The auth branch is harmless until then: an `is_fixable=True` issue with no registered fix-flow simply shows no button.)

- [ ] **Step 5: Rewrite `_reset_breaker_on_success` dismiss tail**

Replace the two `persistent_notification.async_dismiss(...)` calls with:

```python
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{self.config_entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}",
        )
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{self.config_entry.entry_id}_{AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX}",
        )
```

- [ ] **Step 6: Delete the now-dead `_format_notification` static method**

Remove the entire `_format_notification` method (from `@staticmethod` / `def _format_notification(` through its final `return title, message`). Grep first to confirm no other caller:

Run: `grep -rn "_format_notification" custom_components/ha_pronote/ tests/`
Expected: zero matches after deletion (only the method definition existed). If any test referenced it, delete that test too (it tested the old notification text now owned by HA i18n).

- [ ] **Step 7: Run the new tests**

Run: `uv run pytest tests/test_coordinator.py -k "ip_ban or clears_ip_ban" -q`
Expected: PASS (2 passed).

- [ ] **Step 8: Run the full coordinator suite (catch removed-notification regressions)**

Run: `uv run pytest tests/test_coordinator.py -q`
Expected: PASS. If a Phase 5 test asserted `persistent_notification` was created/dismissed, update it to assert `ir.async_get_issue(...)` instead (those tests now describe the new behavior). Show the failure, fix the assertion to the issue-registry equivalent, re-run.

- [ ] **Step 9: Lint**

Run: `uv run ruff format custom_components/ha_pronote/coordinator.py tests/test_coordinator.py && uv run ruff check custom_components/ha_pronote/coordinator.py tests/test_coordinator.py`
Expected: `All checks passed!`. If ruff flags an unused import (`persistent_notification` F401 — should already be gone; or `redact` if it became unused — it is still used), remove it.

- [ ] **Step 10: Commit**

```bash
git add custom_components/ha_pronote/coordinator.py tests/test_coordinator.py
git commit -m "feat(diag): migrate breaker notifications to Repair Issues (DIAG-02)

IP-ban → is_fixable=False WARNING issue; auth-circuit → is_fixable=True ERROR
issue (fix-flow added in next commit). Drops persistent_notification +
_format_notification; HA now localizes via issues.* keys."
```

---

## Task 4: Auth-circuit fix-flow → reauth (DIAG-03)

**Files:**
- Create: `custom_components/ha_pronote/repairs.py`
- Create: `tests/test_repairs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repairs.py
"""DIAG-03 — auth-circuit Repair Issue fix-flow launches the reauth flow."""

from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote.const import DOMAIN

_ENTRY_DATA = {
    "url": "https://example.com/pronote/eleve.html",
    "account_type": "eleve",
    "username": "alice",
    "password": "old_pw",
    "session": {"token": "abc"},
    "child_identifier": "jean_dupont",
    "child_index": None,
    "child_name": "Jean Dupont",
}


async def test_auth_repair_fix_flow_starts_reauth(hass, mock_pronote_client) -> None:
    """Confirming the auth_circuit repair launches a reauth flow for the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data=_ENTRY_DATA,
        version=1,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from custom_components.ha_pronote.repairs import async_create_fix_flow

    flow = await async_create_fix_flow(
        hass, f"{entry.entry_id}_auth_circuit", {"entry_id": entry.entry_id}
    )
    flow.hass = hass

    # init → confirm form
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # confirm → entry created + a reauth flow now in progress for the entry
    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "create_entry"

    reauth_flows = [
        f
        for f in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if f["context"].get("source") == "reauth"
        and f["context"].get("entry_id") == entry.entry_id
    ]
    assert len(reauth_flows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repairs.py -q`
Expected: FAIL — `ModuleNotFoundError: ...repairs`.

- [ ] **Step 3: Write `repairs.py`**

Use `entry.async_start_reauth(self.hass)` if Task 0 reported `True`; otherwise use the fallback shown in the comment.

```python
# custom_components/ha_pronote/repairs.py
"""DIAG-03 — Repair fix-flow that launches the Phase 6 reauth flow.

HA auto-discovers this module by filename. The auth_circuit Repair Issue
(created in coordinator._handle_failure) is is_fixable=True; clicking its
fix button drives this flow, which confirms then hands off to reauth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.repairs import RepairsFlow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult


class PronoteAuthRepairFlow(RepairsFlow):
    """Confirm dialog → launch reauth for the affected entry."""

    def __init__(self, entry_id: str) -> None:
        """Stash the entry id the auth_circuit issue was raised for."""
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Entry point — go straight to the confirm step."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict | None = None) -> FlowResult:
        """Confirm → start the reauth flow, then close the repair."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is not None:
                entry.async_start_reauth(self.hass)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """HA hook — build the fix-flow for our auth_circuit issue."""
    entry_id = (data or {}).get("entry_id", "")
    return PronoteAuthRepairFlow(entry_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_repairs.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Lint**

Run: `uv run ruff format custom_components/ha_pronote/repairs.py tests/test_repairs.py && uv run ruff check custom_components/ha_pronote/repairs.py tests/test_repairs.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add custom_components/ha_pronote/repairs.py tests/test_repairs.py
git commit -m "feat(diag): auth-circuit repair fix-flow launches reauth (DIAG-03)"
```

---

## Task 5: Full-suite regression + manifest sanity

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: all green. Baseline before this plan was **477 passed, 7 skipped**. New: +2 diagnostics, +2 coordinator issue-lifecycle, +1 repairs = **~482 passed**. If any Phase 5 notification test still references `persistent_notification`, it should already have been fixed in Task 3 Step 8 — if a straggler appears, repoint its assertion to `ir.async_get_issue(...)`.

- [ ] **Step 2: Confirm no stray `persistent_notification` references remain**

Run: `grep -rn "persistent_notification" custom_components/ha_pronote/`
Expected: zero matches.

- [ ] **Step 3: Confirm the three regression guards still pass (unrelated, but cheap)**

Run: `uv run pytest tests/test_init.py -k "no_deprecated or no_vol_strip or no_options_flow_init" -q`
Expected: PASS (3 passed).

- [ ] **Step 4: Final commit (if Step 1 required any test fixes)**

```bash
git add -A
git commit -m "test(diag): repoint Phase 5 notification assertions to issue registry"
```
(Skip if Steps 1-3 were already green with no edits.)

---

## Self-Review Notes

- **Spec coverage:** DIAG-01 → Task 1; DIAG-02 → Tasks 2+3; DIAG-03 → Tasks 2 (i18n) + 3 (issue creation) + 4 (fix-flow). `session` wholesale redaction → Task 1 Step 3 + asserted Task 1 Step 1. Persistent-notification removal → Task 3 Steps 3/5/6 + Task 5 Step 2.
- **Type consistency:** `issue_id = f"{entry_id}_{kind}"` identical in `_handle_failure`, `_reset_breaker_on_success`, and both tests. `translation_key` values (`ip_suspended`, `auth_circuit`) match the `issues.*` JSON keys. `PronoteAuthRepairFlow(entry_id)` constructor arg matches `async_create_fix_flow`'s `data["entry_id"]`.
- **Ordering:** i18n keys (Task 2) land before the coordinator creates issues referencing them (Task 3) — avoids a window where an issue renders with a missing translation key.
- **Wave-0 risk:** `entry.async_start_reauth` probed in Task 0 with a documented fallback.
