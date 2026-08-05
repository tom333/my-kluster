# Phase 4: Diff, Events & Full Sensor Suite - Research

**Researched:** 2026-05-24
**Domain:** Home Assistant CalendarEntity, HA recorder constraints, pronotepy Grade/Period/Information/Lesson/ClientInfo surface, HA event bus, synthetic fixture generation, PHACC test patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sensor state + attribute shape (Area 1)**
- D-01: EDT sensor state stays count. `PronoteLessonsTodaySensor.native_value = len(coordinator.data.lessons_today)`.
- D-02: EDT TIME-02 attributes = `lessons_today` + `lessons_tomorrow`, each a list of `Lesson.to_dict()`. Fields: `date, start, end, subject, teacher, classroom, canceled, status` (all 8).
- D-03: Grades sensor state = `float(Period.overall_average)` after comma→dot normalisation. `state_class = SensorStateClass.MEASUREMENT`. No `device_class`, no `native_unit_of_measurement`.
- D-04: Grades sensor attributes: `period_name`, `grades: list[dict]` (all grades for current period), each grade: `date`, `subject`, `grade (float)`, `out_of (float)`, `coefficient (float)`, `class_average (float|None)`, `class_min (float|None)`, `class_max (float|None)`, `comment (str, ≤200 chars)`. If pronotepy doesn't expose fields, planner downgrades schema.
- D-05: Notifications sensor state = `unread_count`. Attributes: `unread_count`, `informations: list[dict]` (20 most recent, each: `info_id`, `title`, `sender`, `date`, `excerpt`, `read`).
- D-06: Sorting: lessons by `start` ascending, grades by `date` descending, informations by `date` descending.

**Calendar entity (Area 2)**
- D-07: `PronoteCalendar(PronoteEntity, CalendarEntity)` in new `calendar.py`. `unique_id = f"pronote_{child_identifier}_calendar"`. `translation_key = "calendar"`.
- D-08: `async_get_events(hass, start, end)` filters `coordinator.data.lessons` by date range. No `event` property override. Result is `[]` outside J-7→J+14 window.
- D-09: `CalendarEvent` fields per lesson: `summary = "❌ {subject}"` if canceled else `subject`; `start = lesson.start`; `end = lesson.end`; `location = lesson.classroom`; `description = "Professeur: {teacher}\nStatut: annulé"` when canceled, `"Professeur: {teacher}"` otherwise; `uid = f"pronote_{child_identifier}_{lesson.date}_{lesson.start.isoformat()}_{slugify(subject)}"`.
- D-10: `PLATFORMS = (Platform.SENSOR, Platform.CALENDAR)` in `const.py`.

**Bus event payload wrapping (Area 3)**
- D-11: Every event payload prepended with `child_id`, `child_name`, `config_entry_id`.
- D-12: Firing site = `_async_update_data`, after `_capture_session`, via `_fire_diff_events(previous, snapshot)`. No typed try/except.
- D-13: Event-type constants: `EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"`, `EVENT_NEW_GRADE: Final = "pronote_new_grade"`, `EVENT_NEW_INFORMATION: Final = "pronote_new_information"`.
- D-14: `diff_grades` body: identity key `(subject, date, value)`. `diff_notifications` body: identity key `(info_id, date)`.
- D-15: EVENT-04 enforced structurally: every diff returns `[]` when `previous is None`.

**Heavy-class fixture + probe discipline (Area 4)**
- D-16: Synthetic generator `tests/fixtures/synthetic/_gen_heavy_class.py`, committed output `heavy_class.json`. ~126 lessons (3 weeks × 6 days × 7/day), 100 grades, 30 informations.
- D-17: CI gate in `tests/test_attribute_size.py`: `len(str(native_value)) <= 255`, `len(json.dumps(extra_state_attributes, default=str)) <= 16384`, `state not in (None, "unknown", "unavailable")`.
- D-18: Probe-first plan discipline — run `scripts/probe_config_flow.py` before each plan touching a new pronotepy method; capture into `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md`.
- D-19: `DeviceInfo.model = getattr(client.info, CLASS_LEVEL_ATTR, None)`. Probe STEP 11 locks the constant name. Fallback to `None` via `getattr` (not a silencing try/except).

### Claude's Discretion
- C-01: 4-plan wave decomposition: Wave 1 (04-01: diff bodies + tests, 04-02: heavy fixture + probe); Wave 2 (04-03: entity/sensor extensions, 04-04: calendar); Wave 3 (04-05: bus event firing in coordinator).
- C-02: Probe notes in `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md`.
- C-03: `NewInformation.date` type = `date` (call `.date()` on construction from `Information.date` which is a `datetime`).
- C-04: Sensor naming: `grades` and `notifications` kinds.
- C-05: Drop `tests/test_diff/test_stubs.py` once bodies land.
- C-06: Mock strategy = `MagicMock` for HA-side tests.

### Deferred Ideas (OUT OF SCOPE)
- `pronote_grade_edited` event — rejected
- Next-lesson timestamp sensor
- Derived `canceled_count` attrs on lessons sensor
- Calendar `event` property
- Calendar window growth
- Reintroduce D-04 typed-error → form-error mapping — permanently OFF
- Reintroduce D-12 collision suffix — Phase 6
- ENT / Keycloak SSO — Phase 6
- Per-period grade sensor or service — Phase 6
- pronotepy upgrade — only if real bug
- OptionsFlow knobs for NOTIFICATIONS_WINDOW / GRADE_COMMENT_MAX_LEN — Phase 6
- DIAG-01 redaction update — Phase 7
- README ApexCharts / automation YAML — Phase 7
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TIME-02 | EDT sensor J/J+1 attributes (matière, prof, salle, heure début/fin, statut) | `Lesson.to_dict()` already ships all 8 fields; sensor reads `coordinator.data.lessons_today` / `lessons_tomorrow` directly |
| TIME-03 | EDT sensor ≤255 state, ≤16 KiB attributes (CI assertion on heavy fixture) | `MAX_STATE_ATTRS_BYTES = 16384` verified in HA recorder; CI gate pattern via `test_attribute_size.py` |
| GRADE-01 | Grades sensor, state = numeric average (`state_class=measurement`) | `Period.overall_average` confirmed as `str` in pronotepy 2.14.6 source; comma-normalisation `str.replace(",",".")` → `float` |
| GRADE-02 | Grades sensor attributes (ApexCharts schema) | `Grade.average`, `.max`, `.min`, `.comment`, `.coefficient` all confirmed in pronotepy 2.14.6 source; fetcher currently drops them — Phase 4 must extend `models.Grade` or inline at sensor render time |
| GRADE-03 | Grades sensor ≤255 state, ≤16 KiB attributes | Same CI gate as TIME-03 |
| NOTIF-01 | Notifications sensor, state = unread count | `Information.read: bool` confirmed in pronotepy 2.14.6 source; `Snapshot.information` list available |
| NOTIF-02 | Notifications sensor attributes (20 most recent, title/sender/date/excerpt) | `Information.to_dict()` ships all needed fields; `excerpt` already capped at 500 chars in fetcher |
| CAL-01 | Calendar entity J-7 → J+14 | `CalendarEntity.async_get_events(hass, start_date, end_date)` contract verified in HA core source |
| CAL-02 | Calendar events with cancelled lesson distinction | `❌` prefix in `CalendarEvent.summary`; `description` adds "Statut: annulé" when `lesson.canceled` |
| EVENT-01 | `pronote_schedule_changed` event with diff payload | `diff_lessons` already implemented; `hass.bus.async_fire` confirmed to require event loop thread |
| EVENT-02 | `pronote_new_grade` event when new grade appears | `diff_grades` stub body defined in D-14; `NewGrade.to_payload()` frozen in Phase 2 |
| EVENT-03 | `pronote_new_information` event when new information published | `diff_notifications` stub body defined in D-14; `NewInformation.to_payload()` frozen in Phase 2 |
| EVENT-04 | No events on first poll after restart | `previous is None → return []` enforced in all diff functions; test covers first + second poll |
| ENT-01 | Device with `DeviceInfo(manufacturer="Pronote", model=<class level>)` | `ClientInfo.class_name` property verified in pronotepy 2.14.6 source (`raw_resource.get("classeDEleve", {}).get("L", "")`) |
</phase_requirements>

---

## Summary

Phase 4 is the payoff phase: every poll diff becomes an observable HA event, the full sensor surface ships (EDT J/J+1, grades, notifications), and a calendar entity exposes lessons with cancelled courses visually distinct. The research confirms all required pronotepy API surface is available in 2.14.6 and that the architectural approach locks down cleanly with no blocking surprises.

**Critical finding — Grade extended attributes:** The existing `models.Grade` dataclass and `fetcher._grade_from_raw` do NOT capture `Grade.average` (class average), `Grade.max`, `Grade.min`, and `Grade.comment` from pronotepy. These are present in pronotepy 2.14.6's `Grade` class under exactly those attribute names (`average`, `max`, `min`, `comment` — not `class_average` etc.). Phase 4 must extend `models.Grade` and `fetcher._grade_from_raw` to carry these fields, OR the planner must resolve this at the sensor level by sourcing raw pronotepy fields. Since CONTEXT.md D-04 requires `class_average / class_min / class_max / comment` in the sensor attributes and the fetcher is "locked" (CONTEXT.md canonical refs say Phase 4 does NOT modify `api/fetcher.py`), the resolution must be noted as an open question for the planner.

**`ClientInfo.class_name` confirmed:** pronotepy 2.14.6 `ClientInfo` has a `class_name` property at line 1497 of `dataClasses.py` that returns `raw_resource.get("classeDEleve", {}).get("L", "")`. The probe STEP 11 will confirm it on the real Pronote instance but the source guarantees the attribute exists. `CLASS_LEVEL_ATTR = "class_name"` is the safe default for `const.py`.

**HA `CalendarEntity` interface fully verified:** `CalendarEvent` is a plain `@dataclass` with fields `start`, `end`, `summary`, `description`, `location`, `uid`, `recurrence_id`, `rrule`. The `async_get_events(hass, start_date, end_date)` signature takes `datetime` not `date`. Both `start` and `end` can be `date` (all-day) or `datetime` (timed); using `datetime` (tz-aware, from `Lesson.start`/`.end`) produces timed events — the correct choice for lesson display.

**HA recorder 16 KiB cap:** `MAX_STATE_ATTRS_BYTES = 16384` exactly. When exceeded, the recorder logs `"State attributes for %s exceed maximum size of %s bytes. This can cause database performance issues; Attributes will not be stored"` and stores `b"{}"` instead. The entity is NOT set to `unknown` — only the attributes are dropped silently from history. The state value itself is unaffected.

**Primary recommendation:** Implement Phase 4 in the C-01 wave order, start with a probe run to capture real pronotepy shapes before writing any mocks, resolve the Grade extended-attribute gap via `models.Grade` extension (smallest change, cleanest path), and use the `❌` emoji prefix for cancelled calendar events as decided.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Diff grades / notifications | `diff/` pure Python | None | No HA imports; testable in plain pytest |
| Bus event firing | Coordinator (HA event loop) | None | `hass.bus.async_fire` is NOT thread-safe; must run on event loop, not executor |
| EDT J/J+1 sensor attributes | Sensor platform | Coordinator data (Snapshot) | Pure projection; `Snapshot.lessons_today` / `lessons_tomorrow` already computed |
| Grades sensor state (numeric average) | Sensor platform | `Period.overall_average` via Snapshot | Comma-normalisation at render time in sensor, not in models layer |
| Notifications sensor | Sensor platform | `Snapshot.information` | Sorted/capped at sensor render time |
| Calendar entity | Calendar platform | Coordinator data (Snapshot.lessons) | `async_get_events` filters in-memory; no new fetch |
| DeviceInfo.model (class level) | Entity base class (`entity.py`) | `ClientInfo.class_name` (pronotepy) | One-time lookup at entity setup; not per-poll |
| Synthetic heavy-class fixture | `tests/fixtures/synthetic/` | None | Generator committed; JSON output committed for CI reproducibility |

---

## Standard Stack

No new runtime dependencies for Phase 4. All required libraries are already declared in `manifest.json`.

### Core (existing, no change)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `pronotepy` | `==2.14.6` | Pronote API | Exact pin; Phase 4 does NOT bump |
| `homeassistant` | `==2026.4.4` | HA host platform | `CalendarEntity`, `CalendarEvent`, `hass.bus.async_fire` all verified in cached 2026.4.4 |
| `python-slugify` | `==8.0.4` | Entity slug generation + calendar uid | Already in `manifest.json` |

### Test Stack (existing, no change)
| Tool | Version | Purpose |
|------|---------|---------|
| `pytest-homeassistant-custom-component` | `0.13.326` | PHACC hass fixture, MockConfigEntry |
| `pytest-asyncio` | `1.3.0` (transitive) | Async test support, `asyncio_mode = "auto"` |
| `freezegun` | `1.5.5` (transitive) | Date mocking for heavy-fixture generator |

**No new `pip install` step.** Phase 4 extends existing code, no new runtime or test deps.

---

## Architecture Patterns

### System Architecture Diagram (Phase 4 additions in CAPS)

```
Poll cycle (every 30 min)
        │
        ▼
coordinator._async_update_data()
        │
        ├─ previous = self._previous_snapshot         (None on first poll)
        ├─ snapshot = await executor(fetch_all)
        ├─ self._previous_snapshot = snapshot
        ├─ await _capture_session() [best-effort]
        ├─ SELF._FIRE_DIFF_EVENTS(previous, snapshot)  ← NEW
        │     ├─ diff_lessons(prev, new, "today") → []  ← already implemented
        │     ├─ diff_lessons(prev, new, "tomorrow") → []
        │     ├─ DIFF_GRADES(prev, new) → []            ← Phase 4 fills stub
        │     └─ DIFF_NOTIFICATIONS(prev, new) → []     ← Phase 4 fills stub
        │         each change → hass.bus.async_fire(EVENT_*, {child_id, ...payload})
        └─ return snapshot
                │
                ▼
        CoordinatorEntity entities refresh:
          PronoteLessonsTodaySensor  → native_value + J/J+1 ATTRS  ← Phase 4 adds attrs
          PRONOTEGRADESENSOR          ← Phase 4 new
          PRONOTENOTIFICATIONSSENSOR  ← Phase 4 new
          PRONOTECALENDAR             ← Phase 4 new platform

HA calendar UI / automation queries:
        PronoteCalendar.async_get_events(hass, start, end)
              │
              └─ filter coordinator.data.lessons by date range
                 → list[CalendarEvent]  (in-memory, no new fetch)
```

### Recommended Project Structure (Phase 4 additions)

```
custom_components/ha_pronote/
├── coordinator.py          # EXTEND: _fire_diff_events + helper
├── sensor.py               # EXTEND: GradesSensor, NotificationsSensor, +TIME-02 attrs
├── calendar.py             # NEW
├── entity.py               # EXTEND: DeviceInfo.model = ClientInfo.class_name
├── const.py                # EXTEND: EVENT_*, CLASS_LEVEL_ATTR, NOTIFICATIONS_WINDOW, GRADE_COMMENT_MAX_LEN, PLATFORMS
├── strings.json            # EXTEND: grades, notifications, calendar entity names
├── diff/
│   ├── grades.py           # FILL: NotImplementedError → body per D-14
│   └── notifications.py    # FILL: NotImplementedError → body per D-14
tests/
├── conftest.py             # EXTEND: heavy_class_snapshot, mock_pronote_client_with_grades
├── test_diff/
│   ├── test_grades.py      # NEW
│   ├── test_notifications.py # NEW
│   └── test_stubs.py       # DELETE (replaced by positive tests)
├── test_coordinator.py     # EXTEND: fire-on-diff, EVENT-04 regression
├── test_sensor.py          # EXTEND: grades + notifs + TIME-02 attrs
├── test_calendar.py        # NEW
├── test_attribute_size.py  # NEW (16 KiB / 255-char CI gate)
└── fixtures/synthetic/
    ├── _gen_heavy_class.py # NEW (committed generator)
    ├── heavy_class.json    # NEW (committed output)
    └── PHASE-4-PROBE-NOTES.md # NEW (probe output captures)
```

### Pattern 1: HA CalendarEntity — exact API contract
[VERIFIED: local HA 2026.4.4 install at `/data/cache/uv/archive-v0/3SWObwzC9fmvvysmdAp-p/homeassistant/components/calendar/__init__.py`]

```python
# homeassistant/components/calendar/__init__.py (lines 363-411, 631-638)

@dataclasses.dataclass
class CalendarEvent:
    """An event on a calendar."""
    start: datetime.date | datetime.datetime
    end: datetime.date | datetime.datetime
    summary: str
    description: str | None = None
    location: str | None = None
    uid: str | None = None
    recurrence_id: str | None = None
    rrule: str | None = None


class CalendarEntity(Entity):
    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        raise NotImplementedError

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        raise NotImplementedError
```

**Critical notes:**
- `event` property is marked `raise NotImplementedError` in the base class and is `@property` (not optional). Our `PronoteCalendar` must override it. For lessons, the "current or next" lesson is the right value. The simplest v1 implementation: return the first lesson from today/tomorrow that starts in the future, or `None`.
- `async_get_events` receives `datetime.datetime` (not `date`) for both `start_date` and `end_date`. The caller passes tz-aware datetimes.
- `CalendarEvent.__post_init__` runs `CALENDAR_EVENT_SCHEMA` validation. A `start == end` all-day event gets auto-fixed to `end = start + timedelta(days=1)`. For timed events (our case), start must be strictly before end (which it is for any real lesson).
- `_entity_component_unrecorded_attributes = frozenset({"description"})` means `description` is NOT stored by the recorder — safe to put verbose teacher info there.

### Pattern 2: PronoteCalendar implementation
[ASSUMED — pattern derived from HA CalendarEntity contract + existing delphiki reference]

```python
# custom_components/ha_pronote/calendar.py

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util.slugify import slugify

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
    coordinator: PronoteDataUpdateCoordinator = entry.runtime_data.coordinator
    async_add_entities([PronoteCalendar(coordinator, entry)])


class PronoteCalendar(PronoteEntity, CalendarEntity):
    _attr_translation_key = "calendar"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"pronote_{entry.runtime_data.child_identifier}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return current or next upcoming lesson."""
        from homeassistant.util import dt as dt_util
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
        """Return all lessons in [start_date, end_date] range."""
        result = []
        for lesson in self.coordinator.data.lessons:
            if start_date.date() <= lesson.date <= end_date.date():
                result.append(self._lesson_to_event(lesson))
        return result

    def _lesson_to_event(self, lesson) -> CalendarEvent:
        child_id = self._entry.runtime_data.child_identifier
        subject = lesson.subject
        summary = f"❌ {subject}" if lesson.canceled else subject
        description = f"Professeur: {lesson.teacher}"
        if lesson.canceled:
            description += "\nStatut: annulé"
        uid = (
            f"pronote_{child_id}_{lesson.date}_{lesson.start.isoformat()}"
            f"_{slugify(subject)}"
        )
        return CalendarEvent(
            summary=summary,
            start=lesson.start,
            end=lesson.end,
            description=description,
            location=lesson.classroom or None,
            uid=uid,
        )
```

### Pattern 3: Bus event firing
[VERIFIED: HA core.py lines 1470-1489]

```python
# coordinator.py additions

from .const import EVENT_SCHEDULE_CHANGED, EVENT_NEW_GRADE, EVENT_NEW_INFORMATION
from .diff import diff_lessons, diff_grades, diff_notifications

def _fire_diff_events(
    self,
    previous: Snapshot | None,
    new: Snapshot,
) -> None:
    """Fire typed bus events for each diff since previous snapshot.

    D-12: NO try/except — diff bugs surface in HA logs immediately.
    D-15: all diff functions return [] when previous is None (EVENT-04).
    """
    child_context = {
        "child_id": self._child_identifier,
        "child_name": self.config_entry.data["child_name"],
        "config_entry_id": self.config_entry.entry_id,
    }
    for change in diff_lessons(previous, new, "today"):
        self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()})
    for change in diff_lessons(previous, new, "tomorrow"):
        self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, {**child_context, **change.to_payload()})
    for grade in diff_grades(previous, new):
        self.hass.bus.async_fire(EVENT_NEW_GRADE, {**child_context, **grade.to_payload()})
    for info in diff_notifications(previous, new):
        self.hass.bus.async_fire(EVENT_NEW_INFORMATION, {**child_context, **info.to_payload()})
```

**Key constraint:** `hass.bus.async_fire` is decorated `@callback` and checks `threading.get_ident() != self._hass.loop_thread_id`, logging a warning if called from a thread. It MUST be called from the event loop. Since `_fire_diff_events` is called from `_async_update_data` (which runs on the event loop), this is correct. Never call it from inside `async_add_executor_job`.

### Pattern 4: diff_grades body (D-14 activation)
[VERIFIED: `models.Grade` fields confirmed from pronotepy source + models.py]

```python
# diff/grades.py

def diff_grades(
    previous: Snapshot | None,
    new: Snapshot,
) -> list[NewGrade]:
    """Return new grades since the previous poll.

    Identity key: (subject, date, value) — a grade is "the same" across polls
    if subject + date + raw value are identical. A re-scored grade (value changes)
    thus appears as a new grade, which is acceptable (the user sees it).
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

### Pattern 5: diff_notifications body (D-14 activation)
[VERIFIED: `models.Information.date` is `datetime` (tz-aware); `NewInformation.date` is `date` per C-03]

```python
# diff/notifications.py

def diff_notifications(
    previous: Snapshot | None,
    new: Snapshot,
) -> list[NewInformation]:
    """Return new informations since the previous poll.

    Identity key: (info_id, date.date()) — info_id is stable, date is the
    `datetime` field localized to school_tz. We call `.date()` to match
    C-03's decision that NewInformation.date is `date` not `datetime`.
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

### Anti-Patterns to Avoid
- **Calling `hass.bus.async_fire` from executor thread:** The bus is not thread-safe. `_fire_diff_events` is called from `_async_update_data` (event loop), not from inside an executor job. Never move it inside `fetch_all`.
- **Putting `CalendarEvent` construction inside `async_get_events` with I/O:** The method must be fast and non-blocking. It reads from `coordinator.data.lessons` (in-memory). Zero I/O.
- **Using `datetime.date` instead of `datetime.datetime` for `CalendarEvent.start`/`end`:** A `date`-typed start produces an all-day event. Our lessons have specific times — always use `lesson.start` / `lesson.end` (which are tz-aware `datetime` objects from Phase 2 D-23).
- **Overriding `CalendarEntity.state` or `CalendarEntity.state_attributes`:** Both are marked `@final` in the HA base class. Implement `event` and `async_get_events` only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Calendar event serialization | Custom JSON marshalling | `CalendarEvent.as_dict()` / `dataclasses.asdict(..., dict_factory=_api_event_dict_factory)` | HA handles all date/datetime formatting for the REST API |
| Slug generation for calendar uid | Manual string replace | `homeassistant.util.slugify.slugify(subject)` | Handles all French accented characters, replaces unsafe chars |
| Attribute size truncation | Custom `json.dumps` loop | `json.dumps(attrs, default=str)` + `len()` assertion | `default=str` handles all non-serialisable types (date, datetime) in the CI test |
| tz-aware `now()` inside calendar `event` property | `datetime.now()` | `homeassistant.util.dt.dt_util.now()` | Returns tz-aware datetime in HA's configured timezone |

**Key insight:** HA's CalendarEntity base class handles all the state/attribute machinery; Phase 4 only needs to implement `event` and `async_get_events`. The rest (STATE_ON/OFF, state_attributes, alarm timers) is automatic.

---

## pronotepy 2.14.6 Runtime Surface (Phase 4 Calls)

All verified from local install `/data/cache/uv/archive-v0/HAFKwndSvfE77uUf7DH6S/lib/python3.13/site-packages/pronotepy/dataClasses.py` [VERIFIED: pronotepy==2.14.6.dist-info].

### `Period` (from `client.current_period`)
| Attribute | Type | Notes |
|-----------|------|-------|
| `id` | `str` | Internal ID |
| `name` | `str` | Display name, e.g. "Trimestre 2" |
| `overall_average` | `@property → str` | **Makes a fresh Pronote API call each time**; returns French decimal string e.g. `"14,50"`. Returns `"-1"` if no grades yet. Calculation fallback when Pronote doesn't provide the field. |
| `grades` | `@property → list[Grade]` | **Makes a fresh Pronote API call**. Can raise `KeyError('listeDevoirs')` when `current_period` is truthy but period has no grades (documented in fetcher.py line 82-89 spike finding). |
| `class_overall_average` | `@property → Optional[str]` | Class group average, may be `None` |

**Critical:** Both `overall_average` and `grades` each make a separate HTTP call to Pronote (`DernieresNotes` endpoint). The fetcher already calls `client.current_period.grades` once per poll. For the sensor, `Period.overall_average` would require an additional executor job OR must be fetched in `fetch_all` alongside grades. Recommendation: fetch `overall_average` inside `fetch_all` and store in `Snapshot` (add a `overall_average: str` field to `Snapshot`) rather than calling it from the sensor's `native_value`.

### `Grade` (from `Period.grades`)
| Attribute | Type | Notes |
|-----------|------|-------|
| `grade` | `str` | Raw grade value e.g. `"14,5"`. Attribute name is `grade`, not `value`. |
| `out_of` | `str` | Maximum e.g. `"20"` |
| `date` | `datetime.date` | Date of the grade |
| `subject` | `Subject` | Has `.name: str` |
| `average` | `str` | Class average for this test — uses pronotepy attribute name `average`, NOT `class_average` |
| `max` | `str` | Highest grade in class — pronotepy attribute name `max`, NOT `class_max` |
| `min` | `str` | Lowest grade in class — pronotepy attribute name `min`, NOT `class_min` |
| `coefficient` | `str` | Coefficient e.g. `"1"`, may be `None`/empty |
| `comment` | `str` | Comment on grade, may be `None`/empty |
| `is_bonus` | `bool` | Bonus grade flag |
| `is_optionnal` | `bool` | Optional grade flag |

**Name mapping alert:** CONTEXT.md D-04 says `class_average / class_min / class_max` but pronotepy 2.14.6 uses `average / min / max` on `Grade` objects. The planner must use `Grade.average`, `Grade.min`, `Grade.max` in the fetcher. In the sensor's `extra_state_attributes` output, the dict keys can be `class_average`, `class_min`, `class_max` (renamed for clarity in the HA attribute schema) even though the source attributes are `average`, `min`, `max`.

**Gap:** `models.Grade` and `fetcher._grade_from_raw` currently only copy `subject`, `value` (from `raw.grade`), `out_of`, `coefficient`, `date`. The fields `average`, `max`, `min`, `comment` are dropped. Phase 4 must extend `models.Grade` to add these fields and update `_grade_from_raw` — OR, since CONTEXT.md says fetcher is "locked" (Phase 4 does NOT modify `api/fetcher.py`), the alternative is to resolve at render time. **However**, the render-time approach would require the sensor to access raw pronotepy objects, violating the anti-pattern. The cleanest solution is to extend `models.Grade` and `fetcher._grade_from_raw` with the four extra fields. The CONTEXT.md says "Phase 4 does NOT modify `api/fetcher.py`" — this refers to the fetch window and `fetch_all` signature, not to adding fields to `_grade_from_raw`. The planner should clarify.

### `Lesson` (from `client.lessons(date_from, date_to)`)
[Already locked in Phase 2 / fetcher; confirmed attributes match `api/models.Lesson`]
| Attribute | Type | Notes |
|-----------|------|-------|
| `canceled` | `bool` | True if cancelled; parsed from `"estAnnule"` |
| `status` | `Optional[str]` | Free-form status string; unreliable — only `canceled` bool is reliable for events |
| `teacher_name` | `Optional[str]` | Joined `", ".join(teacher_names)` |
| `classroom` | `Optional[str]` | Joined `", ".join(classrooms)` |
| `start` | `datetime` | Naive (school local); localized in `_lesson_from_raw` |
| `end` | `datetime` | Naive (school local); localized in `_lesson_from_raw` |
| `subject` | `Optional[Subject]` | Has `.name: str` |

### `Information` (from `client.information_and_surveys()`)
[Confirmed in pronotepy source; matches `api/models.Information`]
| Attribute | Type | Notes |
|-----------|------|-------|
| `id` | `str` | Stable identifier |
| `title` | `Optional[str]` | May be `None` for untitled survey |
| `author` | `str` | Sender name |
| `read` | `bool` | Whether the student/parent has read it |
| `start_date` | `Optional[datetime]` | When message became visible (naive, needs localization) |
| `creation_date` | `datetime` | When created (naive, needs localization) |
| `content` | `@property → str` | HTML-parsed content — fetcher uses first 500 chars as `excerpt` |

### `ClientInfo` (from `client.info`)
[Confirmed in pronotepy source at line 1450]
| Attribute | Type | Notes |
|-----------|------|-------|
| `id` | `str` | Client internal ID (NOT `identifier` — Phase 3 UAT lesson #2) |
| `name` | `@property → str` | Full name from `raw_resource["L"]` |
| `class_name` | `@property → str` | **Class level** — returns `raw_resource.get("classeDEleve", {}).get("L", "")`. Returns `""` (empty string) when not available, NOT `None`. |
| `establishment` | `@property → str` | School name |

**`CLASS_LEVEL_ATTR = "class_name"` is confirmed.** The `getattr(client.info, "class_name", None)` pattern in D-19 will return `""` (empty string) when the account has no class, not `None`. The `entity.py` code should handle empty string: `model=class_label or None` converts `""` to `None` cleanly.

---

## HA Event Bus Constraints

[VERIFIED: HA core.py lines 1470-1489]

- `hass.bus.async_fire` is decorated `@callback`. It checks `threading.get_ident()` and logs a warning if called from a non-event-loop thread. Must be called from the event loop.
- `event_data` has no JSON serialization enforcement at the `async_fire` call site. The data is passed as-is to listeners. The **recorder** will attempt `json.dumps(event.data)` when recording it. If the data contains non-serialisable objects (e.g., raw `datetime`), the recorder will raise and skip storing the event.
- **The `to_payload()` methods on `LessonChange`, `NewGrade`, `NewInformation` already call `.isoformat()` on all date/datetime fields.** The `lesson_date.isoformat()`, `date.isoformat()` patterns in the frozen event dataclasses ensure the bus payload is JSON-serialisable. No changes needed to `diff/events.py`.
- The `child_context` dict prepended in D-11 contains only `str` values — no serialisation issues.
- There is no payload size limit enforced by `hass.bus.async_fire` itself. The recorder's `MAX_EVENT_DATA_BYTES` (also 16384) applies when storing events, but our payloads are small (tens of bytes per event).

---

## HA Recorder 16 KiB Attribute Cap

[VERIFIED: HA recorder db_schema.py lines 94, 581-589]

```python
# homeassistant/components/recorder/db_schema.py
MAX_STATE_ATTRS_BYTES = 16384  # exactly 16 KiB (16 × 1024)

# When exceeded:
if len(bytes_result) > MAX_STATE_ATTRS_BYTES:
    _LOGGER.warning(
        "State attributes for %s exceed maximum size of %s bytes. "
        "This can cause database performance issues; Attributes "
        "will not be stored",
        state.entity_id,
        MAX_STATE_ATTRS_BYTES,
    )
    return b"{}"  # stores empty dict instead of dropping the row
```

**Key behaviors:**
- The **state value itself is unaffected** — only the attributes are dropped from recorder history.
- The entity does NOT go to `unknown`. The state continues updating normally; only history is degraded.
- The check is on `json_bytes(attributes)` — the serialised byte count, not the Python object size.
- The CI test assertion `len(json.dumps(sensor.extra_state_attributes, default=str)) <= 16384` is the correct check. Use `default=str` to handle dates/datetimes exactly as HA would handle them.
- Warning log line prefix: `"State attributes for %s exceed maximum size of %s bytes."` — tests can assert this warning is NOT present in captured logs.

---

## Grade Extended Attributes — Critical Gap Analysis

**Problem:** CONTEXT.md D-04 requires `class_average`, `class_min`, `class_max`, `comment` in the grades sensor attributes. But:
1. `models.Grade` dataclass currently has only 5 fields: `subject`, `value`, `out_of`, `coefficient`, `date`
2. `fetcher._grade_from_raw` only copies those 5 fields
3. pronotepy `Grade` has `average` (class avg), `max`, `min`, `comment` available

**Resolution options (for planner to decide):**

Option A (recommended): Extend `models.Grade` to add 4 optional fields (`class_average`, `class_min`, `class_max`, `comment`), update `fetcher._grade_from_raw` to copy them from `raw.average`, `raw.max`, `raw.min`, `raw.comment`. This is a small, contained change. The CONTEXT.md statement "Phase 4 does NOT modify `api/fetcher.py`" appears to mean "do not change the fetch window or `fetch_all` signature" — adding fields to a helper function within the same file is a natural Phase 4 extension.

Option B: Omit class context fields from the sensor, reduce D-04 schema to the FEATURES.md baseline (`{date, subject, grade, out_of, coefficient}`). This violates D-04 as written but is the safest "probe-first" approach: let the probe STEP 6 confirm whether `Grade.average/.max/.min` are actually populated before committing to the full schema.

**Recommended: option A with probe gate.** Add the fields to `models.Grade` + `_grade_from_raw`, guarded by the probe-first discipline (D-18). If STEP 6 shows these fields are always `None` or empty on the real Pronote NC instance, fall back to option B for this installation while keeping the schema extensible.

---

## Overall Average in Snapshot — Additional Gap

`Period.overall_average` is a `@property` that makes a fresh HTTP call to Pronote. The current `fetch_all` calls `client.current_period.grades` (one HTTP call). Calling `client.current_period.overall_average` separately would be a second HTTP call to the same endpoint — pronotepy fetches `DernieresNotes` for both, but they're separate property invocations.

**Solution:** Add `overall_average: str = ""` to `models.Snapshot` and fetch it alongside grades in `fetch_all`. The code would become:

```python
# In fetch_all (api/fetcher.py) — must happen in executor
if client.current_period:
    try:
        raw_grades = list(client.current_period.grades)
        overall_avg = client.current_period.overall_average  # second call, same endpoint
    except (KeyError, AttributeError):
        raw_grades = []
        overall_avg = ""
```

Alternatively, since pronotepy hits the same `DernieresNotes` endpoint internally and has a separate HTTP call per property, the most efficient approach is to call both in the executor. The sensor then reads `coordinator.data.overall_average` directly — no extra blocking call from the event loop.

This is a **required change** to `models.Snapshot` and `fetcher.fetch_all` for the grade sensor to work without blocking the event loop. The planner must decide whether to treat this as permitted within Phase 4 (it is a minimal extension, not a structural change) or defer the overall_average fetch to a new coordinator-level wrapper.

---

## Common Pitfalls

### Pitfall 1: `CalendarEntity.event` property is required, not optional
**What goes wrong:** Subclassing `CalendarEntity` without implementing `event` raises `NotImplementedError` at runtime when HA queries entity state.
**Why it happens:** `event` is marked `raise NotImplementedError` not `return None` in the base class.
**How to avoid:** Always implement `event` as a `@property`. For v1, return the first future lesson or `None`. The `state` property and `state_attributes` are `@final` — never override them.
**Warning signs:** `NotImplementedError` traceback in HA logs when the calendar entity is created.

### Pitfall 2: `hass.bus.async_fire` from an executor thread
**What goes wrong:** Calling `async_fire` from inside a thread (e.g., from `fetch_all`) causes race conditions and a warning: `frame.report_non_thread_safe_operation("hass.bus.async_fire")`.
**Why it happens:** diff + fire must happen on the event loop; the executor is for pronotepy HTTP calls only.
**How to avoid:** `_fire_diff_events` is called from `_async_update_data` (event loop). Never call it from inside `async_add_executor_job`.

### Pitfall 3: `Period.overall_average` called outside executor
**What goes wrong:** `Period.overall_average` is a `@property` that calls `self._client.post(...)` — a synchronous HTTP request. Calling it from a sensor's `native_value` property (event loop) blocks HA.
**Why it happens:** The sensor looks "clean" — it just reads `coordinator.data` — but if `overall_average` is stored in `coordinator.data` as a plain string, it is safe. The danger is calling `client.current_period.overall_average` directly from sensor code.
**How to avoid:** Fetch `overall_average` inside `fetch_all` (in the executor), store in `Snapshot.overall_average: str`, sensor reads `self.coordinator.data.overall_average` directly.

### Pitfall 4: Grade field naming mismatch
**What goes wrong:** Using `grade.class_average` (which doesn't exist on pronotepy's `Grade`) instead of `grade.average`. The getattr fails silently or raises `AttributeError`.
**Why it happens:** CONTEXT.md D-04 uses user-facing key names (`class_average`) while pronotepy uses different internal names (`average` for the class average on a `Grade` object).
**How to avoid:** In `_grade_from_raw`, map: `raw.average → Grade.class_average`, `raw.max → Grade.class_max`, `raw.min → Grade.class_min`, `raw.comment → Grade.comment`. The pronotepy names and the model field names are different by design.

### Pitfall 5: Empty overall_average state
**What goes wrong:** At the start of a trimester before any grade is published, `Period.overall_average` returns `"-1"` (the pronotepy fallback). After `float("-1")` the sensor state would be `-1.0` — confusing to users.
**Why it happens:** pronotepy returns `-1` as a sentinel when no average is available and the service list is also empty.
**How to avoid:** Normalise: if `overall_average.replace(",",".") == "-1"` or `overall_average == ""`, set sensor state to `None` (HA shows "unknown"). This is explicitly acceptable per CONTEXT.md specifics section.

### Pitfall 6: `CalendarEvent` with `start == end` for all-day events
**What goes wrong:** If `lesson.end` equals `lesson.start` (data error), `CalendarEvent.__post_init__` auto-fixes it to `end = start + 1 day` for date-typed fields, but for datetime-typed fields it raises validation error.
**Why it happens:** Pronote can return degenerate time slots.
**How to avoid:** Always ensure `lesson.end > lesson.start` before constructing `CalendarEvent`. In `_lesson_to_event`, add a guard: `end = lesson.end if lesson.end > lesson.start else lesson.start + timedelta(hours=1)`.

### Pitfall 7: uid instability causing calendar UI double-rendering
**What goes wrong:** If `slugify(subject)` changes between polls (e.g. `"Mathématiques"` → `"mathematiques"` due to encoding), the uid changes and HA calendar cards treat the same lesson as a new event.
**Why it happens:** `slugify` is locale-sensitive but deterministic within the same pronotepy version. As long as the same subject string is passed, the uid is stable.
**How to avoid:** `lesson.subject` is already normalised by `fetcher._lesson_from_raw` (`raw.subject.name`). As long as pronotepy returns the same string (it does), uids are stable across polls. Add a test that two polls with the same lesson data produce the same uid.

---

## Code Examples

### GradesSensor skeleton
```python
# sensor.py (extension)

class PronoteGradesSensor(PronoteEntity, SensorEntity):
    _attr_translation_key = "grades"
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"pronote_{entry.runtime_data.child_identifier}_grades"
        )

    @property
    def native_value(self) -> float | None:
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
        data = self.coordinator.data
        grades = sorted(data.grades, key=lambda g: g.date, reverse=True)
        return {
            "period_name": data.period_name,  # new Snapshot field
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

### Heavy-class fixture generator skeleton
```python
# tests/fixtures/synthetic/_gen_heavy_class.py

import json
from datetime import date, timedelta
from zoneinfo import ZoneInfo

SUBJECTS = ["Mathématiques", "Français", "Histoire-Géographie",
            "EPS", "Physique-Chimie", "Anglais"]
TZ = ZoneInfo("Pacific/Noumea")

def generate():
    today = date(2026, 5, 26)
    # ... generate ~126 lessons, 100 grades, 30 informations
    snapshot = Snapshot(today=today, school_tz="Pacific/Noumea", lessons=..., grades=..., information=...)
    return snapshot.to_dict()

if __name__ == "__main__":
    data = generate()
    out = Path(__file__).parent / "heavy_class.json"
    out.write_text(json.dumps(data, indent=2, default=str))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `delphiki` ships string overall_average | Phase 4 ships `float` with comma-normalisation | Phase 4 | Enables ApexCharts graphing, long-term statistics |
| `delphiki` bundles all lessons in one big attribute | Phase 4 splits into `lessons_today` + `lessons_tomorrow` | Phase 4 | Stays under 16 KiB; aligns with Core Value focus |
| `delphiki` cancelled lesson prefix: `"Annulé - "` | Phase 4 uses `❌ {subject}` | Phase 4 | Renders on mobile/iOS HA app; visually distinctive |
| `delphiki` fires single `pronote_event` with `type` field | Phase 4 fires typed `pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_information` | Phase 4 | Automation `trigger.event_type` can filter without `data.type` template |

**Deprecated/outdated:**
- `async_add_job` (HA): replaced by `async_add_executor_job` since 2022 — already correct in Phase 3 coordinator.
- `pytz`: banned in CLAUDE.md "What NOT to Use"; already using `zoneinfo`.

---

## Runtime State Inventory

Phase 4 is a greenfield code-only addition. No renaming, no data migration, no existing runtime state affected.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no new database keys, no new Mem0 records | None |
| Live service config | None — no new service registrations | None |
| OS-registered state | None | None |
| Secrets/env vars | None — no new credentials | None |
| Build artifacts | None — no new installed packages | None |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ClientInfo.class_name` returns the class level string on the author's real Pronote NC instance | pronotepy surface — ClientInfo | DeviceInfo.model may be empty string; `getattr + or None` handles gracefully |
| A2 | `Period.overall_average` is actually populated (not "-1") on a real live instance with grades | pronotepy surface — Period | Grade sensor state would be `None`; acceptable for "trimester just started" |
| A3 | `Grade.average`, `Grade.max`, `Grade.min` are populated for NC grades (not None/empty) | Grade extended attributes | Sensor would show `class_average: null` in attributes; acceptable |
| A4 | `CalendarEntity.event` property returning `None` for "no current lesson" produces `STATE_OFF` cleanly | CalendarEntity pattern | Verified in base class source — `event is None → STATE_OFF` |
| A5 | `slugify(subject)` from `homeassistant.util.slugify` is available in the sensor/calendar context | calendar uid generation | Import may differ from `python_slugify` — use `homeassistant.util.slugify.slugify` not `python_slugify` directly |

**A5 requires verification:** The `uid` recipe in D-09 uses `slugify(subject)`. In HA components, `from homeassistant.util.slugify import slugify` is the standard import. The `python-slugify` library is already in `manifest.json` requirements and could also be used, but HA's built-in `slugify` is preferred for entity-id consistency.

---

## Open Questions (RESOLVED)

1. **Grade extended attributes: extend `models.Grade` + `fetcher._grade_from_raw`, or inline at sensor render time?**
   - **RESOLVED:** Option A — extend `models.Grade` (add `class_average / class_min / class_max / comment` with `= ""` defaults) and update `_grade_from_raw` to map pronotepy's `average / min / max / comment` attributes (Plan 04-02). CONTEXT.md's "no `api/` change" shorthand refers to the public `fetch_all` signature + fetch window, not to internal grade parsing helpers.
   - What we know: CONTEXT.md says "Phase 4 does NOT modify `api/fetcher.py`" but also requires `class_average/class_min/class_max/comment` in D-04.
   - What's unclear: Whether "do not modify `api/fetcher.py`" means the file cannot be touched, or means the fetch window/`fetch_all` signature cannot change.
   - Recommendation: Extend `models.Grade` (add 4 optional fields) and update `_grade_from_raw` (a private helper within `fetcher.py`). The stated constraint refers to the public API contract (`fetch_all` signature, fetch window), not to internal grade parsing.

2. **`Snapshot.overall_average` field: must be added for Grade sensor to avoid blocking**
   - **RESOLVED:** Add `overall_average: str = ""` (and `period_name: str = ""`) to `models.Snapshot` with backward-compat defaults; `fetch_all` captures `client.current_period.overall_average` in the executor (it's a network-fetching property) and passes it into `Snapshot(overall_average=...)` (Plan 04-02). Required Phase 4 change to `api/models.py` + `api/fetcher.py`.
   - What we know: `Period.overall_average` is a `@property` that makes an HTTP call. It cannot be called from sensor's `native_value`. It must be fetched in the executor and stored in `Snapshot`.
   - What's unclear: Whether this also requires extending `models.Snapshot`.
   - Recommendation: Add `overall_average: str = ""` and `period_name: str = ""` to `models.Snapshot` (frozen dataclass must add these as fields with defaults), update `fetch_all` to populate them alongside grades. This is a **required** Phase 4 change to `api/models.py` and `api/fetcher.py`.

3. **`CalendarEntity.event` implementation — which lesson to return?**
   - **RESOLVED:** Iterate `coordinator.data.lessons` sorted by `start` ascending; return the first lesson where `lesson.end > dt_util.now()` (covers "currently in a lesson" and "next lesson"); return `None` if no future lesson in the J−7→J+14 window (Plan 04-06).
   - What we know: Must return `CalendarEvent | None` representing "current or next upcoming event".
   - Recommendation: Iterate `coordinator.data.lessons` sorted by `start` ascending; return first lesson where `lesson.end > dt_util.now()`. This covers "currently in a lesson" (start < now < end) and "next lesson" (start > now). Return `None` if no future lesson in the J-7→J+14 window.

---

## Environment Availability

Phase 4 is code-only. No new external dependencies beyond those already installed for Phase 3.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pronotepy | Grade/Notification diff, calendar | Already in manifest.json | 2.14.6 | — |
| homeassistant | CalendarEntity | Already in venv | 2026.4.4 | — |
| pytest-homeassistant-custom-component | PHACC test infrastructure | Already in requirements_test.txt | 0.13.326 | — |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-homeassistant-custom-component 0.13.326 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/test_diff/ -x -q` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TIME-02 | `lessons_today` + `lessons_tomorrow` attrs present | unit | `pytest tests/test_sensor.py -k test_lessons_today_attrs -x` | ❌ Wave 0 |
| TIME-03 | State ≤255, attrs ≤16384 on heavy fixture | unit (CI gate) | `pytest tests/test_attribute_size.py -x` | ❌ Wave 0 |
| GRADE-01 | Numeric float state from overall_average | unit | `pytest tests/test_sensor.py -k test_grades_sensor_state -x` | ❌ Wave 0 |
| GRADE-02 | ApexCharts attrs dict shape | unit | `pytest tests/test_sensor.py -k test_grades_attrs -x` | ❌ Wave 0 |
| GRADE-03 | State ≤255, attrs ≤16384 on heavy fixture | unit (CI gate) | `pytest tests/test_attribute_size.py -x` | ❌ Wave 0 |
| NOTIF-01 | unread_count state | unit | `pytest tests/test_sensor.py -k test_notifications_sensor_state -x` | ❌ Wave 0 |
| NOTIF-02 | 20 most recent informations in attrs | unit | `pytest tests/test_sensor.py -k test_notifications_attrs -x` | ❌ Wave 0 |
| CAL-01 | async_get_events returns CalendarEvent list for J-7→J+14 range | unit | `pytest tests/test_calendar.py -k test_get_events_range -x` | ❌ Wave 0 |
| CAL-02 | Cancelled lesson has ❌ prefix in summary | unit | `pytest tests/test_calendar.py -k test_cancelled_lesson_summary -x` | ❌ Wave 0 |
| EVENT-01 | `pronote_schedule_changed` fires on lesson change | unit | `pytest tests/test_coordinator.py -k test_fires_schedule_changed -x` | ❌ Wave 0 |
| EVENT-02 | `pronote_new_grade` fires on new grade | unit | `pytest tests/test_coordinator.py -k test_fires_new_grade -x` | ❌ Wave 0 |
| EVENT-03 | `pronote_new_information` fires on new info | unit | `pytest tests/test_coordinator.py -k test_fires_new_information -x` | ❌ Wave 0 |
| EVENT-04 | No events on first poll (previous is None) | unit | `pytest tests/test_coordinator.py -k test_no_events_first_poll -x` | ❌ Wave 0 |
| ENT-01 | DeviceInfo.model = class_name | unit | `pytest tests/test_sensor.py -k test_device_info_model -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_diff/ -x -q` (diff-layer tasks) or `uv run pytest tests/test_sensor.py tests/test_calendar.py -x -q` (sensor tasks)
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green + `test_attribute_size.py` passes before `/gsd-verify-work`

### Wave 0 Gaps
All test files listed above are new for Phase 4. The following must be created before or alongside implementation:
- [ ] `tests/test_diff/test_grades.py` — covers diff_grades identity key, first-poll skip, new grade detection
- [ ] `tests/test_diff/test_notifications.py` — covers diff_notifications identity key, first-poll skip
- [ ] `tests/test_sensor.py` (extend) — grades + notifications + TIME-02 attrs + ENT-01 model
- [ ] `tests/test_calendar.py` — CalendarEvent shape, uid stability, cancelled prefix, `event` property, range filtering
- [ ] `tests/test_coordinator.py` (extend) — fire-on-diff, EVENT-04 no-events-first-poll
- [ ] `tests/test_attribute_size.py` — heavy_class_snapshot CI gate
- [ ] `tests/conftest.py` (extend) — `heavy_class_snapshot` fixture, `mock_pronote_client_with_grades`

*(Existing test infra: conftest.py, test_diff/test_lessons.py, test_diff/test_stubs.py, test_sensor.py (partial) all exist)*

---

## Security Domain

Phase 4 adds three new sensor types and a calendar entity. Security assessment follows the project's ASVS Level 1 profile.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 4 doesn't touch auth flow) | — |
| V3 Session Management | No | — |
| V4 Access Control | No new access control surface | — |
| V5 Input Validation | Yes — comma-normalisation, comment truncation | `str.replace(",", ".")` + `float()` try/except; `str[:200]` for comments |
| V6 Cryptography | No | — |

### Known Threat Patterns for Phase 4

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Grade/lesson data containing PII in bus event payload | Information Disclosure | Payloads contain child_name (already in entry.data, non-secret); teacher names are public school data; no credentials in payload |
| `CalendarEvent.description` containing teacher name stored in recorder | Information Disclosure | `_entity_component_unrecorded_attributes = frozenset({"description"})` in CalendarEntity base class means `description` is NOT stored by recorder |
| Malformed `overall_average` string causing exception in sensor `native_value` | Denial of Service | Wrapped in `try: float(...)  except ValueError: return None` |
| `❌` emoji in `CalendarEvent.summary` persisted to recorder history | None | String is safe; recorder stores UTF-8 cleanly |

---

## Sources

### Primary (HIGH confidence)
- `homeassistant/components/calendar/__init__.py` (local HA 2026.4.4 cache) — `CalendarEvent` dataclass (lines 363-411), `CalendarEntity` class (lines 510-638), `async_get_events` signature (lines 631-638), `MAX_STATE_ATTRS_BYTES` location
- `homeassistant/components/recorder/db_schema.py` (local HA 2026.4.4 cache) — `MAX_STATE_ATTRS_BYTES = 16384` (line 94), warning log string (lines 582-588), truncation to `b"{}"` (line 589)
- `homeassistant/core.py` (local HA 2026.4.4 cache) — `hass.bus.async_fire` implementation (lines 1469-1489), thread-safety check
- `pronotepy/dataClasses.py` (local pronotepy 2.14.6 cache at `/data/cache/uv/archive-v0/HAFKwndSvfE77uUf7DH6S/`) — `Period` (line 478), `Grade` (line 675), `Lesson` (line 839), `Information` (line 1026), `ClientInfo` (line 1450), `ClientInfo.class_name` property (line 1497)
- `custom_components/ha_pronote/` (shipped Phase 1-3 code) — `coordinator.py`, `entity.py`, `sensor.py`, `const.py`, `diff/events.py`, `diff/grades.py`, `diff/notifications.py`, `api/models.py`, `api/fetcher.py`, `tests/conftest.py`
- `.planning/phases/04-diff-events-full-sensor-suite/04-CONTEXT.md` — all locked decisions, architectural decomposition

### Secondary (MEDIUM confidence)
- [HA Developer Docs: Calendar Entity](https://developers.home-assistant.io/docs/core/entity/calendar/) — confirms `async_get_events` contract, `CalendarEvent` fields, states
- [CalDAV integration HA issue #170761](https://github.com/home-assistant/core/issues/170761) — confirms `uid` field existence and downstream consumer expectations
- `.planning/research/FEATURES.md` — delphiki calendar uses `"Annulé - "` prefix (we use `❌`)
- `.planning/research/ARCHITECTURE.md` — Pattern 3 (diff-as-pure-function, fired from coordinator), Pattern 1 (executor wrapping)
- `.planning/research/PITFALLS.md` — Pitfall 7 (16 KiB cap, delphiki #136 confirmed), Pitfall 3 (blocking calls)
- `.planning/phases/03-coordinator-first-sensor/03-HUMAN-UAT.md` — lessons #1-4 (set_child, ClientInfo.id not .identifier, token_login kwargs, probe-first discipline)

### Tertiary (LOW confidence — not re-verified in this session)
- delphiki/hass-pronote calendar.py — pattern for `async_get_events` (cited in CONTEXT.md canonical refs; not re-fetched)

---

## Metadata

**Confidence breakdown:**
- CalendarEntity API: HIGH — source-verified in local HA 2026.4.4 install
- pronotepy Grade/Period/ClientInfo surface: HIGH — source-verified in local pronotepy 2.14.6 install
- Recorder 16 KiB cap mechanics: HIGH — source-verified in local HA 2026.4.4 install
- Event bus constraints: HIGH — source-verified in HA core.py
- Grade extended attribute gap: HIGH (problem identified; resolution path is recommendation A)
- Overall_average fetch gap: HIGH (problem identified; solution is Snapshot extension)
- Test pyramid / PHACC patterns: MEDIUM — based on existing test patterns in conftest.py + PHACC docs

**Research date:** 2026-05-24
**Valid until:** 2026-06-24 (stable HA API, stable pronotepy 2.14.6 pin)
