"""Local fixtures for tests/test_diff/. NO PHACC autouse -- diff/ is HA-free per D-19.

The root ``tests/conftest.py`` defines an autouse fixture that requires PHACC's
``enable_custom_integrations`` -- that fixture only loads when the HA test
harness is available. ``tests/test_diff/`` is pure-Python (D-19), so we OVERRIDE
the autouse here with a no-op of the same name. The override means the
diff/ test suite runs without the HA harness installed (matches D-19 boundary).

Adds two fixture-loader helpers:

- ``load_fixture(name)`` -> ``Snapshot``
- ``load_raw_fixture(name)`` -> ``dict``

Both accept a path relative to ``tests/fixtures/``, e.g. ``"real/cancellation_T0.json"``
or ``"synthetic/multi_change_T1.json"``. When a real-fixture path is missing
(Plan 02-02 may have captured ``partial:``), ``load_fixture`` ``pytest.skip``s
rather than failing the test -- the synthetic fixtures cover the same algorithm
branches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from custom_components.ha_pronote.api.models import Snapshot

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root autouse -- diff/ is HA-free per D-19."""
    return


@pytest.fixture
def load_fixture() -> Callable[[str], Snapshot]:
    """Load a fixture by relative path under ``tests/fixtures/`` and parse to ``Snapshot``.

    Returns a callable ``_load(name)`` that:

    - reads ``tests/fixtures/<name>`` and parses the JSON;
    - returns the rebuilt ``Snapshot`` (tz-aware datetimes via ``fromisoformat``);
    - ``pytest.skip``s when the fixture is missing (real-fixture spike was partial).
    """

    def _load(name: str) -> Snapshot:
        path = FIXTURE_ROOT / name
        if not path.is_file():
            pytest.skip(f"fixture {name!r} not found (spike may have captured this scenario partially)")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Snapshot.from_dict(raw)

    return _load


@pytest.fixture
def load_raw_fixture() -> Callable[[str], dict]:
    """Load a fixture as a parsed dict (no Snapshot rebuilding).

    Useful for tests that need to assert on the raw ISO strings or top-level
    keys before they pass through the dataclass.
    """

    def _load(name: str) -> dict:
        path = FIXTURE_ROOT / name
        if not path.is_file():
            pytest.skip(f"fixture {name!r} not found (spike may have captured this scenario partially)")
        return json.loads(path.read_text(encoding="utf-8"))

    return _load
