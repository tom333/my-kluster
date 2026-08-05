"""Local fixtures for tests/test_api/. NO PHACC autouse — api/ is HA-free per D-19.

The root ``tests/conftest.py`` defines an autouse fixture that requires PHACC's
``enable_custom_integrations`` — that fixture only loads when the HA test
harness is available. ``tests/test_api/`` is pure-Python (D-19), so we OVERRIDE
the autouse here with a no-op of the same name. The override means the
api/ test suite runs without the HA harness installed (matches D-19 boundary).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests_mock as _requests_mock_pkg


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root autouse — api/ is HA-free per D-19.

    Same fixture name as ``tests/conftest.py``; pytest's nested-conftest
    resolution gives the closer fixture priority, so this no-op replaces
    the PHACC-backed root version inside ``tests/test_api/``.
    """
    return


@pytest.fixture
def mocked_pronote_session():
    """Hermetic mock of pronotepy's underlying ``requests.Session`` (D-26).

    Yields a ``requests_mock.Mocker`` context. Tests can register expected
    HTTP exchanges; no demo Pronote instance is contacted.
    """
    with _requests_mock_pkg.Mocker() as mocker:
        yield mocker


@pytest.fixture
def fixture_path() -> Path:
    """Return the ``tests/fixtures/`` directory path (Phase 2 fixture root)."""
    return Path(__file__).resolve().parent.parent / "fixtures"
