"""Pure politesse tests — no ``hass`` fixture, no ``freezer``.

TZ matrix on ``Europe/Paris`` and ``Pacific/Noumea`` per DIST-06 (D-20). File
name carries the ``tz_matrix`` substring so V-14's
``pytest -k 'tz_matrix'`` selector resolves all collected cases (file-name
precedent: ``tests/test_diff/test_lessons_tz_matrix.py``).

Test layout per D-20: every public function in
``custom_components.ha_pronote.politesse`` gets a ``TestXxx`` class. Every test
takes ``school_tz`` as its first parameter via the module-level pytestmark
parametrize. No fixtures — the autouse fixture in ``tests/conftest.py``
(``setup_ha_calendar_http_dependency``) is overridden below to keep this file
hermetic (no HA harness required).

Date selection (all dates verified against ``date.weekday()``):

- ``date(2026, 5, 12)`` — Tuesday (weekday=1) school day, no vacation, no férié
- ``date(2026, 5, 16)`` — Saturday (weekday=5) weekend
- ``date(2026, 5, 17)`` — Sunday (weekday=6); Mon 18 May is a school day → Sun
  evening is the primer window
- ``date(2026, 4, 10)`` — vacation day (inside ``(2026-04-04, 2026-04-19)``)
- ``date(2026, 4, 19)`` — Sunday + last vacation day; Mon 20 Apr is a school
  day → last-day-of-vacation evening primer
- ``date(2026, 7, 14)`` — Tue 14 Juillet férié when injected into
  ``holiday_dates``
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import random
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.politesse import (
    PolitesseOptions,
    compute_interval,
    is_afternoon_window,
    is_primer_window,
    is_quiet_hours,
    is_school_day,
    next_backoff,
    should_fire_event,
    should_poll,
)

pytestmark = pytest.mark.parametrize("school_tz", ["Europe/Paris", "Pacific/Noumea"])


# Conftest's ``setup_ha_calendar_http_dependency`` is autouse and requires the
# ``hass`` fixture; override it locally to keep this file hermetic (D-20 — no
# HA harness needed). The fixture below has the same name so pytest picks it
# up first.
@pytest.fixture(autouse=True)
def setup_ha_calendar_http_dependency():
    """Override the root conftest's HA-dependent autouse — politesse tests are HA-free (D-20)."""
    return


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root conftest's PHACC autouse — politesse tests are HA-free (D-20)."""
    return


# Vacation range covering the Avril 2026 NC school break; used by the
# vacation + last-day-of-vacation tests.
_AVRIL_VACATION: tuple[tuple[date, date], ...] = ((date(2026, 4, 4), date(2026, 4, 19)),)


def _build_options(
    school_tz: str,
    *,
    holiday_dates: frozenset[date] = frozenset(),
    vacation_ranges: tuple[tuple[date, date], ...] = (),
) -> PolitesseOptions:
    """Build a ``PolitesseOptions`` with the const.py-locked defaults.

    Defaults mirror what the coordinator (Plan 05-03) will inject at runtime
    once ``const.py`` carries the keys:

    - ``refresh_interval=30 min``
    - ``afternoon_interval=15 min``
    - ``afternoon_window=(17:00, 20:00)``
    - ``quiet_hours=(22:00, 06:00)`` (cross-midnight)
    - ``suspended_cadence=6h``
    - ``quiet_cadence=4h``
    - ``jitter_seconds=30``
    """
    return PolitesseOptions(
        school_tz=ZoneInfo(school_tz),
        refresh_interval=timedelta(minutes=30),
        afternoon_interval=timedelta(minutes=15),
        afternoon_window=(time(17, 0), time(20, 0)),
        quiet_hours=(time(22, 0), time(6, 0)),
        suspended_cadence=timedelta(hours=6),
        quiet_cadence=timedelta(hours=4),
        vacation_ranges=vacation_ranges,
        holiday_dates=holiday_dates,
        jitter_seconds=30,
    )


# ---------------------------------------------------------------------------
# TestIsSchoolDay (D-03)
# ---------------------------------------------------------------------------


class TestIsSchoolDay:
    """D-03 — weekday<5 AND not vacation AND not férié."""

    def test_weekday_no_vacation_no_ferie_is_school_day(self, school_tz):
        # school_tz is irrelevant for is_school_day (no datetime arg) but the
        # module-level pytestmark forces every test to accept the parameter.
        del school_tz
        assert is_school_day(date(2026, 5, 12), vacation_ranges=(), holiday_dates=frozenset()) is True

    def test_saturday_is_not_school_day(self, school_tz):
        del school_tz
        assert is_school_day(date(2026, 5, 16), vacation_ranges=(), holiday_dates=frozenset()) is False

    def test_sunday_is_not_school_day(self, school_tz):
        del school_tz
        assert is_school_day(date(2026, 5, 17), vacation_ranges=(), holiday_dates=frozenset()) is False

    def test_vacation_day_is_not_school_day(self, school_tz):
        del school_tz
        assert is_school_day(date(2026, 4, 10), vacation_ranges=_AVRIL_VACATION, holiday_dates=frozenset()) is False

    def test_ferie_day_is_not_school_day(self, school_tz):
        del school_tz
        ferie = frozenset({date(2026, 7, 14)})
        # 14 July 2026 is a Tuesday (weekday=1) so only the holiday_dates
        # injection blocks it — proves the ferie branch.
        assert is_school_day(date(2026, 7, 14), vacation_ranges=(), holiday_dates=ferie) is False


# ---------------------------------------------------------------------------
# TestIsQuietHours (D-08)
# ---------------------------------------------------------------------------


class TestIsQuietHours:
    """D-08 — cross-midnight default 22h-6h + degenerate inverted bounds."""

    def test_inside_cross_midnight_at_23h(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 23, 0, tzinfo=tz)
        assert is_quiet_hours(now, school_tz=tz, quiet_start=time(22, 0), quiet_end=time(6, 0)) is True

    def test_inside_cross_midnight_at_5h(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 13, 5, 0, tzinfo=tz)
        assert is_quiet_hours(now, school_tz=tz, quiet_start=time(22, 0), quiet_end=time(6, 0)) is True

    def test_outside_cross_midnight_at_12h(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 12, 0, tzinfo=tz)
        assert is_quiet_hours(now, school_tz=tz, quiet_start=time(22, 0), quiet_end=time(6, 0)) is False

    def test_degenerate_window_inside(self, school_tz):
        """Non-cross-midnight: quiet_start <= local_time < quiet_end."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 13, 0, tzinfo=tz)
        assert is_quiet_hours(now, school_tz=tz, quiet_start=time(12, 0), quiet_end=time(14, 0)) is True

    def test_degenerate_window_outside(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 14, 0, tzinfo=tz)
        # 14:00 is excluded by the half-open upper bound.
        assert is_quiet_hours(now, school_tz=tz, quiet_start=time(12, 0), quiet_end=time(14, 0)) is False


# ---------------------------------------------------------------------------
# TestIsAfternoonWindow (D-07)
# ---------------------------------------------------------------------------


class TestIsAfternoonWindow:
    """D-07 — half-open [window_start, window_end)."""

    def test_inside_window(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 18, 30, tzinfo=tz)
        assert is_afternoon_window(now, school_tz=tz, window_start=time(17, 0), window_end=time(20, 0)) is True

    def test_lower_bound_inclusive(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 17, 0, tzinfo=tz)
        assert is_afternoon_window(now, school_tz=tz, window_start=time(17, 0), window_end=time(20, 0)) is True

    def test_upper_bound_exclusive(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 20, 0, tzinfo=tz)
        assert is_afternoon_window(now, school_tz=tz, window_start=time(17, 0), window_end=time(20, 0)) is False

    def test_before_window(self, school_tz):
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 16, 59, tzinfo=tz)
        assert is_afternoon_window(now, school_tz=tz, window_start=time(17, 0), window_end=time(20, 0)) is False


# ---------------------------------------------------------------------------
# TestIsPrimerWindow (D-06)
# ---------------------------------------------------------------------------


class TestIsPrimerWindow:
    """D-06 — non-school-day AND tomorrow=school-day AND in afternoon window."""

    def test_sunday_19h_primer_when_monday_is_school_day(self, school_tz):
        """V-18 primer: Sun 17 May 19h → Mon 18 May school day."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 17, 19, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert is_primer_window(now, options) is True

    def test_last_vacation_day_evening_primer(self, school_tz):
        """V-19 primer: Sun 19 Apr 19h (last vacation day) → Mon 20 Apr school day."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 4, 19, 19, 0, tzinfo=tz)
        options = _build_options(school_tz, vacation_ranges=_AVRIL_VACATION)
        assert is_primer_window(now, options) is True

    def test_sunday_morning_not_in_primer_window(self, school_tz):
        """Sun morning fails the afternoon-window predicate."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 17, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert is_primer_window(now, options) is False

    def test_weekday_afternoon_not_in_primer_window(self, school_tz):
        """Today is school day → primer is irrelevant (and returns False)."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 18, 30, tzinfo=tz)
        options = _build_options(school_tz)
        assert is_primer_window(now, options) is False


# ---------------------------------------------------------------------------
# TestShouldPoll (D-05)
# ---------------------------------------------------------------------------


class TestShouldPoll:
    """D-05 — False on weekend/vacation/férié UNLESS in primer window."""

    def test_should_poll_weekend_suspended(self, school_tz):
        """V-03 — Sat 10h: weekend, no primer → False."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 16, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert should_poll(now, options) is False

    def test_should_poll_vacation_suspended(self, school_tz):
        """V-04 — mid-Avril vacation, no primer → False."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 4, 10, 14, 0, tzinfo=tz)
        options = _build_options(school_tz, vacation_ranges=_AVRIL_VACATION)
        assert should_poll(now, options) is False

    def test_should_poll_ferie_suspended(self, school_tz):
        """V-05 — Tue 14 Juillet 14h with ferie injection → False."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 7, 14, 14, 0, tzinfo=tz)
        options = _build_options(school_tz, holiday_dates=frozenset({date(2026, 7, 14)}))
        assert should_poll(now, options) is False

    def test_should_poll_true_in_primer_window(self, school_tz):
        """Primer exception: Sun 19h → True even though today is non-school."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 17, 19, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert should_poll(now, options) is True

    def test_should_poll_true_on_weekday(self, school_tz):
        """Tue 10h → True (school day, no other branch needed)."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert should_poll(now, options) is True


# ---------------------------------------------------------------------------
# TestShouldFireEvent (D-09)
# ---------------------------------------------------------------------------


class TestShouldFireEvent:
    """D-09 — returns not is_quiet_hours."""

    def test_should_fire_event_false_in_quiet_hours(self, school_tz):
        """V-06 — Tue 23h: inside default 22h-6h quiet window → False."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 23, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert should_fire_event(now, options) is False

    def test_should_fire_event_true_outside_quiet_hours(self, school_tz):
        """Tue 12h → True."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 12, 0, tzinfo=tz)
        options = _build_options(school_tz)
        assert should_fire_event(now, options) is True


# ---------------------------------------------------------------------------
# TestComputeInterval (D-04)
# ---------------------------------------------------------------------------


class TestComputeInterval:
    """D-04 — branches top-down: quiet > suspended > afternoon > base, ±jitter, ≥1 min clamp."""

    def test_compute_interval_weekday_afternoon(self, school_tz):
        """V-01 — Tue 18h30 with Wed=school → afternoon branch ≈ 15 min."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 18, 30, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        # base = 15 min = 900 s; jitter is ±30 s → |delta| ≤ 30 s.
        assert abs((interval - timedelta(minutes=15)).total_seconds()) <= 30

    def test_compute_interval_base_weekday_morning(self, school_tz):
        """V-02 — Tue 10h → base 30 min (not afternoon)."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(minutes=30)).total_seconds()) <= 30

    def test_compute_interval_quiet_hours_cadence(self, school_tz):
        """V-07 — Tue 23h → quiet branch 4h."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 23, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(hours=4)).total_seconds()) <= 30

    def test_compute_interval_sunday_evening_primer(self, school_tz):
        """V-18 — Sun 17 May 19h primer → afternoon branch ≈ 15 min."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 17, 19, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(minutes=15)).total_seconds()) <= 30

    def test_compute_interval_last_day_of_vacation_evening_primer(self, school_tz):
        """V-19 — Sun 19 Apr 19h (last vacation day) → afternoon ≈ 15 min."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 4, 19, 19, 0, tzinfo=tz)
        options = _build_options(school_tz, vacation_ranges=_AVRIL_VACATION)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(minutes=15)).total_seconds()) <= 30

    def test_compute_interval_friday_18h_with_saturday_off(self, school_tz):
        """Fri 18h: today=school + tomorrow=weekend → NOT afternoon (branch 3 fails) → base 30 min.

        CONTEXT.md specifics — afternoon tightening requires tomorrow=school.
        """
        # 2026-05-15 is a Friday (weekday=4).
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 15, 18, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(minutes=30)).total_seconds()) <= 30

    def test_compute_interval_saturday_23h_quiet_wins_over_suspended(self, school_tz):
        """Sat 23h: quiet branch (1) wins over suspended branch (2) per D-04 ordering."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 16, 23, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        # Quiet cadence is 4h; suspended cadence is 6h. Quiet wins.
        assert abs((interval - timedelta(hours=4)).total_seconds()) <= 30

    def test_compute_interval_suspended_weekend_daytime(self, school_tz):
        """Sat 10h: outside quiet, no primer → suspended branch 6h."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 16, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        interval = compute_interval(now, options, rng=rng)
        assert abs((interval - timedelta(hours=6)).total_seconds()) <= 30

    def test_jitter_within_pm_30s_bounds(self, school_tz):
        """V-12 — 100 calls against a shared rng; every result within ±30 s of the base."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng = random.Random(42)
        base = timedelta(minutes=30)
        for _ in range(100):
            interval = compute_interval(now, options, rng=rng)
            delta = (interval - base).total_seconds()
            assert abs(delta) <= 30, f"jitter delta {delta!r} exceeds ±30 s"

    def test_jitter_seeded_rng_reproducible(self, school_tz):
        """V-13 — two random.Random(seed=42) instances produce identical sequences."""
        tz = ZoneInfo(school_tz)
        now = datetime(2026, 5, 12, 10, 0, tzinfo=tz)
        options = _build_options(school_tz)
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        # Compare 10 successive draws to make sure the RNG state advances
        # identically, not just one shot.
        seq_a = [compute_interval(now, options, rng=rng_a) for _ in range(10)]
        seq_b = [compute_interval(now, options, rng=rng_b) for _ in range(10)]
        assert seq_a == seq_b


# ---------------------------------------------------------------------------
# TestNextBackoff (D-11, V-09 — drives COORD-07's breaker curve in Plan 05-03)
# ---------------------------------------------------------------------------


class TestNextBackoff:
    """D-11 — fixed schedule, clamped at the last index."""

    def test_next_backoff_schedule_clamps_at_24h(self, school_tz):
        """V-09 — index 0 → 1h; index 4 → 24h; any index ≥ 4 → 24h."""
        del school_tz
        assert next_backoff(0) == timedelta(hours=1)
        assert next_backoff(1) == timedelta(hours=2)
        assert next_backoff(2) == timedelta(hours=4)
        assert next_backoff(3) == timedelta(hours=12)
        assert next_backoff(4) == timedelta(hours=24)
        assert next_backoff(5) == timedelta(hours=24)
        assert next_backoff(99) == timedelta(hours=24)

    def test_next_backoff_negative_strike_raises(self, school_tz):
        del school_tz
        with pytest.raises(ValueError, match="strike_index must be >= 0"):
            next_backoff(-1)


# ---------------------------------------------------------------------------
# TestNaiveDatetimeRejection — every predicate that takes ``now`` must raise
# ValueError on naive input (re-raise discipline).
# ---------------------------------------------------------------------------


class TestNaiveDatetimeRejection:
    """All five ``now``-taking predicates raise ValueError on tz-naive input."""

    def test_naive_datetime_raises_value_error_compute_interval(self, school_tz):
        options = _build_options(school_tz)
        with pytest.raises(ValueError, match="now must be tz-aware"):
            compute_interval(datetime(2026, 5, 12, 10, 0), options)

    def test_naive_datetime_raises_value_error_should_poll(self, school_tz):
        options = _build_options(school_tz)
        with pytest.raises(ValueError, match="now must be tz-aware"):
            should_poll(datetime(2026, 5, 12, 10, 0), options)

    def test_naive_datetime_raises_value_error_should_fire_event(self, school_tz):
        options = _build_options(school_tz)
        with pytest.raises(ValueError, match="now must be tz-aware"):
            should_fire_event(datetime(2026, 5, 12, 10, 0), options)

    def test_naive_datetime_raises_value_error_is_quiet_hours(self, school_tz):
        tz = ZoneInfo(school_tz)
        with pytest.raises(ValueError, match="now must be tz-aware"):
            is_quiet_hours(
                datetime(2026, 5, 12, 23, 0),
                school_tz=tz,
                quiet_start=time(22, 0),
                quiet_end=time(6, 0),
            )

    def test_naive_datetime_raises_value_error_is_afternoon_window(self, school_tz):
        tz = ZoneInfo(school_tz)
        with pytest.raises(ValueError, match="now must be tz-aware"):
            is_afternoon_window(
                datetime(2026, 5, 12, 18, 30),
                school_tz=tz,
                window_start=time(17, 0),
                window_end=time(20, 0),
            )


# ---------------------------------------------------------------------------
# Phase 6 OPT-02 / D-09 — adaptive_enabled toggle tests
# ---------------------------------------------------------------------------


def test_compute_interval_respects_adaptive_disabled(school_tz: str) -> None:
    """Phase 6 OPT-02 / D-09 — adaptive_enabled=False bypasses every adaptive branch.

    At 18:00 Thursday (in school_tz) with tomorrow=school-day, adaptive_enabled=True
    would hit the afternoon-window branch (15 min). With adaptive_enabled=False we
    always return refresh_interval (30 min) ± jitter.

    school_tz parameter from module pytestmark covers both Europe/Paris and Pacific/Noumea
    (DIST-06): same tz is used for options.school_tz and for creating now, following
    the Phase 5 _build_options pattern.
    """
    tz = ZoneInfo(school_tz)
    options = PolitesseOptions(
        school_tz=tz,
        refresh_interval=timedelta(minutes=30),
        afternoon_interval=timedelta(minutes=15),
        afternoon_window=(time(17, 0), time(20, 0)),
        quiet_hours=(time(22, 0), time(6, 0)),
        suspended_cadence=timedelta(hours=6),
        quiet_cadence=timedelta(hours=4),
        vacation_ranges=(),
        holiday_dates=frozenset(),
        jitter_seconds=30,
        adaptive_enabled=False,
    )
    # 2026-05-07 is a Thursday (weekday=3); 18:00 in school_tz is inside the
    # 17h-20h afternoon-window branch (and Fri 08 May is a school day). With
    # adaptive=False we bypass that branch and return refresh_interval ± jitter.
    now = datetime(2026, 5, 7, 18, 0, tzinfo=tz)
    rng = random.Random(42)
    interval = compute_interval(now, options, rng=rng)
    # 30 min ± 30s → in [29:30, 30:30]; never 15 min (the bypassed afternoon branch).
    assert timedelta(minutes=29, seconds=30) <= interval <= timedelta(minutes=30, seconds=30)


def test_compute_interval_adaptive_enabled_default_preserves_phase5(school_tz: str) -> None:
    """Phase 6 regression — adaptive_enabled defaults True so Phase 5 branches still fire."""
    tz = ZoneInfo(school_tz)
    # Construct WITHOUT passing adaptive_enabled — proves the default is True.
    options = PolitesseOptions(
        school_tz=tz,
        refresh_interval=timedelta(minutes=30),
        afternoon_interval=timedelta(minutes=15),
        afternoon_window=(time(17, 0), time(20, 0)),
        quiet_hours=(time(22, 0), time(6, 0)),
        suspended_cadence=timedelta(hours=6),
        quiet_cadence=timedelta(hours=4),
        vacation_ranges=(),
        holiday_dates=frozenset(),
        jitter_seconds=30,
    )
    assert options.adaptive_enabled is True
    # Same Thursday-18h scenario — afternoon branch should win → 15 min ± 30s.
    # (Fri 08 May is a school day, so the afternoon branch fires when adaptive=True.)
    now = datetime(2026, 5, 7, 18, 0, tzinfo=tz)
    rng = random.Random(42)
    interval = compute_interval(now, options, rng=rng)
    assert timedelta(minutes=14, seconds=30) <= interval <= timedelta(minutes=15, seconds=30)
