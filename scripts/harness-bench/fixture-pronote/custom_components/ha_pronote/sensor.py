"""Sensor platform — D-13, D-14, D-15, D-16, TIME-01, ENT-02.

Phase 3 ships ONE sensor (PronoteLessonsTodaySensor) — the count of today's
lessons (D-14). Phase 4 adds grades, notifications, and the J/J+1 attribute
payload on this sensor (TIME-02).

unique_id (D-13, ENT-02): ``f"pronote_{child_identifier}_lessons_today"`` —
FROZEN v1, never altered by nickname (Phase 6's OPT-03 only changes display
name, never the unique_id).

translation_key (ENT-03): ``"lessons_today"`` — must match the
``entity.sensor.lessons_today.name`` key in strings.json (Plan 01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .const import GRADE_COMMENT_MAX_LEN, GRADES_WINDOW, NOTIFICATIONS_WINDOW
from .entity import PronoteEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PronoteDataUpdateCoordinator
    from .data import PronoteConfigEntry


def _to_float(raw: str) -> float | None:
    """Comma-to-dot normalisation for Pronote grade float values.

    Returns None for empty strings or non-numeric strings (T-04-1 mitigation).
    This is a typed conversion guard, NOT a swallowing catch — the ValueError
    signals a malformed string from Pronote, and returning None is the correct
    response (sensor state becomes 'unknown' in HA rather than crashing).
    Per 'no silent exceptions' memory: the ValueError is for the string->float
    conversion only, not for any business-logic remapping.
    """
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PronoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Forward platform setup — Phase 4 wires 3 sensors."""
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            PronoteLessonsTodaySensor(coordinator, entry),
            PronoteGradesSensor(coordinator, entry),  # Phase 4 — GRADE-01/02
            PronoteNotificationsSensor(coordinator, entry),  # Phase 4 — NOTIF-01/02
        ]
    )


class PronoteLessonsTodaySensor(PronoteEntity, SensorEntity):
    """TIME-01 — count of today's lessons (D-14, D-16).

    Phase 4 adds the J/J+1 lesson list payload in extra_state_attributes
    (TIME-02, TIME-03 — under HA's 16 KiB attribute size limit).
    """

    _attr_translation_key = "lessons_today"  # ENT-03 -> strings.json
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "lessons"

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: PronoteConfigEntry,
    ) -> None:
        """Lock unique_id per D-13 — FROZEN v1, never re-derived."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_lessons_today"

    @property
    def native_value(self) -> int:
        """D-14 / TIME-01 — count of today's lessons (Snapshot.lessons_today)."""
        return len(self.coordinator.data.lessons_today)

    @property
    def extra_state_attributes(self) -> dict:
        """TIME-02 — J/J+1 lesson lists. D-02: two separate keys, Lesson.to_dict() each.

        Lessons sorted by start ascending (D-06 — pronotepy returns school-day order;
        Snapshot.lessons_today / lessons_tomorrow already filtered by date).
        """
        return {
            "lessons_today": [
                lesson.to_dict()
                for lesson in sorted(self.coordinator.data.lessons_today, key=lambda lesson: lesson.start)
            ],
            "lessons_tomorrow": [
                lesson.to_dict()
                for lesson in sorted(self.coordinator.data.lessons_tomorrow, key=lambda lesson: lesson.start)
            ],
        }


class PronoteGradesSensor(PronoteEntity, SensorEntity):
    """GRADE-01/02/03 — numeric overall average + per-grade ApexCharts attribute list.

    State: float(Period.overall_average) after comma-to-dot normalisation (D-03).
    None when overall_average is '' or '-1' (no grades yet — HA shows 'unknown').
    State is read from coordinator.data.overall_average (fetched in executor).
    """

    _attr_translation_key = "grades"  # C-04 -> strings.json entity.sensor.grades.name
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    # D-03: no device_class, no native_unit_of_measurement (no good HA fit for grade averages)

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: PronoteConfigEntry,
    ) -> None:
        """Lock unique_id per D-13."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_grades"

    @property
    def native_value(self) -> float | None:
        """D-03: float(overall_average) after comma-to-dot; None for '' or '-1'.

        '-1' is pronotepy's sentinel when the period exists but no grades published.
        '' is the fetcher's default when the period.overall_average call raised.
        Both map to None so HA shows 'unknown' (acceptable per CONTEXT.md <specifics>).
        """
        raw = self.coordinator.data.overall_average
        if not raw:
            return None
        normalised = raw.replace(",", ".")
        if normalised == "-1":
            return None  # pronotepy sentinel: no grades published yet
        return _to_float(normalised)

    @property
    def extra_state_attributes(self) -> dict:
        """D-04 — ApexCharts-shaped grade list, sorted newest first (D-06).

        comment capped at GRADE_COMMENT_MAX_LEN chars (T-04-2 mitigation — D-04).
        float values use _to_float() (comma-to-dot normalisation).
        """
        data = self.coordinator.data
        # D-06: newest first. D-04 (UAT-revised): cap at GRADES_WINDOW so the
        # 9-field schema fits under the 16 KiB recorder cap on heavy fixtures.
        grades = sorted(data.grades, key=lambda g: g.date, reverse=True)[:GRADES_WINDOW]
        return {
            "period_name": data.period_name,
            "grades": [
                {
                    "date": g.date.isoformat(),
                    "subject": g.subject,
                    "grade": _to_float(g.value),
                    "out_of": _to_float(g.out_of),
                    "coefficient": _to_float(g.coefficient),
                    "class_average": _to_float(g.class_average),
                    "class_min": _to_float(g.class_min),
                    "class_max": _to_float(g.class_max),
                    "comment": (g.comment or "")[:GRADE_COMMENT_MAX_LEN],
                }
                for g in grades
            ],
        }


class PronoteNotificationsSensor(PronoteEntity, SensorEntity):
    """NOTIF-01/02 — unread count state + 20 most-recent informations list.

    State: sum of info.read == False in Snapshot.information (D-05).
    Attributes: unread_count mirrors state + informations list capped at
    NOTIFICATIONS_WINDOW (D-05). Sorted by date descending (D-06).
    """

    _attr_translation_key = "notifications"  # C-04 -> strings.json entity.sensor.notifications.name
    _attr_icon = "mdi:bell"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: PronoteConfigEntry,
    ) -> None:
        """Lock unique_id per D-13."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_notifications"

    @property
    def native_value(self) -> int:
        """D-05: unread_count = number of informations with read == False."""
        return sum(1 for i in self.coordinator.data.information if not i.read)

    @property
    def extra_state_attributes(self) -> dict:
        """D-05/D-06: 20 most recent informations, sorted by date desc."""
        infos = sorted(
            self.coordinator.data.information,
            key=lambda i: i.date,
            reverse=True,
        )[:NOTIFICATIONS_WINDOW]
        return {
            "unread_count": self.native_value,
            "informations": [
                {
                    "info_id": i.info_id,
                    "title": str(i.title or ""),  # probe STEP 7: title may be None
                    "sender": i.sender,
                    "date": i.date.isoformat(),
                    "excerpt": i.excerpt,
                    "read": i.read,
                }
                for i in infos
            ],
        }
