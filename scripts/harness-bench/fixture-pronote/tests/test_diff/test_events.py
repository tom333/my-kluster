"""Tests for diff/events.py — D-09 frozen taxonomy + Pattern 3 payload schema."""

from __future__ import annotations

import dataclasses
from datetime import date
import json
from typing import get_args

import pytest

from custom_components.ha_pronote.diff import ChangeType, DayLabel, LessonChange, NewGrade, NewInformation


def test_change_type_taxonomy_is_exactly_four_values():
    """D-09 + ROADMAP Phase 4 success criterion #1: frozen taxonomy."""
    assert set(get_args(ChangeType)) == {"canceled", "modified", "teacher", "room"}


def test_day_label_is_today_or_tomorrow():
    assert set(get_args(DayLabel)) == {"today", "tomorrow"}


def test_lesson_change_to_payload_is_json_serializable():
    change = LessonChange(
        change_type="canceled",
        day="today",
        lesson_date=date(2026, 5, 4),
        subject="Mathematiques",
        before={"canceled": False, "classroom": "A1"},
        after={"canceled": True, "classroom": "A1"},
    )
    payload = change.to_payload()
    round_tripped = json.loads(json.dumps(payload))
    assert round_tripped["change_type"] == "canceled"
    assert round_tripped["day"] == "today"
    assert round_tripped["lesson_date"] == "2026-05-04"
    assert round_tripped["subject"] == "Mathematiques"
    assert round_tripped["before"] == {"canceled": False, "classroom": "A1"}
    assert round_tripped["after"] == {"canceled": True, "classroom": "A1"}


def test_lesson_change_with_none_before():
    change = LessonChange(
        change_type="modified",
        day="tomorrow",
        lesson_date=date(2026, 5, 5),
        subject="Histoire",
        before=None,
        after={"x": 1},
    )
    payload = change.to_payload()
    assert payload["before"] is None
    assert payload["after"] == {"x": 1}


def test_lesson_change_with_none_after():
    change = LessonChange(
        change_type="canceled",
        day="today",
        lesson_date=date(2026, 5, 4),
        subject="Maths",
        before={"x": 1},
        after=None,
    )
    payload = change.to_payload()
    assert payload["after"] is None


def test_lesson_change_is_frozen():
    change = LessonChange("canceled", "today", date(2026, 5, 4), "Maths", None, None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        change.change_type = "modified"  # type: ignore[misc]


def test_new_grade_to_payload():
    g = NewGrade(
        subject="Maths",
        value="14,5",
        out_of="20",
        coefficient="1",
        date=date(2026, 5, 1),
    )
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
        g.value = "15,0"  # type: ignore[misc]


def test_new_information_to_payload_is_json_serializable():
    info = NewInformation(
        info_id="id1",
        title="Reunion parents",
        sender="Direction",
        date=date(2026, 5, 1),
        excerpt="Une reunion d'information aura lieu...",
    )
    payload = info.to_payload()
    round_tripped = json.loads(json.dumps(payload, ensure_ascii=False))
    assert round_tripped["info_id"] == "id1"
    assert round_tripped["title"] == "Reunion parents"
    assert round_tripped["sender"] == "Direction"
    assert round_tripped["date"] == "2026-05-01"
    assert round_tripped["excerpt"].startswith("Une reunion")


def test_new_information_is_frozen():
    info = NewInformation("id1", "T", "S", date(2026, 5, 1), "x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.title = "Y"  # type: ignore[misc]
