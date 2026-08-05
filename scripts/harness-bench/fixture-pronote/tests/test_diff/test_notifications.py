"""Tests for diff_notifications -- first-poll skip + identity-key set diff (D-14, EVENT-03, EVENT-04)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from custom_components.ha_pronote.api.models import Information, Snapshot
from custom_components.ha_pronote.diff import diff_notifications
from custom_components.ha_pronote.diff.events import NewInformation

_TZ = ZoneInfo("Pacific/Noumea")
_DEFAULT_DT = datetime(2026, 5, 10, 12, 0, tzinfo=_TZ)


def _make_snapshot(infos: list[Information]) -> Snapshot:
    return Snapshot(today=date(2026, 5, 10), school_tz="Pacific/Noumea", information=infos)


def _info(
    info_id: str = "1",
    d: datetime = _DEFAULT_DT,
) -> Information:
    return Information(info_id=info_id, title="T", sender="S", date=d, excerpt="E", read=False)


class TestFirstPollInvariant:
    def test_previous_none_with_info_returns_empty(self):
        """EVENT-04: no events on first poll."""
        assert diff_notifications(None, _make_snapshot([_info()])) == []

    def test_previous_none_empty_returns_empty(self):
        assert diff_notifications(None, _make_snapshot([])) == []


class TestIdentityKey:
    def test_same_info_emits_nothing(self):
        snap = _make_snapshot([_info()])
        assert diff_notifications(snap, snap) == []

    def test_new_info_emits_one_event(self):
        prev = _make_snapshot([_info(info_id="1")])
        new = _make_snapshot([_info(info_id="1"), _info(info_id="2")])
        result = diff_notifications(prev, new)
        assert len(result) == 1
        assert isinstance(result[0], NewInformation)
        assert result[0].info_id == "2"

    def test_date_is_date_not_datetime(self):
        """C-03: NewInformation.date must be date, not datetime (Information.date is datetime)."""
        prev = _make_snapshot([])
        new = _make_snapshot([_info()])
        result = diff_notifications(prev, new)
        assert len(result) == 1
        assert isinstance(result[0].date, date)
        # Verify it is NOT a datetime subclass instance (datetime IS a subclass of date)
        assert type(result[0].date) is date

    def test_returned_info_fields_match_source(self):
        prev = _make_snapshot([])
        new = _make_snapshot([_info(info_id="abc")])
        result = diff_notifications(prev, new)
        assert result[0].info_id == "abc"
        assert result[0].title == "T"
        assert result[0].sender == "S"
        assert result[0].excerpt == "E"
