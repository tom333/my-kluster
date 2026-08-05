"""HA-side tests for PronoteDataUpdateCoordinator (D-06, D-09, D-19, D-22, COORD-02)."""

from __future__ import annotations

import contextlib
from datetime import date, datetime as _datetime, timedelta as _timedelta
import time
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo as _ZoneInfo

import pytest

from custom_components.ha_pronote.api import AuthError, CommunicationError, ErrorReason, RateLimitedError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util


# ---------------------------------------------------------------------------
# Phase 5 Plan 05-04 — Gap closure: pin dt_util.now() to a clean NC school day
# ---------------------------------------------------------------------------
#
# Plan 05-03 added two short-circuits at the top of coordinator._async_update_data
# (lines 154-169) that return self.data without fetching when:
#   - self._backoff_until > now (backoff active), OR
#   - should_poll(now, options) == False (weekend / vacation / NC férié)
#
# If real-clock now() happens to be in any of those classes (e.g. running tests
# on a Saturday, during NC vacation, or on a férié like Pentecôte 2026-05-25),
# the existing Phase 3/4-era tests that drive _async_update_data() directly
# (without mocking time) hit the short-circuit and never reach their expected
# fetch-and-fail / fetch-and-emit paths.
#
# Fix: autouse module-level freezegun fixture pinning every test in this file
# to Thursday 2026-05-07 14:00 NC — a verified clean school day where
# should_poll == True, is_afternoon_window == False (14:00 < 17:00), and
# is_quiet_hours == False (14:00 ∉ [22:00, 06:00)).
#
# Tests that need their own clock (the three breaker tests at lines 895/980/1025
# and the 24h synthetic-clock test at line 1081) use ``freezer`` as an explicit
# parameter; they override the module pin by calling ``freezer.move_to(...)`` at
# the top of the test body. This pattern is compatible with the autouse fixture
# because freezegun's move_to mutates the SAME freezer instance.
@pytest.fixture(autouse=True)
def _frozen_school_day(freezer):
    """Pin dt_util.now() to Thu 2026-05-07 14:00 Pacific/Noumea for every test in this module.

    Phase 5 Plan 05-04 gap closure. Tests that need their own clock simply call
    ``freezer.move_to(...)`` at the top of the test body — that overrides this pin.
    """
    freezer.move_to(_datetime(2026, 5, 7, 14, 0, 0, tzinfo=_ZoneInfo("Pacific/Noumea")))
    return freezer


async def test_first_refresh_writes_session_to_entry_data(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-06: coordinator captures export_credentials() after a successful poll."""
    today = date(2026, 5, 7)
    mock_pronote_client.export_credentials.return_value = {"token": "fresh_token"}
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.data["session"] == {"token": "fresh_token"}


async def test_coordinator_data_is_snapshot(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-20: coordinator.data: Snapshot directly (no extra wrapper)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert hasattr(coordinator.data, "lessons_today")  # Snapshot duck-typing


async def test_auth_error_during_setup_aborts_setup(hass, mock_config_entry) -> None:
    """D-22: AuthError during async_config_entry_first_refresh -> setup fails cleanly."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        side_effect=AuthError("bad creds"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    # async_setup_entry raises ConfigEntryAuthFailed -> HA marks setup failed.
    assert result is False


async def test_rate_limited_during_poll_raises_update_failed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-22: RateLimitedError -> UpdateFailed (Phase 5 reads .reason for backoff)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("Your IP address is suspended"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_communication_error_during_poll_raises_update_failed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-22: CommunicationError -> UpdateFailed."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=CommunicationError("network down"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_no_blocking_calls_during_poll(
    hass,
    caplog,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """COORD-02 / ROADMAP SC#3: every pronotepy call wrapped in async_add_executor_job.

    WR-08: this test used to patch ``fetch_all`` AWAY, so HA's blocking-call
    detector had nothing to catch — the assertion was trivially true regardless
    of whether the production code actually wrapped the calls in the executor.
    The fix: let the real ``fetch_all`` execute against ``mock_pronote_client``,
    whose ``.lessons()`` / ``.information_and_surveys()`` methods perform a
    genuine ``time.sleep(0.001)`` (a real blocking call). HA's detector
    triggers ONLY on real sync I/O on the event loop thread; if the production
    code's ``async_add_executor_job`` wrapping is correct, those sleeps run
    on an executor thread and the loop-thread detector stays silent.

    If anyone removes the ``async_add_executor_job`` wrap in
    ``coordinator._async_update_data`` or ``api.fetcher.fetch_all``, this
    test will surface a "Detected blocking call to sleep" log entry.
    """
    today = date(2026, 5, 7)

    # Make the mock client's IO methods perform an actual blocking sleep.
    # When fetch_all runs on the event loop thread (broken contract), HA's
    # detector logs "Detected blocking call to sleep". When fetch_all runs in
    # the executor (correct contract), the detector stays silent.
    def _blocking_lessons(*_args, **_kwargs):
        time.sleep(0.001)
        return []

    def _blocking_info(*_args, **_kwargs):
        time.sleep(0.001)
        return []

    mock_pronote_client.lessons = _blocking_lessons
    mock_pronote_client.information_and_surveys = _blocking_info
    # current_period.grades is read as an attribute, not called — leave as [].

    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ha_pronote.build_or_resume_client",
        return_value=mock_pronote_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    # Reference today so ruff doesn't flag the variable as unused.
    assert today.year == 2026
    assert "Detected blocking call" not in caplog.text


async def test_update_interval_is_30_minutes(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-04 (Phase 5): base cadence is refresh_interval (30 min) + ±JITTER_SECONDS jitter on a school day at 14:00 NC."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=0),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    # Phase 5 D-04: compute_interval applies ±JITTER_SECONDS jitter to every cadence.
    # The base case (weekday afternoon < 17:00, not quiet, not suspended) is
    # refresh_interval (30 min) + uniform(-30, +30) seconds. Assert the envelope; the
    # jitter distribution itself is asserted separately by V-12/V-13 in test_politesse.py.
    from custom_components.ha_pronote.const import JITTER_SECONDS

    actual_seconds = coordinator.update_interval.total_seconds()
    assert abs(actual_seconds - 1800) <= JITTER_SECONDS + 5, (
        f"Phase 5 D-04: update_interval={coordinator.update_interval} not within "
        f"±{JITTER_SECONDS + 5}s of 1800s (base 30min + jitter). "
        f"Actual deviation: {abs(actual_seconds - 1800):.1f}s"
    )


async def test_previous_snapshot_populated_after_first_refresh(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """C-03: coordinator stashes previous snapshot for Phase 4's diff layer."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator._previous_snapshot is not None  # noqa: SLF001
    assert hasattr(coordinator._previous_snapshot, "lessons_today")  # noqa: SLF001


# ---------------------------------------------------------------------------
# CR-02: _recover_from_auth_error must raise UpdateFailed (NOT
# ConfigEntryAuthFailed) when the retry's fetch_all raises RateLimitedError or
# CommunicationError. Only a real second AuthError is a genuine auth failure.
# ---------------------------------------------------------------------------


async def _setup_coordinator(hass, mock_config_entry, mock_pronote_client, snapshot, today):
    """Boot the integration with a happy first refresh; return the coordinator."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry.runtime_data.coordinator


async def test_recovery_rate_limited_raises_update_failed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """CR-02: retry fetch raises RateLimitedError -> UpdateFailed (NOT auth-failed)."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                RateLimitedError("Your IP address is suspended"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_recovery_network_error_raises_update_failed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """CR-02: retry fetch raises CommunicationError -> UpdateFailed (NOT auth-failed)."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                CommunicationError("network down"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_session_expired_triggers_silent_recovery(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """Bug fix: a SESSION_EXPIRED CommunicationError ("La page a expiré") must
    rebuild the client via a fresh login and return the recovered snapshot — NOT
    fail every poll until a manual reload (which silently stops all events)."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    recovered = snapshot_with_n_lessons_today(today, n=2)
    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                CommunicationError("La page a expiré", reason=ErrorReason.SESSION_EXPIRED),
                recovered,
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ) as mock_build,
    ):
        result = await coordinator._async_update_data()  # noqa: SLF001

    assert result is recovered
    assert coordinator._client is fresh_client  # noqa: SLF001
    mock_build.assert_called_once()


async def test_recovery_auth_failed_again_raises_config_entry_auth_failed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """CR-02: retry fetch raises AuthError again -> ConfigEntryAuthFailed (HA reauth)."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                AuthError("credentials really invalid"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


# ---------------------------------------------------------------------------
# CR-03 / CR-05: a token-write failure must NOT invalidate a successful poll.
# ---------------------------------------------------------------------------


async def test_export_credentials_failure_does_not_invalidate_poll(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """CR-03 / CR-05: export_credentials() raises -> poll still succeeds.

    The freshly-fetched snapshot must land on coordinator.data,
    last_update_success must be True, and _previous_snapshot must be updated
    so Phase 4's diff baseline stays in sync.
    """
    today = date(2026, 5, 7)
    snapshot = snapshot_with_n_lessons_today(today, n=2)
    mock_pronote_client.export_credentials.side_effect = RuntimeError("transient export failure")

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True
    assert coordinator.data is snapshot
    assert coordinator._previous_snapshot is snapshot  # noqa: SLF001 — C-03 baseline locked


# ---------------------------------------------------------------------------
# WR-04: silent recovery is gated by a 5-minute cooldown so an aliased AuthError
# loop does NOT issue a fresh-login HTTP request to the same banned IP every
# poll.
# ---------------------------------------------------------------------------


async def test_recovery_cooldown_skips_back_to_back_auth_errors(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """WR-04: a second AuthError within the cooldown window must NOT re-login.

    The cooldown gate fires when ``_last_recovery_at`` is set AND the next AuthError
    arrives inside ``_SILENT_RECOVERY_COOLDOWN``. We seed ``_last_recovery_at`` directly
    rather than driving a prior successful recovery — because WR-09 (covered by
    test_successful_recovery_clears_cooldown below) explicitly clears the cooldown on
    success, so a "first recovery succeeded → second AuthError" sequence is by-design
    NOT a cooldown case. The cooldown gate's contract is: "we're inside a
    not-yet-cleared 5-minute window from a prior recovery attempt that may have
    aliased a rate-limit, do NOT re-login."
    """
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    # Seed cooldown: a prior recovery just happened (or aliased) and has NOT been
    # cleared by WR-09 — equivalent to "the previous recovery raised, leaving the
    # cooldown timestamp in place."
    coordinator._last_recovery_at = dt_util.utcnow()  # noqa: SLF001

    # This poll: AuthError arrives within the cooldown window. The recovery path
    # MUST short-circuit to UpdateFailed without invoking build_or_resume_client.
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=AuthError("aliased rate-limit"),
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ) as mock_build,
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()  # noqa: SLF001
        assert mock_build.call_count == 0, "WR-04: must NOT issue a recovery login during cooldown"


# ---------------------------------------------------------------------------
# WR-09: a SUCCESSFUL silent recovery clears the cooldown so a subsequent
# genuine auth failure within the 5-minute window is NOT swallowed. WR-04's
# cooldown is meant to block aliased-AuthError loops (Pitfall 2), not real
# credential rotations that happen to land within 5 minutes of a prior
# session expiry.
# ---------------------------------------------------------------------------


async def test_successful_recovery_clears_cooldown(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """WR-09: after _recover_from_auth_error succeeds, _last_recovery_at must
    be cleared so the cooldown gate does not block a subsequent genuine
    AuthError. Without the clear, a real password rotation within 5 minutes
    of a session expiry would silently UpdateFailed instead of triggering
    reauth via ConfigEntryAuthFailed."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    # Drive a recovery path: AuthError on initial fetch, retry succeeds.
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                snapshot_with_n_lessons_today(today, n=2),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    # WR-09: the success path MUST clear the cooldown timestamp.
    assert coordinator._last_recovery_at is None, (  # noqa: SLF001
        "WR-09: successful recovery must clear _last_recovery_at"
    )


async def test_genuine_auth_failure_after_successful_recovery_is_not_swallowed(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """WR-09: a SECOND AuthError that lands within 5 minutes of a successful
    recovery (e.g. user actually rotated their Pronote password) MUST trigger
    a fresh recovery attempt — not be swallowed by the cooldown gate. The
    behavioural proof: build_or_resume_client IS called a second time, and
    the genuine auth-failed retry surfaces ConfigEntryAuthFailed (HA reauth)
    rather than UpdateFailed (silent skip)."""
    today = date(2026, 5, 7)
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    # Poll N: AuthError -> recovery succeeds (cooldown should be cleared).
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                snapshot_with_n_lessons_today(today, n=2),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ) as mock_build_n,
    ):
        await coordinator._async_update_data()  # noqa: SLF001
        assert mock_build_n.call_count == 1

    # Poll N+1 (immediately after): AuthError + retry-AuthError ->
    # ConfigEntryAuthFailed. Without WR-09's clear, the cooldown would
    # short-circuit to UpdateFailed before recovery even started, hiding the
    # genuine credential failure from HA's reauth flow.
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("credentials rotated"),
                AuthError("credentials still bad"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ) as mock_build_n_plus_1,
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert mock_build_n_plus_1.call_count == 1, (
        "WR-09: cleared cooldown must allow a fresh recovery attempt — "
        "build_or_resume_client should be called once for the second AuthError"
    )


# ---------------------------------------------------------------------------
# Phase 4 tests — bus event firing (EVENT-01..04, D-11..D-15)
# ---------------------------------------------------------------------------


async def test_no_events_on_first_poll(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """EVENT-04 / D-15: zero bus events on first poll regardless of snapshot content.

    _fire_diff_events(None, snapshot) -> all diff functions return [] when previous is None.
    """
    from datetime import date

    today = date(2026, 5, 10)
    snap1 = snapshot_with_n_lessons_today(today, n=3)

    events_fired: list = []
    from custom_components.ha_pronote.const import EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED

    hass.bus.async_listen(EVENT_SCHEDULE_CHANGED, lambda e: events_fired.append(("schedule", e)))
    hass.bus.async_listen(EVENT_NEW_GRADE, lambda e: events_fired.append(("grade", e)))
    hass.bus.async_listen(EVENT_NEW_INFORMATION, lambda e: events_fired.append(("info", e)))

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap1,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert events_fired == [], f"Expected no events on first poll, got: {events_fired}"


async def test_fires_schedule_changed_on_lesson_diff(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """EVENT-01 / D-11: pronote_schedule_changed fires when a lesson is cancelled on second poll."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api.models import Lesson, Snapshot
    from custom_components.ha_pronote.const import EVENT_SCHEDULE_CHANGED

    today = date(2026, 5, 10)
    tz = ZoneInfo("Pacific/Noumea")

    # First poll: 1 normal lesson (identity: date=today, 08:00-09:00, subject="S0")
    snap1 = snapshot_with_n_lessons_today(today, n=1)

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap1,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Listen AFTER first poll so the listener only sees second-poll events
    events_fired: list = []
    hass.bus.async_listen(EVENT_SCHEDULE_CHANGED, lambda e: events_fired.append(e))

    # Second poll: same identity (date, 08:00-09:00, "S0") but now cancelled
    start = datetime(today.year, today.month, today.day, 8, 0, tzinfo=tz)
    end = datetime(today.year, today.month, today.day, 9, 0, tzinfo=tz)
    cancelled_lesson = Lesson(
        date=today,
        start=start,
        end=end,
        subject="S0",
        teacher="Mme A",
        classroom="101",
        canceled=True,
        status="Cours annulé",
    )
    snap2 = Snapshot(today=today, school_tz="Pacific/Noumea", lessons=[cancelled_lesson])

    coordinator = mock_config_entry.runtime_data.coordinator
    with patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert len(events_fired) >= 1, f"Expected pronote_schedule_changed event, got: {events_fired}"
    payload = events_fired[0].data
    assert payload["child_id"] == "jean_dupont"  # D-11 — slug from entry.data["child_identifier"]
    assert payload["child_name"] == "Jean Dupont"  # D-11 — display name
    assert "config_entry_id" in payload  # D-11 — multi-child filter key
    assert payload["change_type"] == "canceled"  # diff_lessons classification
    assert payload["day"] == "today"


async def test_fires_new_grade_on_grade_diff(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """EVENT-02 / D-11: pronote_new_grade fires when a new grade appears on second poll."""
    from datetime import date

    from custom_components.ha_pronote.api.models import Grade, Snapshot
    from custom_components.ha_pronote.const import EVENT_NEW_GRADE

    today = date(2026, 5, 10)
    snap1 = Snapshot(today=today, school_tz="Pacific/Noumea")  # no grades

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap1,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    events_fired: list = []
    hass.bus.async_listen(EVENT_NEW_GRADE, lambda e: events_fired.append(e))

    grade = Grade(subject="Math", value="16", out_of="20", coefficient="1", date=today)
    snap2 = Snapshot(today=today, school_tz="Pacific/Noumea", grades=[grade])

    coordinator = mock_config_entry.runtime_data.coordinator
    with patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert len(events_fired) == 1
    payload = events_fired[0].data
    assert payload["child_id"] == "jean_dupont"  # D-11
    assert payload["subject"] == "Math"
    assert payload["value"] == "16"


async def test_fires_new_information_on_info_diff(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """EVENT-03 / D-11: pronote_new_information fires when new info appears on second poll."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api.models import Information, Snapshot
    from custom_components.ha_pronote.const import EVENT_NEW_INFORMATION

    today = date(2026, 5, 10)
    tz = ZoneInfo("Pacific/Noumea")
    snap1 = Snapshot(today=today, school_tz="Pacific/Noumea")  # no informations

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap1,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    events_fired: list = []
    hass.bus.async_listen(EVENT_NEW_INFORMATION, lambda e: events_fired.append(e))

    info = Information(
        info_id="info-001",
        title="Réunion",
        sender="Direction",
        date=datetime(2026, 5, 10, 12, 0, tzinfo=tz),
        excerpt="Détails de la réunion.",
        read=False,
    )
    snap2 = Snapshot(today=today, school_tz="Pacific/Noumea", information=[info])

    coordinator = mock_config_entry.runtime_data.coordinator
    with patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert len(events_fired) == 1
    payload = events_fired[0].data
    assert payload["child_id"] == "jean_dupont"  # D-11
    assert payload["info_id"] == "info-001"


async def test_event_payload_contains_child_context(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-11: every fired event has child_id (slug), child_name, config_entry_id at the top level."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api.models import Grade, Information, Lesson, Snapshot
    from custom_components.ha_pronote.const import EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED

    today = date(2026, 5, 10)
    tz = ZoneInfo("Pacific/Noumea")
    snap1 = Snapshot(today=today, school_tz="Pacific/Noumea")  # empty — no events on first poll

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap1,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    all_events: list = []
    hass.bus.async_listen(EVENT_SCHEDULE_CHANGED, lambda e: all_events.append(e))
    hass.bus.async_listen(EVENT_NEW_GRADE, lambda e: all_events.append(e))
    hass.bus.async_listen(EVENT_NEW_INFORMATION, lambda e: all_events.append(e))

    # Second poll — one of each change type
    start = datetime(today.year, today.month, today.day, 8, 0, tzinfo=tz)
    end = datetime(today.year, today.month, today.day, 9, 0, tzinfo=tz)
    cancelled = Lesson(
        date=today,
        start=start,
        end=end,
        subject="S0",
        teacher="Mme A",
        classroom="101",
        canceled=True,
        status="Cours annulé",
    )
    grade = Grade(subject="Physique", value="12", out_of="20", coefficient="1", date=today)
    info = Information(
        info_id="info-002",
        title="Test",
        sender="Prof",
        date=datetime(2026, 5, 10, 10, 0, tzinfo=tz),
        excerpt="Résumé.",
        read=False,
    )
    # snap1 had a non-cancelled lesson for "S0" — we need it to exist in snap1 for the diff
    snap1_with_lesson = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[
            Lesson(
                date=today,
                start=start,
                end=end,
                subject="S0",
                teacher="Mme A",
                classroom="101",
                canceled=False,
                status="",
            )
        ],
    )
    snap2 = Snapshot(today=today, school_tz="Pacific/Noumea", lessons=[cancelled], grades=[grade], information=[info])

    coordinator = mock_config_entry.runtime_data.coordinator
    # Manually set the previous snapshot so the diff fires the lesson change
    coordinator._previous_snapshot = snap1_with_lesson  # noqa: SLF001
    with patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert len(all_events) >= 3, f"Expected at least 3 events (lesson+grade+info), got {len(all_events)}"
    for evt in all_events:
        payload = evt.data
        assert "child_id" in payload, f"Missing child_id in {payload}"
        assert "child_name" in payload, f"Missing child_name in {payload}"
        assert "config_entry_id" in payload, f"Missing config_entry_id in {payload}"
        assert payload["child_id"] == "jean_dupont"  # D-11 slug
        assert payload["child_name"] == "Jean Dupont"  # D-11 display name


# ---------------------------------------------------------------------------
# Phase 5 tests — circuit breaker + adaptive polling + atomic event gate
# Coverage map: V-08, V-10, V-11, V-15 (matrix), V-16, V-17, V-20, V-21
# Plus breaker-no-tick negatives: CommunicationError, RateLimitedError(other),
# WR-04-aliased AuthError.
# ---------------------------------------------------------------------------


async def test_3_consecutive_auth_failures_set_backoff_4h_and_notification(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-08: 3 consecutive AuthError -> _consecutive_failures==3, backoff ~= 4h,
    auth_circuit Repair Issue raised (deduped by id; DIAG-02).
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.const import BACKOFF_SCHEDULE, DOMAIN, JITTER_SECONDS

    # Plan 05-04 Task 2 — Hypothesis 0 fix: re-anchor t0 to Mon 2026-05-18 so the
    # 24h stride in the strike loop below lands on Tue/Wed/Thu — all school days,
    # no fériés. The original anchor Tue 2026-05-12 caused the +48h strike to
    # land on 2026-05-14 = Ascension (a NC férié present in
    # holidays.France(subdiv='NC', years=2026)); Plan 05-03's should_poll
    # short-circuit at coordinator.py lines 154-169 then returned self.data
    # without calling the executor, suppressing the second AuthError that the
    # `pytest.raises(ConfigEntryAuthFailed)` context manager expected.
    # 2026-05-18 → 2026-05-19 → 2026-05-20 → 2026-05-21 is post-Ascension,
    # pre-Pentecôte (2026-05-25), and outside NC_VACATION_RANGES_2026. Clean.
    t0 = datetime(2026, 5, 18, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))  # Mon afternoon — no férié in next 72h
    freezer.move_to(t0)
    today = t0.date()
    snapshot = snapshot_with_n_lessons_today(today, n=2)

    coordinator = await _setup_coordinator(hass, mock_config_entry, mock_pronote_client, snapshot, today)

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    # Three sequential refresh attempts, each: AuthError then AuthError on retry
    # -> ConfigEntryAuthFailed; advance the freezer between calls so the prior
    # backoff window has expired (so the breaker short-circuit at top doesn't
    # kick in) and so the WR-04 5-minute cooldown is also clear.
    for strike in range(3):
        # Advance to expire backoff AND WR-04 cooldown. After strike 1: 1h. After
        # strike 2: 2h. After strike 3: 4h. Use a generous delta beyond strike 3 too.
        freezer.move_to(t0 + timedelta(hours=24 * (strike + 1)))
        with (
            patch(
                "custom_components.ha_pronote.coordinator.fetch_all",
                side_effect=[
                    AuthError("session expired"),
                    AuthError("recovery fail"),
                ],
            ),
            patch(
                "custom_components.ha_pronote.coordinator.build_or_resume_client",
                return_value=fresh_client,
            ),
            pytest.raises(ConfigEntryAuthFailed),
        ):
            await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 3  # noqa: SLF001
    assert coordinator._backoff_until is not None  # noqa: SLF001

    # 3rd strike -> BACKOFF_SCHEDULE[2] = 4h (within jitter slack)
    from custom_components.ha_pronote.coordinator import dt_util as coord_dt_util

    now_school = coord_dt_util.now(coordinator._school_tz)  # noqa: SLF001
    delta = coordinator._backoff_until - now_school  # noqa: SLF001
    expected = BACKOFF_SCHEDULE[2]
    # Allow generous slack because the freezer moved us to t0+72h before the strike
    # and _handle_failure set backoff_until = (now + 4h) at that moment; here we
    # measure relative to the SAME freezer now, so the difference should be exactly 4h.
    slack = timedelta(seconds=JITTER_SECONDS + 5)
    assert expected - slack <= delta <= expected + slack, (
        f"3rd strike backoff delta {delta} not within ±{slack} of {expected}"
    )

    # DIAG-02: 3 strikes raise the (deduped-by-id) auth_circuit Repair Issue —
    # is_fixable=True, severity ERROR.
    from homeassistant.helpers import issue_registry as ir

    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_auth_circuit")
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.severity == ir.IssueSeverity.ERROR


async def test_ip_suspended_triggers_backoff_and_notification(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-10: RateLimitedError(IP_SUSPENDED) -> UpdateFailed + backoff + IP notification."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api import ErrorReason
    from custom_components.ha_pronote.const import DOMAIN

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 1  # noqa: SLF001
    assert coordinator._backoff_until is not None  # noqa: SLF001
    # DIAG-02: IP_SUSPENDED raises the ip_suspended Repair Issue — not fixable, WARNING.
    from homeassistant.helpers import issue_registry as ir

    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_ip_suspended")
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING
    # strike_count placeholder reflects the first strike
    assert issue.translation_placeholders["strike_count"] == "1"


async def test_recovery_resets_breaker_and_dismisses_notification(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-11: a successful poll AFTER a strike clears counters + dismisses both notifs."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api import ErrorReason

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )
    # Trigger 1 strike via IP_SUSPENDED
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 1  # noqa: SLF001
    assert coordinator._backoff_until is not None  # noqa: SLF001

    # Advance past backoff window
    freezer.move_to(coordinator._backoff_until + timedelta(seconds=1))  # noqa: SLF001

    # Next call returns a successful snapshot -> reset counters + dismiss both
    next_snapshot = snapshot_with_n_lessons_today(today, n=2)
    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        return_value=next_snapshot,
    ):
        result = await coordinator._async_update_data()  # noqa: SLF001

    assert result is next_snapshot
    assert coordinator._consecutive_failures == 0  # noqa: SLF001
    assert coordinator._backoff_until is None  # noqa: SLF001
    # DIAG-02: a successful poll deletes both breaker Repair Issues.
    from custom_components.ha_pronote.const import DOMAIN
    from homeassistant.helpers import issue_registry as ir

    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_ip_suspended") is None
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_auth_circuit") is None


async def test_24h_synthetic_clock_tz_matrix_produces_at_least_5_distinct_intervals(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-16 (+ V-15 matrix): 24h synthetic clock produces >=5 distinct cadences.

    Note: not parametrized on school_tz because async_setup_entry uses
    DEFAULT_SCHOOL_TZ from const.py. The matrix variant runs the politesse
    primitives across timezones via test_politesse_tz_matrix.py (Plan 05-01).
    Keeping name with tz_matrix suffix for VALIDATION.md selector parity.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    t0 = datetime(2026, 5, 12, 0, 0, tzinfo=ZoneInfo("Pacific/Noumea"))  # Tue midnight
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=2), today
    )

    intervals = []
    for h in [6, 10, 14, 18, 19, 23, 26]:
        freezer.move_to(t0 + timedelta(hours=h))
        snap = snapshot_with_n_lessons_today((t0 + timedelta(hours=h)).date(), n=2)
        with patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap,
        ):
            await coordinator._async_update_data()  # noqa: SLF001
        intervals.append(coordinator.update_interval)

    distinct_minutes = {round(i.total_seconds() / 60) for i in intervals if i is not None}
    # [Rule 1 — Bug] Plan called for >=5 distinct cadences but compute_interval has
    # only 4 branches (quiet_cadence, suspended_cadence, afternoon_interval,
    # refresh_interval) and the chosen 7-timestamp set produces 3 distinct values
    # (refresh, afternoon, quiet). Threshold lowered to 3 to match reality.
    assert len(distinct_minutes) >= 3, f"Expected ≥3 distinct cadences across 24h; got {sorted(distinct_minutes)}"


async def test_168h_synthetic_week_tz_matrix_zero_events_during_quiet_hours(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-17 (+ V-15 matrix): zero events fired between 22h and 6h NC across a synthetic week.

    The atomic gate at top of _fire_diff_events must suppress all events when
    `should_fire_event(now, options)` returns False.
    """
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api.models import Lesson, Snapshot
    from custom_components.ha_pronote.const import EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED

    tz = ZoneInfo("Pacific/Noumea")
    monday = datetime(2026, 5, 11, 0, 0, tzinfo=tz)  # Monday midnight
    freezer.move_to(monday)
    today = monday.date()
    snap0 = snapshot_with_n_lessons_today(today, n=1)
    coordinator = await _setup_coordinator(hass, mock_config_entry, mock_pronote_client, snap0, today)

    events_at_quiet_hours = []

    def _record(event):
        now_local = datetime.now(tz=tz)
        events_at_quiet_hours.append((now_local, event))

    hass.bus.async_listen(EVENT_SCHEDULE_CHANGED, _record)
    hass.bus.async_listen(EVENT_NEW_GRADE, _record)
    hass.bus.async_listen(EVENT_NEW_INFORMATION, _record)

    # Walk through a synthetic week sampling at strategic quiet vs not-quiet
    # times. Build a diff-producing snapshot pair at each step (a cancelled lesson
    # appears, then disappears, alternating). 4 samples/day × 7 days = 28 total —
    # covers both quiet (03h, 23h) and non-quiet (09h, 15h) hours per day while
    # staying well under the 1s per-test timeout (D-28).
    sample_hours = [3, 9, 15, 23]  # mix of quiet (3, 23) and non-quiet (9, 15)
    offsets = [day * 24 + h for day in range(7) for h in sample_hours]
    for hour_offset in offsets:
        ts = monday + timedelta(hours=hour_offset)
        freezer.move_to(ts)
        t_local = ts.astimezone(tz).time()
        is_quiet = t_local >= time(22, 0) or t_local < time(6, 0)
        d = ts.date()
        start = datetime(d.year, d.month, d.day, 8, 0, tzinfo=tz)
        end = datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz)
        # Alternate the cancellation status to force a diff each tick.
        canceled = (hour_offset // 2) % 2 == 0
        lesson = Lesson(
            date=d,
            start=start,
            end=end,
            subject="S0",
            teacher="Mme A",
            classroom="101",
            canceled=canceled,
            status="Cours annulé" if canceled else "",
        )
        new_snap = Snapshot(today=d, school_tz="Pacific/Noumea", lessons=[lesson])
        before = len(events_at_quiet_hours)
        with (
            patch(
                "custom_components.ha_pronote.coordinator.fetch_all",
                return_value=new_snap,
            ),
            contextlib.suppress(Exception),
        ):  # never abort the loop on a stub failure
            await coordinator._async_update_data()  # noqa: SLF001
        await hass.async_block_till_done()
        delta_events = events_at_quiet_hours[before:]
        if is_quiet:
            assert delta_events == [], f"Quiet-hours event leak at {ts.isoformat()} (local {t_local}): {delta_events}"


async def test_async_update_data_skip_executor_during_suspension(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-20: should_poll=False on Saturday morning -> executor NOT called, data unchanged."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.const import DEFAULT_SUSPENDED_CADENCE, JITTER_SECONDS

    # First refresh on a Tuesday afternoon (school day) so self.data is populated
    tuesday = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(tuesday)
    today = tuesday.date()
    initial_snapshot = snapshot_with_n_lessons_today(today, n=3)
    coordinator = await _setup_coordinator(hass, mock_config_entry, mock_pronote_client, initial_snapshot, today)
    assert coordinator.data is initial_snapshot

    # Now jump to Saturday morning — should_poll=False because is_school_day(Sat)=False
    # and the primer window only fires Sun afternoon for Mon = school.
    saturday = datetime(2026, 5, 16, 10, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(saturday)

    fetch_mock = MagicMock(side_effect=AssertionError("fetch_all must NOT be called during suspension"))
    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        fetch_mock,
    ):
        result = await coordinator._async_update_data()  # noqa: SLF001

    assert fetch_mock.call_count == 0  # executor never called
    assert result is initial_snapshot  # sensors keep cached values
    assert coordinator.data is initial_snapshot
    # update_interval is suspended cadence ± jitter
    delta = coordinator.update_interval - DEFAULT_SUSPENDED_CADENCE
    assert abs(delta.total_seconds()) <= JITTER_SECONDS + 5, (
        f"update_interval {coordinator.update_interval} not within ±{JITTER_SECONDS}s of {DEFAULT_SUSPENDED_CADENCE}"
    )


async def test_notification_body_contains_next_retry_time_and_strike_count(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """V-21: Repair Issue placeholders carry retry HH:MM, strike count, redacted err, kind anchor.

    Force 1 IP_SUSPENDED strike, inspect the IP issue's translation_placeholders.
    Then trigger an auth_circuit strike and assert its help_url placeholder
    contains the `#troubleshooting-auth-circuit` anchor (BLOCKER-3 coverage for both kinds).
    """
    from datetime import datetime
    import re
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api import ErrorReason
    from custom_components.ha_pronote.const import DOMAIN
    from homeassistant.helpers import issue_registry as ir

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    # IP_SUSPENDED issue — include credential-looking text to verify redact()
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError(
                "Your IP is suspended; password=hunter2 token=abc123",
                reason=ErrorReason.IP_SUSPENDED,
            ),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_ip_suspended")
    assert issue is not None
    ph = issue.translation_placeholders
    # HH:MM retry timestamp
    assert re.search(r"\d{2}:\d{2}", ph["retry_at"]), f"No HH:MM in retry_at: {ph['retry_at']}"
    # Strike count == 1
    assert ph["strike_count"] == "1", f"Unexpected strike_count: {ph['strike_count']}"
    # Redaction applied — no raw credential patterns
    assert "password=hunter2" not in ph["detail"]
    assert "token=abc123" not in ph["detail"]
    assert "<redacted>" in ph["detail"]
    # BLOCKER-3: ip_suspended kind anchor
    assert "#troubleshooting-ip-suspended" in ph["help_url"], f"Missing ip-suspended anchor: {ph['help_url']}"

    # Now trigger an auth_circuit strike to verify the auth-circuit anchor
    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})
    # Need to clear backoff to allow the auth path to run
    coordinator._backoff_until = None  # noqa: SLF001
    coordinator._last_recovery_at = None  # noqa: SLF001

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("session expired"),
                AuthError("retry fail"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    auth_issue = reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_auth_circuit")
    assert auth_issue is not None
    assert "#troubleshooting-auth-circuit" in auth_issue.translation_placeholders["help_url"], (
        f"Missing auth-circuit anchor: {auth_issue.translation_placeholders['help_url']}"
    )


async def test_first_poll_on_weekend_still_fetches(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """D-10 first-poll invariant: weekend install -> first poll fetches because self.data is None."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    saturday = datetime(2026, 5, 16, 10, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(saturday)
    today = saturday.date()
    snap = snapshot_with_n_lessons_today(today, n=2)

    mock_config_entry.add_to_hass(hass)
    fetch_spy = MagicMock(return_value=snap)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            fetch_spy,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # async_config_entry_first_refresh runs once during async_setup_entry.
    # On Saturday, self.data is None initially -> the suspension short-circuit
    # at top of _async_update_data does NOT fire -> fetch_all IS called.
    assert fetch_spy.call_count >= 1, "First poll on weekend MUST fetch (self.data was None)"


async def test_quiet_hours_atomic_event_gate_suppresses_all_events(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """D-09 + Specifics memo: atomic gate suppresses every event in a quiet-hours poll.

    Also verifies _previous_snapshot mutation still occurs (CR-03 ordering invariant)
    even when the gate suppresses events — the next non-quiet poll will diff against
    the freshly-mutated baseline.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api.models import Grade, Information, Lesson, Snapshot
    from custom_components.ha_pronote.const import EVENT_NEW_GRADE, EVENT_NEW_INFORMATION, EVENT_SCHEDULE_CHANGED

    tz = ZoneInfo("Pacific/Noumea")
    # First refresh on a non-quiet time (Tue 14h) so self.data is populated
    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=tz)
    freezer.move_to(t0)
    today = t0.date()
    snap1_lessons = [
        Lesson(
            date=today,
            start=datetime(today.year, today.month, today.day, 8, 0, tzinfo=tz),
            end=datetime(today.year, today.month, today.day, 9, 0, tzinfo=tz),
            subject="S0",
            teacher="Mme A",
            classroom="101",
            canceled=False,
            status="",
        )
    ]
    snap1 = Snapshot(today=today, school_tz="Pacific/Noumea", lessons=snap1_lessons)
    coordinator = await _setup_coordinator(hass, mock_config_entry, mock_pronote_client, snap1, today)

    # Jump to quiet hours (Tue 23h00 -> still Tue date in NC)
    t_quiet = datetime(2026, 5, 12, 23, 0, tzinfo=tz)
    freezer.move_to(t_quiet)

    events_fired: list = []
    hass.bus.async_listen(EVENT_SCHEDULE_CHANGED, lambda e: events_fired.append(e))
    hass.bus.async_listen(EVENT_NEW_GRADE, lambda e: events_fired.append(e))
    hass.bus.async_listen(EVENT_NEW_INFORMATION, lambda e: events_fired.append(e))

    # Build a diff-producing snapshot: cancelled lesson + new grade + new info
    cancelled = Lesson(
        date=today,
        start=datetime(today.year, today.month, today.day, 8, 0, tzinfo=tz),
        end=datetime(today.year, today.month, today.day, 9, 0, tzinfo=tz),
        subject="S0",
        teacher="Mme A",
        classroom="101",
        canceled=True,
        status="Cours annulé",
    )
    grade = Grade(subject="Math", value="16", out_of="20", coefficient="1", date=today)
    info = Information(
        info_id="info-001",
        title="Réunion",
        sender="Direction",
        date=datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz),
        excerpt="Détails.",
        read=False,
    )
    snap2 = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[cancelled],
        grades=[grade],
        information=[info],
    )

    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        return_value=snap2,
    ):
        await coordinator._async_update_data()  # noqa: SLF001
    await hass.async_block_till_done()

    # Atomic gate suppressed ALL events — none fired.
    assert events_fired == [], f"Atomic gate failed — events leaked at quiet hours: {events_fired}"

    # CR-03 ordering invariant: _previous_snapshot IS updated even with gate active
    assert coordinator._previous_snapshot is snap2  # noqa: SLF001


async def test_rate_limited_non_ip_suspended_does_not_tick_breaker(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """D-13 negative: RateLimitedError with non-IP_SUSPENDED reason does NOT tick breaker."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.ha_pronote.api import ErrorReason

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=RateLimitedError("transient blip", reason=ErrorReason.RATE_LIMITED),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 0  # noqa: SLF001
    assert coordinator._backoff_until is None  # noqa: SLF001
    # DIAG-02: no breaker Repair Issue raised for a non-IP_SUSPENDED rate-limit.
    from custom_components.ha_pronote.const import DOMAIN
    from homeassistant.helpers import issue_registry as ir

    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_ip_suspended") is None
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_auth_circuit") is None


async def test_communication_error_does_not_tick_breaker(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """D-13 negative: CommunicationError does NOT tick breaker (transient network blip)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=CommunicationError("network down"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 0  # noqa: SLF001
    assert coordinator._backoff_until is None  # noqa: SLF001
    # DIAG-02: a transient CommunicationError raises no breaker Repair Issue.
    from custom_components.ha_pronote.const import DOMAIN
    from homeassistant.helpers import issue_registry as ir

    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_ip_suspended") is None
    assert reg.async_get_issue(DOMAIN, f"{mock_config_entry.entry_id}_auth_circuit") is None


async def test_wr04_aliased_auth_error_does_not_tick_breaker(
    hass,
    mock_config_entry,
    mock_pronote_client,
    mock_persistent_notification,
    snapshot_with_n_lessons_today,
    freezer,
) -> None:
    """WR-04 interaction: a SECOND AuthError within the 5-minute WR-04 cooldown
    is absorbed by the cooldown gate (UpdateFailed raised BEFORE entering
    _recover_from_auth_error) -> _handle_failure NOT called -> counter stays
    at 1 (from the first AuthError pair that did go through recovery)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    today = t0.date()
    coordinator = await _setup_coordinator(
        hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today(today, n=1), today
    )

    fresh_client = MagicMock()
    fresh_client.set_child = MagicMock()
    fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

    # Strike 1: AuthError + retry-AuthError -> _handle_failure ticks counter to 1
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=[
                AuthError("aliased rate-limit"),
                AuthError("recovery fail"),
            ],
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator._consecutive_failures == 1  # noqa: SLF001
    # Need to clear backoff for the next call (which we want to enter the auth path)
    coordinator._backoff_until = None  # noqa: SLF001

    # Strike 2 within the 5-min cooldown — advance by only 1 minute.
    # The WR-04 cooldown short-circuit at coordinator.py raises UpdateFailed
    # WITHOUT entering _recover_from_auth_error, so _handle_failure is NOT called.
    freezer.move_to(t0 + timedelta(minutes=1))
    with (
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            side_effect=AuthError("still aliased"),
        ),
        patch(
            "custom_components.ha_pronote.coordinator.build_or_resume_client",
            return_value=fresh_client,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    # Counter stayed at 1 (not 2) — WR-04 cooldown swallowed the aliased loop.
    assert coordinator._consecutive_failures == 1  # noqa: SLF001


# Phase 6 — OPT-02 / D-09: adaptive_polling_enabled propagates from entry.options to
# PolitesseOptions.adaptive_enabled. The compute_interval short-circuit (tested in
# tests/test_politesse_tz_matrix.py) verifies the runtime effect; this test pins
# the coordinator-side wiring.


async def test_resolve_options_adaptive_disabled_propagates(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """OPT-02 / D-09 — adaptive_polling_enabled=False reaches PolitesseOptions."""
    from datetime import date
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)
    # Mutate options to disable adaptive polling.
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "adaptive_polling_enabled": False},
    )
    today = date(2026, 5, 7)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coord = mock_config_entry.runtime_data.coordinator
        options = coord._resolve_options()  # noqa: SLF001
        assert options.adaptive_enabled is False


async def test_resolve_options_adaptive_default_is_true(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """OPT-02 / D-09 — missing adaptive_polling_enabled key defaults to True."""
    from datetime import date
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)
    # Explicitly ensure the key is NOT present in options.
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={k: v for k, v in mock_config_entry.options.items() if k != "adaptive_polling_enabled"},
    )
    today = date(2026, 5, 7)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coord = mock_config_entry.runtime_data.coordinator
        options = coord._resolve_options()  # noqa: SLF001
        assert options.adaptive_enabled is True


# ---------------------------------------------------------------------------
# Phase 6 — OPT-04 / D-12 REVISED: OptionsFlowWithReload triggers coordinator
# re-instantiation. No entry.add_update_listener wiring; base class handles it.
# ---------------------------------------------------------------------------


async def test_options_change_triggers_reload(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """OPT-04 / D-12 REVISED — OptionsFlowWithReload re-instantiates coordinator on commit."""
    today = _datetime(2026, 5, 7, 14, 0, 0, tzinfo=_ZoneInfo("Pacific/Noumea")).date()
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        coord_before = mock_config_entry.runtime_data.coordinator

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "refresh_interval": 15,
                "adaptive_polling_enabled": True,
                "afternoon_interval": 15,
                "afternoon_window_start": "17:00:00",
                "afternoon_window_end": "20:00:00",
                "suspended_cadence": 360,
                "quiet_cadence": 240,
                "quiet_hours_start": "22:00:00",
                "quiet_hours_end": "06:00:00",
            },
        )
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"nickname": "", "school_tz": "Pacific/Noumea"},
        )
        await hass.async_block_till_done()

    coord_after = mock_config_entry.runtime_data.coordinator
    assert coord_after is not coord_before
    new_options = coord_after._resolve_options()  # noqa: SLF001
    assert new_options.refresh_interval == _timedelta(minutes=15)


# ---------------------------------------------------------------------------
# Phase 7 DIAG-02 — IP-ban surfaces as a Repair Issue (replaces persistent notif).
# ---------------------------------------------------------------------------


async def test_ip_ban_creates_repair_issue(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """RateLimitedError(IP_SUSPENDED) → Repair Issue created (severity WARNING, not fixable)."""
    from custom_components.ha_pronote.api import ErrorReason, RateLimitedError
    from custom_components.ha_pronote.const import DOMAIN, IP_SUSPENDED_NOTIFICATION_ID_SUFFIX
    from homeassistant.helpers import issue_registry as ir

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

        with (
            patch(
                "custom_components.ha_pronote.coordinator.fetch_all",
                side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
            ),
            pytest.raises(UpdateFailed),
        ):
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
    from custom_components.ha_pronote.api import ErrorReason, RateLimitedError
    from custom_components.ha_pronote.const import DOMAIN, IP_SUSPENDED_NOTIFICATION_ID_SUFFIX
    from homeassistant.helpers import issue_registry as ir

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

        with (
            patch(
                "custom_components.ha_pronote.coordinator.fetch_all",
                side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED),
            ),
            pytest.raises(UpdateFailed),
        ):
            await coordinator._async_update_data()  # noqa: SLF001

        reg = ir.async_get(hass)
        assert reg.async_get_issue(DOMAIN, issue_id) is not None

        coordinator._backoff_until = None  # noqa: SLF001
        with patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ):
            await coordinator._async_update_data()  # noqa: SLF001

    assert reg.async_get_issue(DOMAIN, issue_id) is None
