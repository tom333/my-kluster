"""Diff lessons under tz matrix — Europe/Paris and Pacific/Noumea (D-25).

The NC-author blind-spot guard. Phase 2 CONTEXT.md: "the pytest matrix STARTS
in Phase 2" even though DIST-06 lands officially in Phase 5.

Strategy: for each scenario, parametrize over both timezones at TWO levels:

1. Runner's ambient TZ (via ``TZ`` env var) — proves the diff is independent
   of the operating environment's locale (an HA install on a VPS in Europe
   servicing a NC family).
2. Fixture-local ``school_tz`` — already varied across the synthetic fixtures
   (Plan 02-03). When the matrix runs ``Pacific/Noumea`` ambient, fixtures
   with ``school_tz=Europe/Paris`` still pass (the diff doesn't compare tz;
   it compares datetimes which already encode their offset).

The matrix proves: regardless of where HA runs OR what timezone the school
server uses, ``diff_lessons`` produces the same answer.
"""

from __future__ import annotations

import pytest

from custom_components.ha_pronote.diff import diff_lessons

pytestmark = pytest.mark.parametrize(
    "school_tz",
    ["Europe/Paris", "Pacific/Noumea"],
)


def test_first_poll_is_silent_under_tz_matrix(school_tz, monkeypatch, load_fixture):
    """D-08: ``previous is None`` → ``[]`` regardless of ambient TZ."""
    monkeypatch.setenv("TZ", school_tz)
    new = load_fixture("synthetic/first_poll_after_restart.json")
    assert diff_lessons(None, new, "today") == []


def test_reorder_is_silent_under_tz_matrix(school_tz, monkeypatch, load_fixture):
    """Pitfall 10: same lessons, different order → no events under any ambient TZ."""
    monkeypatch.setenv("TZ", school_tz)
    t0 = load_fixture("synthetic/reorder_no_op_T0.json")
    t1 = load_fixture("synthetic/reorder_no_op_T1.json")
    assert diff_lessons(t0, t1, "today") == []


def test_multi_change_emits_three_under_tz_matrix(school_tz, monkeypatch, load_fixture):
    """D-09: canceled + room + teacher all detected, regardless of ambient TZ."""
    monkeypatch.setenv("TZ", school_tz)
    t0 = load_fixture("synthetic/multi_change_T0.json")
    t1 = load_fixture("synthetic/multi_change_T1.json")
    events = diff_lessons(t0, t1, "today")
    assert len(events) == 3
    change_types = {event.change_type for event in events}
    assert change_types == {"canceled", "room", "teacher"}


def test_real_cancellation_under_tz_matrix(school_tz, monkeypatch, load_fixture, load_raw_fixture):
    """D-09 real-fixture probe — skips when Plan 02-02 captured byte-identical T0/T1.

    SPIKE-FINDINGS S-04 documents that the author's account did not
    naturally produce a cancellation between captures, so the real
    fixtures may have identical lessons arrays. When that is the case,
    the synthetic ``multi_change`` test above carries the cancel branch.
    """
    monkeypatch.setenv("TZ", school_tz)
    raw_t0 = load_raw_fixture("real/cancellation_T0.json")
    raw_t1 = load_raw_fixture("real/cancellation_T1.json")
    if raw_t0.get("lessons") == raw_t1.get("lessons"):
        pytest.skip(
            "real/cancellation_T0/T1 lessons are byte-identical "
            "(Plan 02-02 S-04 acknowledged gap -- Phase 4 verification gate)"
        )
    t0 = load_fixture("real/cancellation_T0.json")
    t1 = load_fixture("real/cancellation_T1.json")
    events = diff_lessons(t0, t1, "today")
    assert any(event.change_type == "canceled" for event in events)
