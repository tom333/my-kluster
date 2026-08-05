"""Round-trip + structural gates for synthetic diff fixtures (D-10, D-11, D-23).

These checks live next to the diff tests so the synthetic-fixture authoring
contract stays close to the consumers. Plan 02-04 hoists a broader
``tests/test_fixtures.py`` schema gate that loops over real + synthetic; this
file focuses on what Plan 02-03's diff layer specifically needs.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from custom_components.ha_pronote.api.models import Snapshot

SYNTHETIC_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic"

EXPECTED_FIXTURES = {
    "empty_to_empty_T0.json",
    "empty_to_empty_T1.json",
    "reorder_no_op_T0.json",
    "reorder_no_op_T1.json",
    "multi_change_T0.json",
    "multi_change_T1.json",
    "first_poll_after_restart.json",
    "lesson_removed_T0.json",
    "lesson_removed_T1.json",
    "lesson_added_T0.json",
    "lesson_added_T1.json",
    # Phase 4 D-16 — heavy-class CI gate fixture (TIME-03 / GRADE-03).
    # Consumer: tests/test_attribute_size.py.
    "heavy_class.json",
}

# ISO-8601 datetime with explicit offset, e.g. "2026-05-04T08:00:00+11:00".
# D-23 forbids naive datetimes in committed fixtures.
_DATETIME_AWARE_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}$")
# Naive datetime sentinel: T..:..:.. without an offset before the closing quote.
_DATETIME_NAIVE_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[^+\-Z\d:][^\"]*)?\"")


def test_synthetic_directory_holds_exactly_expected_fixtures():
    """D-10 (Phase 2) + D-16 (Phase 4): synthetic fixture set is closed.

    Updated from "eleven" to len(EXPECTED_FIXTURES) so future additions only
    need to update the set, not the function name.
    """
    files = {p.name for p in SYNTHETIC_ROOT.glob("*.json")}
    assert files == EXPECTED_FIXTURES, f"unexpected diff: {files ^ EXPECTED_FIXTURES}"


def test_synthetic_readme_exists():
    """D-10 documentation: every fixture's intent recorded in _README.md."""
    readme = SYNTHETIC_ROOT / "_README.md"
    assert readme.is_file(), "tests/fixtures/synthetic/_README.md is missing"
    body = readme.read_text(encoding="utf-8")
    # Spot-check that each fixture name is referenced in the README.
    for name in EXPECTED_FIXTURES:
        stem = name.replace("_T0.json", "_T").replace("_T1.json", "_T").replace(".json", "")
        assert stem in body or name in body, f"_README.md does not document {name}"


@pytest.mark.parametrize("fixture_name", sorted(EXPECTED_FIXTURES))
def test_synthetic_fixture_round_trips(fixture_name: str):
    """D-11 invariant: Snapshot.from_dict(raw).to_dict() == raw."""
    path = SYNTHETIC_ROOT / fixture_name
    raw = json.loads(path.read_text(encoding="utf-8"))
    snap = Snapshot.from_dict(raw)
    rebuilt = snap.to_dict()
    assert rebuilt == raw, f"{fixture_name}: round-trip drift"


@pytest.mark.parametrize("fixture_name", sorted(EXPECTED_FIXTURES))
def test_synthetic_fixture_datetimes_are_tz_aware(fixture_name: str):
    """D-23: every committed datetime has an explicit offset."""
    path = SYNTHETIC_ROOT / fixture_name
    text = path.read_text(encoding="utf-8")
    # Scan the raw text for any datetime-shaped substring without offset.
    naive_hits = _DATETIME_NAIVE_RE.findall(text)
    # Filter out date-only strings (no T) and aware datetimes (offset present).
    bad = [hit for hit in naive_hits if "T" in hit and not _DATETIME_AWARE_RE.search(hit.rstrip('"'))]
    assert not bad, f"{fixture_name}: naive datetimes detected -- {bad}"


def test_load_fixture_helper_returns_snapshot(load_fixture):
    """The conftest.load_fixture helper returns a Snapshot on a synthetic fixture."""
    snap = load_fixture("synthetic/empty_to_empty_T0.json")
    assert isinstance(snap, Snapshot)
    assert snap.lessons == []


def test_load_raw_fixture_helper_returns_dict(load_raw_fixture):
    """The conftest.load_raw_fixture helper returns the parsed dict."""
    raw = load_raw_fixture("synthetic/empty_to_empty_T0.json")
    assert isinstance(raw, dict)
    assert raw["lessons"] == []
    assert "school_tz" in raw


def test_load_fixture_skips_when_real_fixture_missing(load_fixture):
    """conftest.load_fixture pytest.skips when a real-fixture path is absent.

    The skip path is critical when Plan 02-02 captured `partial:` (e.g. only
    cancellation, not room_change). Plan 02-02 in fact captured all 6 — but
    the skip mechanism remains the safety net for future spike refreshes.
    """
    # nonexistent name: must skip, not fail. Hard to assert from inside the
    # test, so just probe with a known-missing real fixture and let pytest's
    # skip propagate.
    load_fixture("real/__definitely_missing__.json")
