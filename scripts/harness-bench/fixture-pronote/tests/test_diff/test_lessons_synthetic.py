"""Combinatorics edge cases -- synthetic fixtures only (D-10).

These complement test_lessons.py by covering paths that real spike fixtures
can't reliably reproduce (period rollover noise, lesson added in the middle
of a week).

Algorithm decisions reflected here -- per SPIKE-FINDINGS-bain3-311.md S-04
acknowledged gap and the frozen 4-value taxonomy (D-09):

- Lesson removed (identity in T0 only): silent. The taxonomy has no `removed`
  value; SPIKE-FINDINGS S-04 ambiguity ("cannot empirically distinguish a real
  removal from a polling race") plus the ``Snapshot.lessons_today`` filter
  (D-16) means period-rollover noise is filtered before reaching the diff.
- Lesson added (identity in T1 only): silent. Mid-week scheduling additions
  are normal and not change events from a parent's perspective.
"""

from __future__ import annotations

from custom_components.ha_pronote.diff import diff_lessons


def test_lesson_removed_outside_today_window_is_silent(load_fixture):
    """D-10: a J-1 lesson disappearing should NOT emit for day=today.

    Both fixtures share `today=2026-05-04`. T0 contains a J-1 lesson on
    `2026-05-03` plus one lesson today; T1 retains only the today lesson.
    The Snapshot.lessons_today filter (D-16) drops the J-1 lesson before
    the diff runs, so the diff for day="today" sees identical inputs.
    """
    t0 = load_fixture("synthetic/lesson_removed_T0.json")
    t1 = load_fixture("synthetic/lesson_removed_T1.json")
    events = diff_lessons(t0, t1, "today")
    assert events == []


def test_lesson_added_emits_no_event(load_fixture):
    """Algorithm decision (silent on addition): a new lesson at T1 emits nothing.

    The frozen 4-value taxonomy (D-09) has no `added` value. SPIKE-FINDINGS
    S-04 default-recommends silent because additions are normal mid-week
    scheduling, not change events from a parent's perspective.
    """
    t0 = load_fixture("synthetic/lesson_added_T0.json")
    t1 = load_fixture("synthetic/lesson_added_T1.json")
    events = diff_lessons(t0, t1, "today")
    assert events == []


def test_lesson_uncanceled_emits_modified_change(load_fixture):
    """An identity match where canceled True->False is a `modified` event.

    Even though `canceled` is a content key, the algorithm classifies the
    True->False direction as `modified` rather than `canceled` -- the latter
    is reserved for the False->True flip.
    """
    # Construct via Snapshot ad hoc -- the synthetic suite doesn't ship a
    # dedicated uncanceled fixture, but we can swap the multi_change pair.
    t0 = load_fixture("synthetic/multi_change_T1.json")  # has Math canceled=True
    t1 = load_fixture("synthetic/multi_change_T0.json")  # Math canceled=False
    events = diff_lessons(t0, t1, "today")
    # 3 changes: Math (canceled True->False = modified), Histoire (room),
    # SVT (teacher).
    canceled_events = [e for e in events if e.change_type == "canceled"]
    assert canceled_events == [], "True->False on canceled MUST NOT emit canceled"
    modified_events = [e for e in events if e.change_type == "modified" and e.subject == "Mathematiques"]
    assert len(modified_events) == 1


def test_diff_lessons_for_tomorrow_window(load_fixture):
    """Sanity: when no lesson is on `tomorrow`, day=tomorrow returns empty."""
    t0 = load_fixture("synthetic/multi_change_T0.json")
    t1 = load_fixture("synthetic/multi_change_T1.json")
    assert diff_lessons(t0, t1, "tomorrow") == []
