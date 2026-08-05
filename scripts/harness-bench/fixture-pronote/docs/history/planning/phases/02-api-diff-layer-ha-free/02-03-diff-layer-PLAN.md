---
phase: 02-api-diff-layer-ha-free
plan: 03
type: execute
wave: 3
depends_on: ["02-01", "02-02"]
files_modified:
  - custom_components/ha_pronote/diff/__init__.py
  - custom_components/ha_pronote/diff/events.py
  - custom_components/ha_pronote/diff/lessons.py
  - custom_components/ha_pronote/diff/grades.py
  - custom_components/ha_pronote/diff/notifications.py
  - tests/fixtures/synthetic/empty_to_empty_T0.json
  - tests/fixtures/synthetic/empty_to_empty_T1.json
  - tests/fixtures/synthetic/reorder_no_op_T0.json
  - tests/fixtures/synthetic/reorder_no_op_T1.json
  - tests/fixtures/synthetic/multi_change_T0.json
  - tests/fixtures/synthetic/multi_change_T1.json
  - tests/fixtures/synthetic/first_poll_after_restart.json
  - tests/fixtures/synthetic/lesson_removed_T0.json
  - tests/fixtures/synthetic/lesson_removed_T1.json
  - tests/fixtures/synthetic/lesson_added_T0.json
  - tests/fixtures/synthetic/lesson_added_T1.json
  - tests/test_diff/__init__.py
  - tests/test_diff/conftest.py
  - tests/test_diff/test_lessons.py
  - tests/test_diff/test_lessons_synthetic.py
  - tests/test_diff/test_events.py
  - tests/test_diff/test_stubs.py
autonomous: true
requirements: [EVENT-05]
must_haves:
  truths:
    - "diff_lessons(None, snapshot, day) == [] for any non-empty snapshot — first-poll skip (D-08, Pitfall 10, EVENT-04 cross-cutting tracker for Phase 4)"
    - "diff_lessons emits zero events when only lesson order changed across polls (Pitfall 10 reorder no-op)"
    - "diff_lessons distinguishes a real cancellation from a room change on the captured tests/fixtures/real/cancellation_T{0,1}.json and room_change_T{0,1}.json pairs (ROADMAP success criterion #3)"
    - "ChangeType taxonomy is exactly the 4 values: canceled, modified, teacher, room (D-09, ROADMAP Phase 4 success criterion #1)"
    - "LessonChange.to_payload() returns a JSON-serializable dict matching ARCHITECTURE.md Pattern 3 schema lines 260-278"
    - "diff_grades and diff_notifications raise NotImplementedError until Phase 4 fills them (D-02)"
    - "NewGrade and NewInformation dataclasses exist in diff/events.py with frozen=True (D-02, D-03, C-01)"
    - "All 11 synthetic fixtures round-trip through Snapshot.from_dict/to_dict cleanly (D-11, D-23 — committed datetimes are ISO-8601 with explicit offset)"
  artifacts:
    - path: "custom_components/ha_pronote/diff/__init__.py"
      provides: "Single import surface for diff (C-01) — re-exports diff_lessons, LessonChange, NewGrade, NewInformation"
      contains: "__all__"
    - path: "custom_components/ha_pronote/diff/events.py"
      provides: "Frozen dataclasses LessonChange, NewGrade, NewInformation + ChangeType Literal (D-09, C-01)"
      contains: "ChangeType = Literal"
    - path: "custom_components/ha_pronote/diff/lessons.py"
      provides: "diff_lessons(previous, new, day) -> list[LessonChange] — identity vs content key, room vs cancel (D-05..D-09)"
      contains: "def diff_lessons"
    - path: "custom_components/ha_pronote/diff/grades.py"
      provides: "diff_grades stub raising NotImplementedError (D-02 — Phase 4 fills)"
      contains: "raise NotImplementedError"
    - path: "custom_components/ha_pronote/diff/notifications.py"
      provides: "diff_notifications stub raising NotImplementedError (D-02 — Phase 4 fills)"
      contains: "raise NotImplementedError"
    - path: "tests/fixtures/synthetic/first_poll_after_restart.json"
      provides: "Snapshot fixture for the previous-is-None invariant (D-10)"
      contains: '"school_tz"'
    - path: "tests/fixtures/synthetic/reorder_no_op_T0.json"
      provides: "Lessons in some order — paired with reorder_no_op_T1.json (same lessons, different order)"
      contains: '"lessons"'
  key_links:
    - from: "custom_components/ha_pronote/diff/lessons.py"
      to: "tests/fixtures/SPIKE-FINDINGS-bain3-311.md"
      via: "Algorithm derivation per D-06, D-07 (Plan 02-02 produced the findings)"
      pattern: "spike|SPIKE-FINDINGS|D-08|bain3"
    - from: "custom_components/ha_pronote/diff/lessons.py"
      to: "custom_components/ha_pronote/diff/events.py"
      via: "Imports LessonChange + ChangeType"
      pattern: "from \\.events import"
    - from: "custom_components/ha_pronote/diff/__init__.py"
      to: "custom_components/ha_pronote/diff/lessons.py"
      via: "Re-exports diff_lessons (single import surface, C-01)"
      pattern: "from \\.lessons import diff_lessons"
    - from: "tests/test_diff/test_lessons.py"
      to: "tests/fixtures/real/cancellation_T0.json"
      via: "Loads real fixture pair via load_fixture conftest helper"
      pattern: "load_fixture"
---

<objective>
Implement the diff layer that consumes the spike findings (Plan 02-02) and the
api/ models (Plan 02-01) to produce typed `LessonChange` events. This is the
heart of Phase 2 — the algorithm that distinguishes a cancellation from a
room change on real fixtures (ROADMAP success criterion #3) and emits zero
events on first poll or pure reorder (ROADMAP success criterion #4).

Purpose: this plan owns EVENT-05 — "the diff layer distinguishes lesson identity
from content for an unambiguous change_type". The four `change_type` values
(`canceled`, `modified`, `teacher`, `room`) are frozen here so Phase 4 only
routes them onto `hass.bus.async_fire("pronote_schedule_changed", ...)`.

`diff/grades.py` and `diff/notifications.py` ship as type-locked stubs (D-02) —
the dataclasses (`NewGrade`, `NewInformation`) live in `diff/events.py` per
C-01, the function bodies raise `NotImplementedError` until Phase 4. This locks
Phase 4's contract while keeping Phase 2's surface narrow.

Output: 5 new files in `custom_components/ha_pronote/diff/` + 11 synthetic
fixture JSONs in `tests/fixtures/synthetic/` + 5 test files in
`tests/test_diff/`. NO modifications to Plan 02-01 or 02-02 outputs.
</objective>

<execution_context>
@/home/moi/projets/perso/pronote/.claude/get-shit-done/workflows/execute-plan.md
@/home/moi/projets/perso/pronote/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md
@.planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md
@.planning/research/PITFALLS.md
@.planning/research/ARCHITECTURE.md
@.planning/research/FEATURES.md

# Spike output Plan 02-02 produced — THE source of truth for diff/lessons.py
@tests/fixtures/SPIKE-FINDINGS-bain3-311.md
@tests/fixtures/real/cancellation_T0.json
@tests/fixtures/real/cancellation_T1.json
@tests/fixtures/real/room_change_T0.json
@tests/fixtures/real/room_change_T1.json
@tests/fixtures/real/teacher_swap_T0.json
@tests/fixtures/real/teacher_swap_T1.json

# Plan 02-01 outputs that this plan consumes
@custom_components/ha_pronote/api/__init__.py
@custom_components/ha_pronote/api/models.py
@custom_components/ha_pronote/api/errors.py
@custom_components/ha_pronote/__init__.py
@custom_components/ha_pronote/const.py

<interfaces>
<!-- Contracts this plan PRODUCES — Phase 4's coordinator and Phase 4's
     diff_grades / diff_notifications bodies consume these. -->

# diff/events.py contract (D-09, C-01)
```python
from dataclasses import dataclass
from datetime import date as Date
from typing import Any, Literal

# Frozen taxonomy — Phase 4 success criterion #1, ROADMAP §"Phase 4"
ChangeType = Literal["canceled", "modified", "teacher", "room"]
DayLabel = Literal["today", "tomorrow"]

@dataclass(frozen=True)
class LessonChange:
    change_type: ChangeType
    day: DayLabel
    lesson_date: Date
    subject: str
    before: dict[str, Any] | None     # Lesson.to_dict() of T0 entry, or None for added-shaped
    after: dict[str, Any] | None      # Lesson.to_dict() of T1 entry, or None for removed-shaped

    def to_payload(self) -> dict[str, Any]: ...

@dataclass(frozen=True)
class NewGrade:
    """Type contract locked here. Phase 4 fills diff_grades body."""
    subject: str
    value: str
    out_of: str
    coefficient: str
    date: Date
    def to_payload(self) -> dict[str, Any]: ...

@dataclass(frozen=True)
class NewInformation:
    """Type contract locked here. Phase 4 fills diff_notifications body."""
    info_id: str
    title: str
    sender: str
    date: Date           # date-only payload — Phase 4 may revisit if datetime is needed
    excerpt: str
    def to_payload(self) -> dict[str, Any]: ...
```

# diff/lessons.py contract
```python
def diff_lessons(
    previous: Snapshot | None,
    new: Snapshot,
    day: DayLabel,                    # "today" or "tomorrow"
) -> list[LessonChange]:
    """Returns LessonChange events for the requested day.

    First-poll invariant (D-08): previous is None -> [].
    Reorder no-op invariant: same identity+content keys regardless of order -> [].
    """
```

# diff/__init__.py contract (C-01)
```python
from .events import LessonChange, NewGrade, NewInformation, ChangeType, DayLabel
from .lessons import diff_lessons
# Phase 4 will append: from .grades import diff_grades
# Phase 4 will append: from .notifications import diff_notifications
__all__ = [...]
```

# Synthetic fixture shape (matches Snapshot.to_dict(), D-10, D-11):
{
  "today": "2026-05-04",
  "school_tz": "Europe/Paris",          # fixture-local — D-25 matrix loops both tz's
  "lessons": [...],
  "grades": [],
  "information": []
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Define diff/events.py + diff/__init__.py + stub modules + their tests</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Diff Scope" (D-01..D-04) + §"Diff Algorithm" (D-09) + §"Claude's Discretion" (C-01, C-02)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"diff/__init__.py" + §"diff/events.py" + §"diff/grades.py" + §"diff/notifications.py"
    - .planning/research/ARCHITECTURE.md §"Pattern 3" lines 260–278 (event payload schema — frozen here)
    - .planning/research/FEATURES.md §"Rich pronote_schedule_changed events" (change_type taxonomy locked: canceled / modified / teacher / room)
    - custom_components/ha_pronote/__init__.py (Phase 1 docstring shape to mirror)
    - custom_components/ha_pronote/config_flow.py (Phase 1 placeholder pattern — same shape for diff/grades.py and diff/notifications.py stubs)
    - custom_components/ha_pronote/api/models.py (Plan 02-01 — Lesson, Grade, Information shapes referenced by stubs)
  </read_first>
  <behavior>
    - `from custom_components.ha_pronote.diff import LessonChange, NewGrade, NewInformation, diff_lessons` succeeds (single import surface, C-01).
    - `LessonChange` is `@dataclass(frozen=True)` with fields `change_type: ChangeType`, `day: DayLabel`, `lesson_date: Date`, `subject: str`, `before: dict | None`, `after: dict | None`.
    - `ChangeType = Literal["canceled", "modified", "teacher", "room"]` — exactly 4 values, frozen taxonomy (D-09, ROADMAP Phase 4 success criterion #1, FEATURES.md).
    - `DayLabel = Literal["today", "tomorrow"]` — exactly 2 values.
    - `LessonChange("canceled", "today", date(2026, 5, 4), "Maths", {...}, None).to_payload()` returns a dict with keys `change_type`, `day`, `lesson_date`, `subject`, `before`, `after`. The `lesson_date` value is the ISO string `"2026-05-04"`.
    - `json.dumps(LessonChange(...).to_payload())` does not raise (the payload is JSON-serializable — required for `hass.bus.async_fire` consumption in Phase 4).
    - `NewGrade("Maths", "14,5", "20", "1", date(2026, 5, 1)).to_payload() == {"subject": "Maths", "value": "14,5", "out_of": "20", "coefficient": "1", "date": "2026-05-01"}`.
    - `NewInformation("id1", "Title", "Sender", date(2026, 5, 1), "excerpt").to_payload()` is JSON-serializable.
    - `diff_grades(None, snap)` raises `NotImplementedError` with a message mentioning "Phase 4" and "D-02".
    - `diff_notifications(None, snap)` raises `NotImplementedError` with the same message shape.
    - All four dataclasses are frozen (immutable — `pytest.raises(dataclasses.FrozenInstanceError)`).
    - Zero `homeassistant.*` imports anywhere in `diff/` (D-19 — Plan 02-04's AST guard verifies).
  </behavior>
  <action>
    Build the diff/ package marker, the events dataclasses (single import surface per C-01), and the stub modules for grades and notifications.

    **1. Create `custom_components/ha_pronote/diff/events.py`** per D-02, D-03, D-09, C-01 + PATTERNS.md §"diff/events.py":

    ```python
    """Event dataclasses — Phase 4 routes these onto hass.bus.async_fire.

    D-09 + ROADMAP Phase 4 success criterion #1 + FEATURES.md §"Rich
    pronote_schedule_changed events": the four change_type values are FROZEN.
    Adding or renaming a value is a breaking change for downstream automations.

    C-01: single import surface — Phase 4 imports LessonChange, NewGrade,
    NewInformation, ChangeType, DayLabel from `custom_components.ha_pronote.diff`.

    Pattern 3 (ARCHITECTURE.md lines 260–278) — `to_payload()` shape is the
    contract Phase 4's coordinator forwards verbatim into the bus event.
    """
    from __future__ import annotations

    from dataclasses import dataclass
    from datetime import date as Date
    from typing import Any, Literal

    ChangeType = Literal["canceled", "modified", "teacher", "room"]
    DayLabel = Literal["today", "tomorrow"]


    @dataclass(frozen=True)
    class LessonChange:
        """A single lesson-level change between two snapshots.

        change_type: one of the four FROZEN taxonomy values (D-09).
        day: which day this change applies to ("today" or "tomorrow").
        lesson_date: the ISO date of the changed lesson.
        subject: the lesson's subject name (anonymized in fixtures).
        before: Lesson.to_dict() of the T0 entry, or None for "added"-shaped events.
        after: Lesson.to_dict() of the T1 entry, or None for "removed"-shaped events.
        """

        change_type: ChangeType
        day: DayLabel
        lesson_date: Date
        subject: str
        before: dict[str, Any] | None
        after: dict[str, Any] | None

        def to_payload(self) -> dict[str, Any]:
            """JSON-serializable dict matching ARCHITECTURE.md Pattern 3 schema.

            Phase 4 forwards this verbatim into hass.bus.async_fire.
            """
            return {
                "change_type": self.change_type,
                "day": self.day,
                "lesson_date": self.lesson_date.isoformat(),
                "subject": self.subject,
                "before": self.before,
                "after": self.after,
            }


    @dataclass(frozen=True)
    class NewGrade:
        """Type contract locked in Phase 2; diff_grades body lands in Phase 4 (D-02).

        Field list MUST match what Phase 4's diff_grades will produce.
        """

        subject: str
        value: str          # raw "14,5" or "14.5" — Phase 4 sensor normalizes
        out_of: str
        coefficient: str
        date: Date

        def to_payload(self) -> dict[str, Any]:
            return {
                "subject": self.subject,
                "value": self.value,
                "out_of": self.out_of,
                "coefficient": self.coefficient,
                "date": self.date.isoformat(),
            }


    @dataclass(frozen=True)
    class NewInformation:
        """Type contract locked in Phase 2; diff_notifications body lands in Phase 4 (D-02).

        Field list MUST match what Phase 4's diff_notifications will produce.
        """

        info_id: str
        title: str
        sender: str
        date: Date
        excerpt: str

        def to_payload(self) -> dict[str, Any]:
            return {
                "info_id": self.info_id,
                "title": self.title,
                "sender": self.sender,
                "date": self.date.isoformat(),
                "excerpt": self.excerpt,
            }
    ```

    **2. Create `custom_components/ha_pronote/diff/__init__.py`** per C-01 + PATTERNS.md §"diff/__init__.py":

    ```python
    """Pure diff functions over Snapshot. HA-free per D-19.

    Public surface (consumed by Phase 4 coordinator):
    - diff_lessons(previous, new, day) -> list[LessonChange]
    - diff_grades(previous, new) -> list[NewGrade]              [Phase 4 fills body]
    - diff_notifications(previous, new) -> list[NewInformation] [Phase 4 fills body]
    - LessonChange, NewGrade, NewInformation, ChangeType, DayLabel (types)
    """
    from __future__ import annotations

    from .events import (
        ChangeType,
        DayLabel,
        LessonChange,
        NewGrade,
        NewInformation,
    )
    from .grades import diff_grades
    from .lessons import diff_lessons
    from .notifications import diff_notifications

    __all__ = [
        "ChangeType",
        "DayLabel",
        "LessonChange",
        "NewGrade",
        "NewInformation",
        "diff_grades",
        "diff_lessons",
        "diff_notifications",
    ]
    ```

    **3. Create `custom_components/ha_pronote/diff/grades.py`** as a type-locked stub per D-02, C-01 + PATTERNS.md §"diff/grades.py":

    ```python
    """Grade diff — body lands in Phase 4 (D-02). Type contract locked here.

    Phase 2 ships `NewGrade` (in `diff/events.py` per C-01). Phase 4 fills this
    body. The function signature below freezes Phase 4's contract so it cannot
    drift across phases.
    """
    from __future__ import annotations

    from typing import TYPE_CHECKING

    from .events import NewGrade

    if TYPE_CHECKING:
        from custom_components.ha_pronote.api.models import Snapshot


    def diff_grades(previous: "Snapshot | None", new: "Snapshot") -> list[NewGrade]:
        """Return new grades since the previous poll.

        Phase 2 stub. Phase 4 fills the body per D-02:
          - first-poll skip: previous is None -> [].
          - identity key per grade: (subject, date, value) — set difference.

        Raises:
            NotImplementedError: until Phase 4 ships.
        """
        raise NotImplementedError(
            "diff_grades body lands in Phase 4 (D-02). "
            "Phase 2 ships only the NewGrade dataclass contract."
        )
    ```

    **4. Create `custom_components/ha_pronote/diff/notifications.py`** as a mirror stub per D-02:

    ```python
    """Information diff — body lands in Phase 4 (D-02). Type contract locked here.

    Phase 2 ships `NewInformation` (in `diff/events.py` per C-01). Phase 4 fills
    this body. The function signature below freezes Phase 4's contract.
    """
    from __future__ import annotations

    from typing import TYPE_CHECKING

    from .events import NewInformation

    if TYPE_CHECKING:
        from custom_components.ha_pronote.api.models import Snapshot


    def diff_notifications(
        previous: "Snapshot | None", new: "Snapshot"
    ) -> list[NewInformation]:
        """Return new informations since the previous poll.

        Phase 2 stub. Phase 4 fills the body per D-02:
          - first-poll skip: previous is None -> [].
          - identity key per information: (info_id, date) — set difference.

        Raises:
            NotImplementedError: until Phase 4 ships.
        """
        raise NotImplementedError(
            "diff_notifications body lands in Phase 4 (D-02). "
            "Phase 2 ships only the NewInformation dataclass contract."
        )
    ```

    **5. Create `tests/test_diff/__init__.py`**: empty file (package marker).

    **6. Create `tests/test_diff/test_events.py`** (covers events.py contract):

    ```python
    """Tests for diff/events.py — D-09 frozen taxonomy + Pattern 3 payload schema."""
    from __future__ import annotations

    import dataclasses
    import json
    from datetime import date

    import pytest

    from custom_components.ha_pronote.diff import (
        ChangeType,
        DayLabel,
        LessonChange,
        NewGrade,
        NewInformation,
    )


    def test_change_type_taxonomy_is_exactly_four_values():
        """D-09 + ROADMAP Phase 4 success criterion #1: frozen taxonomy."""
        # Literal types aren't iterable at runtime, but typing.get_args reveals members.
        from typing import get_args
        assert set(get_args(ChangeType)) == {"canceled", "modified", "teacher", "room"}


    def test_day_label_is_today_or_tomorrow():
        from typing import get_args
        assert set(get_args(DayLabel)) == {"today", "tomorrow"}


    def test_lesson_change_to_payload_is_json_serializable():
        change = LessonChange(
            change_type="canceled",
            day="today",
            lesson_date=date(2026, 5, 4),
            subject="Mathématiques",
            before={"canceled": False, "classroom": "A1"},
            after={"canceled": True, "classroom": "A1"},
        )
        payload = change.to_payload()
        # round-trip through json.dumps/json.loads
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["change_type"] == "canceled"
        assert round_tripped["day"] == "today"
        assert round_tripped["lesson_date"] == "2026-05-04"
        assert round_tripped["subject"] == "Mathématiques"
        assert round_tripped["before"] == {"canceled": False, "classroom": "A1"}
        assert round_tripped["after"] == {"canceled": True, "classroom": "A1"}


    def test_lesson_change_with_none_before():
        change = LessonChange("modified", "tomorrow", date(2026, 5, 5), "Histoire",
                              before=None, after={"x": 1})
        payload = change.to_payload()
        assert payload["before"] is None


    def test_lesson_change_is_frozen():
        change = LessonChange("canceled", "today", date(2026, 5, 4), "Maths", None, None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            change.change_type = "modified"


    def test_new_grade_to_payload():
        g = NewGrade(subject="Maths", value="14,5", out_of="20", coefficient="1",
                     date=date(2026, 5, 1))
        assert g.to_payload() == {
            "subject": "Maths",
            "value": "14,5",
            "out_of": "20",
            "coefficient": "1",
            "date": "2026-05-01",
        }


    def test_new_grade_is_frozen():
        g = NewGrade("Maths", "14,5", "20", "1", date(2026, 5, 1))
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.value = "15,0"


    def test_new_information_to_payload_is_json_serializable():
        info = NewInformation(
            info_id="id1",
            title="Réunion parents",
            sender="Direction",
            date=date(2026, 5, 1),
            excerpt="Une réunion d'information aura lieu...",
        )
        payload = info.to_payload()
        round_tripped = json.loads(json.dumps(payload, ensure_ascii=False))
        assert round_tripped["info_id"] == "id1"
        assert round_tripped["title"] == "Réunion parents"
        assert round_tripped["date"] == "2026-05-01"


    def test_new_information_is_frozen():
        info = NewInformation("id1", "T", "S", date(2026, 5, 1), "x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.title = "Y"
    ```

    **7. Create `tests/test_diff/test_stubs.py`** (covers grades.py + notifications.py):

    ```python
    """Tests for the Phase 2 type-locked stubs (D-02). Bodies land in Phase 4."""
    from __future__ import annotations

    import pytest

    from custom_components.ha_pronote.diff import diff_grades, diff_notifications


    def test_diff_grades_raises_not_implemented():
        with pytest.raises(NotImplementedError, match="Phase 4|D-02"):
            diff_grades(None, None)


    def test_diff_notifications_raises_not_implemented():
        with pytest.raises(NotImplementedError, match="Phase 4|D-02"):
            diff_notifications(None, None)
    ```

    **8. Verification commands:**
    - `ruff format custom_components/ha_pronote/diff tests/test_diff/test_events.py tests/test_diff/test_stubs.py tests/test_diff/__init__.py`
    - `ruff check custom_components/ha_pronote/diff tests/test_diff`
    - `pytest tests/test_diff/test_events.py tests/test_diff/test_stubs.py -v` — all pass.
    - `python -c "from custom_components.ha_pronote.diff import LessonChange, NewGrade, NewInformation, ChangeType, DayLabel; print('ok')"` exits 0.
  </action>
  <verify>
    <automated>ruff check custom_components/ha_pronote/diff tests/test_diff &amp;&amp; pytest tests/test_diff/test_events.py tests/test_diff/test_stubs.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `custom_components/ha_pronote/diff/__init__.py`, `events.py`, `grades.py`, `notifications.py` exist.
    - `grep -c "ChangeType = Literal\\[" custom_components/ha_pronote/diff/events.py` returns 1.
    - `grep -E '"canceled"|"modified"|"teacher"|"room"' custom_components/ha_pronote/diff/events.py` returns at least 4 lines (one per value in the Literal).
    - `grep -c "@dataclass(frozen=True)" custom_components/ha_pronote/diff/events.py` returns 3 (LessonChange, NewGrade, NewInformation).
    - `grep -c "raise NotImplementedError" custom_components/ha_pronote/diff/grades.py` returns 1.
    - `grep -c "raise NotImplementedError" custom_components/ha_pronote/diff/notifications.py` returns 1.
    - `grep -rE "from homeassistant" custom_components/ha_pronote/diff` returns nothing.
    - `pytest tests/test_diff/test_events.py tests/test_diff/test_stubs.py` exits 0.
    - `ruff check custom_components/ha_pronote/diff tests/test_diff` exits 0.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Author 11 synthetic fixtures + tests/test_diff/conftest.py loader</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Fixture Sourcing" (D-10, D-11, D-23, D-25)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"tests/fixtures/synthetic/*.json" + §"tests/test_diff/conftest.py"
    - custom_components/ha_pronote/api/models.py (Plan 02-01) — `Snapshot.to_dict()` shape that synthetic fixtures must conform to
    - tests/fixtures/SPIKE-FINDINGS-bain3-311.md (Plan 02-02) — gives concrete examples of real lesson shape that synthetic fixtures should mirror
    - tests/fixtures/real/cancellation_T0.json (Plan 02-02) — shape reference
  </read_first>
  <behavior>
    - 11 synthetic fixture JSON files exist under `tests/fixtures/synthetic/`:
      - `empty_to_empty_T0.json` + `empty_to_empty_T1.json` (vacation: zero lessons → zero lessons)
      - `reorder_no_op_T0.json` + `reorder_no_op_T1.json` (3 identical lessons in different order)
      - `multi_change_T0.json` + `multi_change_T1.json` (3 lessons; one canceled, one room change, one teacher swap)
      - `first_poll_after_restart.json` (single fixture — used as the `new` arg with `previous=None`)
      - `lesson_removed_T0.json` + `lesson_removed_T1.json` (period rollover noise — should be silent if outside today/tomorrow window)
      - `lesson_added_T0.json` + `lesson_added_T1.json` (a new lesson appears at T1)
    - Each fixture parses as valid JSON with the 5 required top-level keys (`today`, `school_tz`, `lessons`, `grades`, `information`).
    - Every datetime string in every committed fixture has an explicit ISO offset (matches regex `[+-]\\d{2}:\\d{2}$`) — D-23 (no naive datetimes in committed fixtures).
    - Every fixture round-trips: `Snapshot.from_dict(json.loads(text)).to_dict() == json.loads(text)` (D-11).
    - `tests/test_diff/conftest.py` exposes a `load_fixture(name)` fixture that reads from either `tests/fixtures/real/` or `tests/fixtures/synthetic/` (whichever exists) and returns a `Snapshot`.
  </behavior>
  <action>
    Author the 11 hand-crafted synthetic fixtures + the `load_fixture` test helper. Synthetic fixtures cover combinatorics edge cases that the real spike (Plan 02-02) cannot reliably reproduce on demand.

    **1. Decide the synthetic-fixture date convention:**

    Use `today = "2026-05-04"` (a Monday — picks both a weekday and a regular school day in metropolitan France) for fixtures that need a deterministic "today" reference. The `school_tz` field varies by fixture to exercise the D-25 timezone matrix (Plan 02-04 parameterizes the test, but the fixture data itself encodes the school_tz so each fixture is self-contained).

    Use timezone offset `+11:00` for `Pacific/Noumea` (no DST), `+02:00` for `Europe/Paris` summer (May-Oct), `+01:00` for winter — date 2026-05-04 is summer-time in Paris.

    Lesson identity hypothesis from D-08 (start date, start time, end time, subject) — synthetic fixtures use this to construct unambiguous reorder/cancel/room/teacher scenarios.

    **2. Create `tests/fixtures/synthetic/empty_to_empty_T0.json`** (vacation):
    ```json
    {
      "today": "2026-05-04",
      "school_tz": "Pacific/Noumea",
      "lessons": [],
      "grades": [],
      "information": []
    }
    ```

    **3. Create `tests/fixtures/synthetic/empty_to_empty_T1.json`** (still vacation):
    Same content as T0. Diff result: `[]`.

    **4. Create `tests/fixtures/synthetic/reorder_no_op_T0.json`**: 3 lessons in order [A, B, C]:
    ```json
    {
      "today": "2026-05-04",
      "school_tz": "Pacific/Noumea",
      "lessons": [
        {
          "date": "2026-05-04",
          "start": "2026-05-04T08:00:00+11:00",
          "end":   "2026-05-04T09:00:00+11:00",
          "subject": "Mathematiques",
          "teacher": "M. Prof",
          "classroom": "Salle A1",
          "canceled": false,
          "status": ""
        },
        {
          "date": "2026-05-04",
          "start": "2026-05-04T09:00:00+11:00",
          "end":   "2026-05-04T10:00:00+11:00",
          "subject": "Histoire",
          "teacher": "Mme Profa",
          "classroom": "Salle B2",
          "canceled": false,
          "status": ""
        },
        {
          "date": "2026-05-04",
          "start": "2026-05-04T10:00:00+11:00",
          "end":   "2026-05-04T11:00:00+11:00",
          "subject": "SVT",
          "teacher": "M. Profb",
          "classroom": "Salle C3",
          "canceled": false,
          "status": ""
        }
      ],
      "grades": [],
      "information": []
    }
    ```

    **5. Create `tests/fixtures/synthetic/reorder_no_op_T1.json`**: SAME 3 lessons, REVERSED order [C, B, A]. Identity + content tuples identical to T0; only array order differs. Diff result MUST be `[]`.

    **6. Create `tests/fixtures/synthetic/multi_change_T0.json`**: 3 lessons today (date 2026-05-04) — Math at 08:00 (Salle A1, M. Prof, not canceled), Histoire at 09:00 (Salle B2, Mme Profa, not canceled), SVT at 10:00 (Salle C3, M. Profb, not canceled). Use `school_tz: "Europe/Paris"` and offset `+02:00` for variety.

    **7. Create `tests/fixtures/synthetic/multi_change_T1.json`**: same 3 identity tuples, but:
    - Math at 08:00 → `canceled: true` (status `"Cours annulé"`).
    - Histoire at 09:00 → `classroom` changed to `"Salle B5"` (room change).
    - SVT at 10:00 → `teacher` changed to `"Mme Profx"` (teacher swap, classroom unchanged).
    Diff result expected: 3 `LessonChange` events, one of each type (canceled, room, teacher).

    **8. Create `tests/fixtures/synthetic/first_poll_after_restart.json`**: a snapshot with 5 lessons today + 3 grades + 2 informations. Used as the `new` argument with `previous=None` to assert `diff_lessons(None, snap, "today") == []` regardless of how full the snapshot is.

    **9. Create `tests/fixtures/synthetic/lesson_removed_T0.json` + `lesson_removed_T1.json`**: 3 lessons in T0; T1 has only 2 (the third lesson identity tuple is GONE from T1). The "removed" lesson is on date `2026-05-03` (yesterday — outside today/tomorrow window). Diff result for `day="today"`: `[]` (period rollover noise — silent per D-10). For `day="today"` to filter on lessons-today, the "removed" lesson MUST not be on today's date; otherwise the diff would emit canceled.

    Actually, refine: per the SPIKE-FINDINGS algorithm decision, a lesson removed from today's window MAY emit `canceled` (Algorithm decision step 4 in the SPIKE-FINDINGS doc). Pick the date so that the "removed" lesson is OUTSIDE the today/tomorrow filter to test the silent-noise case. Document this clearly in the fixture's comment field (JSON doesn't support comments, so put a `_doc` key at top level: `"_doc": "Period rollover: a J-1 lesson present in T0 is gone in T1 — diff for day=today MUST be silent (D-10)."`).

    NOTE on `_doc` key: `Snapshot.from_dict` will reject unknown keys if `from_dict` is strict. To avoid this, EITHER:
    - Make `Snapshot.from_dict` tolerant of leading-underscore keys (skip them) — Plan 02-01 implementer's choice, document if added.
    - OR put the doc string in a sibling `.md` file: `tests/fixtures/synthetic/lesson_removed.md` describing the scenario. RECOMMENDED — keeps JSON clean.

    Use the `.md` companion file approach. Create `tests/fixtures/synthetic/_README.md` documenting all 11 fixtures' intent.

    **10. Create `tests/fixtures/synthetic/lesson_added_T0.json` + `lesson_added_T1.json`**: T0 has 2 lessons today; T1 has the same 2 PLUS a third newly-added lesson at 14:00. Diff result: depending on the algorithm decision in SPIKE-FINDINGS, either `[]` (silent — additions aren't change events) OR 1 `LessonChange(change_type="modified", before=None, after={...})`.

    **11. Create `tests/fixtures/synthetic/_README.md`**:
    ```markdown
    # Synthetic Diff Fixtures (D-10)

    Hand-crafted Snapshot.to_dict()-shaped JSON for combinatorics edge cases
    that the real-Pronote spike (Plan 02-02) cannot reliably reproduce on demand.

    All 11 fixtures conform to the D-11 round-trip invariant (verified by
    Plan 02-04's tests/test_fixtures.py). Datetimes are tz-aware ISO strings
    with explicit offset (D-23).

    | Fixture | Scenario | Expected diff result |
    |---|---|---|
    | empty_to_empty_T{0,1}.json | Vacation: zero lessons in both polls | [] |
    | reorder_no_op_T{0,1}.json | Same 3 lessons, different array order | [] |
    | multi_change_T{0,1}.json | 3 lessons; one canceled, one room change, one teacher swap | 3 LessonChange events, one of each kind |
    | first_poll_after_restart.json | Used as `new` with `previous=None` (single file) | [] regardless of snapshot size |
    | lesson_removed_T{0,1}.json | A J-1 lesson disappears (period rollover noise) | [] for day=today (silent per D-10) |
    | lesson_added_T{0,1}.json | A new lesson appears at T1 | Depends on SPIKE-FINDINGS Algorithm decision step 5 |

    Authoring constraints:
    - Datetimes ISO-8601 with explicit offset (D-23).
    - school_tz field varies (Pacific/Noumea + Europe/Paris) — Plan 02-04's
      pytest matrix (D-25) loops both timezones over each fixture.
    - Identity tuples (date, start, end, subject) deliberately chosen to
      exercise edge cases — see test_lessons_synthetic.py.

    ## Note on `lesson_removed_T0/T1` (PC-02-07 — accepted-as-is regression sentinel)

    `lesson_removed_T0/T1` keeps the J-1 lesson **outside** the `lessons_today`
    window: T0 has the J-1 lesson, T1 doesn't. The `api/` layer's
    `Snapshot.lessons_today` filter (D-16) prevents period-rollover noise from
    reaching the diff layer at all — by the time `diff_lessons` runs, the
    removed lesson is already filtered out for `day="today"`. The `events == []`
    assertion in `test_lesson_removed_outside_today_window_is_silent` is therefore
    structurally guaranteed (vacuously true) given the current `lessons_today`
    contract.

    The fixture is **kept as a regression sentinel** against future changes
    that might (a) widen `lessons_today` to include yesterday/tomorrow, or
    (b) move `diff_lessons` to operate on the full `Snapshot.lessons` window
    instead of the day-filtered slice. If either change ships and the filter
    is no longer the safety net, this test starts emitting events and the
    fixture's purpose flips from "structural invariant" to "real assertion".
    Do NOT delete the fixture even if the test "trivially passes" — that's
    by design.
    ```

    **12. Create `tests/test_diff/conftest.py`** per D-25, D-23 + PATTERNS.md §"tests/test_diff/conftest.py":

    ```python
    """Fixture loader for tests/test_diff/. NO PHACC autouse — diff/ is HA-free per D-19."""
    from __future__ import annotations

    import json
    from pathlib import Path

    import pytest

    from custom_components.ha_pronote.api.models import Snapshot

    FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


    @pytest.fixture
    def load_fixture():
        """Load a fixture by name from real/ or synthetic/.

        Returns the parsed `Snapshot`. tz-aware datetimes are reconstructed
        via `datetime.fromisoformat` (which preserves the explicit offset).

        Args:
            name: Either ``"real/cancellation_T0.json"`` or
                ``"synthetic/multi_change_T1.json"`` — relative path from
                tests/fixtures/.
        """

        def _load(name: str) -> Snapshot:
            path = FIXTURE_ROOT / name
            if not path.is_file():
                pytest.skip(f"fixture {name} not found (spike may have skipped this scenario)")
            raw = json.loads(path.read_text(encoding="utf-8"))
            return Snapshot.from_dict(raw)

        return _load


    @pytest.fixture
    def load_raw_fixture():
        """Load a fixture as raw dict (for tests that need to assert ISO strings)."""

        def _load(name: str) -> dict:
            path = FIXTURE_ROOT / name
            if not path.is_file():
                pytest.skip(f"fixture {name} not found")
            return json.loads(path.read_text(encoding="utf-8"))

        return _load
    ```

    Note: the `pytest.skip` for missing real fixtures is critical — Plan 02-02 may
    have completed `partial:` (only the cancellation scenario captured live). Tests
    that depend on `room_change` or `teacher_swap` real fixtures will skip rather
    than fail when those aren't present, AND the synthetic equivalents in
    `tests/fixtures/synthetic/multi_change_*.json` cover the same algorithm branches.

    **13. Verification commands:**
    - `python -c "
import json
from pathlib import Path
import sys
sys.path.insert(0, '.')
from custom_components.ha_pronote.api.models import Snapshot
for p in sorted(Path('tests/fixtures/synthetic').glob('*.json')):
    raw = json.loads(p.read_text())
    snap = Snapshot.from_dict(raw)
    rt = snap.to_dict()
    assert rt == raw, f'{p}: round-trip drift'
print('11 synthetic fixtures OK')"` exits 0 with the message.
    - `ls tests/fixtures/synthetic/*.json | wc -l` returns 11.
    - `grep -rE 'T[0-9]{2}:[0-9]{2}:[0-9]{2}[^+-]*"' tests/fixtures/synthetic/ | grep -v '+' | grep -v '^$'` returns nothing (every datetime has an offset).
  </action>
  <verify>
    <automated>ls tests/fixtures/synthetic/*.json | wc -l | grep -q '^11$' &amp;&amp; python -c "
import json
import sys
from pathlib import Path
sys.path.insert(0, '.')
from custom_components.ha_pronote.api.models import Snapshot
for p in sorted(Path('tests/fixtures/synthetic').glob('*.json')):
    raw = json.loads(p.read_text())
    snap = Snapshot.from_dict(raw)
    assert snap.to_dict() == raw, f'{p}: round-trip drift'
print('11 synthetic fixtures round-trip OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - 11 JSON files exist under `tests/fixtures/synthetic/`.
    - `tests/fixtures/synthetic/_README.md` exists documenting all 11 fixtures.
    - Every fixture round-trips through `Snapshot.from_dict`/`to_dict` cleanly.
    - `tests/test_diff/conftest.py` exists with `load_fixture` and `load_raw_fixture` fixtures using `pytest.skip` for missing real-fixture scenarios.
    - No naive datetimes in any committed fixture (every `T..:..:..` is followed by an offset).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Implement diff/lessons.py + comprehensive tests against real and synthetic fixtures</name>
  <read_first>
    - tests/fixtures/SPIKE-FINDINGS-bain3-311.md (Plan 02-02) — THE algorithm derivation source. Read §"Algorithm decision" verbatim — that's what diff_lessons MUST implement.
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Diff Algorithm" (D-05..D-09)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"diff/lessons.py" + §"tests/test_diff/test_lessons.py"
    - .planning/research/PITFALLS.md §"Pitfall 10" (the prior hypothesis SPIKE-FINDINGS confirms or refines)
    - custom_components/ha_pronote/api/models.py (Plan 02-01) — Lesson, Snapshot, lessons_today, lessons_tomorrow
    - custom_components/ha_pronote/diff/events.py (Task 1) — LessonChange, ChangeType, DayLabel
    - tests/fixtures/real/*.json (Plan 02-02 — all available scenarios)
    - tests/fixtures/synthetic/*.json (Task 2 — combinatorics)
  </read_first>
  <behavior>
    - `diff_lessons(None, snap_with_50_lessons, "today") == []` (D-08, ROADMAP success criterion #4: zero events on first poll).
    - For the synthetic `reorder_no_op` pair: `diff_lessons(prev, new, "today") == []` (Pitfall 10 reorder no-op).
    - For the synthetic `multi_change` pair: `diff_lessons` returns exactly 3 `LessonChange` events, one each of `change_type="canceled"`, `change_type="room"`, `change_type="teacher"`.
    - For the synthetic `empty_to_empty` pair: `diff_lessons(prev, new, "today") == []`.
    - For the real `cancellation_T0/T1` pair (if present): `diff_lessons(prev, new, "today")` includes at least one `LessonChange(change_type="canceled", ...)` matching the SPIKE-FINDINGS Concrete-diffs section.
    - For the real `room_change_T0/T1` pair (if present): includes at least one `LessonChange(change_type="room", ...)` and ZERO `change_type="canceled"` events for that lesson identity (the bain3#311 anti-pattern — a room change must NOT be reported as a canceled+added pair).
    - For the real `teacher_swap_T0/T1` pair (if present): includes at least one `LessonChange(change_type="teacher", ...)`.
    - The `day` parameter filters: `diff_lessons(prev, new, "today")` only inspects `prev.lessons_today` and `new.lessons_today`; same for `"tomorrow"`.
    - Every emitted `LessonChange.before` / `.after` is a JSON-serializable dict (not a Lesson object) — already enforced by the `to_payload()` shape since it uses `Lesson.to_dict()`.
    - All tests run in well under 1 second per test (pytest-timeout=1 from Plan 02-04 will enforce).
  </behavior>
  <action>
    Implement the central diff algorithm. The SPIKE-FINDINGS-bain3-311.md document (Plan 02-02 output) is the source of truth — open it, read §"Algorithm decision" carefully, and translate that decision into code.

    **1. Read SPIKE-FINDINGS-bain3-311.md and extract the algorithm parameters:**

    From SPIKE-FINDINGS, capture the verdict on:
    - Identity key (D-08): confirmed `(date, start_time, end_time, subject)` OR refined to something else.
    - Content key: confirmed `(canceled, status, classroom, teacher)` OR refined.
    - bain3#311 paired-lesson behavior: Option A (paired entries), B (one entry replaces), or C (other) — and how to consolidate.
    - Algorithm steps for added/removed lessons.

    If SPIKE-FINDINGS confirms the D-08 hypothesis verbatim, implement that. If it refines, implement the refined version. Cite the SPIKE-FINDINGS section in the code comment at the top of `diff/lessons.py`.

    **2. Create `custom_components/ha_pronote/diff/lessons.py`:**

    Skeleton (the EXACT bodies depend on SPIKE-FINDINGS, but the structure is fixed):

    ```python
    """Diff lessons — identity vs content key, room vs cancellation discrimination.

    Algorithm derivation: tests/fixtures/SPIKE-FINDINGS-bain3-311.md (D-06, D-07).
    Read that document FIRST — its §"Algorithm decision" is the contract this
    module implements.

    Frozen taxonomy (D-09, ROADMAP Phase 4 success criterion #1):
      - "canceled" — lesson disappeared OR canceled flag flipped True
      - "modified" — content changed but identity matched (catch-all)
      - "teacher"  — teacher field changed (subset of "modified")
      - "room"     — classroom field changed (subset of "modified")

    First-poll invariant (D-08, EVENT-04 cross-cutting tracker for Phase 4):
      diff_lessons(None, snapshot, day) -> [] regardless of snapshot size.

    Reorder no-op invariant (Pitfall 10):
      Same identity + content tuples regardless of array order -> [].
    """
    from __future__ import annotations

    from datetime import time
    from typing import TYPE_CHECKING

    from .events import LessonChange

    if TYPE_CHECKING:
        from custom_components.ha_pronote.api.models import Lesson, Snapshot

        from .events import DayLabel

    # Identity key (D-08, spike-locked per SPIKE-FINDINGS-bain3-311.md):
    #   date + start time + end time + subject
    # Refinement: substitute teacher is a CONTENT change, NOT an identity change.
    def _identity_key(lesson: "Lesson") -> tuple:
        return (lesson.date, lesson.start.time(), lesson.end.time(), lesson.subject)


    # Content key (D-08, spike-locked):
    #   canceled flag + raw status string + classroom + teacher
    def _content_key(lesson: "Lesson") -> tuple:
        return (lesson.canceled, lesson.status, lesson.classroom, lesson.teacher)


    def _classify_change(before: "Lesson", after: "Lesson") -> str:
        """Choose the most specific change_type (D-09) given identity match.

        Order matters: canceled > room > teacher > modified.
        """
        if after.canceled and not before.canceled:
            return "canceled"
        if before.canceled and not after.canceled:
            # Lesson uncanceled — Pitfall 10 edge case. Treated as modified.
            return "modified"
        if before.classroom != after.classroom:
            return "room"
        if before.teacher != after.teacher:
            return "teacher"
        return "modified"


    def diff_lessons(
        previous: "Snapshot | None",
        new: "Snapshot",
        day: "DayLabel",
    ) -> list[LessonChange]:
        """Return LessonChange events between two snapshots for the requested day.

        Args:
            previous: previous Snapshot, or None on first poll after restart.
            new: current Snapshot.
            day: "today" or "tomorrow" — selects the lesson slice to compare.

        Returns:
            List of LessonChange events. Empty when previous is None
            (D-08 invariant), or when the day's lessons are identical
            modulo array order (reorder no-op, Pitfall 10).
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

        # Identity tuples present in both T0 and T1 — content diff per D-08.
        for identity in prev_by_identity.keys() & new_by_identity.keys():
            before = prev_by_identity[identity]
            after = new_by_identity[identity]
            if _content_key(before) == _content_key(after):
                continue   # identical lesson, no change
            events.append(
                LessonChange(
                    change_type=_classify_change(before, after),  # type: ignore[arg-type]
                    day=day,
                    lesson_date=after.date,
                    subject=after.subject,
                    before=before.to_dict(),
                    after=after.to_dict(),
                )
            )

        # Identity tuples present only in T0 (lesson removed).
        # SPIKE-FINDINGS-bain3-311.md §"Algorithm decision" step 4 records the
        # verdict: either "emit canceled on removal" OR "silent on removal".
        # The executor reads SPIKE-FINDINGS, picks ONE branch, and writes it
        # uncommented. NEVER leave commented-out alternative branches in
        # production code (PC-02-06).
        for identity in prev_by_identity.keys() - new_by_identity.keys():
            before = prev_by_identity[identity]
            # ↓↓↓ EXECUTOR DECISION POINT ↓↓↓
            #
            # If SPIKE-FINDINGS verdict for "lesson removed from lessons_today"
            # is "emit canceled":  REPLACE the `pass` below with:
            #
            #     events.append(
            #         LessonChange(
            #             change_type="canceled",
            #             day=day,
            #             lesson_date=before.date,
            #             subject=before.subject,
            #             before=before.to_dict(),
            #             after=None,
            #         )
            #     )
            #
            # If SPIKE-FINDINGS verdict is "silent":  DELETE this entire `for`
            # loop (it serves no purpose in silent-mode). Do NOT keep it as a
            # `pass`-only loop with a TODO — the AST guard / static check in
            # Plan 02-04 forbids "Uncomment" / "TODO: spike" markers.
            #
            # ↑↑↑ EXECUTOR DECISION POINT ↑↑↑
            del before  # placeholder removed by the chosen branch above

        # Identity tuples present only in T1 (lesson added).
        # SPIKE-FINDINGS-bain3-311.md §"Algorithm decision" step 5 records the
        # verdict: either "emit modified on addition" OR "silent on addition"
        # (default-recommended in the spike: silent — additions are normal
        # mid-week scheduling and are not change events from a parent's
        # perspective).
        for identity in new_by_identity.keys() - prev_by_identity.keys():
            after = new_by_identity[identity]
            # ↓↓↓ EXECUTOR DECISION POINT ↓↓↓
            #
            # If SPIKE-FINDINGS verdict for "lesson added to lessons_today" is
            # "emit modified":  REPLACE the `pass` below with:
            #
            #     events.append(
            #         LessonChange(
            #             change_type="modified",
            #             day=day,
            #             lesson_date=after.date,
            #             subject=after.subject,
            #             before=None,
            #             after=after.to_dict(),
            #         )
            #     )
            #
            # If SPIKE-FINDINGS verdict is "silent":  DELETE this entire `for`
            # loop (do NOT keep a `pass`-only loop with a TODO).
            #
            # ↑↑↑ EXECUTOR DECISION POINT ↑↑↑
            del after  # placeholder removed by the chosen branch above

        return events
    ```

    **SPIKE-FINDINGS-driven branch resolution (PC-02-06):**

    The two `EXECUTOR DECISION POINT` blocks above are NOT optional comments —
    they are placeholders the executor MUST resolve at execute time. Step:

    1. Open `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` and locate the
       "Algorithm decision" section (steps 4 and 5). Plan 02-02 produced this
       file with concrete verdicts.

    2. For step 4 (lesson removed from `lessons_today`):
       - Verdict says "emit canceled on removal" → write the production
         `events.append(LessonChange(change_type="canceled", …))` block AND
         add a positive-emission test in `tests/test_diff/test_lessons_synthetic.py`
         that asserts the emitted event has `change_type="canceled"`.
       - Verdict says "silent on removal" → DELETE the `for` loop entirely
         (no commented alternative, no `pass`-only stub, no `TODO` marker).
         The `lesson_removed_T0/T1` synthetic fixtures act as a regression
         sentinel — the existing test asserts `events == []`.

    3. For step 5 (lesson added to `lessons_today`): same rule, with
       `change_type="modified"` and the `lesson_added_T0/T1` synthetic fixtures.

    4. Update the module docstring to record which branch was chosen and cite
       the SPIKE-FINDINGS section line.

    **Forbidden patterns (PC-02-06):** commented-out production code, `pass`-only
    `for` loops with `TODO` notes, and any `# Uncomment` / `# TODO: spike` /
    `# pragma:.* spike` markers in `custom_components/ha_pronote/diff/` or
    `tests/test_diff/`. Plan 02-04 Task 1 adds a CI static check that fails
    the build if any such marker survives execute time.

    **3. Special case for bain3#311 — paired canceled+room-change consolidation:**

    If SPIKE-FINDINGS shows Option A (pronotepy returns BOTH the canceled lesson AND the new lesson at the same identity tuple — i.e. the identity key isn't actually unique because pronotepy keeps both records), the algorithm above breaks (a Python dict overwrites duplicate keys). Detect this case:

    ```python
    def _build_identity_index(lessons: list["Lesson"]) -> dict[tuple, list["Lesson"]]:
        """Group lessons by identity tuple. Lists handle bain3#311 paired-lesson case."""
        out: dict[tuple, list["Lesson"]] = {}
        for L in lessons:
            out.setdefault(_identity_key(L), []).append(L)
        return out
    ```

    And in `diff_lessons`, replace the dict-comprehension with `_build_identity_index(...)`. When an identity tuple has 2 lessons (one canceled=True + one canceled=False), consolidate per SPIKE-FINDINGS Algorithm decision step 6 — typically into a single `change_type="room"` event using the canceled lesson as `before` and the non-canceled as `after`.

    The executor of this task picks dict OR `_build_identity_index` per the SPIKE-FINDINGS verdict on Option A/B/C. If the verdict is unclear, default to `_build_identity_index` (defensive — handles both cases without breaking).

    **4. Update `tests/test_diff/test_lessons.py`** (already partially scaffolded by Task 2):

    ```python
    """Diff lessons tests — covers ROADMAP success criteria #3 and #4.

    NOTE: Plan 02-04 wraps these in a tz-matrix parametrize (D-25). For now
    they run on whatever the test runner's local TZ is — the assertions use
    fixture-local school_tz, so they pass regardless. Plan 02-04's matrix is
    belt-and-suspenders for any HA-side code that lands later.
    """
    from __future__ import annotations

    from datetime import date

    import pytest

    from custom_components.ha_pronote.diff import LessonChange, diff_lessons


    class TestFirstPollInvariant:
        def test_previous_none_with_empty_new_returns_empty(self, load_fixture):
            new = load_fixture("synthetic/empty_to_empty_T1.json")
            assert diff_lessons(None, new, "today") == []

        def test_previous_none_with_full_new_returns_empty(self, load_fixture):
            """D-08, ROADMAP success criterion #4: zero events on first poll."""
            new = load_fixture("synthetic/first_poll_after_restart.json")
            # Sanity: snapshot has lessons (otherwise the test is vacuous).
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
        """Three identity-stable changes in one poll — exercises every change_type."""

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

        def test_emits_one_room_event(self, load_fixture):
            t0 = load_fixture("synthetic/multi_change_T0.json")
            t1 = load_fixture("synthetic/multi_change_T1.json")
            events = diff_lessons(t0, t1, "today")
            room = [e for e in events if e.change_type == "room"]
            assert len(room) == 1

        def test_emits_one_teacher_event(self, load_fixture):
            t0 = load_fixture("synthetic/multi_change_T0.json")
            t1 = load_fixture("synthetic/multi_change_T1.json")
            events = diff_lessons(t0, t1, "today")
            teacher = [e for e in events if e.change_type == "teacher"]
            assert len(teacher) == 1

        def test_change_type_is_one_of_the_four_frozen_values(self, load_fixture):
            t0 = load_fixture("synthetic/multi_change_T0.json")
            t1 = load_fixture("synthetic/multi_change_T1.json")
            events = diff_lessons(t0, t1, "today")
            for e in events:
                assert e.change_type in {"canceled", "modified", "teacher", "room"}


    class TestRealCancellation:
        """ROADMAP success criterion #3: real fixture from the spike (D-05)."""

        def test_real_cancellation_emits_at_least_one_canceled_event(self, load_fixture):
            t0 = load_fixture("real/cancellation_T0.json")  # may pytest.skip if not present
            t1 = load_fixture("real/cancellation_T1.json")
            events = diff_lessons(t0, t1, "today")
            assert any(e.change_type == "canceled" for e in events), (
                "Expected at least one canceled event from the live spike capture. "
                "Inspect tests/fixtures/SPIKE-FINDINGS-bain3-311.md if this fails — "
                "the algorithm may need refinement per the empirical findings."
            )


    class TestRealRoomChange:
        """ROADMAP success criterion #3: real fixture from the spike (D-05).

        Critical assertion — Pitfall 10 / bain3#311: a room change must NOT be
        reported as a canceled+added pair.
        """

        def test_real_room_change_emits_room_event(self, load_fixture):
            t0 = load_fixture("real/room_change_T0.json")
            t1 = load_fixture("real/room_change_T1.json")
            events = diff_lessons(t0, t1, "today")
            assert any(e.change_type == "room" for e in events), (
                "Expected at least one room event from the live spike capture."
            )

        def test_real_room_change_does_not_emit_phantom_canceled(self, load_fixture):
            """bain3#311: the room-changed lesson must NOT appear as canceled."""
            t0 = load_fixture("real/room_change_T0.json")
            t1 = load_fixture("real/room_change_T1.json")
            events = diff_lessons(t0, t1, "today")
            # If both a canceled + room event share the same lesson_date+subject,
            # that's the bain3#311 anti-pattern.
            canceled = [(e.lesson_date, e.subject) for e in events if e.change_type == "canceled"]
            room = [(e.lesson_date, e.subject) for e in events if e.change_type == "room"]
            overlap = set(canceled) & set(room)
            assert not overlap, (
                f"bain3#311 anti-pattern: same lesson reported as both canceled AND room: {overlap}"
            )


    class TestRealTeacherSwap:
        def test_real_teacher_swap_emits_teacher_event(self, load_fixture):
            t0 = load_fixture("real/teacher_swap_T0.json")
            t1 = load_fixture("real/teacher_swap_T1.json")
            events = diff_lessons(t0, t1, "today")
            assert any(e.change_type == "teacher" for e in events), (
                "Expected at least one teacher event from the live spike capture."
            )


    class TestPayloadShape:
        def test_event_payload_is_json_serializable(self, load_fixture):
            import json
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
                # ISO date format: YYYY-MM-DD
                assert isinstance(payload["lesson_date"], str)
                date.fromisoformat(payload["lesson_date"])  # raises if not ISO


    class TestDaySelector:
        def test_day_today_uses_lessons_today_only(self, load_fixture):
            """The day argument selects the lesson slice."""
            # multi_change fixtures have all lessons on `today` — so day=tomorrow
            # should emit zero events.
            t0 = load_fixture("synthetic/multi_change_T0.json")
            t1 = load_fixture("synthetic/multi_change_T1.json")
            events = diff_lessons(t0, t1, "tomorrow")
            assert events == []
    ```

    **5. Create `tests/test_diff/test_lessons_synthetic.py`** as a thin extension covering combinatorics-only paths the real fixtures don't (lesson_added, lesson_removed):

    ```python
    """Combinatorics edge cases — synthetic fixtures only (D-10).

    These complement test_lessons.py by covering paths that real spike fixtures
    can't reliably reproduce (period rollover noise, lesson added in the middle
    of a week).
    """
    from __future__ import annotations

    from custom_components.ha_pronote.diff import diff_lessons


    def test_lesson_removed_outside_today_window_is_silent(load_fixture):
        """D-10: a J-1 lesson disappearing should NOT emit for day=today."""
        t0 = load_fixture("synthetic/lesson_removed_T0.json")
        t1 = load_fixture("synthetic/lesson_removed_T1.json")
        events = diff_lessons(t0, t1, "today")
        # The removed lesson is on yesterday's date; today's window is unaffected.
        assert events == []


    def test_lesson_added_default_silent(load_fixture):
        """Algorithm decision step 5 default — lesson additions are silent.

        If SPIKE-FINDINGS upgrades this to emit "modified", the executor of
        this task updates the assertion AND documents the change in the docstring.
        """
        t0 = load_fixture("synthetic/lesson_added_T0.json")
        t1 = load_fixture("synthetic/lesson_added_T1.json")
        events = diff_lessons(t0, t1, "today")
        # Default: silent. Update if SPIKE-FINDINGS confirms emission.
        assert events == [] or all(e.change_type == "modified" for e in events)
    ```

    **6. Verification commands:**
    - `ruff format custom_components/ha_pronote/diff tests/test_diff`
    - `ruff check custom_components/ha_pronote/diff tests/test_diff`
    - `pytest tests/test_diff/ -v` — all pass.
    - `pytest tests/test_diff/ --cov=custom_components/ha_pronote/diff --cov-report=term-missing` — coverage on `diff/lessons.py` ≥ 90% (the gate threshold; Plan 02-04 enforces in CI).
    - `python -c "from custom_components.ha_pronote.diff import diff_lessons; print('ok')"` exits 0.
  </action>
  <verify>
    <automated>ruff check custom_components/ha_pronote/diff tests/test_diff &amp;&amp; pytest tests/test_diff/ -v &amp;&amp; pytest tests/test_diff/ --cov=custom_components/ha_pronote/diff --cov-report=term-missing</automated>
  </verify>
  <acceptance_criteria>
    - `custom_components/ha_pronote/diff/lessons.py` exists and contains `def diff_lessons` with signature `(previous, new, day)`.
    - `grep -c "if previous is None" custom_components/ha_pronote/diff/lessons.py` returns at least 1 (D-08 first-poll invariant).
    - `grep -E '"canceled"|"modified"|"teacher"|"room"' custom_components/ha_pronote/diff/lessons.py` returns at least 4 lines covering all 4 change_type values.
    - `pytest tests/test_diff/ -v` exits 0 with at least 18 tests collected (some may pytest.skip if Plan 02-02 was `partial:`).
    - `pytest tests/test_diff/ --cov=custom_components/ha_pronote/diff --cov-report=term` shows ≥90% coverage on `diff/lessons.py` (NOT on the whole `diff/` — the omit list in Plan 02-04 will exclude grades.py and notifications.py).
    - `grep -c "SPIKE-FINDINGS" custom_components/ha_pronote/diff/lessons.py` returns at least 1 (the docstring cites the source).
    - `grep -rE "from homeassistant" custom_components/ha_pronote/diff tests/test_diff` returns nothing.
    - `grep -c "Uncomment if SPIKE" custom_components/ha_pronote/diff/lessons.py` returns 0 (PC-02-06 — no commented-out branch points survived execute time).
    - `grep -rE "(# Uncomment|# TODO: spike|# pragma:.* spike|EXECUTOR DECISION POINT)" custom_components/ha_pronote/diff/ tests/test_diff/` returns nothing — every executor decision point was resolved into uncommented production code OR deleted (PC-02-06).
    - **SPIKE-FINDINGS-driven test addition (PC-02-06):** When `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` records `"emit canceled on removal"` for Algorithm decision step 4, `grep -q 'change_type="canceled"' tests/test_diff/test_lessons_synthetic.py` succeeds (a positive-emission test for the `lesson_removed_T0/T1` fixture pair exists). When SPIKE-FINDINGS records `"silent on removal"`, `grep -q "lesson_removed_T1.json" tests/test_diff/test_lessons_synthetic.py` succeeds AND that test asserts `events == []`. Either branch — but never both, never neither.
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `previous: Snapshot \| None` (untrusted across HA restart) → `diff_lessons` | A previous snapshot may be stale, partially populated, or shaped by an older pronotepy version. The first-poll invariant (D-08) is the safety mechanism. |
| `LessonChange.before` / `.after` (dict, JSON-serializable) → Phase 4 `hass.bus.async_fire` | The diff's output crosses into HA's event bus. Anything in `before`/`after` becomes part of an automation trigger payload. |
| Synthetic fixture JSON (committed) → `Snapshot.from_dict` | Hand-authored data crossing the dataclass boundary. The schema-roundtrip test (Plan 02-04) is the gate. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-03-01 | Tampering / Information Disclosure | `LessonChange.before` / `.after` payloads forwarded to bus | mitigate | The dict shape comes from `Lesson.to_dict()` (Plan 02-01) which contains ONLY plain values (no pronotepy back-refs — D-24, Anti-Pattern 5). Test `test_event_payload_is_json_serializable` (Task 3) asserts `json.dumps` succeeds. **Severity: LOW** (Phase 2 boundary; full automation surface is Phase 4). |
| T-02-03-02 | Tampering | A maintainer adds a 5th `change_type` value without updating the frozen taxonomy | mitigate | `test_change_type_taxonomy_is_exactly_four_values` (Task 1) asserts `set(get_args(ChangeType)) == {"canceled", "modified", "teacher", "room"}`. Adding a 5th value fails CI. **Severity: MEDIUM** — would silently break Phase 4 automation contracts. |
| T-02-03-03 | Information Disclosure | bain3#311 false-positive flood — phantom `canceled` events for every room change | mitigate | `test_real_room_change_does_not_emit_phantom_canceled` asserts no overlap of (lesson_date, subject) between canceled and room events. SPIKE-FINDINGS-bain3-311.md §"Algorithm decision" step 6 documents the consolidation rule. **Severity: HIGH** (this is the entire reason Phase 2 has a spike). |
| T-02-03-04 | Spoofing | Synthetic fixture authoring drift — committed fixture violates `Snapshot.to_dict()` shape | mitigate | Task 2 verification gate runs `Snapshot.from_dict / to_dict` round-trip on every committed fixture. Plan 02-04 encodes this as `tests/test_fixtures.py` for CI enforcement. **Severity: LOW** — caught in pre-commit if the developer runs the verify command. |
| T-02-03-05 | Denial of Service | Period rollover noise (every Monday morning a chunk of last-week's lessons disappear) → false-positive event flood | mitigate | `test_lesson_removed_outside_today_window_is_silent` (Task 3) covers the synthetic case. The day-window filtering (`previous.lessons_today` vs full `previous.lessons`) is the primary defense — only lessons in the today/tomorrow slice are inspected. **Severity: MEDIUM** — would spam users with notifications every Monday. |
</threat_model>

<verification>
**Plan-level checks:**

1. **diff/ subpackage HA-free (D-19):**
   - `grep -rE "from homeassistant|import homeassistant" custom_components/ha_pronote/diff tests/test_diff` returns nothing.

2. **Frozen taxonomy locked (D-09):**
   - `grep -E '"canceled".*"modified".*"teacher".*"room"|ChangeType = Literal' custom_components/ha_pronote/diff/events.py` finds exactly the 4-value Literal definition.
   - `pytest tests/test_diff/test_events.py::test_change_type_taxonomy_is_exactly_four_values` exits 0.

3. **First-poll invariant locked (D-08):**
   - `grep -c "if previous is None" custom_components/ha_pronote/diff/lessons.py` returns ≥1.
   - `pytest tests/test_diff/test_lessons.py::TestFirstPollInvariant -v` exits 0.

4. **Real-fixture diff works (ROADMAP success criterion #3):**
   - `pytest tests/test_diff/test_lessons.py::TestRealCancellation tests/test_diff/test_lessons.py::TestRealRoomChange tests/test_diff/test_lessons.py::TestRealTeacherSwap -v` exits 0 (or skips per Plan 02-02 `partial:` outcome — skips count as pass for the verification gate).

5. **Stubs raise NotImplementedError (D-02):**
   - `pytest tests/test_diff/test_stubs.py -v` exits 0.

6. **All 11 synthetic fixtures conform to the schema:**
   - The Task 2 verify command (the inline Python script) exits 0.

7. **Coverage on diff/lessons.py ≥ 90% (DIST-05):**
   - `pytest tests/test_diff/ --cov=custom_components/ha_pronote/diff/lessons --cov-fail-under=90` exits 0.

8. **All Phase 1 + Plan 02-01 + Plan 02-02 contracts preserved:**
   - `pytest tests/test_init.py tests/test_manifest.py tests/test_api/ tests/test_scripts/` exits 0 (existing tests still pass).
</verification>

<success_criteria>
- `custom_components/ha_pronote/diff/` contains 4 Python files: `__init__.py`, `events.py`, `lessons.py`, `grades.py`, `notifications.py` (5 files total).
- 11 synthetic fixture JSONs in `tests/fixtures/synthetic/` + `_README.md`.
- 5 test files in `tests/test_diff/`: `__init__.py`, `conftest.py`, `test_events.py`, `test_lessons.py`, `test_lessons_synthetic.py`, `test_stubs.py` (6 files total).
- `pytest tests/test_diff/ -v` exits 0 with at least 18 tests collected (some may skip if Plan 02-02 partial).
- ROADMAP success criterion #3 satisfied (real cancellation_T0/T1 → emits canceled; room_change_T0/T1 → emits room WITHOUT phantom canceled).
- ROADMAP success criterion #4 partially satisfied: zero events on first poll, zero events on pure reorder. Coverage gate ≥90% is finalized in Plan 02-04 CI workflow.
- EVENT-05 satisfied: identity vs content key separation produces an unambiguous `change_type`.
- D-02 honored: `diff_grades` and `diff_notifications` raise `NotImplementedError`; their dataclasses (`NewGrade`, `NewInformation`) are locked.
- Zero `homeassistant.*` imports in any new file (Plan 02-04's AST guard re-verifies).
- All 5 STRIDE threats are mitigated and verified.
</success_criteria>

<output>
After completion, create `.planning/phases/02-api-diff-layer-ha-free/02-03-SUMMARY.md` documenting:
- Which `Algorithm decision` branch from SPIKE-FINDINGS was implemented (steps 4 and 5 — silent default vs emit).
- Whether the bain3#311 paired-lesson special case (Option A consolidation) was needed in the actual implementation, or whether the dict-by-identity-key approach was sufficient (Option B/C).
- Coverage on `diff/lessons.py` (must be ≥90% locally; Plan 02-04 enforces in CI).
- Test count breakdown (synthetic vs real-fixture, real fixtures skipped or run).
- Phase 4 hand-off: pointer to `LessonChange.to_payload()` shape as the bus event payload contract.
</output>
</content>
</invoke>