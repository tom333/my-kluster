"""Calendar platform — CAL-01, CAL-02, D-07..D-09, D-10.

One PronoteCalendar per child. async_get_events filters coordinator.data.lessons
by date range (in-memory, no new HTTP call). event property returns current/next
upcoming lesson (required by CalendarEntity base class — raises NotImplementedError
if absent per RESEARCH Pitfall 1).

CalendarEntity.state and state_attributes are @final — never override them.
HA base class sets _entity_component_unrecorded_attributes = frozenset({"description"})
so the teacher name in description is NOT stored by recorder (T-04-3 mitigation).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import slugify  # D-09 uid contract — HA slugify, NOT python-slugify
import homeassistant.util.dt as dt_util

from .entity import PronoteEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api.models import Lesson
    from .coordinator import PronoteDataUpdateCoordinator
    from .data import PronoteConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PronoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Wire one PronoteCalendar per entry (D-10: PLATFORMS includes CALENDAR)."""
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([PronoteCalendar(coordinator, entry)])


class PronoteCalendar(PronoteEntity, CalendarEntity):
    """CAL-01/02 — full J-7→J+14 calendar; cancelled lessons visually distinct.

    Unique ID: f"pronote_{child_identifier}_calendar" (D-07, ENT-02 extension).
    """

    _attr_translation_key = "calendar"  # → strings.json entity.calendar.calendar.name (D-07)

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: PronoteConfigEntry,
    ) -> None:
        """D-07 — unique_id = pronote_{child_identifier}_calendar."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return current or next upcoming lesson.

        REQUIRED by CalendarEntity base class (raises NotImplementedError if absent).
        Returns the first lesson from coordinator.data.lessons where lesson.end > now().
        This covers both "currently in progress" and "next upcoming" cases.
        Returns None when no future lesson exists in the J-7→J+14 window.
        """
        now = dt_util.now()
        for lesson in sorted(self.coordinator.data.lessons, key=lambda lesson: lesson.start):
            if lesson.end > now:
                return self._lesson_to_event(lesson)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """D-08: return all lessons in [start_date.date(), end_date.date()] range.

        Uses date-level comparison to include all timed lessons on boundary days.
        No I/O — reads coordinator.data.lessons in-memory.
        Result is [] outside the J-7→J+14 fetch window (the fetcher window is hardcoded;
        Phase 6 could grow it).
        """
        return [
            self._lesson_to_event(lesson)
            for lesson in self.coordinator.data.lessons
            if start_date.date() <= lesson.date <= end_date.date()
        ]

    def _lesson_to_event(self, lesson: Lesson) -> CalendarEvent:
        """D-09: map one Lesson to a CalendarEvent with stable uid.

        uid formula: pronote_{child_id}_{lesson.date}_{lesson.start.isoformat()}_{slugify(subject)}
        Uses homeassistant.util.slugify (not python_slugify) for HA entity-id consistency (A5).

        T-04-06c mitigation: end <= start degenerate guard — end forced to start + 1h.
        """
        child_id = self._entry.runtime_data.child_identifier
        subject = lesson.subject or ""
        summary = f"❌ {subject}" if lesson.canceled else subject  # CAL-02
        description = f"Professeur: {lesson.teacher}"
        if lesson.canceled:
            description += "\nStatut: annulé"  # D-09 — free-form status NOT used

        # T-04-06c guard: degenerate Pronote data where end <= start (Pitfall 6)
        end = lesson.end if lesson.end > lesson.start else lesson.start + timedelta(hours=1)

        uid = f"pronote_{child_id}_{lesson.date}_{lesson.start.isoformat()}_{slugify(subject)}"
        return CalendarEvent(
            summary=summary,
            start=lesson.start,
            end=end,
            description=description,
            location=lesson.classroom or None,  # empty string → None (HA hides the field)
            uid=uid,
        )
