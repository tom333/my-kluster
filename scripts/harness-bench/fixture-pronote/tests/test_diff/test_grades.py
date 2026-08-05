"""Tests for diff_grades -- first-poll skip + identity-key set diff (D-14, EVENT-02, EVENT-04)."""

from __future__ import annotations

from datetime import date

from custom_components.ha_pronote.api.models import Grade, Snapshot
from custom_components.ha_pronote.diff import diff_grades
from custom_components.ha_pronote.diff.events import NewGrade


def _make_snapshot(grades: list[Grade]) -> Snapshot:
    return Snapshot(today=date(2026, 5, 10), school_tz="Pacific/Noumea", grades=grades)


def _grade(subject: str = "Math", value: str = "15", d: date = date(2026, 5, 10)) -> Grade:
    return Grade(subject=subject, value=value, out_of="20", coefficient="1", date=d)


class TestFirstPollInvariant:
    def test_previous_none_with_grades_returns_empty(self):
        """EVENT-04: no events on first poll."""
        assert diff_grades(None, _make_snapshot([_grade()])) == []

    def test_previous_none_empty_snapshot_returns_empty(self):
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
        assert isinstance(result[0], NewGrade)
        assert result[0].subject == "Français"

    def test_different_value_same_subject_date_emits_event(self):
        """Re-scored grade is treated as new (acceptable -- user sees it)."""
        prev = _make_snapshot([_grade(value="14")])
        new = _make_snapshot([_grade(value="15")])
        assert len(diff_grades(prev, new)) == 1

    def test_returned_grade_fields_match_source(self):
        prev = _make_snapshot([])
        new = _make_snapshot([_grade(subject="EPS", value="16", d=date(2026, 5, 9))])
        result = diff_grades(prev, new)
        assert result[0].subject == "EPS"
        assert result[0].value == "16"
        assert result[0].out_of == "20"
        assert result[0].date == date(2026, 5, 9)

    def test_no_false_positives_on_multiple_subjects(self):
        grades = [_grade("Math"), _grade("Français"), _grade("EPS")]
        snap = _make_snapshot(grades)
        assert diff_grades(snap, snap) == []
