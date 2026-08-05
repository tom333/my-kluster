"""Shared fixtures for HA-Pronote tests."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pronotepy
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_pronote.api.models import Lesson, Snapshot
from custom_components.ha_pronote.const import DOMAIN
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests.

    Without this, the ``hass`` fixture refuses to load anything from
    ``custom_components/`` and our integration would be invisible.
    """
    return


@pytest.fixture(autouse=True)
async def setup_ha_calendar_http_dependency(hass, request):
    """Phase 4 — HA's `calendar` platform depends on `http`. PHACC test HA
    doesn't auto-load `http`, so when our integration forwards Platform.CALENDAR
    (via const.PLATFORMS post-Plan 04-04), the `calendar` component fails its
    dependency setup and our entire entry setup fails with SETUP_ERROR.

    This fixture sets up `http` once per test BEFORE the integration's
    async_setup_entry runs. Test markers like `no_ha_http` opt out (used for
    pure-Python tests that don't need the full HA).
    """
    if "hass" in request.fixturenames and "no_ha_http" not in request.keywords:
        await async_setup_component(hass, "http", {})


# Phase 3 additions — HA-side test fixtures (C-05). MagicMock at the
# build_or_resume_client / build_client seam, NOT requests-mock at the HTTP layer
# (that strategy stays for tests/test_api/).


@pytest.fixture
def mock_pronote_client():
    """A MagicMock standing in for pronotepy.Client (eleve account).

    info.name, children=[], lessons(), current_period.grades, information_and_surveys(),
    export_credentials() — the surface fetch_all + build_or_resume_client touch.
    """
    client = MagicMock()
    client.info.name = "Jean Dupont"
    client.info.class_name = "3ème A"  # Phase 4 — CLASS_LEVEL_ATTR probe-confirmed
    client.children = []  # eleve = no parent-side children attribute used
    client.current_period = MagicMock()
    client.current_period.grades = []
    client.lessons = MagicMock(return_value=[])
    client.information_and_surveys = MagicMock(return_value=[])
    client.export_credentials = MagicMock(return_value={"token": "abc123"})
    return client


@pytest.fixture
def mock_parent_client_two_children():
    """A MagicMock for pronotepy.ParentClient with 2 children — D-02 pick_child path.

    `client.__class__ = pronotepy.ParentClient` makes `isinstance(client, pronotepy.ParentClient)`
    return True so config_flow.async_step_user takes the parent branch (otherwise it
    falls through to the eleve else-branch and `slugify(client.info.name)` crashes on
    the auto-MagicMock).
    """
    client = MagicMock()
    client.__class__ = pronotepy.ParentClient
    child0 = MagicMock()
    child0.name = "Alice Dupont"
    child0.identifier = "a3b4c5"
    child1 = MagicMock()
    child1.name = "Bob Dupont"
    child1.identifier = "d6e7f8"
    client.children = [child0, child1]
    client.set_child = MagicMock()
    client.lessons = MagicMock(return_value=[])
    client.current_period = MagicMock()
    client.current_period.grades = []
    client.information_and_surveys = MagicMock(return_value=[])
    client.export_credentials = MagicMock(return_value={"token": "parent_abc"})
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A MockConfigEntry with the D-08 entry.data shape pre-populated.

    Mirrors what config_flow._create_entry produces: the eight D-08 keys
    (url, account_type, username, password, session, child_identifier,
    child_index, child_name) plus the ``unique_id`` per D-05.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="example.com:user:jean_dupont",
        data={
            "url": "https://example.com/pronote/eleve.html",
            "account_type": "eleve",
            "username": "user",
            "password": "pass",
            "session": {"token": "abc123"},
            "child_identifier": "jean_dupont",
            "child_index": None,
            "child_name": "Jean Dupont",
        },
        version=1,
    )


@pytest.fixture
def make_lesson():
    """Builder that produces a tz-aware Lesson on a given date.

    Some sensor tests inject a Snapshot with N lessons today — this builder
    saves boilerplate. school_tz defaults to Pacific/Noumea (D-23 default).
    """

    def _build(today: date, hour: int = 8, subject: str = "Math") -> Lesson:
        tz = ZoneInfo("Pacific/Noumea")
        start = datetime(today.year, today.month, today.day, hour, 0, tzinfo=tz)
        end = datetime(today.year, today.month, today.day, hour + 1, 0, tzinfo=tz)
        return Lesson(
            date=today,
            start=start,
            end=end,
            subject=subject,
            teacher="Mme A",
            classroom="101",
            canceled=False,
            status="",
        )

    return _build


@pytest.fixture
def snapshot_with_n_lessons_today(make_lesson):
    """Builder that produces a Snapshot with N lessons on ``today``.

    Used by tests/test_sensor.py and tests/test_coordinator.py to inject a
    deterministic snapshot via patch("...coordinator.fetch_all", return_value=...).
    """

    def _build(today: date, n: int = 3) -> Snapshot:
        return Snapshot(
            today=today,
            school_tz="Pacific/Noumea",
            lessons=[make_lesson(today, hour=8 + i, subject=f"S{i}") for i in range(n)],
        )

    return _build


# Phase 4 additions — heavy-class snapshot + grades-capable mock client.


@pytest.fixture
def heavy_class_snapshot() -> Snapshot:
    """Load tests/fixtures/synthetic/heavy_class.json as a Snapshot.

    Used by tests/test_attribute_size.py CI gate (D-17). JSON committed
    alongside _gen_heavy_class.py (D-16). Verifies: >= 126 lessons, 100 grades,
    30 infos with overall_average "14,50" and period_name "Trimestre 2".
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
    mock_grade.average = "13"  # pronotepy attr name -> maps to Grade.class_average
    mock_grade.min = "8"  # pronotepy attr name -> maps to Grade.class_min
    mock_grade.max = "18"  # pronotepy attr name -> maps to Grade.class_max
    mock_grade.comment = ""
    mock_pronote_client.current_period.grades = [mock_grade]
    return mock_pronote_client


# Phase 7 (DIAG-02) — the circuit breaker now raises HA Repair Issues via
# issue_registry instead of persistent_notification. The issue registry works
# natively under PHACC (no wiring needed), so tests assert on it directly via
# `homeassistant.helpers.issue_registry.async_get(hass)`. This fixture is kept
# as a harmless passive guard for the many Phase 5 coordinator tests that list
# it as a parameter but never assert on it.


@pytest.fixture
def mock_persistent_notification():
    """No-op compatibility shim (breaker migrated to Repair Issues — DIAG-02).

    Returns a SimpleNamespace with unused `.create`/`.dismiss` MagicMocks so the
    legacy fixture signature stays valid. Tests that assert on breaker UX now use
    the issue registry directly (`ir.async_get(hass).async_get_issue(...)`).
    """
    from types import SimpleNamespace

    return SimpleNamespace(create=MagicMock(), dismiss=MagicMock())
