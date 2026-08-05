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

    issue_id = f"{entry.entry_id}_auth_circuit"
    flow = await async_create_fix_flow(hass, issue_id, {"entry_id": entry.entry_id})
    flow.hass = hass
    # HA sets these on a real flow run; set them so the confirm form renders.
    flow.handler = DOMAIN
    flow.issue_id = issue_id

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "create_entry"

    reauth_flows = [
        f
        for f in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if f["context"].get("source") == "reauth" and f["context"].get("entry_id") == entry.entry_id
    ]
    assert len(reauth_flows) == 1


async def test_auth_repair_confirm_form_forwards_child_name(hass, mock_pronote_client) -> None:
    """The confirm dialog forwards child_name so {child_name} renders (not literal)."""
    from homeassistant.helpers import issue_registry as ir

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

    issue_id = f"{entry.entry_id}_auth_circuit"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="auth_circuit",
        translation_placeholders={"child_name": "Jean Dupont"},
        data={"entry_id": entry.entry_id},
    )

    from custom_components.ha_pronote.repairs import async_create_fix_flow

    flow = await async_create_fix_flow(hass, issue_id, {"entry_id": entry.entry_id})
    flow.hass = hass
    # HA sets these on a real flow run; set them for the unit-level render test.
    flow.handler = DOMAIN
    flow.issue_id = issue_id

    result = await flow.async_step_confirm()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"child_name": "Jean Dupont"}
