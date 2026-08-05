# Phase 4: Diff, Events & Full Sensor Suite - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 19 (new/modified production + test files)
**Analogs found:** 19 / 19 (all from existing codebase; external references are idea-only)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `custom_components/ha_pronote/diff/grades.py` | pure-function diff | transform (set diff) | `diff/lessons.py:diff_lessons` | exact (same pattern, simpler identity key) |
| `custom_components/ha_pronote/diff/notifications.py` | pure-function diff | transform (set diff) | `diff/lessons.py:diff_lessons` | exact |
| `custom_components/ha_pronote/api/models.py` | model (EXTEND) | declarative dataclass | the file itself | exact (self-analog) |
| `custom_components/ha_pronote/api/fetcher.py` | service (EXTEND) | request-response + transform | the file itself (`_grade_from_raw`, `fetch_all`) | exact (self-analog) |
| `custom_components/ha_pronote/coordinator.py` | service (EXTEND) | event-driven + request-response | the file itself (`_async_update_data`) | exact (self-analog) |
| `custom_components/ha_pronote/entity.py` | base class (EXTEND) | declarative | the file itself (`device_info` property) | exact (self-analog) |
| `custom_components/ha_pronote/sensor.py` | HA platform (EXTEND) | request-response | the file itself (`PronoteLessonsTodaySensor`) | exact (self-analog) |
| `custom_components/ha_pronote/calendar.py` | HA platform (NEW) | request-response (HA pulls events in range) | `sensor.py:PronoteLessonsTodaySensor` + HA CalendarEntity contract | role-match |
| `custom_components/ha_pronote/const.py` | constants (EXTEND) | declarative | the file itself (Phase 1+2+3 append style) | exact (self-analog) |
| `custom_components/ha_pronote/strings.json` | i18n config (EXTEND) | declarative | the file itself (Phase 3 entity.sensor block) | exact (self-analog) |
| `tests/fixtures/synthetic/_gen_heavy_class.py` | generator script (NEW) | batch transform | `tests/fixtures/synthetic/` JSON shape | no direct analog (see §No Analog Found) |
| `tests/fixtures/synthetic/heavy_class.json` | fixture (NEW) | declarative | existing `synthetic/*.json` shape | partial-match |
| `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` | documentation (NEW) | none | `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` | format-match |
| `tests/test_diff/test_grades.py` | test (NEW) | unit | `tests/test_diff/test_lessons.py` | exact |
| `tests/test_diff/test_notifications.py` | test (NEW) | unit | `tests/test_diff/test_lessons.py` | exact |
| `tests/test_sensor.py` | test (EXTEND) | unit + integration | the file itself + `test_coordinator.py` setup pattern | exact (self-analog) |
| `tests/test_calendar.py` | test (NEW) | unit + integration | `tests/test_sensor.py` setup pattern | role-match |
| `tests/test_coordinator.py` | test (EXTEND) | unit + integration | the file itself | exact (self-analog) |
| `tests/test_attribute_size.py` | test (NEW) | unit (CI gate) | `tests/test_sensor.py` entity setup pattern + HA `MAX_STATE_ATTRS_BYTES` | role-match |
| `tests/conftest.py` | test fixture (EXTEND) | declarative | the file itself (`mock_pronote_client`, `snapshot_with_n_lessons_today`) | exact (self-analog) |

---

## Pattern Assignments

### `custom_components/ha_pronote/diff/grades.py` (FILL-STUB, transform)

**Analog:** `custom_components/ha_pronote/diff/lessons.py`

**Docstring style** (lines 1-62 of lessons.py — condense for grades):
```python
"""Grade diff — first-poll skip + identity-key set difference (D-14, EVENT-02).

Identity key per grade: ``(subject, date, value)`` — same pronotepy-raw string
value so a re-scored grade appears as new (acceptable; user sees it).
First-poll invariant: ``diff_grades(None, snapshot) -> []`` (EVENT-04).
"""
```

**Imports pattern** (mirror grades.py lines 1-16 — keep TYPE_CHECKING guard):
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Snapshot
    from .events import NewGrade
```

**Core pattern** (mirror `diff_lessons` lines 118-157, simplified — no identity/content split, just set diff):
```python
def diff_grades(previous: Snapshot | None, new: Snapshot) -> list[NewGrade]:
    """Return new grades since the previous poll.

    Args:
        previous: Previous Snapshot, or None on first poll after restart.
        new: Current Snapshot.

    Returns:
        List of NewGrade events. Empty when previous is None (EVENT-04).
    """
    if previous is None:
        return []
    prev_keys = {(g.subject, g.date, g.value) for g in previous.grades}
    return [
        NewGrade(
            subject=g.subject,
            value=g.value,
            out_of=g.out_of,
            coefficient=g.coefficient,
            date=g.date,
        )
        for g in new.grades
        if (g.subject, g.date, g.value) not in prev_keys
    ]
```

**Delta from analog:** No `_identity_key` / `_content_key` / `_classify_change` helpers needed — a single `prev_keys` set suffices. No `day` parameter. `NewGrade` fields match `diff/events.py` frozen contract exactly.

---

### `custom_components/ha_pronote/diff/notifications.py` (FILL-STUB, transform)

**Analog:** `custom_components/ha_pronote/diff/lessons.py`

**Core pattern** (same shape as diff_grades above):
```python
def diff_notifications(previous: Snapshot | None, new: Snapshot) -> list[NewInformation]:
    """Return new informations since the previous poll.

    Identity key: (info_id, date.date()) — C-03: Information.date is datetime
    (tz-aware); NewInformation.date is date. Call .date() at construction.
    """
    if previous is None:
        return []
    prev_keys = {(i.info_id, i.date.date()) for i in previous.information}
    return [
        NewInformation(
            info_id=i.info_id,
            title=i.title,
            sender=i.sender,
            date=i.date.date(),       # C-03: datetime → date
            excerpt=i.excerpt,
        )
        for i in new.information
        if (i.info_id, i.date.date()) not in prev_keys
    ]
```

**Delta from analog:** `Information.date` is a tz-aware `datetime`; `NewInformation.date` is a `date` (C-03). Call `.date()` at construction — this is explicit, not a silent swallow. The identity key uses `i.date.date()` consistently.

---

### `custom_components/ha_pronote/api/models.py` (EXTEND — Grade + Snapshot dataclasses)

**Analog:** the file itself — `Grade` (lines 67-95) and `Snapshot` (lines 133-173).

**Existing Grade pattern** (lines 67-95 — add 4 optional fields AFTER existing 5):
```python
@dataclass(frozen=True)
class Grade:
    subject: str
    value: str
    out_of: str
    coefficient: str
    date: date
    # Phase 4 additions — pronotepy attr names: average/max/min/comment
    # Mapped to user-facing names per RESEARCH.md "Name mapping alert"
    class_average: str = ""
    class_min: str = ""
    class_max: str = ""
    comment: str = ""
```

**`to_dict` / `from_dict` pattern** (lines 76-95 — add the 4 new fields in the same style):
```python
    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "value": self.value,
            "out_of": self.out_of,
            "coefficient": self.coefficient,
            "date": self.date.isoformat(),
            "class_average": self.class_average,  # Phase 4 add
            "class_min": self.class_min,
            "class_max": self.class_max,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Grade:
        return cls(
            # ... existing 5 fields ...
            class_average=data.get("class_average", ""),  # Phase 4 add — default "" for old fixtures
            class_min=data.get("class_min", ""),
            class_max=data.get("class_max", ""),
            comment=data.get("comment", ""),
        )
```

**Existing Snapshot pattern** (lines 133-173 — add 2 new fields with defaults):
```python
@dataclass(frozen=True)
class Snapshot:
    today: date
    school_tz: str
    lessons: list[Lesson] = field(default_factory=list)
    grades: list[Grade] = field(default_factory=list)
    information: list[Information] = field(default_factory=list)
    # Phase 4 additions — fetched alongside grades in executor (RESEARCH gap #5)
    overall_average: str = ""   # Period.overall_average (comma-string, may be "-1")
    period_name: str = ""       # Period.name e.g. "Trimestre 2"
```

**`to_dict` / `from_dict` for Snapshot** (lines 154-173 — include the 2 new fields):
```python
    def to_dict(self) -> dict[str, Any]:
        return {
            "today": self.today.isoformat(),
            "school_tz": self.school_tz,
            "lessons": [...],
            "grades": [...],
            "information": [...],
            "overall_average": self.overall_average,  # Phase 4 add
            "period_name": self.period_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            # ... existing fields ...
            overall_average=data.get("overall_average", ""),  # default for pre-Phase-4 fixtures
            period_name=data.get("period_name", ""),
        )
```

**Delta from analog:** All new fields have default values (`= ""` / `data.get(..., "")`) so existing Phase 2 synthetic fixtures continue to round-trip without modification. `frozen=True` is preserved; the `field(default_factory=...)` pattern for list fields is unchanged.

---

### `custom_components/ha_pronote/api/fetcher.py` (EXTEND — `_grade_from_raw` + `fetch_all`)

**Analog:** the file itself — `_grade_from_raw` (lines 143-151) and `fetch_all` (lines 26-109).

**`_grade_from_raw` extension** (lines 143-151 — add 4 pronotepy-to-model field mappings):
```python
def _grade_from_raw(raw: Any) -> Grade:
    """Field-by-field copy of a pronotepy grade.

    pronotepy attr → model field mapping (RESEARCH.md "Name mapping alert"):
      raw.average → Grade.class_average  (class avg, NOT raw.class_average)
      raw.max     → Grade.class_max
      raw.min     → Grade.class_min
      raw.comment → Grade.comment
    """
    return Grade(
        subject=raw.subject.name if raw.subject else "",
        value=str(raw.grade) if raw.grade is not None else "",
        out_of=str(raw.out_of) if raw.out_of is not None else "",
        coefficient=str(raw.coefficient) if raw.coefficient is not None else "",
        date=raw.date,
        class_average=str(raw.average) if getattr(raw, "average", None) is not None else "",
        class_min=str(raw.min) if getattr(raw, "min", None) is not None else "",
        class_max=str(raw.max) if getattr(raw, "max", None) is not None else "",
        comment=str(raw.comment) if getattr(raw, "comment", None) else "",
    )
```

**`fetch_all` extension** (lines 78-109 — capture `overall_average` + `period_name` alongside grades):
```python
        try:
            raw_grades = list(client.current_period.grades) if client.current_period else []
            # Phase 4: fetch overall_average + period_name in same executor call.
            # Period.overall_average is a @property making a fresh HTTP call —
            # must stay in executor (RESEARCH Pitfall 3).
            overall_avg = ""
            period_name = ""
            if client.current_period:
                overall_avg = getattr(client.current_period, "overall_average", "") or ""
                period_name = getattr(client.current_period, "name", "") or ""
        except (KeyError, AttributeError):
            raw_grades = []
            overall_avg = ""
            period_name = ""
```

**Snapshot construction** (lines 103-109 — include new fields):
```python
    return Snapshot(
        today=today,
        school_tz=str(school_tz),
        lessons=[_lesson_from_raw(item, school_tz) for item in raw_lessons],
        grades=[_grade_from_raw(item) for item in raw_grades],
        information=[_info_from_raw(item, school_tz) for item in raw_info],
        overall_average=overall_avg,   # Phase 4 add
        period_name=period_name,       # Phase 4 add
    )
```

**Delta from analog:** `overall_average` and `period_name` MUST be fetched in the executor (not from sensor's `native_value`) because `Period.overall_average` is a `@property` that makes a synchronous HTTP call. The `getattr(..., None)` fallback pattern (not try/except) is used per the "no silent exceptions" preference — missing attributes are normal and must not swallow real errors.

---

### `custom_components/ha_pronote/coordinator.py` (EXTEND — `_async_update_data`)

**Analog:** the file itself — `_async_update_data` (lines 98-157).

**Imports to add** (at existing import block):
```python
from .const import (
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
    EVENT_NEW_GRADE,
    EVENT_NEW_INFORMATION,
    EVENT_SCHEDULE_CHANGED,
)
from .diff import diff_grades, diff_lessons, diff_notifications
```

**`_async_update_data` insertion site** (lines 147-157 — after `self._previous_snapshot = snapshot`, before `try: _capture_session`):
```python
        # C-03 — snapshot captured first (CR-03 ordering preserved).
        previous = self._previous_snapshot   # capture BEFORE overwrite
        self._previous_snapshot = snapshot   # C-03 (already here in Phase 3)

        try:
            await self._capture_session()    # D-06 (already here)
        except Exception:                   # noqa: BLE001
            _LOGGER.warning("Failed to persist session token; will retry next poll", exc_info=True)

        # Phase 4: fire typed bus events for each diff.
        # D-12: NO try/except — diff bugs surface in HA logs immediately.
        self._fire_diff_events(previous, snapshot)

        return snapshot
```

**New helper method** (add to class body — after `_capture_session`):
```python
    def _fire_diff_events(
        self,
        previous: Snapshot | None,
        new: Snapshot,
    ) -> None:
        """Fire typed bus events for each change since previous snapshot.

        D-12: NO typed try/except — diff bugs surface raw in HA logs.
        D-15: all diff functions return [] when previous is None (EVENT-04).
        D-11: every payload is prepended with child_id, child_name, config_entry_id.
        """
        child_context = {
            "child_id": self._child_identifier,
            "child_name": self.config_entry.data["child_name"],
            "config_entry_id": self.config_entry.entry_id,
        }
        for change in diff_lessons(previous, new, "today"):
            self.hass.bus.async_fire(
                EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()}
            )
        for change in diff_lessons(previous, new, "tomorrow"):
            self.hass.bus.async_fire(
                EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()}
            )
        for grade in diff_grades(previous, new):
            self.hass.bus.async_fire(
                EVENT_NEW_GRADE, {**child_context, **grade.to_payload()}
            )
        for info in diff_notifications(previous, new):
            self.hass.bus.async_fire(
                EVENT_NEW_INFORMATION, {**child_context, **info.to_payload()}
            )
```

**Delta from analog:** The CR-03 snapshot ordering is preserved: `previous = self._previous_snapshot` is captured BEFORE overwriting. `_fire_diff_events` is called from `_async_update_data` (event loop) — never inside an executor job (RESEARCH Pitfall 2: `hass.bus.async_fire` is `@callback`, not thread-safe). No `try/except` around the fire call.

---

### `custom_components/ha_pronote/entity.py` (EXTEND — `device_info` property)

**Analog:** the file itself — `device_info` property (lines 54-61).

**Existing pattern** (lines 54-61 — add `model=` line):
```python
    @property
    def device_info(self) -> DeviceInfo:
        """D-17 — Phase 4 adds model=<class level> per D-19."""
        from .const import CLASS_LEVEL_ATTR  # imported here to avoid circular at module level
        client = self._entry.runtime_data.client
        class_label = getattr(client.info, CLASS_LEVEL_ATTR, None)
        # D-19: empty string → None (ClientInfo.class_name returns "" not None when absent)
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.runtime_data.child_identifier)},
            name=self._entry.data["child_name"],
            manufacturer="Pronote",
            model=class_label or None,  # None hides the row in HA UI
        )
```

**Delta from analog:** `getattr(client.info, CLASS_LEVEL_ATTR, None)` is an explicit visible default (per "no silent exceptions" — not a swallowing catch). The `or None` converts `""` to `None` (confirmed by RESEARCH: `ClientInfo.class_name` returns `""` not `None` when unavailable). The `_LOGGER.info` on missing class_label is optional and benign; omit unless the planner wants it.

---

### `custom_components/ha_pronote/sensor.py` (EXTEND — 3 changes)

**Analog:** the file itself — `PronoteLessonsTodaySensor` (entire file, lines 1-69).

#### Change 1 — TIME-02 attrs on `PronoteLessonsTodaySensor`

**Add `extra_state_attributes` property** (after `native_value` at line 69):
```python
    @property
    def extra_state_attributes(self) -> dict:
        """TIME-02 — J/J+1 lesson lists. D-02: two separate keys, Lesson.to_dict() each."""
        return {
            "lessons_today": [
                lesson.to_dict()
                for lesson in self.coordinator.data.lessons_today
            ],
            "lessons_tomorrow": [
                lesson.to_dict()
                for lesson in self.coordinator.data.lessons_tomorrow
            ],
        }
```

#### Change 2 — `PronoteGradesSensor` (new class at end of file)

**Pattern** (mirror `PronoteLessonsTodaySensor` class structure — lines 44-69):
```python
class PronoteGradesSensor(PronoteEntity, SensorEntity):
    """GRADE-01/02 — numeric overall average + per-grade attribute list."""

    _attr_translation_key = "grades"
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    # No device_class, no native_unit_of_measurement (D-03)

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_grades"

    @property
    def native_value(self) -> float | None:
        """D-03: float(overall_average) after comma→dot; None for empty/"-1"."""
        raw = self.coordinator.data.overall_average
        if not raw:
            return None
        normalised = raw.replace(",", ".")
        if normalised == "-1":
            return None
        try:
            return float(normalised)
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """D-04 — ApexCharts-shaped grade list, sorted newest first."""
        data = self.coordinator.data
        grades = sorted(data.grades, key=lambda g: g.date, reverse=True)
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
                    "comment": (g.comment or "")[:200],
                }
                for g in grades
            ],
        }
```

**`_to_float` helper** (module-level, before the sensor classes):
```python
def _to_float(raw: str) -> float | None:
    """Comma→dot normalisation for grade float values. Returns None for empty/invalid."""
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None
```

#### Change 3 — `PronoteNotificationsSensor` (new class at end of file)

**Pattern** (mirror `PronoteLessonsTodaySensor` class structure):
```python
class PronoteNotificationsSensor(PronoteEntity, SensorEntity):
    """NOTIF-01/02 — unread count state + 20 most-recent informations list."""

    _attr_translation_key = "notifications"
    _attr_icon = "mdi:bell"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_notifications"

    @property
    def native_value(self) -> int:
        """D-05: unread_count = count of info.read == False."""
        return sum(1 for i in self.coordinator.data.information if not i.read)

    @property
    def extra_state_attributes(self) -> dict:
        """D-05/D-06: 20 most recent informations, sorted by date desc."""
        from .const import NOTIFICATIONS_WINDOW
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
                    "title": i.title,
                    "sender": i.sender,
                    "date": i.date.isoformat(),
                    "excerpt": i.excerpt,
                    "read": i.read,
                }
                for i in infos
            ],
        }
```

#### Change 4 — `async_setup_entry` extension

**Extend existing `async_add_entities` call** (line 41 — add 2 new sensor instances):
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: PronoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([
        PronoteLessonsTodaySensor(coordinator, entry),
        PronoteGradesSensor(coordinator, entry),        # Phase 4 add
        PronoteNotificationsSensor(coordinator, entry), # Phase 4 add
    ])
```

**Delta from analog:** `_to_float` is a module-level helper (reused by both grades sensor and `extra_state_attributes`). `extra_state_attributes` on `PronoteLessonsTodaySensor` reads the already-computed `Snapshot.lessons_today` / `lessons_tomorrow` properties (no filtering in sensor — D-06). `NOTIFICATIONS_WINDOW` constant imported from `const` for the cap.

---

### `custom_components/ha_pronote/calendar.py` (NEW — HA platform)

**Analog (structure):** `sensor.py` — `async_setup_entry` + `PronoteLessonsTodaySensor` class structure.
**Analog (HA contract):** `homeassistant/components/calendar/__init__.py` — `CalendarEntity`, `CalendarEvent`.

**Full file pattern:**
```python
"""Calendar platform — CAL-01, CAL-02, D-07..D-09.

One PronoteCalendar per child. async_get_events filters coordinator.data.lessons
by date range (in-memory, no new HTTP call). CalendarEntity.state and
CalendarEntity.state_attributes are @final — do NOT override them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util.slugify import slugify
import homeassistant.util.dt as dt_util

from .entity import PronoteEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from .coordinator import PronoteDataUpdateCoordinator
    from .data import PronoteConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PronoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Wire one PronoteCalendar per entry (D-10 PLATFORMS += CALENDAR)."""
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([PronoteCalendar(coordinator, entry)])


class PronoteCalendar(PronoteEntity, CalendarEntity):
    """CAL-01/02 — full J-7→J+14 calendar; cancelled lessons visually distinct."""

    _attr_translation_key = "calendar"

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, entry: PronoteConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"pronote_{entry.runtime_data.child_identifier}_calendar"
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return current or next upcoming lesson. Required by CalendarEntity base class."""
        now = dt_util.now()
        for lesson in sorted(self.coordinator.data.lessons, key=lambda l: l.start):
            if lesson.end > now:
                return self._lesson_to_event(lesson)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """D-08: return all lessons in [start_date.date(), end_date.date()] range."""
        return [
            self._lesson_to_event(lesson)
            for lesson in self.coordinator.data.lessons
            if start_date.date() <= lesson.date <= end_date.date()
        ]

    def _lesson_to_event(self, lesson) -> CalendarEvent:
        """D-09: map one Lesson → CalendarEvent with stable uid."""
        child_id = self._entry.runtime_data.child_identifier
        subject = lesson.subject or ""
        summary = f"❌ {subject}" if lesson.canceled else subject
        description = f"Professeur: {lesson.teacher}"
        if lesson.canceled:
            description += "\nStatut: annulé"
        # D-09: guard against start == end (degenerate Pronote data)
        end = lesson.end if lesson.end > lesson.start else lesson.start + timedelta(hours=1)
        uid = (
            f"pronote_{child_id}_{lesson.date}_{lesson.start.isoformat()}"
            f"_{slugify(subject)}"
        )
        return CalendarEvent(
            summary=summary,
            start=lesson.start,
            end=end,
            description=description,
            location=lesson.classroom or None,
            uid=uid,
        )
```

**Key constraints:**
- `CalendarEntity.state` and `state_attributes` are `@final` — never override.
- `event` property IS required (raises `NotImplementedError` in base if missing).
- `async_get_events` receives `datetime` not `date` for both parameters.
- `homeassistant.util.slugify.slugify` (not `python_slugify`) for entity-id consistency.
- `lesson.start` / `lesson.end` are already tz-aware `datetime` objects from Phase 2 D-23 — produces timed events (correct for lessons).

---

### `custom_components/ha_pronote/const.py` (EXTEND — append Phase 4 constants)

**Analog:** the file itself — Phase 3 appendix style (lines 19-22).

**Phase 4 appendix** (append after line 22):
```python
# Phase 4 additions — event-type constants (D-13), platform extension (D-10),
# attribute constants (D-19).
from typing import Final  # already imported; shown for context

EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"   # D-13, EVENT-01
EVENT_NEW_GRADE: Final = "pronote_new_grade"                 # D-13, EVENT-02
EVENT_NEW_INFORMATION: Final = "pronote_new_information"     # D-13, EVENT-03

# Probe-locked class level attribute on pronotepy.ClientInfo (D-19, ENT-01).
# RESEARCH confirms: ClientInfo.class_name returns raw_resource.get("classeDEleve",{}).get("L","")
CLASS_LEVEL_ATTR: Final = "class_name"

NOTIFICATIONS_WINDOW: Final = 20    # D-05 — cap on informations list in sensor attrs
GRADE_COMMENT_MAX_LEN: Final = 200  # D-04 — comment truncation length

# D-10 — extend PLATFORMS tuple to include CALENDAR.
# __init__.py already iterates const.PLATFORMS via async_forward_entry_setups — no edit needed there.
PLATFORMS: Final = (Platform.SENSOR, Platform.CALENDAR)  # replaces Phase 3 tuple
```

**Delta from analog:** `PLATFORMS` assignment replaces (not appends to) the Phase 3 tuple. The existing `from homeassistant.const import Platform` import already covers `Platform.CALENDAR`.

---

### `custom_components/ha_pronote/strings.json` (EXTEND — append entity keys)

**Analog:** the file itself — `entity.sensor.lessons_today` block (lines 36-40).

**Phase 4 appendix** (inside the `entity` block):
```json
{
  "entity": {
    "sensor": {
      "lessons_today": { "name": "Lessons today" },
      "grades": { "name": "Grades" },
      "notifications": { "name": "Notifications" }
    },
    "calendar": {
      "calendar": { "name": "Schedule" }
    }
  }
}
```

---

### `tests/conftest.py` (EXTEND — new fixtures for Phase 4)

**Analog:** the file itself — `mock_pronote_client` (lines 31-46) + `snapshot_with_n_lessons_today` (lines 120-135).

**Phase 4 appendix pattern:**
```python
# Phase 4 additions — heavy-class snapshot fixture + grades-capable mock client.

import json
from pathlib import Path

from custom_components.ha_pronote.api.models import Grade, Information, Snapshot


@pytest.fixture
def heavy_class_snapshot() -> Snapshot:
    """Load tests/fixtures/synthetic/heavy_class.json as a Snapshot.

    Used by tests/test_attribute_size.py CI gate. JSON committed alongside
    _gen_heavy_class.py (D-16).
    """
    path = Path(__file__).parent / "fixtures" / "synthetic" / "heavy_class.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Snapshot.from_dict(raw)


@pytest.fixture
def mock_pronote_client_with_grades(mock_pronote_client):
    """Extends mock_pronote_client with current_period.overall_average + grades list.

    Shape matches probe-captured pronotepy 2.14.6 surface (PHASE-4-PROBE-NOTES.md STEP 6).
    C-06: MagicMock at the build_or_resume_client seam — NOT requests-mock.
    """
    mock_pronote_client.current_period.overall_average = "14,50"
    mock_pronote_client.current_period.name = "Trimestre 2"
    mock_grade = MagicMock()
    mock_grade.subject = MagicMock()
    mock_grade.subject.name = "Mathématiques"
    mock_grade.grade = "15"
    mock_grade.out_of = "20"
    mock_grade.coefficient = "2"
    mock_grade.date = date(2026, 5, 10)
    mock_grade.average = "13"
    mock_grade.min = "8"
    mock_grade.max = "18"
    mock_grade.comment = ""
    mock_pronote_client.current_period.grades = [mock_grade]
    return mock_pronote_client
```

---

### `tests/test_diff/test_grades.py` (NEW)

**Analog:** `tests/test_diff/test_lessons.py` — `TestFirstPollInvariant`, class-based test structure, `load_fixture` fixture, parametrize pattern.

**Full file pattern:**
```python
"""tests for diff_grades — first-poll skip + identity-key set diff (D-14, EVENT-02, EVENT-04)."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.api.models import Grade, Snapshot
from custom_components.ha_pronote.diff import diff_grades
from custom_components.ha_pronote.diff.events import NewGrade


def _make_snapshot(grades: list[Grade]) -> Snapshot:
    tz = ZoneInfo("Pacific/Noumea")
    return Snapshot(today=date(2026, 5, 10), school_tz="Pacific/Noumea", grades=grades)


def _grade(subject="Math", value="15", date_=date(2026, 5, 10)) -> Grade:
    return Grade(subject=subject, value=value, out_of="20", coefficient="1", date=date_)


class TestFirstPollInvariant:
    def test_previous_none_returns_empty(self):
        """EVENT-04: no events on first poll."""
        new = _make_snapshot([_grade()])
        assert diff_grades(None, new) == []

    def test_previous_none_empty_returns_empty(self):
        assert diff_grades(None, _make_snapshot([])) == []


class TestIdentityKey:
    def test_same_grade_emits_nothing(self):
        snap = _make_snapshot([_grade()])
        assert diff_grades(snap, snap) == []

    def test_new_grade_emits_one_event(self):
        prev = _make_snapshot([_grade(subject="Math")])
        new = _make_snapshot([_grade(subject="Math"), _grade(subject="Français")])
        result = diff_grades(prev, new)
        assert len(result) == 1
        assert result[0].subject == "Français"

    def test_different_value_same_subject_date_emits_event(self):
        """Re-scored grade is treated as new (acceptable — user sees it)."""
        prev = _make_snapshot([_grade(value="14")])
        new = _make_snapshot([_grade(value="15")])
        assert len(diff_grades(prev, new)) == 1
```

---

### `tests/test_diff/test_notifications.py` (NEW)

**Analog:** `tests/test_diff/test_lessons.py` and `test_grades.py` pattern above.

**Core pattern** (mirror test_grades.py structure with Information/NewInformation):
```python
from custom_components.ha_pronote.api.models import Information, Snapshot
from custom_components.ha_pronote.diff import diff_notifications

def _info(info_id="1", date_=datetime(2026, 5, 10, 12, 0, tzinfo=ZoneInfo("Pacific/Noumea"))) -> Information:
    return Information(info_id=info_id, title="T", sender="S", date=date_, excerpt="E", read=False)

class TestFirstPollInvariant:
    def test_previous_none_returns_empty(self):
        assert diff_notifications(None, _make_snapshot([_info()])) == []

class TestIdentityKey:
    def test_new_info_emits_one_event(self):
        prev = _make_snapshot([_info(info_id="1")])
        new = _make_snapshot([_info(info_id="1"), _info(info_id="2")])
        result = diff_notifications(prev, new)
        assert len(result) == 1
        assert result[0].info_id == "2"

    def test_date_is_date_not_datetime(self):
        """C-03: NewInformation.date must be date, not datetime."""
        prev = _make_snapshot([])
        new = _make_snapshot([_info()])
        result = diff_notifications(prev, new)
        from datetime import date
        assert isinstance(result[0].date, date)
        assert not isinstance(result[0].date, datetime)
```

---

### `tests/test_sensor.py` (EXTEND — Phase 4 sensor tests)

**Analog:** the file itself — `test_sensor_native_value_equals_lessons_today_count` (lines 17-41) as the setup pattern; adapt for grades and notifications.

**Setup pattern to mirror** (the `patch` + `async_setup` + `hass.states.get` idiom):
```python
async def test_grades_sensor_state_float(
    hass,
    mock_config_entry,
    mock_pronote_client_with_grades,
    snapshot_with_n_lessons_today,
) -> None:
    today = date(2026, 5, 10)
    # Build a snapshot that includes overall_average
    from custom_components.ha_pronote.api.models import Snapshot
    snapshot = Snapshot(today=today, school_tz="Pacific/Noumea", overall_average="14,50", period_name="Trimestre 2")
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client_with_grades),
        patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snapshot),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get("sensor.jean_dupont_grades")
    assert state is not None
    assert float(state.state) == pytest.approx(14.5)
```

**TIME-02 attrs test** (update `test_sensor_no_lessons_attribute_in_state` — this test will FLIP in Phase 4):
```python
async def test_time02_attrs_present(hass, mock_config_entry, mock_pronote_client, ...) -> None:
    """TIME-02: lessons_today + lessons_tomorrow keys present in state.attributes."""
    # ... setup ...
    state = hass.states.get("sensor.jean_dupont_lessons_today")
    assert "lessons_today" in state.attributes
    assert "lessons_tomorrow" in state.attributes
    assert isinstance(state.attributes["lessons_today"], list)
```

---

### `tests/test_calendar.py` (NEW)

**Analog:** `tests/test_sensor.py` — `async_setup_entry` setup pattern; `CalendarEntity` HA contract.

**Key patterns:**
```python
"""HA-side tests for PronoteCalendar (CAL-01, CAL-02, D-07..D-09)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from custom_components.ha_pronote.api.models import Lesson, Snapshot

_CALENDAR_ENTITY_ID = "calendar.jean_dupont_schedule"
_TZ = ZoneInfo("Pacific/Noumea")


def _make_lesson(d: date, hour: int = 8, subject: str = "Math", canceled: bool = False) -> Lesson:
    start = datetime(d.year, d.month, d.day, hour, 0, tzinfo=_TZ)
    end = datetime(d.year, d.month, d.day, hour + 1, 0, tzinfo=_TZ)
    return Lesson(date=d, start=start, end=end, subject=subject,
                  teacher="Mme A", classroom="101", canceled=canceled, status="")


async def test_calendar_entity_created(hass, mock_config_entry, mock_pronote_client) -> None:
    """D-07: PronoteCalendar entity present in entity registry."""
    # ... setup + assert entity_id in hass.states

async def test_cancelled_lesson_has_x_prefix(hass, ...) -> None:
    """CAL-02: CalendarEvent.summary starts with ❌ for canceled lessons."""
    today = date(2026, 5, 10)
    snapshot = Snapshot(today=today, school_tz="Pacific/Noumea",
                        lessons=[_make_lesson(today, canceled=True)])
    # ... setup ...
    calendar = ... # get calendar entity
    start = datetime(2026, 5, 10, 0, 0, tzinfo=_TZ)
    end = datetime(2026, 5, 10, 23, 59, tzinfo=_TZ)
    events = await calendar.async_get_events(hass, start, end)
    assert events[0].summary.startswith("❌")

async def test_uid_stable_across_polls(hass, ...) -> None:
    """D-09: same lesson in two polls produces same CalendarEvent.uid."""
    # build two identical snapshots, assert uid equality

async def test_event_property_returns_none_with_no_future_lessons(hass, ...) -> None:
    """CalendarEntity.event returns None when no future lesson exists."""
```

---

### `tests/test_coordinator.py` (EXTEND — bus event firing tests)

**Analog:** the file itself — `test_first_refresh_writes_session_to_entry_data` (lines 16-38) as the coordinator setup + refresh pattern.

**Event firing test pattern:**
```python
async def test_fires_schedule_changed_on_lesson_diff(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today
) -> None:
    """EVENT-01: pronote_schedule_changed fires when lesson content changes."""
    today = date(2026, 5, 10)
    # First poll — no events (EVENT-04 first-poll skip)
    snap1 = snapshot_with_n_lessons_today(today, n=2)
    events_fired = []
    hass.bus.async_listen("pronote_schedule_changed", lambda e: events_fired.append(e))
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
        patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap1),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert len(events_fired) == 0  # EVENT-04

    # Second poll with a changed lesson
    snap2 = ... # lesson with canceled=True
    coordinator = mock_config_entry.runtime_data.coordinator
    with patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=snap2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert len(events_fired) == 1
    assert events_fired[0].data["child_id"] == "jean_dupont"
    assert events_fired[0].data["change_type"] == "canceled"

async def test_no_events_on_first_poll(hass, ...) -> None:
    """EVENT-04: zero events on first poll regardless of snapshot content."""
    # ... setup: first poll with non-empty snapshot ...
    assert len(events_fired) == 0
```

---

### `tests/test_attribute_size.py` (NEW — CI gate)

**Analog:** `tests/test_sensor.py` entity setup pattern + HA `MAX_STATE_ATTRS_BYTES = 16384`.

**Full file pattern:**
```python
"""CI gate: sensor state ≤255 chars AND extra_state_attributes ≤16384 bytes.

D-17: parametrised over PronoteLessonsTodaySensor, PronoteGradesSensor,
PronoteNotificationsSensor against the heavy_class fixture.
Fail = CI blocks merge.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from custom_components.ha_pronote.sensor import (
    PronoteGradesSensor,
    PronoteLessonsTodaySensor,
    PronoteNotificationsSensor,
)

MAX_STATE_BYTES = 255
MAX_ATTRS_BYTES = 16384  # HA recorder MAX_STATE_ATTRS_BYTES


@pytest.mark.parametrize("sensor_cls", [
    PronoteLessonsTodaySensor,
    PronoteGradesSensor,
    PronoteNotificationsSensor,
])
async def test_sensor_state_and_attrs_within_limits(
    hass, mock_config_entry, mock_pronote_client, heavy_class_snapshot, sensor_cls
) -> None:
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
        patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=heavy_class_snapshot),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Find the entity state (entity_id varies by sensor_cls)
    entity_ids = hass.states.async_entity_ids("sensor")
    # ... locate the right state by checking attributes ...
    state = ...  # the sensor's hass state

    assert state.state not in (None, "unknown", "unavailable")
    assert len(str(state.state)) <= MAX_STATE_BYTES
    attrs = json.dumps(state.attributes, default=str)
    assert len(attrs.encode("utf-8")) <= MAX_ATTRS_BYTES, (
        f"{sensor_cls.__name__} attrs = {len(attrs.encode())} bytes > {MAX_ATTRS_BYTES}"
    )
```

---

### `tests/fixtures/synthetic/_gen_heavy_class.py` (NEW)

**Analog (shape only):** existing `synthetic/*.json` files — `Snapshot.to_dict()` output structure. No direct code analog; use `Snapshot`, `Lesson`, `Grade`, `Information` constructors directly.

**Key generation parameters** (D-16):
- 3 weeks × 6 teaching days × 7 lessons/day = 126 lessons
- 100 grades across 4-6 subjects with French names (Mathématiques, Français, Histoire-Géographie, EPS, Physique-Chimie, Anglais)
- 30 informations with excerpts at the 500-char cap
- `today = date(2026, 5, 26)` as the anchor (J-7 → J+14 window)
- Output: `heavy_class.json` via `Path(__file__).parent / "heavy_class.json"`

**Module-level entry point pattern** (mirror `scripts/probe_config_flow.py` style):
```python
if __name__ == "__main__":
    data = generate()
    out = Path(__file__).parent / "heavy_class.json"
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {len(data['lessons'])} lessons, {len(data['grades'])} grades, "
          f"{len(data['information'])} infos to {out}")
```

---

### `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` (NEW)

**Analog:** `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` — top-matter (date, source instance, pronotepy version), section-per-finding format, append-only.

**Header template:**
```markdown
# Phase 4 Probe Notes — pronotepy 2.14.6

**Captured:** (fill in after running probe)
**Source instance:** katiramona.ac-noumea.nc (direct ?login=true URL — Phase 3 UAT finding #6)
**pronotepy version:** 2.14.6
**Script:** scripts/probe_config_flow.py

## STEP 5 — client.lessons(date_from, date_to) shape
(fill in after probe run)

## STEP 6 — client.current_period.grades + overall_average
(fill in after probe run — confirm Grade.average/.max/.min/.comment presence)

## STEP 7 — client.information_and_surveys() shape
(fill in after probe run)

## STEP 11 — ClientInfo attributes
(fill in after probe run — confirm class_name field)
```

---

## Shared Patterns

### Authentication / Setup Seam
**Source:** `tests/conftest.py:mock_config_entry` (lines 69-91) + `patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_client)`
**Apply to:** All HA-side tests in `test_sensor.py`, `test_calendar.py`, `test_coordinator.py`, `test_attribute_size.py`
```python
mock_config_entry.add_to_hass(hass)
with (
    patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
    patch("custom_components.ha_pronote.coordinator.fetch_all", return_value=my_snapshot),
):
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
```

### First-Poll-Skip Invariant
**Source:** `diff/lessons.py` lines 118-119
**Apply to:** `diff/grades.py`, `diff/notifications.py`, `tests/test_diff/test_grades.py`, `tests/test_diff/test_notifications.py`, `tests/test_coordinator.py` EVENT-04 test
```python
if previous is None:
    return []
```

### Executor-Only pronotepy Calls
**Source:** `coordinator.py` lines 101-110 (the `async_add_executor_job(partial(fetch_all, ...))` pattern)
**Apply to:** All pronotepy HTTP properties (`Period.overall_average`, `Period.grades`) — must stay inside `fetch_all`, never called from sensor `native_value` or `extra_state_attributes`

### `getattr` Fallback (No Silent Exceptions)
**Source:** `fetcher.py` lines 156-158 (`getattr(raw, "creation_date", None)`) + project memory `feedback_no_silent_exceptions.md`
**Apply to:** `entity.py` DeviceInfo.model, `_grade_from_raw` class context fields, any new pronotepy attribute access
```python
# Correct pattern — explicit visible default, not a swallowing catch:
class_label = getattr(client.info, CLASS_LEVEL_ATTR, None)
model = class_label or None  # "" → None; None stays None
```

### Final-typed Constants
**Source:** `const.py` lines 10-22 (every constant is `Final`-typed)
**Apply to:** All new constants in `const.py` Phase 4 appendix

### `@dataclass(frozen=True)` with Defaults
**Source:** `api/models.py:Snapshot` (lines 133-141 — `field(default_factory=list)` for list fields)
**Apply to:** New `Snapshot` fields `overall_average` and `period_name` use `= ""` defaults (not `field()`); new `Grade` fields use `= ""` defaults to preserve backward-compat with existing fixture JSON

### Test Class Structure
**Source:** `tests/test_diff/test_lessons.py` — `TestFirstPollInvariant`, `TestReorderNoOp`, `TestMultiChangeSynthetic` (class grouping by scenario)
**Apply to:** `test_grades.py`, `test_notifications.py`

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/fixtures/synthetic/_gen_heavy_class.py` | generator script | batch transform | No fixture generator exists in the codebase — closest is the committed `synthetic/*.json` files, but they were built manually. The generator's output format mirrors `Snapshot.to_dict()` exactly, so `api/models.py` is the indirect analog for the JSON schema. |

---

## Critical Gaps Surfaced (For Planner)

1. **`models.Grade` MUST be extended** — `api/models.py` currently has 5 fields; Phase 4 sensors require `class_average`, `class_min`, `class_max`, `comment`. Add as optional `str = ""` fields. Existing 9 Phase 2 synthetic fixtures will round-trip via `from_dict` with `data.get(..., "")` defaults.

2. **`models.Snapshot` MUST be extended** — `overall_average: str = ""` and `period_name: str = ""` must be added. `Period.overall_average` is a synchronous HTTP `@property`; it MUST be fetched inside `fetch_all` (executor) and stored in `Snapshot` — the sensor's `native_value` reads `coordinator.data.overall_average` (already a string).

3. **`api/fetcher.py` `_grade_from_raw` MUST be extended** — to copy `raw.average → Grade.class_average`, `raw.max → Grade.class_max`, `raw.min → Grade.class_min`, `raw.comment → Grade.comment`. CONTEXT.md's "Phase 4 does NOT modify `api/fetcher.py`" refers to the `fetch_all` signature/window, not to the private `_grade_from_raw` helper. This is a required Phase 4 change.

4. **PROBE-FIRST gate** — Plans 04-03, 04-04, 04-05 must be blocked until `PHASE-4-PROBE-NOTES.md` captures `Grade.average/.max/.min/.comment` presence on the real NC Pronote instance (STEP 6) and `ClientInfo.class_name` (STEP 11). The RESEARCH confirms these attributes exist in pronotepy source but they may be empty on the real instance.

5. **`test_sensor_no_lessons_attribute_in_state`** — this existing Phase 3 test will BREAK when TIME-02 attrs are added. It must be deleted (or inverted to assert `lessons_today` IS present).

6. **`test_diff/test_stubs.py`** — delete when `diff/grades.py` and `diff/notifications.py` bodies land (C-05). Both tests assert `NotImplementedError` which will no longer be raised.

---

## Metadata

**Analog search scope:** `custom_components/ha_pronote/` (all 7 modules + 2 subpackages), `tests/` (all 10 test files + 4 subdirectories), `.planning/phases/03-coordinator-first-sensor/03-PATTERNS.md`
**Files scanned:** 26
**Pattern extraction date:** 2026-05-24
