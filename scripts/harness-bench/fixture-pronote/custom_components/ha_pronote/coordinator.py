"""HA cloud-polling coordinator. Wraps api/fetcher.fetch_all in executor (D-19, COORD-01).

D-19: TimestampDataUpdateCoordinator subclass — gives last_update_success_time
      for free (Phase 4's diff layer reads it).
D-20: coordinator.data: Snapshot directly (no extra wrapper).
D-22: AuthError -> ConfigEntryAuthFailed; RateLimitedError(IP_SUSPENDED) -> UpdateFailed;
      CommunicationError / other -> UpdateFailed.
D-23: school_tz from PronoteData; today via dt_util.now(school_tz).date().
D-24: update_interval = const.DEFAULT_REFRESH_INTERVAL (30 min hardcoded; Phase 5 adapts).
D-06: client.export_credentials() captured AFTER every successful poll, written
      to entry.data['session'] via async_update_entry.
D-09: mid-poll AuthError -> single fresh re-login + retry; second failure ->
      ConfigEntryAuthFailed (HA fires reauth — Phase 6).
C-03: previous Snapshot stashed on self._previous_snapshot (Phase 4 reads).

Phase 5 additions:
D-04: update_interval mutated at end of _async_update_data via compute_interval(now, options).
D-09: _fire_diff_events gated by should_fire_event(now, options) (atomic — top-of-method).
D-10: _async_update_data short-circuits on backoff_until (skip fetch, return self.data) and
      on not should_poll (skip fetch, return self.data) — but only when self.data is not None.
D-12: in-memory circuit breaker — _consecutive_failures, _backoff_until on the instance.
D-13: _handle_failure(err) ticks the counter on RateLimitedError(IP_SUSPENDED) and on
      AuthError surviving _recover_from_auth_error.
D-14: _reset_breaker_on_success() called on every successful poll; deletes both Repair Issues.
DIAG-02: ir.async_create_issue deduped by issue_id = f"{entry_id}_{kind}" (HA localizes via issues.* keys).

Banned (CLAUDE.md "What NOT to Use" + Phase 1 D-30..D-35):
- No legacy timeout helper (use ``asyncio.timeout`` if needed — not needed here).
- No pytz (zoneinfo.ZoneInfo only).
- No direct requests (pronotepy via executor only).
- No storing pronotepy.Client in coordinator.data (Anti-Pattern 7) — the live
  client lives on entry.runtime_data.client (D-21) AND on self._client (mutable
  for D-09 silent recovery).
"""

from __future__ import annotations

from datetime import datetime, time as datetime_time, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, cast

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir  # Phase 7 DIAG-02/03
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .api import (
    AuthError,
    CommunicationError,
    ErrorReason,  # Phase 5 D-13 — IP_SUSPENDED check
    PronoteIntegrationError,
    RateLimitedError,
    fetch_all,
    redact,
    set_active_child,
)
from .api.client import build_or_resume_client
from .const import (
    AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX,  # Phase 5 D-18
    BACKOFF_SCHEDULE,  # Phase 5 D-18
    DEFAULT_AFTERNOON_INTERVAL,  # Phase 5 D-18
    DEFAULT_AFTERNOON_WINDOW,  # Phase 5 D-18
    DEFAULT_QUIET_CADENCE,  # Phase 5 D-18
    DEFAULT_QUIET_HOURS,  # Phase 5 D-18
    DEFAULT_REFRESH_INTERVAL,  # pre-existing (Phase 3 D-24)
    DEFAULT_SUSPENDED_CADENCE,  # Phase 5 D-18
    DOMAIN,  # pre-existing (Phase 1)
    EVENT_NEW_GRADE,  # pre-existing (Phase 4 D-13)
    EVENT_NEW_INFORMATION,  # pre-existing (Phase 4 D-13)
    EVENT_SCHEDULE_CHANGED,  # pre-existing (Phase 4 D-13)
    IP_SUSPENDED_NOTIFICATION_ID_SUFFIX,  # Phase 5 D-18
    JITTER_SECONDS,  # Phase 5 D-18
    NC_VACATION_RANGES_2026,  # Phase 5 D-18
    TROUBLESHOOTING_DOC_URL_BASE,  # Phase 5 — BLOCKER-3 fix (single-source base URL)
)
from .diff import diff_grades, diff_lessons, diff_notifications  # Phase 4 D-14
from .holiday_dates import compute_holiday_dates_for_year  # Phase 5 WR-2 — neutral HA-free helper
from .politesse import PolitesseOptions, compute_interval, next_backoff, should_fire_event, should_poll  # Phase 5 D-16

# WR-04: cooldown applied between consecutive silent-recovery attempts to
# avoid hammering an IP that is already being suspended by Pronote (Pitfall 2:
# AuthError + RateLimitedError can alias when a soft-rate-limit comes back as
# a junk auth response that pronotepy decodes as a CryptoError). 5 minutes
# matches Phase 5's reserved short-backoff target without needing the
# circuit-breaker to be wired.
_SILENT_RECOVERY_COOLDOWN = timedelta(minutes=5)

if TYPE_CHECKING:
    from datetime import date
    from zoneinfo import ZoneInfo

    import pronotepy

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api.models import Snapshot


_LOGGER = logging.getLogger(__name__)


class PronoteDataUpdateCoordinator(TimestampDataUpdateCoordinator["Snapshot"]):
    """One coordinator per ConfigEntry. Polls Pronote on a 30-min cadence (D-19, D-24)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: pronotepy.Client | pronotepy.ParentClient,
        child_identifier: str,
        child_index: int | None,
        school_tz: ZoneInfo,
    ) -> None:
        """Initialize with a live pronotepy client (built by __init__.py:async_setup_entry)."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{child_identifier}",
            update_interval=DEFAULT_REFRESH_INTERVAL,
            config_entry=entry,
        )
        self._client = client  # live, between polls (D-21)
        self._child_identifier = child_identifier  # frozen at flow time (D-11)
        self._child_index = child_index  # for ParentClient.set_child (D-08)
        self._school_tz = school_tz  # D-23
        self._previous_snapshot: Snapshot | None = None  # C-03 — Phase 4 reads
        self._last_recovery_at: datetime | None = None  # WR-04 cooldown gate
        # Phase 5 — D-12 circuit breaker state (in-memory; resets on HA restart).
        self._consecutive_failures: int = 0
        self._backoff_until: datetime | None = None  # tz-aware in school_tz when set

    async def _async_update_data(self) -> Snapshot:
        """Fetch a Snapshot via executor; capture session token on success (D-19)."""
        # Phase 5 — year-rollover refresh for holiday_dates (cheap; ~ms; executor-wrapped).
        # WR-2: imports `compute_holiday_dates_for_year` from the neutral `.holiday_dates`
        # helper module (Plan 05-02) at module top — NOT a function-local import from `.`
        # (which coupled coordinator.py to __init__.py internals and risked circular imports).
        runtime = getattr(self.config_entry, "runtime_data", None) if self.config_entry else None
        now_full = dt_util.now(self._school_tz)
        if runtime is not None and getattr(runtime, "holiday_dates_year", None) != now_full.year:
            runtime.holiday_dates = await self.hass.async_add_executor_job(
                compute_holiday_dates_for_year, now_full.year
            )
            runtime.holiday_dates_year = now_full.year

        # Phase 5 — D-10 backoff short-circuit (gated on self.data is not None so first poll fetches).
        options = self._resolve_options()
        if self._backoff_until is not None and now_full < self._backoff_until and self.data is not None:
            # One-shot: ask HA to wake us when backoff expires (plus jitter via compute_interval).
            self.update_interval = compute_interval(now_full, options)
            _LOGGER.debug(
                "Phase 5 backoff active until %s (strike %d) — skipping poll",
                self._backoff_until.isoformat(),
                self._consecutive_failures,
            )
            return self.data  # keep sensors populated

        # Phase 5 — D-10 should_poll short-circuit (weekend/vacation/férié + not in primer).
        if not should_poll(now_full, options) and self.data is not None:
            self.update_interval = compute_interval(now_full, options)
            _LOGGER.debug("Phase 5 should_poll=False — skipping poll, sensors keep cached values")
            return self.data

        today = now_full.date()  # D-23 — coordinator owns dt_util (now_full computed above)
        try:
            snapshot = await self.hass.async_add_executor_job(
                partial(
                    fetch_all,
                    self._client,
                    today,
                    self._school_tz,
                    self._child_index,
                )
            )
        except AuthError as err:
            # D-09 — silent recovery: ONE cooldown-gated fresh re-login + retry.
            snapshot = await self._silent_recovery_or_raise(err, today)
        except RateLimitedError as err:
            # Phase 5 — D-13: breaker tick on IP_SUSPENDED only; other rate-limit reasons stay transient.
            if err.reason == ErrorReason.IP_SUSPENDED:
                self._handle_failure(err, kind=IP_SUSPENDED_NOTIFICATION_ID_SUFFIX)
            # D-22 — IP_SUSPENDED -> UpdateFailed; Phase 5 ALSO reads .reason for backoff above.
            raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err  # WR-05
        except (CommunicationError, PronoteIntegrationError) as err:
            if err.reason == ErrorReason.SESSION_EXPIRED:
                # "La page a expiré" — expired Pronote session. Same remedy as an
                # AuthError: rebuild the client via a fresh login. Without this,
                # every poll fails until a manual reload and all schedule-change
                # events (notifications) stop silently.
                snapshot = await self._silent_recovery_or_raise(err, today)
            else:
                raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err  # WR-05

        # CR-03: state updates BEFORE side-effects that may fail. The previous
        # ordering (capture-session first, _previous_snapshot last) discarded a
        # successful fetch when export_credentials() raised, flipping every
        # entity to unavailable AND leaving _previous_snapshot stuck on the
        # prior poll — Phase 4's diff layer would later compare an out-of-date
        # baseline and emit phantom "changed lessons" notifications.
        # D-12: capture previous BEFORE overwriting — _fire_diff_events reads it.
        previous = self._previous_snapshot  # Phase 4 — read BEFORE overwrite (D-12)
        self._previous_snapshot = snapshot  # C-03

        # CR-03 / CR-05: token capture is best-effort. A token-write hiccup
        # must NEVER invalidate a successful poll. _capture_session has its own
        # try/except (CR-05); this outer guard is a belt-and-braces hedge.
        try:
            await self._capture_session()  # D-06
        except Exception:  # noqa: BLE001 — defensive: any failure is non-fatal.
            _LOGGER.warning("Failed to persist session token; will retry next poll", exc_info=True)

        # Phase 4: fire typed bus events for each diff since previous snapshot.
        # D-12: NO try/except — diff bugs surface raw in HA logs (no silent exceptions).
        # D-15: all diff functions return [] when previous is None (EVENT-04 invariant).
        # hass.bus.async_fire is @callback — call from event loop only, NEVER from executor.
        self._fire_diff_events(previous, snapshot)

        # Phase 5 — D-14 reset breaker on success + D-04 mutate update_interval (Pattern 4)
        self._reset_breaker_on_success()
        self.update_interval = compute_interval(now_full, options)
        return snapshot

    async def _silent_recovery_or_raise(self, err: PronoteIntegrationError, today: date) -> Snapshot:
        """WR-04 cooldown-gated single fresh-login recovery.

        Shared by the AuthError path (D-09) and the SESSION_EXPIRED path — both
        mean the live client is dead and one fresh login may revive it. Within
        the 5-minute cooldown a repeat failure short-circuits to UpdateFailed
        (anti aliased-loop, WR-04). On success the cooldown clears (WR-09) so a
        later genuine auth failure is free to escalate. ``_recover_from_auth_error``
        owns the terminal mapping: a real retry AuthError -> ConfigEntryAuthFailed
        (reauth); RateLimited / Communication -> UpdateFailed (retry next poll).
        """
        now = dt_util.utcnow()
        if self._last_recovery_at is not None and now - self._last_recovery_at < _SILENT_RECOVERY_COOLDOWN:
            raise UpdateFailed(
                f"[{err.reason}] auth recovery rate-limited; skipping this poll: {redact(err.message)}"
            ) from err
        self._last_recovery_at = now
        snapshot = await self._recover_from_auth_error(err, today)
        self._last_recovery_at = None
        return snapshot

    async def _recover_from_auth_error(
        self,
        original_err: PronoteIntegrationError,
        today: date,
    ) -> Snapshot:
        """D-09: single fresh re-login + retry; on second failure raise ConfigEntryAuthFailed."""
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
                    None,  # force fresh login (skip token_login fast path)
                    f"home-assistant-{entry.entry_id[:8]}",  # AUTH-07 (D-18, C-04)
                )
            )
            # ParentClient: re-apply the chosen child before fetch.
            # CR-04: set_active_child wraps client.set_child with typed-error
            # mapping so a CryptoError on this call surfaces as AuthError (caught
            # by the existing except arm below) instead of leaking pronotepy.
            if self._child_index is not None and hasattr(new_client, "set_child"):
                await self.hass.async_add_executor_job(
                    partial(set_active_child, cast("pronotepy.ParentClient", new_client), self._child_index)
                )
            self._client = new_client
            snapshot = await self.hass.async_add_executor_job(
                partial(
                    fetch_all,
                    self._client,
                    today,
                    self._school_tz,
                    self._child_index,
                )
            )
        # CR-02: D-22 mandates AuthError -> ConfigEntryAuthFailed (HA reauth) but
        # RateLimitedError / CommunicationError -> UpdateFailed (HA retries on
        # the next poll). The previous catch-all on PronoteIntegrationError
        # mis-classified IP_SUSPENDED and transient network blips as auth
        # failures, triggering spurious reauth flows and discarding the
        # circuit-breaker signal Phase 5 needs.
        except AuthError as err:
            # Real auth failure on the retry — credentials genuinely invalid.
            # Phase 5 — D-13: breaker tick on AuthError surviving silent recovery only.
            # The WR-04 cooldown gate above already absorbs the aliased-CryptoError case,
            # so reaching this arm means a genuine auth failure that survives recovery.
            self._handle_failure(err, kind=AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX)
            raise ConfigEntryAuthFailed(f"[{err.reason}] {redact(err.message)}") from err
        except RateLimitedError as err:
            # IP suspended during recovery — Phase 5's circuit-breaker reads .reason.
            raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err
        except (CommunicationError, PronoteIntegrationError) as err:
            # Transient — HA retries on next poll.
            raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err

        return snapshot

    async def _capture_session(self) -> None:
        """D-06: persist export_credentials() to entry.data; non-fatal on failure (CR-05)."""
        entry = self.config_entry
        if entry is None:
            return
        # CR-05: pronotepy 2.14.6 Client.export_credentials is a thin getter
        # today, but it iterates internal state — a half-initialized client
        # (e.g. mid-recovery race) could surface an unhandled KeyError. We
        # treat token capture as best-effort: log and continue so a transient
        # failure never breaks the poll's success.
        try:
            new_session = await self.hass.async_add_executor_job(self._client.export_credentials)
        except Exception:  # noqa: BLE001 — token capture must never break a successful poll.
            _LOGGER.warning("export_credentials() failed; keeping prior session token", exc_info=True)
            return
        if new_session != entry.data.get("session"):
            self.hass.config_entries.async_update_entry(entry, data={**entry.data, "session": new_session})

    def _fire_diff_events(
        self,
        previous: Snapshot | None,
        new: Snapshot,
    ) -> None:
        """Fire typed bus events for each diff since previous snapshot.

        Phase 5 (D-09 + PATTERNS.md Specifics memo): atomic gate — every event in a poll
        fires or none, never half-suppressed. _previous_snapshot is updated BEFORE this
        method runs (CR-03 ordering), so an early return here does NOT corrupt the diff
        baseline for the next real poll.

        D-12: NO typed try/except — diff bugs surface raw in HA logs (no silent exceptions).
        D-15: all diff functions return [] when previous is None (EVENT-04 invariant).
        D-11: every payload is prepended with child_id, child_name, config_entry_id.

        hass.bus.async_fire is @callback — must be called from the event loop. This method
        is called from _async_update_data which runs on the event loop. Never wrap in
        async_add_executor_job.
        """
        now = dt_util.now(self._school_tz)
        options = self._resolve_options()
        if not should_fire_event(now, options):
            _LOGGER.debug(
                "Phase 5 quiet-hours gate ACTIVE — suppressing all events for %s (entry %s)",
                self._child_identifier,
                self.config_entry.entry_id if self.config_entry else "?",
            )
            return

        assert self.config_entry is not None
        child_context = {
            "child_id": self._child_identifier,  # D-11 — frozen slug
            "child_name": self.config_entry.data["child_name"],  # D-11 — display name
            "config_entry_id": self.config_entry.entry_id,  # D-11 — multi-child filter key
        }
        for change in diff_lessons(previous, new, "today"):
            self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()})
        for change in diff_lessons(previous, new, "tomorrow"):
            self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()})
        for grade in diff_grades(previous, new):
            self.hass.bus.async_fire(EVENT_NEW_GRADE, {**child_context, **grade.to_payload()})
        for info in diff_notifications(previous, new):
            self.hass.bus.async_fire(EVENT_NEW_INFORMATION, {**child_context, **info.to_payload()})

    def _resolve_options(self) -> PolitesseOptions:
        """D-17 — adapter from entry.options dict to typed PolitesseOptions.

        Phase 6's OptionsFlow declares voluptuous schemas matching these key names;
        Phase 5 only reads. On malformed input, log warning + fall back to default
        (per feedback_no_silent_exceptions.md — the warning IS the trace; the default
        is the fallback; we NEVER swallow the malformed key silently).
        """
        opts = self.config_entry.options if self.config_entry else {}

        def _read_minutes(key: str, default: timedelta) -> timedelta:
            raw = opts.get(key)
            if raw is None:
                return default
            try:
                return timedelta(minutes=int(raw))
            except ValueError, TypeError:
                _LOGGER.warning(
                    "Phase 5 _resolve_options: malformed option %s=%r; falling back to %s",
                    key,
                    raw,
                    default,
                )
                return default

        def _read_time(key: str, default: datetime_time) -> datetime_time:
            raw = opts.get(key)
            if raw is None:
                return default
            try:
                return datetime_time.fromisoformat(str(raw))
            except ValueError, TypeError:
                _LOGGER.warning(
                    "Phase 5 _resolve_options: malformed option %s=%r; falling back to %s",
                    key,
                    raw,
                    default,
                )
                return default

        # holiday_dates lives on runtime_data — but the coordinator may be called
        # BEFORE runtime_data is fully populated (during async_config_entry_first_refresh
        # the dataclass exists but is constructed AFTER the first refresh). Safe fallback:
        # if runtime_data lacks holiday_dates, use frozenset() (the first-poll fetch will
        # still happen because should_poll's primer + tomorrow=school logic depends on
        # is_school_day which treats an empty holiday_dates set as "no fériés today").
        runtime = getattr(self.config_entry, "runtime_data", None) if self.config_entry else None
        holiday_dates = getattr(runtime, "holiday_dates", frozenset()) if runtime else frozenset()

        return PolitesseOptions(
            school_tz=self._school_tz,
            refresh_interval=_read_minutes("refresh_interval", DEFAULT_REFRESH_INTERVAL),
            afternoon_interval=_read_minutes("afternoon_interval", DEFAULT_AFTERNOON_INTERVAL),
            afternoon_window=(
                _read_time("afternoon_window_start", DEFAULT_AFTERNOON_WINDOW[0]),
                _read_time("afternoon_window_end", DEFAULT_AFTERNOON_WINDOW[1]),
            ),
            quiet_hours=(
                _read_time("quiet_hours_start", DEFAULT_QUIET_HOURS[0]),
                _read_time("quiet_hours_end", DEFAULT_QUIET_HOURS[1]),
            ),
            suspended_cadence=_read_minutes("suspended_cadence", DEFAULT_SUSPENDED_CADENCE),
            quiet_cadence=_read_minutes("quiet_cadence", DEFAULT_QUIET_CADENCE),
            vacation_ranges=NC_VACATION_RANGES_2026,
            holiday_dates=holiday_dates,
            jitter_seconds=JITTER_SECONDS,
            # Phase 6 D-09 / OPT-02 — read adaptive_polling_enabled from entry.options.
            # bool(...) coerces None / missing / 0 / "" → False and any truthy → True.
            # No _read_* helper needed: there's no parse-error path for a bool .get().
            adaptive_enabled=bool(opts.get("adaptive_polling_enabled", True)),
        )

    def _handle_failure(self, err: PronoteIntegrationError, *, kind: str) -> None:
        """D-13 / DIAG-02 — tick the breaker + raise a HA Repair Issue.

        Called from the typed-error except arms in _async_update_data and
        _recover_from_auth_error. The exception STILL propagates via the caller's
        raise — this method is ADDITIVE (per feedback_no_silent_exceptions.md).

        Args:
            err: The typed PronoteIntegrationError that triggered the strike.
            kind: One of IP_SUSPENDED_NOTIFICATION_ID_SUFFIX | AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX —
                  determines the issue_id suffix and the i18n translation_key.
        """
        self._consecutive_failures += 1
        now = dt_util.now(self._school_tz)
        backoff = next_backoff(self._consecutive_failures - 1, schedule=BACKOFF_SCHEDULE)
        self._backoff_until = now + backoff

        if self.config_entry is None:
            return  # cannot create an issue without an entry id

        issue_id = f"{self.config_entry.entry_id}_{kind}"
        language = (self.hass.config.language or "en").split("-")[0]
        retry_str = self._backoff_until.strftime("%H:%M le %d/%m" if language == "fr" else "%H:%M on %d/%m")
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

    def _reset_breaker_on_success(self) -> None:
        """D-14 — clear counters + delete both Repair Issues. Idempotent.

        HA's issue_registry.async_delete_issue silently no-ops when the issue
        doesn't exist, so calling it on every successful poll is safe.
        """
        self._consecutive_failures = 0
        self._backoff_until = None
        if self.config_entry is None:
            return
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
