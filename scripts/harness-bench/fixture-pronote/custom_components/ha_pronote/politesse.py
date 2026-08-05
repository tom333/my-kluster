"""Public — adaptive polling cadence + circuit-breaker predicates (D-03..D-11).

HA-free per D-16 / D-19 / D-20. This module exports the pure-Python predicates
and the ``compute_interval`` algorithm that the coordinator (Plan 05-03) calls
to decide the next ``DataUpdateCoordinator`` refresh delay. No module state, no
``homeassistant.*`` imports, no I/O — every function takes ``now`` and a frozen
``PolitesseOptions`` as arguments.

Algorithm derivation lives in ``.planning/phases/05.../05-CONTEXT.md``:

- D-03: ``is_school_day`` — weekday<5 AND not vacation AND not férié.
- D-04: ``compute_interval`` — branches top-down (quiet > suspended > afternoon
  > base), then adds ±jitter and clamps to ``timedelta(minutes=1)``.
- D-05: ``should_poll`` — False on weekend/vacation/férié UNLESS now is in the
  primer window (D-06).
- D-06: Primer-window unification — today is non-school AND tomorrow is school
  AND now is in the afternoon window. One condition captures Sun-evening,
  last-day-of-vacation-evening, and weekday afternoons (after `should_poll`
  short-circuits to ``True`` for today-is-school).
- D-07: ``is_afternoon_window`` — half-open ``[window_start, window_end)`` in
  ``school_tz``-local time.
- D-08: ``is_quiet_hours`` — cross-midnight when ``quiet_start > quiet_end``;
  otherwise degenerate ``[quiet_start, quiet_end)``.
- D-09: ``should_fire_event`` — ``not is_quiet_hours(now, ...)``.
- D-11: ``next_backoff`` — fixed schedule ``(1h, 2h, 4h, 12h, 24h)`` clamped at
  the last index.
- D-16: Module owns no state. Imports stdlib only.
- D-17: Per-entry options resolved by the coordinator into ``PolitesseOptions``.
- D-19: Jitter via injectable ``rng: random.Random | random = random``.

Re-raise discipline (per feedback_no_silent_exceptions.md): no ``try/except``.
Naive ``datetime`` input raises ``ValueError`` so the caller's stack trace
points at the original bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import random
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from types import ModuleType
    from zoneinfo import ZoneInfo


# D-11 — fixed backoff schedule. Mirrors the value the coordinator imports from
# ``const.BACKOFF_SCHEDULE`` (Plan 05-03 ships that constant); politesse.py
# carries the same tuple so ``next_backoff(0)`` works without a const import.
_DEFAULT_BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
    timedelta(hours=1),
    timedelta(hours=2),
    timedelta(hours=4),
    timedelta(hours=12),
    timedelta(hours=24),
)


@dataclass(frozen=True)
class PolitesseOptions:
    """Resolved per-entry options snapshot consumed by every politesse function.

    Phase 5 ships only the read path; Phase 6's OptionsFlow declares the
    voluptuous schema that maps ``entry.options`` keys to these fields (D-17).
    """

    school_tz: ZoneInfo
    refresh_interval: timedelta  # default 30 min
    afternoon_interval: timedelta  # default 15 min
    afternoon_window: tuple[time, time]  # default (time(17,0), time(20,0)) — half-open [start, end)
    quiet_hours: tuple[time, time]  # default (time(22,0), time(6,0)) — cross-midnight allowed
    suspended_cadence: timedelta  # default 6h
    quiet_cadence: timedelta  # default 4h
    vacation_ranges: tuple[tuple[date, date], ...]  # default const.NC_VACATION_RANGES_2026
    holiday_dates: frozenset[date]  # injected per-entry by coordinator
    jitter_seconds: int  # default 30
    # Phase 6 D-09 / OPT-02 — adaptive polling toggle. When False, compute_interval
    # short-circuits to refresh_interval ± jitter without entering quiet/suspended/
    # afternoon branches. Default True preserves Phase 5 behavior exactly.
    adaptive_enabled: bool = True


def is_school_day(
    d: date,
    *,
    vacation_ranges: tuple[tuple[date, date], ...],
    holiday_dates: frozenset[date],
) -> bool:
    """D-03 — True iff ``d`` is a NC school day.

    Args:
        d: Calendar date to evaluate (no timezone — comparisons are in
            school-local terms; the caller derives ``d`` from
            ``now.astimezone(school_tz).date()``).
        vacation_ranges: Tuple of ``(start, end)`` inclusive ranges for the
            current academic year.
        holiday_dates: Frozenset of NC public-holiday dates (pré-computed by
            the coordinator from ``holidays.France(subdiv='NC')``).

    Returns:
        ``True`` iff ``d.weekday() < 5`` AND ``d`` is not inside any vacation
        range AND ``d`` is not in ``holiday_dates``.
    """
    if d.weekday() >= 5:
        return False
    for start, end in vacation_ranges:
        if start <= d <= end:
            return False
    return d not in holiday_dates


def is_quiet_hours(
    now: datetime,
    *,
    school_tz: ZoneInfo,
    quiet_start: time,
    quiet_end: time,
) -> bool:
    """D-08 — True iff ``now``'s local time-of-day is inside the quiet window.

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive.
        school_tz: ``ZoneInfo`` used to localize ``now``.
        quiet_start: Start of the quiet window (e.g. ``time(22, 0)``).
        quiet_end: End of the quiet window (e.g. ``time(6, 0)``).

    Returns:
        Cross-midnight (``quiet_start > quiet_end``): ``True`` iff
        ``local_time >= quiet_start`` OR ``local_time < quiet_end``.
        Degenerate (``quiet_start <= quiet_end``): ``True`` iff
        ``quiet_start <= local_time < quiet_end`` (half-open).
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")
    local_time = now.astimezone(school_tz).time()
    if quiet_start > quiet_end:
        return local_time >= quiet_start or local_time < quiet_end
    return quiet_start <= local_time < quiet_end


def is_afternoon_window(
    now: datetime,
    *,
    school_tz: ZoneInfo,
    window_start: time,
    window_end: time,
) -> bool:
    """D-07 — True iff ``now``'s local time-of-day is in ``[window_start, window_end)``.

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive.
        school_tz: ``ZoneInfo`` used to localize ``now``.
        window_start: Inclusive start (e.g. ``time(17, 0)``).
        window_end: Exclusive end (e.g. ``time(20, 0)``).

    Returns:
        ``True`` iff ``window_start <= local_time < window_end``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")
    local_time = now.astimezone(school_tz).time()
    return window_start <= local_time < window_end


def is_primer_window(now: datetime, options: PolitesseOptions) -> bool:
    """D-06 — True iff today is a non-school day AND tomorrow is a school day AND now is in the afternoon window.

    Unifies the Sunday-evening primer, the last-day-of-vacation-evening primer,
    and any other "tomorrow is school but today isn't" case. Weekday afternoons
    are handled by the ``should_poll`` short-circuit (today is already a school
    day, so the primer branch is not needed).

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive.
        options: Resolved ``PolitesseOptions`` snapshot.

    Returns:
        ``True`` iff
        ``not is_school_day(today)`` AND ``is_school_day(tomorrow)``
        AND ``is_afternoon_window(now, ...)``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")
    local_now = now.astimezone(options.school_tz)
    today = local_now.date()
    tomorrow = today + timedelta(days=1)
    if is_school_day(
        today,
        vacation_ranges=options.vacation_ranges,
        holiday_dates=options.holiday_dates,
    ):
        return False
    if not is_school_day(
        tomorrow,
        vacation_ranges=options.vacation_ranges,
        holiday_dates=options.holiday_dates,
    ):
        return False
    return is_afternoon_window(
        now,
        school_tz=options.school_tz,
        window_start=options.afternoon_window[0],
        window_end=options.afternoon_window[1],
    )


def should_poll(now: datetime, options: PolitesseOptions) -> bool:
    """D-05 — True iff a poll is permitted at ``now``.

    Returns ``False`` on weekends, vacation days, and fériés — UNLESS ``now``
    is in the primer window (D-06: today is non-school AND tomorrow is school
    AND now is in the afternoon window). The primer exception lets the
    coordinator pre-fetch tomorrow's schedule on Sunday evenings and on the
    last evening of a vacation.

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive.
        options: Resolved ``PolitesseOptions`` snapshot.

    Returns:
        ``True`` iff today is a school day OR ``is_primer_window(now)`` is
        ``True``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")
    today = now.astimezone(options.school_tz).date()
    if is_school_day(
        today,
        vacation_ranges=options.vacation_ranges,
        holiday_dates=options.holiday_dates,
    ):
        return True
    return is_primer_window(now, options)


def should_fire_event(now: datetime, options: PolitesseOptions) -> bool:
    """D-09 — True iff diff events should fire (i.e. ``not is_quiet_hours``).

    The coordinator still runs the poll during quiet hours (so that the silent
    drift of the snapshot continues to track the upstream Pronote state), but
    the ``async_dispatcher_send`` step that emits ``pronote_schedule_changed``
    / ``pronote_new_grade`` / ``pronote_new_information`` is suppressed.

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive
            (via ``is_quiet_hours``).
        options: Resolved ``PolitesseOptions`` snapshot.

    Returns:
        ``not is_quiet_hours(now, school_tz=..., quiet_start=...,
        quiet_end=...)``.
    """
    return not is_quiet_hours(
        now,
        school_tz=options.school_tz,
        quiet_start=options.quiet_hours[0],
        quiet_end=options.quiet_hours[1],
    )


def next_backoff(
    strike_index: int,
    schedule: tuple[timedelta, ...] = _DEFAULT_BACKOFF_SCHEDULE,
) -> timedelta:
    """D-11 — Return the backoff delay for a 0-based strike index, clamped at the schedule's last entry.

    Args:
        strike_index: 0-based consecutive-failure counter. Index 0 returns the
            first cooldown (``1h`` by default); any index beyond the last entry
            returns the last entry (``24h`` by default).
        schedule: Fixed cooldown tuple. Defaults to
            ``(1h, 2h, 4h, 12h, 24h)``. Plan 05-03 passes ``BACKOFF_SCHEDULE``
            from ``const.py`` explicitly.

    Returns:
        ``schedule[min(strike_index, len(schedule) - 1)]``.

    Raises:
        ValueError: If ``strike_index`` is negative.
    """
    if strike_index < 0:
        raise ValueError("strike_index must be >= 0")
    return schedule[min(strike_index, len(schedule) - 1)]


def compute_interval(
    now: datetime,
    options: PolitesseOptions,
    *,
    rng: random.Random | ModuleType = random,
) -> timedelta:
    """D-04 — Return the next polling interval given ``now`` + resolved options.

    Branches top-down (first match wins):

    1. ``is_quiet_hours(now, ...)`` → ``options.quiet_cadence`` (default 4h).
    2. ``not should_poll(now, options)`` → ``options.suspended_cadence`` (6h).
    3. ``is_afternoon_window(now, ...)`` AND tomorrow is a school day →
       ``options.afternoon_interval`` (default 15 min).
    4. Otherwise → ``options.refresh_interval`` (default 30 min).

    Adds ``rng.uniform(-jitter_seconds, +jitter_seconds)`` seconds of jitter
    (D-19; injectable RNG for reproducible tests) and clamps the result to
    ``timedelta(minutes=1)`` so a negative-jitter sub-minute interval cannot
    cause an immediate re-poll.

    Args:
        now: Timezone-aware ``datetime``. Raises ``ValueError`` if naive.
        options: Resolved ``PolitesseOptions`` snapshot.
        rng: Either ``random`` (the stdlib module) or a ``random.Random``
            instance. Production omits this; tests pass
            ``rng=random.Random(seed=42)`` for reproducibility.

    Returns:
        ``timedelta`` clamped to ``>= 1 minute``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")

    # Phase 6 D-09 / OPT-02 — short-circuit when the user disabled adaptive polling.
    # Bypass the quiet / suspended / afternoon branches; always return
    # refresh_interval + jitter, clamped to >= 1 min (matches the tail clamp).
    if not options.adaptive_enabled:
        jittered = options.refresh_interval + timedelta(
            seconds=rng.uniform(-options.jitter_seconds, options.jitter_seconds)
        )
        return max(jittered, timedelta(minutes=1))

    # Branch 1 — quiet hours win over everything else (Sat 23h is quiet, not
    # suspended; D-04 ordering verified in TestComputeInterval/quiet-overlaps-weekend).
    if is_quiet_hours(
        now,
        school_tz=options.school_tz,
        quiet_start=options.quiet_hours[0],
        quiet_end=options.quiet_hours[1],
    ):
        base = options.quiet_cadence
    # Branch 2 — non-school day outside the primer window → suspended cadence.
    elif not should_poll(now, options):
        base = options.suspended_cadence
    # Branch 3 — afternoon window AND tomorrow is a school day → tightened cadence.
    # (Covers both weekday afternoons with tomorrow=school AND the primer
    # window when should_poll already returned True via the primer exception.)
    elif is_afternoon_window(
        now,
        school_tz=options.school_tz,
        window_start=options.afternoon_window[0],
        window_end=options.afternoon_window[1],
    ) and is_school_day(
        now.astimezone(options.school_tz).date() + timedelta(days=1),
        vacation_ranges=options.vacation_ranges,
        holiday_dates=options.holiday_dates,
    ):
        base = options.afternoon_interval
    # Branch 4 — base interval.
    else:
        base = options.refresh_interval

    jitter = rng.uniform(-options.jitter_seconds, options.jitter_seconds)
    result = base + timedelta(seconds=jitter)
    return max(result, timedelta(minutes=1))
