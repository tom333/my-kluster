"""DIAG-03 — Repair fix-flow that launches the Phase 6 reauth flow.

HA auto-discovers this module by filename. The auth_circuit Repair Issue
(created in coordinator._handle_failure) is fixable (is_fixable=True);
clicking its fix button drives this flow, which confirms then hands off to
reauth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

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

        registry = ir.async_get(self.hass)
        issue = registry.async_get_issue(DOMAIN, self.issue_id)
        placeholders = issue.translation_placeholders if issue is not None else None
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """HA hook — build the fix-flow for our auth_circuit issue."""
    entry_id = (data or {}).get("entry_id", "")
    return PronoteAuthRepairFlow(entry_id)
