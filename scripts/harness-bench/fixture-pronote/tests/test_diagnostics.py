"""DIAG-01 — config entry diagnostics dump is PII-safe by default."""

from __future__ import annotations

import json

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote.const import DOMAIN
from custom_components.ha_pronote.diagnostics import async_get_config_entry_diagnostics

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

    for secret in ("s3cr3t-pw", "tok-deadbeef", "deadbeef-uuid", "qr-deadbeef", "client-deadbeef"):
        assert secret not in blob, f"leaked: {secret}"
    assert "https://example.com/pronote/eleve.html" not in blob
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
