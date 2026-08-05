"""HA-side tests for PronoteCalendar (CAL-01, CAL-02, D-07..D-09).

TDD RED: written before calendar.py exists.
TDD GREEN: passes once calendar.py is implemented.

Pure-Python tests (no hass fixture) cover:
  - _lesson_to_event: uid stability, cancelled prefix, description format, location
  - event property: None for all-past lessons, returns next upcoming
  - async_get_events: empty list for no lessons

HA-integration tests (with hass fixture) cover:
  - entity registration
  - range filter
  - cancelled prefix via async_get_events
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.api.models import Lesson, Snapshot

_TZ = ZoneInfo("Pacific/Noumea")


def _make_lesson(
    d: date,
    hour: int = 8,
    subject: str = "Math",
    canceled: bool = False,
    classroom: str = "B204",
    teacher: str = "Mme A",
) -> Lesson:
    """Build a tz-aware Lesson for tests."""
    start = datetime(d.year, d.month, d.day, hour, 0, tzinfo=_TZ)
    end = datetime(d.year, d.month, d.day, hour + 1, 0, tzinfo=_TZ)
    return Lesson(
        date=d,
        start=start,
        end=end,
        subject=subject,
        teacher=teacher,
        classroom=classroom,
        canceled=canceled,
        status="Cours annulé" if canceled else "",
    )


# ---------------------------------------------------------------------------
# Pure-Python tests (no hass fixture) — load-bearing, cannot skip
# ---------------------------------------------------------------------------


def test_lesson_to_event_uid_stability() -> None:
    """D-09: same lesson in two separate calls produces identical uid (no double-rendering)."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    lesson = _make_lesson(date(2026, 5, 10), subject="Mathématiques")

    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"

    cal = object.__new__(PronoteCalendar)
    cal._entry = entry  # noqa: SLF001

    event1 = cal._lesson_to_event(lesson)  # noqa: SLF001
    event2 = cal._lesson_to_event(lesson)  # noqa: SLF001

    assert event1.uid == event2.uid
    assert event1.uid is not None
    assert event1.uid.startswith("pronote_jean_dupont_")
    assert "mathematiques" in event1.uid  # slugify result


def test_lesson_to_event_cancelled_description() -> None:
    """D-09: cancelled lesson description ends with '\\nStatut: annulé'."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    lesson = _make_lesson(date(2026, 5, 10), subject="EPS", canceled=True, teacher="M. Dupont")
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"

    cal = object.__new__(PronoteCalendar)
    cal._entry = entry  # noqa: SLF001

    event = cal._lesson_to_event(lesson)  # noqa: SLF001

    assert "❌" in event.summary
    assert event.description == "Professeur: M. Dupont\nStatut: annulé"


def test_lesson_to_event_active_description() -> None:
    """D-09: active lesson description is 'Professeur: {teacher}' only."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    lesson = _make_lesson(date(2026, 5, 10), subject="Français", teacher="Mme Martin")
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"

    cal = object.__new__(PronoteCalendar)
    cal._entry = entry  # noqa: SLF001

    event = cal._lesson_to_event(lesson)  # noqa: SLF001

    assert event.summary == "Français"
    assert event.description == "Professeur: Mme Martin"


def test_lesson_to_event_empty_classroom_becomes_none() -> None:
    """D-09: empty classroom → CalendarEvent.location = None (HA hides the field)."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    lesson = _make_lesson(date(2026, 5, 10), classroom="")
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"

    cal = object.__new__(PronoteCalendar)
    cal._entry = entry  # noqa: SLF001

    event = cal._lesson_to_event(lesson)  # noqa: SLF001

    assert event.location is None


def test_lesson_to_event_non_empty_classroom_preserved() -> None:
    """D-09: non-empty classroom → CalendarEvent.location == classroom."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    lesson = _make_lesson(date(2026, 5, 10), classroom="S102")
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"

    cal = object.__new__(PronoteCalendar)
    cal._entry = entry  # noqa: SLF001

    event = cal._lesson_to_event(lesson)  # noqa: SLF001

    assert event.location == "S102"


def test_async_get_events_returns_empty_for_no_lessons() -> None:
    """async_get_events returns [] when the snapshot has zero lessons.

    REVISION fix: pure-Python test using object.__new__ + empty Snapshot — no hass.
    """
    from custom_components.ha_pronote.calendar import PronoteCalendar

    calendar = object.__new__(PronoteCalendar)
    coordinator = MagicMock()
    coordinator.data = Snapshot(
        today=date(2026, 5, 10),
        school_tz="Pacific/Noumea",
        lessons=[],
    )
    calendar.coordinator = coordinator
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"
    calendar._entry = entry  # noqa: SLF001

    start = datetime(2026, 5, 10, 0, 0, tzinfo=_TZ)
    end = datetime(2026, 5, 17, 23, 59, tzinfo=_TZ)

    events = asyncio.get_event_loop().run_until_complete(calendar.async_get_events(MagicMock(), start, end))
    assert events == []


def test_event_property_returns_none_for_past_lessons() -> None:
    """event property returns None when all lesson.end timestamps are in the past.

    REVISION fix: pure-Python test using object.__new__ — no hass.
    """
    from custom_components.ha_pronote.calendar import PronoteCalendar

    calendar = object.__new__(PronoteCalendar)
    coordinator = MagicMock()

    # Build a lesson definitively in the past
    past_end = datetime(2020, 1, 1, 9, 0, tzinfo=_TZ)
    past_lesson = Lesson(
        date=date(2020, 1, 1),
        start=datetime(2020, 1, 1, 8, 0, tzinfo=_TZ),
        end=past_end,
        subject="Ancien cours",
        teacher="M. Ancien",
        classroom="A1",
        canceled=False,
        status="",
    )
    coordinator.data = Snapshot(
        today=date(2020, 1, 1),
        school_tz="Pacific/Noumea",
        lessons=[past_lesson],
    )
    calendar.coordinator = coordinator
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"
    calendar._entry = entry  # noqa: SLF001

    assert calendar.event is None


def test_event_property_returns_next_lesson() -> None:
    """event property returns the first future lesson sorted by start."""
    from custom_components.ha_pronote.calendar import PronoteCalendar

    calendar = object.__new__(PronoteCalendar)
    coordinator = MagicMock()

    # Future date far enough ahead that it will always be in the future
    future_date = date(2099, 6, 1)
    future_lesson = Lesson(
        date=future_date,
        start=datetime(2099, 6, 1, 8, 0, tzinfo=_TZ),
        end=datetime(2099, 6, 1, 9, 0, tzinfo=_TZ),
        subject="Cours futur",
        teacher="Mme Future",
        classroom="F101",
        canceled=False,
        status="",
    )
    coordinator.data = Snapshot(
        today=future_date,
        school_tz="Pacific/Noumea",
        lessons=[future_lesson],
    )
    calendar.coordinator = coordinator
    entry = MagicMock()
    entry.runtime_data.child_identifier = "jean_dupont"
    calendar._entry = entry  # noqa: SLF001

    result = calendar.event
    assert result is not None
    assert result.summary == "Cours futur"


# ---------------------------------------------------------------------------
# HA-integration tests (with hass fixture) — entity registration + range filter
# ---------------------------------------------------------------------------


async def test_calendar_entity_created(hass, mock_config_entry, mock_pronote_client) -> None:
    """D-07: PronoteCalendar entity registered in hass.states."""
    today = date(2026, 5, 10)
    snap = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[_make_lesson(today)],
    )
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    calendar_ids = hass.states.async_entity_ids("calendar")
    assert len(calendar_ids) == 1, f"Expected 1 calendar entity, got: {calendar_ids}"


async def test_async_get_events_range_filter(hass, mock_config_entry, mock_pronote_client) -> None:
    """CAL-01: async_get_events returns only lessons within [start_date, end_date]."""
    today = date(2026, 5, 10)
    lesson_in = _make_lesson(today, hour=8, subject="In Range")
    lesson_out = _make_lesson(today + timedelta(days=10), hour=8, subject="Out of Range")
    snap = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[lesson_in, lesson_out],
    )
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Retrieve the PronoteCalendar entity object via entity_components
    entity_components = hass.data.get("entity_components", {})
    calendar_component = entity_components.get("calendar")
    if calendar_component is None:
        pytest.skip("Calendar entity_component not available in this PHACC version")

    calendar_ids = hass.states.async_entity_ids("calendar")
    if not calendar_ids:
        pytest.skip("No calendar entity registered")

    entity_obj = calendar_component.get_entity(calendar_ids[0])
    if entity_obj is None:
        pytest.skip("Calendar entity object not retrievable in this PHACC version")

    start = datetime(2026, 5, 10, 0, 0, tzinfo=_TZ)
    end = datetime(2026, 5, 10, 23, 59, tzinfo=_TZ)
    events = await entity_obj.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "In Range"


async def test_cancelled_lesson_has_x_prefix(hass, mock_config_entry, mock_pronote_client) -> None:
    """CAL-02 / D-09: CalendarEvent.summary starts with ❌ for canceled lessons."""
    today = date(2026, 5, 10)
    snap = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=[_make_lesson(today, subject="Maths", canceled=True)],
    )
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snap,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_components = hass.data.get("entity_components", {})
    calendar_component = entity_components.get("calendar")
    if calendar_component is None:
        pytest.skip("Calendar entity_component not available in this PHACC version")

    calendar_ids = hass.states.async_entity_ids("calendar")
    if not calendar_ids:
        pytest.skip("No calendar entity registered")

    entity_obj = calendar_component.get_entity(calendar_ids[0])
    if entity_obj is None:
        pytest.skip("Calendar entity object not retrievable in this PHACC version")

    start = datetime(2026, 5, 10, 0, 0, tzinfo=_TZ)
    end = datetime(2026, 5, 10, 23, 59, tzinfo=_TZ)
    events = await entity_obj.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary.startswith("❌")
