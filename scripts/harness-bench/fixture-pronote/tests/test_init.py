"""Smoke + setup_entry contract tests for HA-Pronote (Phase 3).

Phase 1's not-implemented placeholder flow test has been removed because
Plan 01 shipped the real flow. The constant smoke test is preserved verbatim.
"""

from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote import DOMAIN, async_migrate_entry
from custom_components.ha_pronote.const import DOMAIN as DOMAIN_CONST


def test_domain_constant_is_ha_pronote() -> None:
    """The package's DOMAIN constant must equal the manifest.domain value.

    If this assertion fails, hassfest will reject the integration because
    ``manifest.json:domain`` no longer matches the directory name.
    """
    assert DOMAIN == "ha_pronote"
    assert DOMAIN_CONST == DOMAIN


async def test_async_setup_entry_happy_path(hass, mock_config_entry, mock_pronote_client) -> None:
    """C-05: setup uses build_or_resume_client (mocked); coordinator first-refresh OK."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.client is mock_pronote_client
    assert mock_config_entry.runtime_data.child_identifier == "jean_dupont"


async def test_async_migrate_entry_returns_true(hass, mock_config_entry) -> None:
    """ENT-04 / D-26 — skeleton returns True; Phase 6+ fills the body."""
    assert await async_migrate_entry(hass, mock_config_entry) is True


async def test_setup_entry_missing_required_key_raises_config_entry_not_ready(hass) -> None:
    """WR-02: a corrupted entry (missing a required key) must NOT escape as KeyError.

    HA wraps ConfigEntryNotReady cleanly (it retries setup and surfaces a
    proper status to the user); a raw KeyError traceback would be opaque.
    """
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:user:jean_dupont",
        data={
            # 'url' deliberately missing — also missing 'username',
            # 'child_identifier', 'child_name' to lock the multi-key path.
            "account_type": "eleve",
            "password": "p",
        },
        version=1,
    )
    bad_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(bad_entry.entry_id)
    await hass.async_block_till_done()
    # ConfigEntryNotReady -> async_setup returns False; HA logs a clean message.
    assert result is False


def test_phase4_const_values() -> None:
    """T-04-04b: event-type constants must match REQUIREMENTS exactly (Final + exact string).

    These values are burned into HA automations — a string drift is a breaking change.
    Phase 4 threat model T-04-04b: values are Final; this test locks them.
    """
    from custom_components.ha_pronote import const
    from homeassistant.const import Platform

    assert const.EVENT_SCHEDULE_CHANGED == "pronote_schedule_changed"
    assert const.EVENT_NEW_GRADE == "pronote_new_grade"
    assert const.EVENT_NEW_INFORMATION == "pronote_new_information"
    assert const.CLASS_LEVEL_ATTR == "class_name"
    assert const.NOTIFICATIONS_WINDOW == 20
    assert const.GRADE_COMMENT_MAX_LEN == 200
    assert Platform.CALENDAR in const.PLATFORMS
    assert Platform.SENSOR in const.PLATFORMS


async def test_unload_entry_shuts_down_coordinator(hass, mock_config_entry, mock_pronote_client) -> None:
    """WR-07: async_unload_entry must call coordinator.async_shutdown.

    Without it the TimestampDataUpdateCoordinator keeps its scheduled refresh
    alive until garbage-collected — and could fire one more poll AFTER unload,
    violating CLAUDE.md 'politesse polling'.
    """
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    # async_shutdown is what cancels the scheduled refresh; stub it so we can
    # observe the call without needing internal HA scheduler plumbing.
    with patch.object(coordinator, "async_shutdown") as mock_shutdown:
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_shutdown.await_count + mock_shutdown.call_count >= 1


# Phase 6 — OPT-04 / D-09: school_tz override via entry.options. The OptionsFlow
# (Plan 06-05) validates the IANA string at submit-time. The __init__ read path
# does NOT wrap exceptions — per user feedback memory feedback_no_silent_exceptions.md,
# ZoneInfoNotFoundError propagates raw.


async def test_async_setup_entry_school_tz_override_takes_effect(hass, mock_pronote_client) -> None:
    """OPT-04 / D-09 — entry.options['school_tz']='Europe/Paris' reaches the coordinator."""
    from zoneinfo import ZoneInfo

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ha_pronote.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data={
            "url": "https://example.com/pronote/eleve.html",
            "account_type": "eleve",
            "username": "alice",
            "password": "p",
            "session": None,
            "child_identifier": "jean_dupont",
            "child_index": None,
            "child_name": "Jean Dupont",
        },
        options={"school_tz": "Europe/Paris"},
        version=1,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.runtime_data.school_tz == ZoneInfo("Europe/Paris")


async def test_async_setup_entry_school_tz_invalid_raises_zoneinfo_error(hass, mock_pronote_client) -> None:
    """OPT-04 — corrupted school_tz: ZoneInfoNotFoundError propagates RAW.

    Per user feedback memory feedback_no_silent_exceptions.md, we do NOT wrap
    the zoneinfo error into ConfigEntryNotReady. HA catches the raw exception
    internally, logs the traceback, and transitions the entry to SETUP_ERROR.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ha_pronote.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data={
            "url": "https://example.com/pronote/eleve.html",
            "account_type": "eleve",
            "username": "alice",
            "password": "p",
            "session": None,
            "child_identifier": "jean_dupont",
            "child_index": None,
            "child_name": "Jean Dupont",
        },
        options={"school_tz": "NotARealZone"},
        version=1,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        # HA catches ZoneInfoNotFoundError internally when async_setup runs the
        # coroutine; the public surface is entry.state.
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    # Setup must NOT succeed (no silent fallback).
    # Per HA semantics, an uncaught exception in async_setup_entry → SETUP_ERROR
    # (NOT SETUP_RETRY — that semantic is reserved for ConfigEntryNotReady,
    # which we deliberately do NOT raise here).
    assert entry.state.name == "SETUP_ERROR"
    # The raw error must reference the bad zone name in the captured reason / log.
    # entry.reason may be None depending on HA version; fall back to checking
    # the exception type via the state machine.
    if entry.reason is not None:
        assert "NotARealZone" in entry.reason or "ZoneInfo" in entry.reason


# ---------------------------------------------------------------------------
# Phase 6 W-2 — permanent regression guards for the three Critical Gotchas.
# Walk-and-grep across the production tree; same pattern for all three guards.
# ---------------------------------------------------------------------------


def test_no_deprecated_add_update_listener_in_production() -> None:
    """D-12 REVISED — production code MUST NOT reference entry.add_update_listener.

    OptionsFlowWithReload (Plan 06-05) is the replacement; using add_update_listener
    together with reloading methods is deprecated 2026-05-07, error in 2026.6,
    removed in 2026.12.
    """
    import pathlib

    root = pathlib.Path("custom_components/ha_pronote")
    offenders = [str(f) for f in root.rglob("*.py") if "add_update_listener(" in f.read_text(encoding="utf-8")]
    assert not offenders, (
        f"Found deprecated `entry.add_update_listener(...)` call in {offenders}. "
        f"Use OptionsFlowWithReload instead (06 D-12 REVISED, RESEARCH Gotcha #1)."
    )


def test_no_vol_strip_in_production() -> None:
    """W-2 permanent regression guard — `vol.Strip` does NOT exist in voluptuous.

    Using it raises AttributeError at module import time, taking down the whole
    integration. Replacement: `lambda v: v.strip()` inside `vol.All(...)`. See
    06-RESEARCH.md Critical Gotcha #2.

    The grep matches the attribute access (`vol.Strip`) but excludes lines where
    the token appears only inside string literals or comments that describe the
    gotcha — we match the bare attribute followed by `(` or whitespace-then-
    something-codey, NOT the literal substring (which would false-positive on
    documentation strings that warn against using the attribute).
    """
    import pathlib
    import re

    root = pathlib.Path("custom_components/ha_pronote")
    # Match attribute access shapes only: `vol.Strip(`, `vol.Strip,`, `vol.Strip)`,
    # `vol.Strip\s+` — NOT inside a comment or docstring that mentions the name.
    pattern = re.compile(r"(?<!\.)\bvol\.Strip\b(?=\s*[(,)\s])")
    offenders: list[str] = []
    for f in root.rglob("*.py"):
        for line in f.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue  # comments warning against the gotcha are allowed
            if pattern.search(line):
                offenders.append(str(f))
                break
    assert not offenders, (
        f"Found `vol.Strip` call in {offenders}. The voluptuous strip helper does "
        f"not exist and raises AttributeError at import. Use `lambda v: v.strip()` "
        f"inside vol.All(...) instead. See 06-RESEARCH.md Critical Gotcha #2."
    )


def test_no_options_flow_init_config_entry_assignment() -> None:
    """W-2 permanent regression guard — OptionsFlow.__init__(config_entry) is removed.

    HA deprecated the pattern in 2024.12 and removed it in 2025.12 — HA now
    injects `self.config_entry` as a read-only property on the OptionsFlow base
    class. Passing `config_entry` to `__init__` or assigning
    `self.config_entry = config_entry` raises AttributeError at flow start.
    See 06-RESEARCH.md Critical Gotcha #3.
    """
    import pathlib
    import re

    root = pathlib.Path("custom_components/ha_pronote")
    offenders: list[str] = []
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if re.search(r"def __init__\(self,\s*config_entry", text) or "self.config_entry = config_entry" in text:
            offenders.append(str(f))
    assert not offenders, (
        f"Found removed OptionsFlow.__init__(config_entry) pattern in {offenders}. "
        f"HA 2025.12+ injects self.config_entry automatically — remove the arg "
        f"and the assignment. See 06-RESEARCH.md Critical Gotcha #3."
    )
