"""Schema gate: every committed fixture round-trips through ``Snapshot``.

D-11 (Phase 2 CONTEXT.md): a refactor of the dataclass shape (Plan 02-01
api/models.py) MUST force every fixture to be revalidated in CI. This test
is the enforcement.

Failure modes this catches:

- Synthetic fixture authored against an older Snapshot shape.
- Real fixture captured with a different pronotepy version that introduced
  a new field.
- ``to_dict()`` lost a field on a refactor.
- ``from_dict()`` reconstructs differently from what ``to_dict()`` emits
  (e.g. ISO datetime parsing changes the offset format).

Notes:

- Files matching ``_raw_*.json`` are excluded — they are gitignored raw
  spike output, not Snapshot-shaped (Plan 02-02 D-12, D-13).
- The fixture's ``school_tz`` field is informational only; ISO datetime
  strings already carry their offset, so ``Snapshot.from_dict`` does not
  need to consult it to rebuild tz-aware datetimes.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from custom_components.ha_pronote.api.models import Snapshot

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root autouse — this gate is HA-free per D-19."""
    return


def _committable_fixtures() -> list[Path]:
    """Every JSON under ``fixtures/`` except gitignored raw spike output."""
    out: list[Path] = []
    for path in sorted(FIXTURE_ROOT.rglob("*.json")):
        if path.name.startswith("_raw_"):
            continue
        out.append(path)
    return out


@pytest.mark.parametrize(
    "fixture_path",
    _committable_fixtures(),
    ids=lambda p: str(p.relative_to(FIXTURE_ROOT)),
)
def test_fixture_round_trips_snapshot(fixture_path: Path) -> None:
    """D-11: ``Snapshot.from_dict(raw).to_dict() == raw``."""
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    snap = Snapshot.from_dict(raw)
    assert snap.to_dict() == raw, (
        f"{fixture_path.relative_to(FIXTURE_ROOT)}: round-trip drift. "
        f"Either the fixture is stale (regenerate via scripts/snapshot.py) "
        f"or Snapshot.from_dict/to_dict was refactored without updating fixtures."
    )


def test_fixture_root_is_not_empty() -> None:
    """Sanity: if fixtures/ goes missing, the parametrize would yield zero cases."""
    assert _committable_fixtures(), "tests/fixtures/ has no committable JSON files"


# ISO datetime regex: anchor on T..:..:.. then require offset before quote/end.
_ISO_DT_WITHOUT_OFFSET = re.compile(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"')


def test_no_naive_datetimes_in_committed_fixtures() -> None:
    """D-23: every datetime string in any committed fixture has an explicit offset."""
    bad: list[tuple[Path, str]] = []
    for path in _committable_fixtures():
        text = path.read_text(encoding="utf-8")
        bad.extend((path, match.group(0)) for match in _ISO_DT_WITHOUT_OFFSET.finditer(text))
    assert not bad, (
        f"D-23: naive datetime strings in committed fixtures: {bad}. "
        f"Every datetime must have an explicit offset or 'Z'."
    )
