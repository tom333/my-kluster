"""Event dataclasses -- Phase 4 routes these onto hass.bus.async_fire.

D-09 + ROADMAP Phase 4 success criterion #1 + FEATURES.md "Rich
pronote_schedule_changed events": the four ``change_type`` values are FROZEN.
Adding or renaming a value is a breaking change for downstream automations.

C-01: single import surface -- Phase 4 imports ``LessonChange``, ``NewGrade``,
``NewInformation``, ``ChangeType``, ``DayLabel`` from
``custom_components.ha_pronote.diff``.

Pattern 3 (ARCHITECTURE.md lines 260-278) -- ``to_payload()`` shape is the
contract Phase 4's coordinator forwards verbatim into the bus event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import date as Date

ChangeType = Literal["canceled", "modified", "teacher", "room"]
DayLabel = Literal["today", "tomorrow"]


@dataclass(frozen=True)
class LessonChange:
    """A single lesson-level change between two snapshots.

    Attributes:
        change_type: One of the four FROZEN taxonomy values (D-09).
        day: Which day this change applies to (``"today"`` or ``"tomorrow"``).
        lesson_date: The ISO date of the changed lesson.
        subject: The lesson's subject name (anonymized in fixtures).
        before: ``Lesson.to_dict()`` of the T0 entry, or ``None`` for "added"-shaped events.
        after: ``Lesson.to_dict()`` of the T1 entry, or ``None`` for "removed"-shaped events.
    """

    change_type: ChangeType
    day: DayLabel
    lesson_date: Date
    subject: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None

    def to_payload(self) -> dict[str, Any]:
        """JSON-serializable dict matching ARCHITECTURE.md Pattern 3 schema.

        Phase 4 forwards this verbatim into ``hass.bus.async_fire``.
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
    """Type contract locked in Phase 2; ``diff_grades`` body lands in Phase 4 (D-02).

    Field list MUST match what Phase 4's ``diff_grades`` will produce.
    """

    subject: str
    value: str
    out_of: str
    coefficient: str
    date: Date

    def to_payload(self) -> dict[str, Any]:
        """JSON-serializable dict for Phase 4's bus event payload."""
        return {
            "subject": self.subject,
            "value": self.value,
            "out_of": self.out_of,
            "coefficient": self.coefficient,
            "date": self.date.isoformat(),
        }


@dataclass(frozen=True)
class NewInformation:
    """Type contract locked in Phase 2; ``diff_notifications`` body lands in Phase 4 (D-02).

    Field list MUST match what Phase 4's ``diff_notifications`` will produce.
    """

    info_id: str
    title: str
    sender: str
    date: Date
    excerpt: str

    def to_payload(self) -> dict[str, Any]:
        """JSON-serializable dict for Phase 4's bus event payload."""
        return {
            "info_id": self.info_id,
            "title": self.title,
            "sender": self.sender,
            "date": self.date.isoformat(),
            "excerpt": self.excerpt,
        }
