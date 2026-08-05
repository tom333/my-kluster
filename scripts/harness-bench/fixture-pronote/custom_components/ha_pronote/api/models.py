"""Plain serializable dataclasses for the Phase 2 → Phase 3 API surface (D-11, D-16, D-23).

All datetimes are tz-aware (TIME-04). ``from_dict`` rejects naive ISO datetimes
to enforce the contract early. The dataclasses are frozen so the diff layer can
treat them as values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .errors import ParseError


def _parse_aware_datetime(value: str, field_name: str) -> datetime:
    """Parse an ISO datetime string and reject naive results (D-23)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ParseError(f"naive datetime in fixture for field {field_name!r}")
    return dt


@dataclass(frozen=True)
class Lesson:
    """A single Pronote lesson entry, tz-aware (D-11, D-23)."""

    date: date
    start: datetime
    end: datetime
    subject: str
    teacher: str
    classroom: str
    canceled: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (datetimes / dates as ISO strings)."""
        return {
            "date": self.date.isoformat(),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "subject": self.subject,
            "teacher": self.teacher,
            "classroom": self.classroom,
            "canceled": self.canceled,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lesson:
        """Reconstruct from a ``to_dict`` payload. Rejects naive datetimes (D-23)."""
        return cls(
            date=date.fromisoformat(data["date"]),
            start=_parse_aware_datetime(data["start"], "start"),
            end=_parse_aware_datetime(data["end"], "end"),
            subject=data["subject"],
            teacher=data["teacher"],
            classroom=data["classroom"],
            canceled=bool(data["canceled"]),
            status=data["status"],
        )


@dataclass(frozen=True)
class Grade:
    """A single Pronote grade entry. ``value`` stays raw (Phase 4 normalizes)."""

    subject: str
    value: str
    out_of: str
    coefficient: str
    date: date
    # Phase 4 additions — pronotepy attribute name → model field name mapping:
    # raw.average → class_average  (pronotepy uses "average" for class avg, NOT "class_average")
    # raw.max     → class_max
    # raw.min     → class_min
    # raw.comment → comment
    # All default to "" so existing Phase 2 fixtures round-trip without change.
    class_average: str = ""
    class_min: str = ""
    class_max: str = ""
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "subject": self.subject,
            "value": self.value,
            "out_of": self.out_of,
            "coefficient": self.coefficient,
            "date": self.date.isoformat(),
            "class_average": self.class_average,  # Phase 4
            "class_min": self.class_min,  # Phase 4
            "class_max": self.class_max,  # Phase 4
            "comment": self.comment,  # Phase 4
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Grade:
        """Reconstruct from a ``to_dict`` payload."""
        return cls(
            subject=data["subject"],
            value=data["value"],
            out_of=data["out_of"],
            coefficient=data["coefficient"],
            date=date.fromisoformat(data["date"]),
            class_average=data.get("class_average", ""),  # Phase 4 — default "" for old fixtures
            class_min=data.get("class_min", ""),
            class_max=data.get("class_max", ""),
            comment=data.get("comment", ""),
        )


@dataclass(frozen=True)
class Information:
    """A single Pronote information / survey entry, tz-aware (D-23)."""

    info_id: str
    title: str
    sender: str
    date: datetime
    excerpt: str
    read: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "info_id": self.info_id,
            "title": self.title,
            "sender": self.sender,
            "date": self.date.isoformat(),
            "excerpt": self.excerpt,
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Information:
        """Reconstruct from a ``to_dict`` payload. Rejects naive datetimes."""
        return cls(
            info_id=data["info_id"],
            title=data["title"],
            sender=data["sender"],
            date=_parse_aware_datetime(data["date"], "date"),
            excerpt=data["excerpt"],
            read=bool(data["read"]),
        )


@dataclass(frozen=True)
class Snapshot:
    """A single fetch result spanning J-7 → J+14 (D-15, D-16)."""

    today: date
    school_tz: str
    lessons: list[Lesson] = field(default_factory=list)
    grades: list[Grade] = field(default_factory=list)
    information: list[Information] = field(default_factory=list)
    # Phase 4 additions — fetched alongside grades in executor (RESEARCH gap #5).
    # Period.overall_average is a @property making a fresh HTTP call — MUST be
    # fetched inside fetch_all (executor) and stored here. Sensor reads this string
    # directly; never calls Period.overall_average from native_value (PITFALL 3).
    overall_average: str = ""  # Period.overall_average comma-string e.g. "14,50"; "-1" = no grades
    period_name: str = ""  # Period.name e.g. "Trimestre 2"

    @property
    def lessons_today(self) -> list[Lesson]:
        """Subset of ``lessons`` whose date == ``self.today`` (D-16)."""
        return [lesson for lesson in self.lessons if lesson.date == self.today]

    @property
    def lessons_tomorrow(self) -> list[Lesson]:
        """Subset of ``lessons`` whose date == ``self.today + 1day`` (D-16)."""
        target = self.today + timedelta(days=1)
        return [lesson for lesson in self.lessons if lesson.date == target]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (round-trips through ``from_dict``)."""
        return {
            "today": self.today.isoformat(),
            "school_tz": self.school_tz,
            "lessons": [lesson.to_dict() for lesson in self.lessons],
            "grades": [grade.to_dict() for grade in self.grades],
            "information": [info.to_dict() for info in self.information],
            "overall_average": self.overall_average,  # Phase 4
            "period_name": self.period_name,  # Phase 4
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        """Reconstruct from a ``to_dict`` payload."""
        return cls(
            today=date.fromisoformat(data["today"]),
            school_tz=data["school_tz"],
            lessons=[Lesson.from_dict(item) for item in data["lessons"]],
            grades=[Grade.from_dict(item) for item in data["grades"]],
            information=[Information.from_dict(item) for item in data["information"]],
            overall_average=data.get("overall_average", ""),  # Phase 4 — default for pre-Phase-4 fixtures
            period_name=data.get("period_name", ""),
        )
