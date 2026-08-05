"""HA-side tests for Phase 4 sensors (D-13..D-17, ENT-02, ENT-03, TIME-01..03, GRADE-01..03, NOTIF-01..02)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.api import CommunicationError
from custom_components.ha_pronote.api.models import Grade, Information, Snapshot
from custom_components.ha_pronote.const import DOMAIN
from custom_components.ha_pronote.sensor import _to_float
from homeassistant.helpers import entity_registry as er

_SENSOR_ENTITY_ID_GUESS = "sensor.jean_dupont_cours_du_jour"


# ---------------------------------------------------------------------------
# Phase 5 Plan 05-04 — Gap closure: pin dt_util.now() to a clean NC school day
# ---------------------------------------------------------------------------
#
# Plan 05-03 added two short-circuits at the top of coordinator._async_update_data
# (lines 154-169) that return self.data without fetching when:
#   - self._backoff_until > now (backoff active), OR
#   - should_poll(now, options) == False (weekend / vacation / NC férié)
#
# If real-clock now() happens to be in any of those classes (e.g. running tests
# on a Saturday, during NC vacation, or on a férié like Pentecôte 2026-05-25),
# the existing Phase 3/4-era tests that drive _async_update_data() directly
# (without mocking time) hit the short-circuit and never reach their expected
# fetch-and-fail / fetch-and-emit paths.
#
# Fix: autouse module-level freezegun fixture pinning every test in this file
# to Thursday 2026-05-07 14:00 NC — a verified clean school day where
# should_poll == True, is_afternoon_window == False (14:00 < 17:00), and
# is_quiet_hours == False (14:00 ∉ [22:00, 06:00)).
@pytest.fixture(autouse=True)
def _frozen_school_day(freezer):
    """Pin dt_util.now() to Thu 2026-05-07 14:00 Pacific/Noumea for every test in this module.

    Phase 5 Plan 05-04 gap closure. Tests that need their own clock simply call
    ``freezer.move_to(...)`` at the top of the test body — that overrides this pin.
    """
    freezer.move_to(datetime(2026, 5, 7, 14, 0, 0, tzinfo=ZoneInfo("Pacific/Noumea")))
    return freezer


async def test_sensor_native_value_equals_lessons_today_count(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-14 / TIME-01: native_value = len(coordinator.data.lessons_today)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=3),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_SENSOR_ENTITY_ID_GUESS)
    assert state is not None, list(hass.states.async_entity_ids("sensor"))
    assert state.state == "3"


async def test_sensor_unique_id_locks_d13(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-13 / ENT-02: unique_id == 'pronote_jean_dupont_lessons_today' (FROZEN v1)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "pronote_jean_dupont_lessons_today")
    assert entity_id is not None, [
        (e.unique_id, e.entity_id) for e in registry.entities.values() if e.platform == DOMAIN
    ]


# NOTE — Phase 3 had a `test_sensor_class_attributes_lock_d15_d16` here that
# did pure-introspection of `PronoteLessonsTodaySensor._attr_*` slots. HA
# 2026.x's `Entity.__init_subclass__` now converts every `_attr_*` declaration
# into a cached_property descriptor at class-construction time, so neither
# direct `Cls.attr`, `vars(Cls)[attr]`, nor `inspect.getattr_static(Cls, attr)`
# can read the literal value the subclass wrote — the descriptor wins.
#
# The functional tests below (test_sensor_state_class_attribute_in_state,
# test_time02_attrs_present, etc.) exercise the same contract via instantiated
# entities and the HA state machine — that's the contract that actually matters.


async def test_sensor_state_class_attribute_in_state(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-16: state.attributes['state_class'] == 'measurement' (graphable in HA stats)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_SENSOR_ENTITY_ID_GUESS)
    assert state is not None
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") == "lessons"


async def test_time02_attrs_present(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """TIME-02 / D-02: extra_state_attributes has 'lessons_today' and 'lessons_tomorrow' keys."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_SENSOR_ENTITY_ID_GUESS)
    assert state is not None
    assert "lessons_today" in state.attributes
    assert "lessons_tomorrow" in state.attributes


async def test_time02_lessons_today_dict_shape(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """TIME-02 / D-02: each lesson in lessons_today is a full Lesson.to_dict() (8 fields)."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_SENSOR_ENTITY_ID_GUESS)
    assert state is not None
    lessons = state.attributes["lessons_today"]
    assert isinstance(lessons, list)
    assert len(lessons) == 2
    # Each lesson must have all 8 Lesson.to_dict() keys (D-02)
    expected_keys = {"date", "start", "end", "subject", "teacher", "classroom", "canceled", "status"}
    for lesson_dict in lessons:
        assert set(lesson_dict.keys()) == expected_keys, f"Missing keys: {expected_keys - set(lesson_dict.keys())}"


async def test_device_info_model_set_from_class_name(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """ENT-01 / D-19: DeviceInfo.model = ClientInfo.class_name when non-empty (eleve path)."""
    from homeassistant.helpers import device_registry as dr

    today = date(2026, 5, 7)
    mock_pronote_client.info.class_name = "3ème A"
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = list(device_registry.devices.values())
    assert len(devices) == 1
    device = devices[0]
    assert device.manufacturer == "Pronote"
    assert device.model == "3ème A"


async def test_device_info_model_none_when_class_name_empty(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """ENT-01 / D-19: DeviceInfo.model is None when class_name == '' (HA hides the row)."""
    from homeassistant.helpers import device_registry as dr

    today = date(2026, 5, 7)
    mock_pronote_client.info.class_name = ""  # empty string -> or None
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = list(device_registry.devices.values())
    assert len(devices) == 1
    assert devices[0].model is None


async def test_device_info_model_for_parent_client(
    hass,
    mock_config_entry,
    snapshot_with_n_lessons_today,
) -> None:
    """ENT-01 / D-19 (ParentClient path): DeviceInfo.model sources from children[child_index].

    PHASE-4-PROBE-NOTES.md STEP 11: client.info.class_name == "" for parent;
    child's class lives in client.children[child_index].class_name.
    """
    from unittest.mock import MagicMock

    import pronotepy
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ha_pronote.const import DOMAIN
    from homeassistant.helpers import device_registry as dr

    today = date(2026, 5, 7)

    # Simulate a ParentClient mock. NOTE: drop spec=pronotepy.ParentClient —
    # `info` is set in __init__ on the real class, not declared at class level,
    # so spec'd Mocks raise AttributeError on `.info` access. The isinstance()
    # check in entity.py is satisfied via __class__ assignment below.
    parent_client = MagicMock()
    parent_client.__class__ = pronotepy.ParentClient  # so isinstance() succeeds
    parent_client.info.name = "M. GUYADER Thomas"
    parent_client.info.class_name = ""  # parent has no class (probe-confirmed)
    child_mock = MagicMock()
    child_mock.class_name = "504"
    parent_client.children = [child_mock]
    parent_client.current_period = MagicMock()
    parent_client.current_period.grades = []
    parent_client.lessons = MagicMock(return_value=[])
    parent_client.information_and_surveys = MagicMock(return_value=[])
    parent_client.export_credentials = MagicMock(return_value={"token": "parent_tok"})
    parent_client.set_child = MagicMock()

    parent_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:parent:guyader_sacha",
        data={
            "url": "https://example.com/pronote/parent.html",
            "account_type": "parent",
            "username": "parent_user",
            "password": "pass",
            "session": {"token": "parent_tok"},
            "child_identifier": "guyader_sacha",
            "child_index": 0,
            "child_name": "GUYADER Sacha",
        },
        version=1,
    )
    parent_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=parent_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        await hass.config_entries.async_setup(parent_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = list(device_registry.devices.values())
    assert len(devices) == 1
    assert devices[0].model == "504"


async def test_sensor_unavailable_when_coordinator_fails(
    hass,
    mock_config_entry,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
) -> None:
    """D-15 + coordinator failure -> entity unavailable on the next refresh."""
    today = date(2026, 5, 7)
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=2),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    with patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        side_effect=CommunicationError("network down"),
    ):
        await coordinator.async_refresh()

    state = hass.states.get(_SENSOR_ENTITY_ID_GUESS)
    assert state is not None
    assert state.state == "unavailable"


# ── _to_float helper unit tests ────────────────────────────────────────────────


def test_to_float_comma_decimal() -> None:
    """D-03: comma-to-dot normalisation, common Pronote format."""
    assert _to_float("14,50") == 14.5
    assert _to_float("15,0") == 15.0
    assert _to_float("7,25") == 7.25


def test_to_float_dot_decimal() -> None:
    """D-03: dot decimal also accepted (e.g., after normalisation roundtrip)."""
    assert _to_float("14.5") == 14.5
    assert _to_float("20.0") == 20.0


def test_to_float_empty_returns_none() -> None:
    """D-03: empty string -> None (no grades published yet)."""
    assert _to_float("") is None


def test_to_float_invalid_returns_none() -> None:
    """D-03 / T-04-1: malformed string -> None, not crash."""
    assert _to_float("N/A") is None
    assert _to_float("—") is None
    assert _to_float("abs") is None


def test_to_float_minus_one() -> None:
    """Probe note: '-1' after comma->dot is '-1.0' -> not None from _to_float itself.

    The GradesSensor.native_value has a separate guard for the '-1' sentinel.
    _to_float itself returns -1.0 for "-1" (valid float). The GradesSensor
    guard is the one that returns None for "-1".
    """
    assert _to_float("-1") == -1.0


# ── PronoteGradesSensor tests ──────────────────────────────────────────────────


def _make_snapshot_with_grades(
    overall_average: str = "14,50",
    period_name: str = "Trimestre 2",
    grades: list | None = None,
) -> Snapshot:
    """Build a minimal Snapshot with given overall_average and grades list."""
    today = date(2026, 5, 7)
    grade_list = grades or [
        Grade(
            subject="Mathématiques",
            value="15",
            out_of="20",
            coefficient="2",
            date=date(2026, 5, 10),
            class_average="13",
            class_min="8",
            class_max="18",
            comment="Très bien",
        )
    ]
    return Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        overall_average=overall_average,
        period_name=period_name,
        grades=grade_list,
    )


async def test_grades_sensor_state_float(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """GRADE-01: state = 14.5 when overall_average = '14,50' (comma-to-dot normalised)."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades("14,50"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None, list(hass.states.async_entity_ids("sensor"))
    assert state.state == "14.5"


async def test_grades_sensor_state_none_when_empty(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """GRADE-01: state is 'unknown' when overall_average = '' (no grades published)."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades(""),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None
    assert state.state == "unknown"


async def test_grades_sensor_state_none_when_minus_one(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """GRADE-01: state is 'unknown' when overall_average = '-1' (pronotepy sentinel)."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades("-1"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None
    assert state.state == "unknown"


async def test_grades_attrs_schema(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """GRADE-02 / D-04: extra_state_attributes has 'period_name' and 'grades' with 9-field schema."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades("14,50"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None
    attrs = state.attributes
    assert "period_name" in attrs
    assert "grades" in attrs
    assert attrs["period_name"] == "Trimestre 2"
    grade_list = attrs["grades"]
    assert isinstance(grade_list, list)
    assert len(grade_list) == 1
    # D-04: 9 required fields per grade
    expected_keys = {
        "date",
        "subject",
        "grade",
        "out_of",
        "coefficient",
        "class_average",
        "class_min",
        "class_max",
        "comment",
    }
    assert set(grade_list[0].keys()) == expected_keys, f"Missing keys: {expected_keys - set(grade_list[0].keys())}"
    # D-03: grade value is float after normalisation
    assert grade_list[0]["grade"] == 15.0
    assert grade_list[0]["out_of"] == 20.0


async def test_grades_attrs_comment_truncated(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """D-04: comment capped at GRADE_COMMENT_MAX_LEN (200) chars."""
    long_comment = "x" * 300  # 300 chars > 200
    grade = Grade(
        subject="Math",
        value="15",
        out_of="20",
        coefficient="1",
        date=date(2026, 5, 10),
        comment=long_comment,
    )
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades("14,50", grades=[grade]),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None
    comment = state.attributes["grades"][0]["comment"]
    assert len(comment) == 200, f"Comment length {len(comment)} != 200"


async def test_grades_sorted_newest_first(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """D-06: grades sorted by date descending (newest first)."""
    grades = [
        Grade(subject="Math", value="12", out_of="20", coefficient="1", date=date(2026, 3, 1)),
        Grade(subject="Math", value="15", out_of="20", coefficient="1", date=date(2026, 5, 10)),
        Grade(subject="Math", value="8", out_of="20", coefficient="1", date=date(2026, 4, 15)),
    ]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_grades("14,50", grades=grades),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notes")
    assert state is not None
    dates = [g["date"] for g in state.attributes["grades"]]
    assert dates == ["2026-05-10", "2026-04-15", "2026-03-01"], f"Not sorted newest first: {dates}"


# ── PronoteNotificationsSensor tests ──────────────────────────────────────────


def _make_snapshot_with_infos(infos: list[Information]) -> Snapshot:
    """Build a minimal Snapshot with given information list."""
    return Snapshot(
        today=date(2026, 5, 7),
        school_tz="Pacific/Noumea",
        information=infos,
    )


def _make_info(
    info_id: str,
    read: bool = False,
    title: str | None = "Test titre",
    days_ago: int = 0,
) -> Information:
    """Builder for Information objects."""
    tz = ZoneInfo("Pacific/Noumea")
    dt = datetime(2026, 5, 7, 10, 0, tzinfo=tz) - timedelta(days=days_ago)
    return Information(
        info_id=info_id,
        title=title,
        sender="M. Test",
        date=dt,
        excerpt="Contenu de test.",
        read=read,
    )


async def test_notifications_sensor_state_unread_count(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """NOTIF-01 / D-05: state = count of info.read == False."""
    infos = [
        _make_info("i1", read=False),
        _make_info("i2", read=True),
        _make_info("i3", read=False),
    ]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None, list(hass.states.async_entity_ids("sensor"))
    assert state.state == "2"


async def test_notifications_sensor_state_all_read(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """NOTIF-01 / D-05: state = 0 when all informations are read."""
    infos = [_make_info("i1", read=True), _make_info("i2", read=True)]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None
    assert state.state == "0"


async def test_notifications_attrs_schema(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """NOTIF-02 / D-05: extra_state_attributes has 'unread_count' and 'informations' with 6-field schema."""
    infos = [_make_info("i1", read=False)]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None
    attrs = state.attributes
    assert "unread_count" in attrs
    assert "informations" in attrs
    assert attrs["unread_count"] == 1
    info_list = attrs["informations"]
    assert isinstance(info_list, list)
    assert len(info_list) == 1
    # D-05: 6 required fields per information
    expected_keys = {"info_id", "title", "sender", "date", "excerpt", "read"}
    assert set(info_list[0].keys()) == expected_keys, f"Missing: {expected_keys - set(info_list[0].keys())}"


async def test_notifications_attrs_capped_at_20(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """NOTIF-02 / D-05: informations list capped at NOTIFICATIONS_WINDOW = 20."""
    # 30 informations — only 20 most recent should appear in attrs
    infos = [_make_info(f"i{i}", read=False, days_ago=i) for i in range(30)]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None
    assert state.state == "30"  # unread count is still full 30
    info_list = state.attributes["informations"]
    assert len(info_list) == 20, f"Expected 20, got {len(info_list)}"


async def test_notifications_attrs_sorted_newest_first(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """D-06: informations sorted by date descending (most recent first)."""
    infos = [
        _make_info("old", days_ago=10),
        _make_info("new", days_ago=0),
        _make_info("mid", days_ago=5),
    ]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None
    ids = [i["info_id"] for i in state.attributes["informations"]]
    assert ids == ["new", "mid", "old"], f"Not sorted newest first: {ids}"


async def test_notifications_title_none_serialised_as_empty_string(
    hass,
    mock_config_entry,
    mock_pronote_client,
) -> None:
    """Probe STEP 7: title may be None — serialised as '' in attributes."""
    infos = [_make_info("i1", title=None)]
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=_make_snapshot_with_infos(infos),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.jean_dupont_notifications")
    assert state is not None
    title = state.attributes["informations"][0]["title"]
    assert title == "", f"Expected '' for None title, got {title!r}"


# Phase 6 — OPT-03 / D-13 / D-14 / D-16: nickname affects DeviceInfo.name only;
# unique_id and entity_id stay frozen (ENT-02). The strip + empty-as-None
# semantics are tested across the truthy / empty / whitespace / None cases.


@pytest.mark.parametrize(
    ("nickname_value", "expected_device_name"),
    [
        (None, "Jean Dupont"),  # missing → fallback to child_name
        ("", "Jean Dupont"),  # empty → fallback
        ("   ", "Jean Dupont"),  # whitespace-only → fallback
        ("Jeannot", "Jeannot"),  # truthy → nickname wins
        ("   Jeannot   ", "Jeannot"),  # strip applied → nickname wins
    ],
    ids=["none", "empty", "whitespace", "truthy", "stripped"],
)
async def test_device_info_nickname_fallback(
    hass,
    mock_pronote_client,
    snapshot_with_n_lessons_today,
    nickname_value,
    expected_device_name,
) -> None:
    """OPT-03 / D-13 / D-14: DeviceInfo.name = nickname (stripped) OR entry.data['child_name']."""
    from datetime import date

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ha_pronote.const import DOMAIN

    options = {} if nickname_value is None else {"nickname": nickname_value}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:alice:jean_dupont",
        data={
            "url": "https://example.com/pronote/eleve.html",
            "account_type": "eleve",
            "username": "alice",
            "password": "p",
            "session": None,
            "child_identifier": "jean_dupont",
            "child_index": None,
            "child_name": "Jean Dupont",
        },
        options=options,
        version=1,
    )
    entry.add_to_hass(hass)
    today = date(2026, 5, 7)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot_with_n_lessons_today(today, n=1),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Read the device from the device registry. The integration creates ONE
    # device per child via DeviceInfo(identifiers={(DOMAIN, child_identifier)}).
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, "jean_dupont")})
    assert device is not None
    assert device.name == expected_device_name
