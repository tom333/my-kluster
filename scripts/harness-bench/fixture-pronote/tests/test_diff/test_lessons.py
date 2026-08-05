"""Diff lessons tests -- covers ROADMAP success criteria #3 and #4.

NOTE: Plan 02-04 wraps these in a tz-matrix parametrize (D-25). For now they
run on whatever the test runner's local TZ is -- the assertions use
fixture-local school_tz, so they pass regardless. Plan 02-04's matrix is
belt-and-suspenders for any HA-side code that lands later.

Real-fixture tests (TestRealCancellation / TestRealRoomChange /
TestRealTeacherSwap) skip when the captured T0 vs T1 lessons array is
byte-identical -- that is the explicit Plan 02-02 S-04 acknowledged gap.
The skip path keeps the test scaffolding ready for the day a real schedule
change is captured (Phase 4 verification gate per the SPIKE-FINDINGS doc).
"""

from __future__ import annotations

from datetime import date
import json

import pytest

from custom_components.ha_pronote.diff import diff_lessons


def _real_pair_has_lesson_change(load_raw_fixture, scenario: str) -> bool:
    """Return True iff the real T0/T1 lessons arrays differ.

    Plan 02-02 S-04 captured fixtures whose ``lessons`` array is byte-identical
    (no teacher-side schedule change occurred during the capture window). The
    diff-layer assertions only fire when the pair actually contains a change.
    """
    t0 = load_raw_fixture(f"real/{scenario}_T0.json")
    t1 = load_raw_fixture(f"real/{scenario}_T1.json")
    return t0["lessons"] != t1["lessons"]


class TestFirstPollInvariant:
    def test_previous_none_with_empty_new_returns_empty(self, load_fixture):
        new = load_fixture("synthetic/empty_to_empty_T1.json")
        assert diff_lessons(None, new, "today") == []

    def test_previous_none_with_full_new_returns_empty(self, load_fixture):
        """D-08, ROADMAP success criterion #4: zero events on first poll."""
        new = load_fixture("synthetic/first_poll_after_restart.json")
        assert len(new.lessons) > 0
        assert diff_lessons(None, new, "today") == []
        assert diff_lessons(None, new, "tomorrow") == []


class TestReorderNoOp:
    def test_same_lessons_different_order_emits_nothing(self, load_fixture):
        """Pitfall 10: array order alone never triggers events."""
        t0 = load_fixture("synthetic/reorder_no_op_T0.json")
        t1 = load_fixture("synthetic/reorder_no_op_T1.json")
        assert diff_lessons(t0, t1, "today") == []


class TestEmptyToEmpty:
    def test_vacation_emits_nothing(self, load_fixture):
        t0 = load_fixture("synthetic/empty_to_empty_T0.json")
        t1 = load_fixture("synthetic/empty_to_empty_T1.json")
        assert diff_lessons(t0, t1, "today") == []
        assert diff_lessons(t0, t1, "tomorrow") == []


class TestMultiChangeSynthetic:
    """Three identity-stable changes in one poll -- exercises every change_type."""

    def test_emits_three_events(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert len(events) == 3

    def test_emits_one_canceled_event(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        canceled = [e for e in events if e.change_type == "canceled"]
        assert len(canceled) == 1
        assert canceled[0].subject == "Mathematiques"
        assert canceled[0].day == "today"

    def test_emits_one_room_event(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        room = [e for e in events if e.change_type == "room"]
        assert len(room) == 1
        assert room[0].subject == "Histoire"
        assert room[0].before["classroom"] == "Salle B2"
        assert room[0].after["classroom"] == "Salle B5"

    def test_emits_one_teacher_event(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        teacher = [e for e in events if e.change_type == "teacher"]
        assert len(teacher) == 1
        assert teacher[0].subject == "SVT"
        assert teacher[0].before["teacher"] == "M. Profb"
        assert teacher[0].after["teacher"] == "Mme Profx"

    def test_change_type_is_one_of_the_four_frozen_values(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        for e in events:
            assert e.change_type in {"canceled", "modified", "teacher", "room"}


class TestRealCancellation:
    """ROADMAP success criterion #3: real fixture from the spike (D-05)."""

    def test_real_cancellation_emits_at_least_one_canceled_event(self, load_fixture, load_raw_fixture):
        if not _real_pair_has_lesson_change(load_raw_fixture, "cancellation"):
            pytest.skip(
                "real/cancellation_T0/T1 lessons are byte-identical "
                "(Plan 02-02 S-04 acknowledged gap -- Phase 4 verification gate)"
            )
        t0 = load_fixture("real/cancellation_T0.json")
        t1 = load_fixture("real/cancellation_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert any(e.change_type == "canceled" for e in events), (
            "Expected at least one canceled event from the live spike capture. "
            "Inspect tests/fixtures/SPIKE-FINDINGS-bain3-311.md if this fails."
        )


class TestRealRoomChange:
    """ROADMAP success criterion #3: real fixture from the spike (D-05).

    Critical assertion -- Pitfall 10 / bain3#311: a room change must NOT be
    reported as a canceled+added pair.
    """

    def test_real_room_change_emits_room_event(self, load_fixture, load_raw_fixture):
        if not _real_pair_has_lesson_change(load_raw_fixture, "room_change"):
            pytest.skip(
                "real/room_change_T0/T1 lessons are byte-identical "
                "(Plan 02-02 S-04 acknowledged gap -- Phase 4 verification gate)"
            )
        t0 = load_fixture("real/room_change_T0.json")
        t1 = load_fixture("real/room_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert any(e.change_type == "room" for e in events), (
            "Expected at least one room event from the live spike capture."
        )

    def test_real_room_change_does_not_emit_phantom_canceled(self, load_fixture, load_raw_fixture):
        """bain3#311: the room-changed lesson must NOT appear as canceled."""
        if not _real_pair_has_lesson_change(load_raw_fixture, "room_change"):
            pytest.skip("real/room_change_T0/T1 lessons are byte-identical (Plan 02-02 S-04 acknowledged gap)")
        t0 = load_fixture("real/room_change_T0.json")
        t1 = load_fixture("real/room_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        canceled = [(e.lesson_date, e.subject) for e in events if e.change_type == "canceled"]
        room = [(e.lesson_date, e.subject) for e in events if e.change_type == "room"]
        overlap = set(canceled) & set(room)
        assert not overlap, f"bain3#311 anti-pattern: same lesson reported as both canceled AND room: {overlap}"


class TestRealTeacherSwap:
    def test_real_teacher_swap_emits_teacher_event(self, load_fixture, load_raw_fixture):
        if not _real_pair_has_lesson_change(load_raw_fixture, "teacher_swap"):
            pytest.skip(
                "real/teacher_swap_T0/T1 lessons are byte-identical "
                "(Plan 02-02 S-04 acknowledged gap -- Phase 4 verification gate)"
            )
        t0 = load_fixture("real/teacher_swap_T0.json")
        t1 = load_fixture("real/teacher_swap_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert any(e.change_type == "teacher" for e in events), (
            "Expected at least one teacher event from the live spike capture."
        )


class TestRealFixturesRoundTripThroughSnapshot:
    """Even when no lesson change is captured, the 6 real fixtures must
    round-trip through Snapshot.from_dict cleanly.

    This is the shape verification SPIKE-FINDINGS S-04 explicitly preserves
    as still-valuable: real PII-safe captures exercise the dataclass parsing
    path on full-size, real-shaped Pronote responses.
    """

    @pytest.mark.parametrize("scenario", ["cancellation", "room_change", "teacher_swap"])
    @pytest.mark.parametrize("phase", ["T0", "T1"])
    def test_real_fixture_round_trips(self, load_fixture, scenario: str, phase: str):
        """Loading via load_fixture must succeed (Snapshot.from_dict happy path)."""
        snap = load_fixture(f"real/{scenario}_{phase}.json")
        # Sanity: real captures have lessons.
        assert len(snap.lessons) > 0


class TestPayloadShape:
    def test_event_payload_is_json_serializable(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        for e in events:
            payload = e.to_payload()
            json.dumps(payload, ensure_ascii=False)  # raises if not serializable

    def test_event_lesson_date_in_payload_is_iso_string(self, load_fixture):
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        for e in events:
            payload = e.to_payload()
            assert isinstance(payload["lesson_date"], str)
            date.fromisoformat(payload["lesson_date"])  # raises if not ISO


class TestDaySelector:
    def test_day_today_uses_lessons_today_only(self, load_fixture):
        """The day argument selects the lesson slice."""
        # multi_change fixtures have all lessons on `today` -- so day=tomorrow
        # should emit zero events.
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "tomorrow")
        assert events == []
