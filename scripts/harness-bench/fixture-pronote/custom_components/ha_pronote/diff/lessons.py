"""Diff lessons -- identity vs content key, room vs cancellation discrimination.

Algorithm derivation: tests/fixtures/SPIKE-FINDINGS-bain3-311.md (D-06, D-07).
Read that document FIRST -- it locks the identity-vs-content split this module
implements.

Identity key (D-08, spike-locked per SPIKE-FINDINGS-bain3-311.md S-04):
    ``(date, start_time, end_time, subject)``

A substitute teacher is a CONTENT change, NOT an identity change. The lesson
"slot" is the same; the teacher in it might differ between polls.

Content keys (D-08, spike-locked):
    ``canceled`` (bool), ``classroom`` (str), ``teacher`` (str)

The ``status`` field is intentionally NOT in the content key: SPIKE-FINDINGS
S-04 documents that pronotepy 2.14.6 maps Pronote's ``indicateurAbsence`` onto
``Lesson.canceled``, while ``status`` is a free-form label that drifts even
when nothing material has changed (e.g. "Cours change de salle"). Using it as
a content key would produce noisy "modified" events with no actionable cause.

Frozen taxonomy (D-09, ROADMAP Phase 4 success criterion #1):

- ``"canceled"`` -- ``canceled`` flag flipped from ``False`` to ``True``
- ``"modified"`` -- content changed but no specific axis matches (catch-all)
- ``"teacher"`` -- teacher field changed (subset of "modified")
- ``"room"``    -- classroom field changed (subset of "modified")

Classification priority when multiple axes change at once:
    canceled (False -> True) > room > teacher > modified

The ``False -> True`` direction on ``canceled`` is the only one that emits
``"canceled"``. The ``True -> False`` direction (lesson uncanceled) emits
``"modified"`` -- no taxonomy member captures "uncancellation" precisely and
flooding parents with ``canceled`` events when a lesson is restored would be
worse than a generic ``modified``. SPIKE-FINDINGS S-04 explicitly flags this
as a known ambiguity carried forward to Phase 4 verification.

Algorithm decisions (per SPIKE-FINDINGS S-04 acknowledged gap):

- **Lesson disappeared from the day's slice** (identity in T0 only): silent.
  The taxonomy has no ``removed`` value; the documented ambiguity ("cannot
  empirically distinguish a real removal from a polling race") plus the
  ``Snapshot.lessons_today`` filter (D-16) makes the period-rollover case
  vacuously empty. Phase 4 verification logs every such event for one month
  before deciding to promote it to a real ``canceled``.
- **Lesson appeared in the day's slice** (identity in T1 only): silent.
  Mid-week scheduling additions are normal and not change events from a
  parent's perspective. Phase 4 may revisit if user feedback warrants.
- **bain3#311 paired-lesson consolidation**: the dict-by-identity-key approach
  below assumes pronotepy emits one ``Lesson`` per identity tuple. SPIKE-FINDINGS
  S-04 could not empirically verify the paired-entry case (Option A in the
  bain3#311 thread). If a future spike captures duplicates per identity tuple,
  swap the dict for a ``defaultdict(list)`` and reduce per-tuple before
  comparing. Until then, the simpler dict approach holds.

First-poll invariant (D-08, EVENT-04 cross-cutting tracker for Phase 4):
``diff_lessons(None, snapshot, day) -> []`` regardless of snapshot size.

Reorder no-op invariant (Pitfall 10):
Same identity + content tuples regardless of array order -> ``[]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import LessonChange

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Lesson, Snapshot

    from .events import ChangeType, DayLabel


def _identity_key(lesson: Lesson) -> tuple:
    """Identity tuple for matching the same lesson across polls (D-08)."""
    return (lesson.date, lesson.start.time(), lesson.end.time(), lesson.subject)


def _content_key(lesson: Lesson) -> tuple:
    """Content tuple compared between T0 and T1 entries with the same identity."""
    return (lesson.canceled, lesson.classroom, lesson.teacher)


def _classify_change(before: Lesson, after: Lesson) -> ChangeType:
    """Choose the most specific change_type (D-09) given an identity match.

    Priority: canceled (False -> True) > room > teacher > modified.
    """
    if after.canceled and not before.canceled:
        return "canceled"
    if before.classroom != after.classroom:
        return "room"
    if before.teacher != after.teacher:
        return "teacher"
    return "modified"


def diff_lessons(
    previous: Snapshot | None,
    new: Snapshot,
    day: DayLabel,
) -> list[LessonChange]:
    """Return ``LessonChange`` events between two snapshots for the requested day.

    Args:
        previous: Previous ``Snapshot``, or ``None`` on first poll after restart.
        new: Current ``Snapshot``.
        day: ``"today"`` or ``"tomorrow"`` -- selects the lesson slice to compare.

    Returns:
        List of ``LessonChange`` events. Empty when ``previous`` is ``None``
        (D-08 invariant), when the day's lessons are identical modulo array
        order (Pitfall 10 reorder no-op), or when only additions / removals
        occurred (silent per SPIKE-FINDINGS S-04 acknowledged gap).
    """
    if previous is None:
        return []

    if day == "today":
        prev_lessons = previous.lessons_today
        new_lessons = new.lessons_today
    else:
        prev_lessons = previous.lessons_tomorrow
        new_lessons = new.lessons_tomorrow

    prev_by_identity = {_identity_key(L): L for L in prev_lessons}
    new_by_identity = {_identity_key(L): L for L in new_lessons}

    events: list[LessonChange] = []

    # Identity tuples present in both T0 and T1 -- content diff per D-08.
    for identity in prev_by_identity.keys() & new_by_identity.keys():
        before = prev_by_identity[identity]
        after = new_by_identity[identity]
        if _content_key(before) == _content_key(after):
            continue  # identical lesson, no change
        events.append(
            LessonChange(
                change_type=_classify_change(before, after),
                day=day,
                lesson_date=after.date,
                subject=after.subject,
                before=before.to_dict(),
                after=after.to_dict(),
            )
        )

    # Identity tuples present only in T0 (lesson disappeared) -- silent per
    # SPIKE-FINDINGS S-04: no taxonomy member captures it cleanly, and the
    # lessons_today filter (D-16) keeps period-rollover noise out of scope.
    # Identity tuples present only in T1 (lesson appeared) -- silent for the
    # same reason: mid-week additions are normal scheduling. Phase 4 may
    # revisit.

    return events
