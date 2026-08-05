"""Static AST guard: api/ + diff/ + their tests have ZERO ``homeassistant.*`` imports.

D-19 (Phase 2 CONTEXT.md): pure-Python boundary. The api/ and diff/
subpackages must be importable without Home Assistant in the environment
so that ``pytest tests/test_api/ tests/test_diff/`` runs in plain pytest
(sub-2-second runtime, ROADMAP success criterion #1).

This is the canonical guard. Ruff's banned-api block (pyproject.toml lines
139-142) is module-level but cannot scope by directory — this AST walk is
the directory-scoped enforcement.

If this test fails, ONE of the following happened:

1. A new ``from homeassistant...`` line was added inside api/ or diff/.
   Move that import to coordinator.py (Phase 3) or Phase 4 wiring.
2. A test under tests/test_api/ or tests/test_diff/ requires HA fixtures.
   Move that test to a different directory (e.g. tests/test_coordinator/).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_PATHS = [
    REPO_ROOT / "custom_components" / "ha_pronote" / "api",
    REPO_ROOT / "custom_components" / "ha_pronote" / "diff",
    REPO_ROOT / "custom_components" / "ha_pronote" / "politesse.py",  # Phase 5 — D-16
    REPO_ROOT
    / "custom_components"
    / "ha_pronote"
    / "holiday_dates.py",  # Phase 5 — WR-2 neutral helper (shipped by Plan 05-02)
    REPO_ROOT / "tests" / "test_api",
    REPO_ROOT / "tests" / "test_diff",
    REPO_ROOT / "tests" / "test_politesse_tz_matrix.py",  # Phase 5 — D-20
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the root autouse — this gate is HA-free per D-19.

    The root ``tests/conftest.py`` defines an autouse fixture that requires
    PHACC's ``enable_custom_integrations``; that only loads when the HA test
    harness is available. This gate is pure-Python (only stdlib ``ast``) and
    must run without the HA harness installed.
    """
    return


def _python_files(root: Path) -> list[Path]:
    """Return every ``.py`` file under ``root`` (or ``[root]`` if it's a file)."""
    if root.is_file() and root.suffix == ".py":
        return [root]
    return list(root.rglob("*.py")) if root.is_dir() else []


@pytest.mark.parametrize(
    "py_file",
    sorted({f for root in GUARDED_PATHS for f in _python_files(root)}),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_no_homeassistant_import(py_file: Path) -> None:
    """D-19: zero homeassistant.* imports in guarded paths."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("homeassistant"), (
                    f"{py_file.relative_to(REPO_ROOT)} imports {alias.name} — "
                    f"D-19 violated. Move to coordinator.py (Phase 3+)."
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("homeassistant"), (
                f"{py_file.relative_to(REPO_ROOT)} imports from {module} — "
                f"D-19 violated. Move to coordinator.py (Phase 3+)."
            )


def test_guarded_paths_are_not_empty() -> None:
    """Sanity: if api/ or diff/ goes missing, this guard would silently pass."""
    for path in GUARDED_PATHS:
        files = _python_files(path)
        assert files, f"guarded path {path.relative_to(REPO_ROOT)} has no .py files"
