"""Pure diff functions over Snapshot. HA-free per D-19.

Public surface (consumed by Phase 4 coordinator):

- ``diff_lessons(previous, new, day) -> list[LessonChange]``
- ``diff_grades(previous, new) -> list[NewGrade]`` (Phase 4 fills body)
- ``diff_notifications(previous, new) -> list[NewInformation]`` (Phase 4 fills body)
- ``LessonChange``, ``NewGrade``, ``NewInformation``, ``ChangeType``, ``DayLabel`` (types)
"""

from __future__ import annotations

from .events import ChangeType, DayLabel, LessonChange, NewGrade, NewInformation
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
