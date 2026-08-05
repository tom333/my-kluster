"""Local fixtures for tests/test_scripts/. NO PHACC autouse — scripts/ is HA-free per D-13."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root autouse — scripts/ is HA-free.

    Same fixture name as ``tests/conftest.py``; pytest's nested-conftest
    resolution gives the closer fixture priority.
    """
    return
