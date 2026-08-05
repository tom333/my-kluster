---
phase: 02-api-diff-layer-ha-free
plan: 04
type: execute
wave: 4
depends_on: ["02-01", "02-02", "02-03"]
files_modified:
  - tests/test_no_ha_imports.py
  - tests/test_fixtures.py
  - tests/test_diff/test_lessons_tz_matrix.py
  - pyproject.toml
  - .github/workflows/test.yml
autonomous: true
requirements: [DIST-05]
must_haves:
  truths:
    - "pytest tests/test_api/ tests/test_diff/ runs in under 2 seconds and passes — no HA harness involved (ROADMAP success criterion #1)"
    - "Diff layer coverage >= 90% enforced in CI via pytest --cov-fail-under=90 (ROADMAP success criterion #4, DIST-05)"
    - "tests/test_no_ha_imports.py exits 0 — zero homeassistant.* imports in api/, diff/, or their tests (D-19)"
    - "Every committed fixture under tests/fixtures/ round-trips Snapshot.from_dict -> to_dict cleanly (D-11)"
    - "Diff lessons tests pass on both Europe/Paris and Pacific/Noumea (D-25, NC-author blind-spot guard, DIST-06 starts here)"
    - "Per-test 1s timeout configured via pytest-timeout (D-28) — slow tests fail loudly"
    - "Coverage omit list excludes diff/grades.py and diff/notifications.py until Phase 4 (D-04, C-02)"
  artifacts:
    - path: "tests/test_no_ha_imports.py"
      provides: "Static AST guard — zero homeassistant.* imports in api/, diff/, their tests (D-19)"
      contains: "def test_no_homeassistant_import"
    - path: "tests/test_fixtures.py"
      provides: "Schema gate — every committed fixture round-trips through Snapshot dataclass (D-11)"
      contains: "Snapshot.from_dict"
    - path: "tests/test_diff/test_lessons_tz_matrix.py"
      provides: "Parametrize core diff scenarios over Europe/Paris + Pacific/Noumea (D-25)"
      contains: "@pytest.mark.parametrize"
    - path: "pyproject.toml"
      provides: "Appended timeout=1, coverage omit, scripts/ ruff per-file-ignores (D-04, D-28, D-13)"
      contains: "timeout"
    - path: ".github/workflows/test.yml"
      provides: "tz matrix axis + --cov-fail-under=90 gate (D-25, D-27)"
      contains: "matrix"
  key_links:
    - from: "tests/test_no_ha_imports.py"
      to: "custom_components/ha_pronote/api/ + custom_components/ha_pronote/diff/"
      via: "AST walk over guarded directories"
      pattern: "GUARDED_PATHS"
    - from: ".github/workflows/test.yml"
      to: "custom_components/ha_pronote/diff/"
      via: "pytest --cov target"
      pattern: "--cov=custom_components/ha_pronote/diff"
    - from: "pyproject.toml"
      to: "custom_components/ha_pronote/diff/grades.py + notifications.py"
      via: "[tool.coverage.run] omit list (D-04, C-02)"
      pattern: "omit"
---

<objective>
Lock the cross-cutting quality gates that enforce ROADMAP success criteria
#1 and #4 in CI: sub-2-second pytest runtime, ≥90% coverage on `diff/`,
zero `homeassistant.*` imports in api/+diff/, every fixture round-trips,
and the diff scenarios run on both `Europe/Paris` and `Pacific/Noumea`.

Purpose: this plan owns DIST-05 ("≥90% coverage on diff layer, CI-enforced")
and seeds DIST-06 (the timezone matrix — fully landed in Phase 5 but starting
in Phase 2 per CONTEXT.md D-25). Without this plan, Plans 02-01..02-03 ship
working code but the gates that prevent regression don't exist.

Output: 3 new test files + `pyproject.toml` append + `.github/workflows/test.yml`
amend. No new code in `custom_components/`.
</objective>

<execution_context>
@/home/moi/projets/perso/pronote/.claude/get-shit-done/workflows/execute-plan.md
@/home/moi/projets/perso/pronote/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md
@.planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md
@.planning/research/PITFALLS.md

# Existing files (preserved + amended in this plan)
@pyproject.toml
@.github/workflows/test.yml
@requirements_test.txt

# Plans 02-01..02-03 outputs (consumed by the gates this plan wires up)
@custom_components/ha_pronote/api/__init__.py
@custom_components/ha_pronote/diff/__init__.py
@custom_components/ha_pronote/diff/lessons.py
@tests/test_api/conftest.py
@tests/test_diff/conftest.py

<interfaces>
<!-- This plan adds GATES, not new public surface. The "interfaces" here are the
     CI invariants that downstream phases inherit. -->

# Gate 1: pure-Python boundary (D-19)
#   tests/test_no_ha_imports.py walks api/, diff/, tests/test_api/, tests/test_diff/
#   and asserts no `homeassistant.*` import appears.
#
# Gate 2: schema invariant (D-11)
#   tests/test_fixtures.py round-trips every JSON in tests/fixtures/{real,synthetic}/
#   through Snapshot.from_dict / to_dict — fails if any drift exists.
#
# Gate 3: timezone matrix (D-25)
#   tests/test_diff/test_lessons_tz_matrix.py wraps the multi_change scenario
#   in a @pytest.mark.parametrize("school_tz", ["Europe/Paris", "Pacific/Noumea"])
#   to prove the diff is tz-agnostic.
#
# Gate 4: coverage threshold (D-27, DIST-05, ROADMAP success criterion #4)
#   .github/workflows/test.yml runs:
#     pytest -q --cov=custom_components/ha_pronote/diff --cov-fail-under=90
#   pyproject.toml [tool.coverage.run] omit excludes diff/grades.py and
#   diff/notifications.py (D-04, C-02) so the 90% gate is honest.
#
# Gate 5: per-test timeout (D-28, ROADMAP success criterion #1)
#   pyproject.toml [tool.pytest.ini_options] timeout = 1 — any test taking
#   over 1s fails loudly via pytest-timeout 2.4.0 (transitive via PHACC).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create tests/test_no_ha_imports.py + tests/test_fixtures.py + tz matrix test</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Tests, Tooling & CI" (D-25, D-26, D-27, D-28) + §"Pure-Python Boundary" (D-19, D-20)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"tests/test_no_ha_imports.py" + §"tests/test_fixtures.py" + §"tests/test_diff/test_lessons.py"
    - .planning/research/PITFALLS.md §"Pitfall 4" (NC tz blind spot)
    - custom_components/ha_pronote/api/ (Plan 02-01) — directories the AST guard scans
    - custom_components/ha_pronote/diff/ (Plan 02-03)
    - tests/fixtures/real/ (Plan 02-02)
    - tests/fixtures/synthetic/ (Plan 02-03)
    - custom_components/ha_pronote/api/models.py — Snapshot.from_dict/to_dict signature for the round-trip test
  </read_first>
  <behavior>
    - `pytest tests/test_no_ha_imports.py` exits 0 — every `.py` file under `custom_components/ha_pronote/api/`, `custom_components/ha_pronote/diff/`, `tests/test_api/`, `tests/test_diff/` has zero `homeassistant.*` imports (D-19).
    - The AST guard fails (exits non-zero) if a file is added with `import homeassistant.helpers` or `from homeassistant.config_entries import ...` (proven by introducing such an import locally and reverting after the test fails).
    - `pytest tests/test_fixtures.py` exits 0 — every committed JSON file under `tests/fixtures/real/` and `tests/fixtures/synthetic/` (excluding `_raw_*.json` which are gitignored) round-trips cleanly: `Snapshot.from_dict(json.loads(text)).to_dict() == json.loads(text)` (D-11).
    - `pytest tests/test_diff/test_lessons_tz_matrix.py` runs the core diff scenarios under `Europe/Paris` AND `Pacific/Noumea` (parametrized) — both pass (D-25).
    - The tz matrix test uses `monkeypatch.setenv("TZ", school_tz)` to flip the runner's local timezone, AND uses fixtures whose internal `school_tz` matches — proving the diff is independent of both ambient TZ and fixture TZ.
  </behavior>
  <action>
    Build the three gate test files. They are the cross-cutting safety net that prevents regression in api/+diff/ across all future phases.

    **1. Create `tests/test_no_ha_imports.py`** per D-19 + PATTERNS.md §"tests/test_no_ha_imports.py":

    ```python
    """Static AST guard: api/ + diff/ + their tests have ZERO `homeassistant.*` imports.

    D-19 (Phase 2 CONTEXT.md): pure-Python boundary. The api/ and diff/
    subpackages must be importable without Home Assistant in the environment
    so that `pytest tests/test_api/ tests/test_diff/` runs in plain pytest
    (sub-2-second runtime, ROADMAP success criterion #1).

    This is the canonical guard. Ruff's banned-api block (pyproject.toml lines
    139-142) is module-level but cannot scope by directory — this AST walk is
    the directory-scoped enforcement.

    If this test fails, ONE of the following happened:
      1. A new `from homeassistant...` line was added inside api/ or diff/.
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
        REPO_ROOT / "tests" / "test_api",
        REPO_ROOT / "tests" / "test_diff",
    ]


    def _python_files(root: Path) -> list[Path]:
        return list(root.rglob("*.py")) if root.is_dir() else []


    @pytest.mark.parametrize(
        "py_file",
        sorted(set(f for root in GUARDED_PATHS for f in _python_files(root))),
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
    ```

    **2. Create `tests/test_fixtures.py`** per D-11 + PATTERNS.md §"tests/test_fixtures.py":

    ```python
    """Schema gate: every committed fixture round-trips through Snapshot.

    D-11 (Phase 2 CONTEXT.md): a refactor of the dataclass shape (Plan 02-01
    api/models.py) MUST force every fixture to be revalidated in CI. This test
    is the enforcement.

    Failure modes this catches:
      - Synthetic fixture authored against an older Snapshot shape.
      - Real fixture captured with a different pronotepy version that introduced
        a new field.
      - to_dict() lost a field on a refactor.
      - from_dict() reconstructs differently from what to_dict() emits (e.g. ISO
        datetime parsing changes the offset format).

    Notes:
      - Files matching `_raw_*.json` are excluded — they're gitignored raw
        spike output, not Snapshot-shaped (Plan 02-02 D-12, D-13).
      - The fixture's `school_tz` field is used by Snapshot.from_dict to
        reconstruct tz-aware datetimes. ISO datetime strings with offset
        already preserve tz; school_tz is informational only.
    """
    from __future__ import annotations

    import json
    from pathlib import Path

    import pytest

    from custom_components.ha_pronote.api.models import Snapshot

    FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


    def _committable_fixtures() -> list[Path]:
        """Every JSON under fixtures/ except gitignored raw spike output."""
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
        """D-11: Snapshot.from_dict(raw).to_dict() == raw."""
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


    def test_no_naive_datetimes_in_committed_fixtures() -> None:
        """D-23: every datetime string in any committed fixture has an explicit offset."""
        import re
        # ISO datetime regex: anchor on T..:..:.. then require offset before quote/end
        iso_dt_with_offset = re.compile(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+\-]\d{2}:\d{2}|Z)"')
        iso_dt_without_offset = re.compile(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"')
        bad: list[tuple[Path, str]] = []
        for path in _committable_fixtures():
            text = path.read_text(encoding="utf-8")
            for match in iso_dt_without_offset.finditer(text):
                bad.append((path, match.group(0)))
        assert not bad, (
            f"D-23: naive datetime strings in committed fixtures: {bad}. "
            f"Every datetime must have an explicit offset or 'Z'."
        )
    ```

    **3. Create `tests/test_diff/test_lessons_tz_matrix.py`** per D-25:

    ```python
    """Diff lessons under tz matrix — Europe/Paris ∪ Pacific/Noumea (D-25).

    The NC-author blind-spot guard. Phase 2 CONTEXT.md: "the pytest matrix STARTS
    in Phase 2" even though DIST-06 lands officially in Phase 5.

    Strategy: for each scenario, parametrize over both timezones at TWO levels:
      1. Runner's ambient TZ (via TZ env var) — proves the diff is independent
         of the operating environment's locale (an HA install on a VPS in Europe
         servicing a NC family).
      2. Fixture-local school_tz — already varied across the synthetic fixtures
         (Plan 02-03). When the matrix runs Pacific/Noumea, fixtures with
         school_tz=Europe/Paris still pass (the diff doesn't compare tz; it
         compares datetimes which already encode their offset).

    The matrix proves: regardless of where HA runs OR what timezone the school
    server uses, diff_lessons produces the same answer.
    """
    from __future__ import annotations

    import pytest

    from custom_components.ha_pronote.diff import diff_lessons

    pytestmark = pytest.mark.parametrize(
        "school_tz",
        ["Europe/Paris", "Pacific/Noumea"],
    )


    def test_first_poll_is_silent_under_tz_matrix(school_tz, monkeypatch, load_fixture):
        monkeypatch.setenv("TZ", school_tz)
        new = load_fixture("synthetic/first_poll_after_restart.json")
        assert diff_lessons(None, new, "today") == []


    def test_reorder_is_silent_under_tz_matrix(school_tz, monkeypatch, load_fixture):
        monkeypatch.setenv("TZ", school_tz)
        t0 = load_fixture("synthetic/reorder_no_op_T0.json")
        t1 = load_fixture("synthetic/reorder_no_op_T1.json")
        assert diff_lessons(t0, t1, "today") == []


    def test_multi_change_emits_three_under_tz_matrix(school_tz, monkeypatch, load_fixture):
        monkeypatch.setenv("TZ", school_tz)
        t0 = load_fixture("synthetic/multi_change_T0.json")
        t1 = load_fixture("synthetic/multi_change_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert len(events) == 3
        change_types = {e.change_type for e in events}
        assert change_types == {"canceled", "room", "teacher"}


    def test_real_cancellation_under_tz_matrix(school_tz, monkeypatch, load_fixture):
        monkeypatch.setenv("TZ", school_tz)
        # load_fixture() pytest.skips if the real fixture isn't present (Plan 02-02 partial).
        t0 = load_fixture("real/cancellation_T0.json")
        t1 = load_fixture("real/cancellation_T1.json")
        events = diff_lessons(t0, t1, "today")
        assert any(e.change_type == "canceled" for e in events)
    ```

    **4. Verification commands:**
    - `ruff format tests/test_no_ha_imports.py tests/test_fixtures.py tests/test_diff/test_lessons_tz_matrix.py`
    - `ruff check tests/test_no_ha_imports.py tests/test_fixtures.py tests/test_diff/test_lessons_tz_matrix.py`
    - `pytest tests/test_no_ha_imports.py -v` — all parametrize cases pass.
    - `pytest tests/test_fixtures.py -v` — all parametrize cases pass.
    - `pytest tests/test_diff/test_lessons_tz_matrix.py -v` — both tz axes × 4 scenarios pass (some real-fixture cases may pytest.skip per Plan 02-02 partial).
  </action>
  <verify>
    <automated>ruff check tests/test_no_ha_imports.py tests/test_fixtures.py tests/test_diff/test_lessons_tz_matrix.py &amp;&amp; pytest tests/test_no_ha_imports.py tests/test_fixtures.py tests/test_diff/test_lessons_tz_matrix.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_no_ha_imports.py` exists with `def test_no_homeassistant_import` parametrized across the 4 guarded directories.
    - `tests/test_fixtures.py` exists with `def test_fixture_round_trips_snapshot` parametrized across all committable fixtures.
    - `tests/test_diff/test_lessons_tz_matrix.py` exists with `pytestmark = pytest.mark.parametrize("school_tz", ...)` covering Europe/Paris + Pacific/Noumea.
    - `pytest tests/test_no_ha_imports.py tests/test_fixtures.py tests/test_diff/test_lessons_tz_matrix.py -v` exits 0.
    - `grep -c "homeassistant" tests/test_no_ha_imports.py` returns at least 4 (the guard's own assertion strings reference it; this is acceptable in a test file scoped outside `tests/test_api/` and `tests/test_diff/`).
    - `grep -c "Snapshot.from_dict" tests/test_fixtures.py` returns at least 1.
    - `grep -E '"Europe/Paris".*"Pacific/Noumea"|"Pacific/Noumea".*"Europe/Paris"' tests/test_diff/test_lessons_tz_matrix.py` returns at least 1.
    - Subprocess CLI tests in `tests/test_scripts/` override the 1s global timeout via `@pytest.mark.timeout(5)` — verified by their continued passing after the global `timeout = 1` is set in `pyproject.toml` (PC-02-02). `grep -c "@pytest.mark.timeout(5)" tests/test_scripts/test_snapshot.py` returns ≥ 2.
    - **Static check for spike-leftover markers (PC-02-06):** `grep -rE "(# Uncomment|# TODO: spike|# pragma:.* spike|EXECUTOR DECISION POINT)" custom_components/ha_pronote/diff/ tests/test_diff/` exits non-zero (no matches). This catches commented-out alternative branches in `diff/lessons.py` that should have been resolved into uncommented production code (or deleted) during Plan 02-03 Task 3 execution.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append timeout + coverage omit to pyproject.toml + amend test.yml workflow</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Tests, Tooling & CI" (D-25, D-27, D-28) + §"Diff Scope" (D-04)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"pyproject.toml" + §".github/workflows/test.yml"
    - pyproject.toml (existing — preserve all current blocks)
    - .github/workflows/test.yml (existing — preserve except for the matrix and pytest invocation)
    - tests/test_api/, tests/test_diff/ (the directories the new test gates target)
  </read_first>
  <behavior>
    - `pyproject.toml [tool.pytest.ini_options]` block has `timeout = 1` (D-28).
    - `pyproject.toml [tool.coverage.run] omit` includes `*/diff/grades.py` and `*/diff/notifications.py` (D-04, C-02) plus existing `tests/*`.
    - `pyproject.toml [tool.ruff.lint.per-file-ignores]` has an entry for `"scripts/*"` excluding `T20`, `INP001`, `D` (D-13).
    - `.github/workflows/test.yml` has `strategy.matrix.tz: ["Europe/Paris", "Pacific/Noumea"]` (D-25).
    - `.github/workflows/test.yml` has `env.TZ: ${{ matrix.tz }}` propagating to runner.
    - `.github/workflows/test.yml` pytest invocation passes `--cov=custom_components/ha_pronote/diff --cov-fail-under=90` (D-27).
    - All existing SHAs in `.github/workflows/test.yml` (actions/checkout, actions/setup-python, astral-sh/setup-uv) are preserved verbatim from Phase 1.
    - Local `pytest tests/test_api/ tests/test_diff/ tests/test_fixtures.py tests/test_no_ha_imports.py tests/test_scripts/` runs in under 2 seconds (ROADMAP success criterion #1).
    - Local `pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90` exits 0 (the gate is honest — Plan 02-03's diff/lessons.py is well above 90%).
  </behavior>
  <action>
    Wire the gates into the project tooling.

    **1. Modify `pyproject.toml`** — apply three append/modify operations preserving all existing content:

    a) **Append `timeout = 1` to `[tool.pytest.ini_options]`** (D-28). Find the existing block (lines 34–50) and add `timeout = 1` at the end of the block, BEFORE the closing of the section. Final shape of the block:

    ```toml
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    norecursedirs = [".git", "testing_config"]
    log_format = "%(asctime)s.%(msecs)03d %(levelname)-8s %(threadName)s %(name)s:%(filename)s:%(lineno)s %(message)s"
    log_date_format = "%Y-%m-%d %H:%M:%S"
    asyncio_mode = "auto"
    asyncio_default_fixture_loop_scope = "function"
    addopts = "-ra -q --strict-markers"
    timeout = 1   # D-28: per-test 1s timeout (sub-2s gate via pytest-timeout 2.4.0 transitive via PHACC)
    markers = [
        "unit: Unit tests (fast, no external dependencies)",
        "integration: Integration tests (use hass fixture)",
    ]
    filterwarnings = [
        "error",
        # "ignore::DeprecationWarning:autoslot",
    ]
    ```

    b) **Modify `[tool.coverage.run]` omit list** (D-04, C-02). Find the existing block (lines 52–54) and replace it with:

    ```toml
    [tool.coverage.run]
    source = ["custom_components/ha_pronote"]
    omit = [
        "tests/*",
        "*/diff/grades.py",         # D-04 / C-02 — Phase 4 fills the body, excluded until then.
        "*/diff/notifications.py",  # D-04 / C-02 — Phase 4 fills the body, excluded until then.
    ]
    ```

    The existing `[tool.coverage.report] exclude_lines` block already contains `"raise NotImplementedError"` (Phase 1 line 59). Both mechanisms compose — the stub bodies are double-excluded as belt-and-suspenders.

    c) **Append `scripts/*` per-file-ignores to `[tool.ruff.lint.per-file-ignores]`** (D-13). Find the existing block (lines 150–155) and add:

    ```toml
    "scripts/*" = [
        "T20",     # print is the script's UX
        "INP001",  # scripts/ is intentionally not a package (no __init__.py)
        "D",       # full docstring set not required for one-shot tooling
    ]
    ```

    Final block shape:
    ```toml
    [tool.ruff.lint.per-file-ignores]
    "tests/*" = [
        "S101",
        "PLR2004",
        "D",
    ]
    "scripts/*" = [
        "T20",
        "INP001",
        "D",
    ]
    ```

    d) **NO change to `[tool.pyright] include`** — current value is `["custom_components/ha_pronote", "tests"]` which already excludes `scripts/`. Per D-13, scripts/ is intentionally outside pyright's coverage.

    **2. Amend `.github/workflows/test.yml`** per D-25, D-27 + PATTERNS.md §"test.yml":

    Replace the entire file with the following (preserving the existing SHAs verbatim):

    ```yaml
    name: Test

    on:
      push:
        branches: [main]
      pull_request:
        branches: [main]

    permissions: {}

    jobs:
      pytest:
        name: Pytest (${{ matrix.tz }})
        runs-on: ubuntu-latest
        strategy:
          fail-fast: false
          matrix:
            tz: ["Europe/Paris", "Pacific/Noumea"]   # D-25 NC-author blind-spot guard
        env:
          TZ: ${{ matrix.tz }}
        steps:
          - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
          - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
            with:
              python-version: "3.14"
          - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
            with:
              enable-cache: true
              cache-dependency-glob: "requirements*.txt"
          - run: uv pip install --system -r requirements_test.txt
          - run: pytest -q --cov=custom_components/ha_pronote/diff --cov-fail-under=90  # D-27
    ```

    Key changes vs Phase 1 baseline:
    - `strategy.matrix.tz` → 2 jobs (D-25).
    - `env.TZ` propagates to runner.
    - `name: Pytest (${{ matrix.tz }})` makes the GitHub Actions UI show one job per timezone.
    - pytest invocation: `--cov=custom_components/ha_pronote/diff --cov-fail-under=90` (D-27).
    - All 3 action SHAs preserved verbatim from Phase 1's existing test.yml.

    **3. Verification commands:**
    - `ruff format pyproject.toml` (no-op — TOML, but verifies the file still parses).
    - `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"` exits 0.
    - `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"` exits 0 (PyYAML is transitive via PHACC).
    - `pytest tests/test_api/ tests/test_diff/ tests/test_fixtures.py tests/test_no_ha_imports.py tests/test_scripts/ -v` runs in under 2 seconds (use `time pytest ...` to verify).
    - `pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90` exits 0.
    - `grep -c "timeout = 1" pyproject.toml` returns 1.
    - `grep -c "*/diff/grades.py" pyproject.toml` returns 1.
    - `grep -c "*/diff/notifications.py" pyproject.toml` returns 1.
    - `grep -c "scripts/\\*" pyproject.toml` returns 1.
    - `grep -c "Pacific/Noumea" .github/workflows/test.yml` returns at least 1.
    - `grep -c -- "--cov-fail-under=90" .github/workflows/test.yml` returns 1.
  </action>
  <verify>
    <automated>python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())" &amp;&amp; python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))" &amp;&amp; grep -q "timeout = 1" pyproject.toml &amp;&amp; grep -q "\\*/diff/grades.py" pyproject.toml &amp;&amp; grep -q "Pacific/Noumea" .github/workflows/test.yml &amp;&amp; grep -q -- "--cov-fail-under=90" .github/workflows/test.yml &amp;&amp; pytest tests/test_api/ tests/test_diff/ tests/test_fixtures.py tests/test_no_ha_imports.py tests/test_scripts/ -v &amp;&amp; pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90 -q</automated>
  </verify>
  <acceptance_criteria>
    - `pyproject.toml` parses as valid TOML.
    - `grep -c "timeout = 1" pyproject.toml` returns 1.
    - `grep -E "\\*/diff/grades.py|\\*/diff/notifications.py" pyproject.toml | wc -l` returns 2.
    - `grep -c '"scripts/\\*"' pyproject.toml` returns 1.
    - `.github/workflows/test.yml` parses as valid YAML.
    - `grep -c "Pacific/Noumea" .github/workflows/test.yml` returns at least 1 (typically 1 in the matrix).
    - `grep -c "Europe/Paris" .github/workflows/test.yml` returns at least 1.
    - `grep -c -- "--cov-fail-under=90" .github/workflows/test.yml` returns 1.
    - All Phase 1 action SHAs preserved (`actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd`, `actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405`, `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b`) — `grep -c '@de0fac2e4500dabe0009e67214ff5f5447ce83dd\\|@a309ff8b426b58ec0e2a45f0f869d46889d02405\\|@08807647e7069bb48b6ef5acd8ec9567f424441b' .github/workflows/test.yml` returns 3.
    - `pytest tests/test_api/ tests/test_diff/ tests/test_fixtures.py tests/test_no_ha_imports.py tests/test_scripts/` runs in under 2 seconds.
    - `pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90 -q` exits 0.
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Future contributor commit → CI pipeline | New imports, new tests, new fixtures all flow through the gates this plan installs. The gates are the only enforcement; without them, regression goes undetected. |
| `.github/workflows/test.yml` (committed) → GitHub Actions runner | A malicious or careless edit could disable the cov-fail-under or remove the tz matrix. Pinned-by-SHA actions (Phase 1 D-23) prevent supply-chain attacks via action releases. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04-01 | Tampering | Future commit accidentally adds `from homeassistant import ...` to `api/` or `diff/` | mitigate | `tests/test_no_ha_imports.py` AST guard fails the offending PR's CI. The error message names the file and the violating import, pointing the contributor toward `coordinator.py` (Phase 3+) as the correct home. **Severity: HIGH** if missed — would break the sub-2-second runtime gate and the "import without HA installed" property that makes Phase 2 unit-testable in isolation. |
| T-02-04-02 | Tampering | A fixture is hand-edited in a way that breaks `Snapshot.from_dict` round-trip | mitigate | `tests/test_fixtures.py` round-trip gate (Task 1) catches drift on every CI run. The error message names the offending file and points to `scripts/snapshot.py` for regeneration. **Severity: MEDIUM** — caught early, recoverable. |
| T-02-04-03 | Tampering | A naive datetime sneaks into a committed fixture (D-23 violation) | mitigate | `test_no_naive_datetimes_in_committed_fixtures` (Task 1) regex-scans every committed fixture and fails if any datetime is missing an offset. **Severity: MEDIUM** — would silently misreport "tomorrow" outside NC. |
| T-02-04-04 | Tampering | Coverage gate quietly drops below 90% | mitigate | `--cov-fail-under=90` in `.github/workflows/test.yml` fails the PR. The `omit` list explicitly excludes only the Phase-4-bound stubs (D-04, C-02), so the gate measures the real diff surface honestly. **Severity: MEDIUM** — would let regression through. |
| T-02-04-05 | Spoofing | Stale or missing tz matrix lets NC-only timezone bug ship | mitigate | The `strategy.matrix.tz` axis runs every test on both Europe/Paris and Pacific/Noumea — any test that depends on ambient TZ fails ON ONE of the two axes. The NC-author blind-spot guard (D-25, ROADMAP cross-cutting). **Severity: MEDIUM** — would erode the project's Core Value silently. |
| T-02-04-06 | Denial of Service (CI runtime) | Slow test creeps over 1s and pushes total runtime past 2s | mitigate | `pytest-timeout` (D-28) fails the offending test with a clear message ("test took 1.7s, exceeded 1s timeout"). Forces the developer to fix the test (mock external IO, reduce fixture size) rather than letting CI degrade. **Severity: LOW** — affects developer velocity, not correctness. |
</threat_model>

<verification>
**Plan-level checks:**

1. **Sub-2-second runtime (ROADMAP success criterion #1):**
   - `time pytest tests/test_api/ tests/test_diff/ -q` reports a real time under 2 seconds. (Note: this is for `test_api` + `test_diff` ONLY per the literal ROADMAP wording; `test_fixtures.py` and `test_no_ha_imports.py` and `test_scripts/` add a small additional cost but are also pure-Python.)

2. **Coverage gate honest (ROADMAP success criterion #4, DIST-05):**
   - `pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90` exits 0.
   - The omit list excludes ONLY `*/diff/grades.py` and `*/diff/notifications.py`; `*/diff/lessons.py`, `*/diff/events.py`, and `*/diff/__init__.py` are all measured.

3. **Pure-Python boundary enforced (D-19):**
   - `pytest tests/test_no_ha_imports.py -v` exits 0.

4. **Schema invariant enforced (D-11):**
   - `pytest tests/test_fixtures.py -v` exits 0 — every committed fixture round-trips.

5. **Tz matrix exercised (D-25):**
   - `pytest tests/test_diff/test_lessons_tz_matrix.py -v` exits 0 — both timezones pass for each scenario.

6. **CI workflow valid:**
   - `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"` exits 0.
   - The matrix axis renders as 2 separate jobs in the GitHub Actions UI (verified visually after first push, OR by `gh run list` after pushing a commit — local verification is the YAML parse).

7. **All Phase 1 + Plans 02-01..02-03 contracts preserved:**
   - `pytest tests/test_init.py tests/test_manifest.py tests/test_api/ tests/test_diff/ tests/test_fixtures.py tests/test_no_ha_imports.py tests/test_scripts/ -v` exits 0.
   - `ruff check custom_components tests scripts` exits 0.

8. **manifest.json untouched:**
   - `git diff custom_components/ha_pronote/manifest.json` returns nothing.
</verification>

<success_criteria>
- 3 new test files: `tests/test_no_ha_imports.py`, `tests/test_fixtures.py`, `tests/test_diff/test_lessons_tz_matrix.py`.
- 2 modified files: `pyproject.toml` (3 surgical appends/edits), `.github/workflows/test.yml` (full replace preserving SHAs).
- ROADMAP success criterion #1 satisfied: `pytest tests/test_api/ tests/test_diff/` runs in under 2 seconds.
- ROADMAP success criterion #4 fully satisfied: ≥90% coverage on `diff/` enforced in CI; zero events on first poll + reorder no-op (already proven by Plan 02-03 tests, re-run by this plan's gates).
- DIST-05 fully satisfied: ≥90% coverage gate is CI-enforced.
- DIST-06 seeded: pytest matrix on `Europe/Paris` + `Pacific/Noumea` operational (Phase 5 expands the coverage to all phases).
- D-19 (pure-Python boundary) is now CI-enforced via the AST guard.
- D-11 (schema invariant) is now CI-enforced via the round-trip test.
- D-23 (tz-aware datetimes) is now CI-enforced via the no-naive-datetimes regex test.
- D-28 (per-test 1s timeout) is configured and active.
- All 6 STRIDE threats are mitigated and CI-verified.
</success_criteria>

<output>
After completion, create `.planning/phases/02-api-diff-layer-ha-free/02-04-SUMMARY.md` documenting:
- Local pytest runtime (e.g. `0.84s for 47 tests`) — ROADMAP success criterion #1 evidence.
- Local coverage on `diff/lessons.py` (e.g. `94%`) — ROADMAP success criterion #4 evidence.
- The commit SHA at which the workflow first runs the matrix in real CI (after first push).
- Phase 2 status: ALL 4 success criteria satisfied; Phase 2 → Phase 3 hand-off ready.
- Forward note: Phase 5 will expand the tz matrix to cover all phases (currently scoped to Phase 2 by D-25).
</output>
</content>
</invoke>