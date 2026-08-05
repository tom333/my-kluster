---
phase: 01-foundations-skeleton
plan: 01
subsystem: infra
tags:
  - foundations
  - tooling
  - uv
  - ruff
  - pyright
  - pytest
  - python
  - hacs
  - mit-license

# Dependency graph
requires: []
provides:
  - "pyproject.toml: single source of truth for ruff (lint+format), pyright (basic), pytest (asyncio_mode=auto), coverage"
  - "Python 3.14 floor pinned (.python-version + requires-python >=3.14.2)"
  - "requirements_test.txt: pinned CI test deps (homeassistant==2026.4.4, PHACC==0.13.326, ruff==0.15.1, codespell==2.4.1)"
  - "package.json: pyright 1.1.409 pinned for npx pyright"
  - "Banned-API guards (async_timeout, pytz, requests) wired in ruff"
  - "MIT LICENSE (Copyright 2026 Thomas Guyader) — resolves OQ-1"
  - "README.md placeholder — sufficient for HACS render_readme=true"
  - ".gitignore covers all RESEARCH §Security task 1 entries"
affects:
  - "01-02 (manifest + skeleton): pyright include path consumes custom_components/ha_pronote"
  - "01-03 (smoke test scaffold): pytest config + asyncio_mode=auto + coverage source"
  - "01-04 (CI workflows): every workflow installs from requirements_test.txt"
  - "01-05 (pre-commit hooks): astral-sh/ruff-pre-commit v0.15.1 must match ruff==0.15.1 pin"

# Tech tracking
tech-stack:
  added:
    - "uv (project manager, via pyproject.toml [project])"
    - "ruff 0.15.1 (lint + format, single tool)"
    - "pyright 1.1.409 (type checker, basic mode, via npx)"
    - "pytest 9.x via pytest-homeassistant-custom-component 0.13.326"
    - "codespell 2.4.1"
    - "homeassistant 2026.4.4 (test-time only)"
  patterns:
    - "pyproject.toml as canonical config (no pytest.ini, no setup.cfg)"
    - "Banned-API enforcement at lint level (async_timeout, pytz, requests)"
    - "Pyright via npm (package.json) so node-side tooling owns the version"
    - "asyncio_mode = auto (mandatory for pytest-homeassistant-custom-component)"
    - "Exact-version pinning for all CI deps; ruff version cross-checked between requirements_test.txt and pyproject.toml [tool.ruff] required-version"

key-files:
  created:
    - "pyproject.toml"
    - ".python-version"
    - "requirements_test.txt"
    - "package.json"
    - ".gitignore"
    - "LICENSE"
    - "README.md"
  modified: []

key-decisions:
  - "OQ-1 resolved: ship MIT LICENSE with copyright 2026 Thomas Guyader"
  - "Ship full ruff config (HA Core verbatim with target-version=py314 + line-length=120) from Phase 1 — not a minimal subset"
  - "Pin ruff 0.15.1 in two places (requirements_test.txt and [tool.ruff] required-version) for cross-file version consistency"
  - "filterwarnings=error in pytest config — surface deprecation warnings as test failures from day 1"

patterns-established:
  - "Pattern: dual-pinned ruff version. requirements_test.txt uses ==0.15.1 and pyproject.toml [tool.ruff] required-version uses >=0.15.1, both bumped together when ruff updates."
  - "Pattern: banned-api as supply-chain guard. Re-introduction of async_timeout/pytz/requests fails CI lint, blocks merge."
  - "Pattern: Python pin parity. .python-version and pyproject.toml requires-python both target 3.14 — uv and ruff agree on the floor."

requirements-completed:
  - DIST-08

# Metrics
duration: ~10min
completed: 2026-05-03
---

# Phase 01 Plan 01: Repo Bootstrap Summary

**Python 3.14 + uv + ruff (lint+format) + pyright (basic) + pytest (asyncio_mode=auto) tooling foundation pinned in pyproject.toml, requirements_test.txt, and package.json; MIT LICENSE and HACS-render-ready README shipped.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-03T06:00Z (approx, agent spawn)
- **Completed:** 2026-05-03T06:11:06Z
- **Tasks:** 3
- **Files created:** 7

## Accomplishments

- Pinned Python 3.14.2 floor (D-07) in `pyproject.toml:requires-python` and `.python-version` — every downstream tool (ruff target-version, uv venv resolver, pyright `venv`) now agrees on the same Python version.
- Single source of truth for tooling shipped in `pyproject.toml` — ruff (lint + format with HA Core's full select/ignore lists, target-version=py314, line-length=120), pyright (basic mode, includes `custom_components/ha_pronote` and `tests`), pytest (`asyncio_mode = "auto"`, `filterwarnings = ["error"]`, custom markers, log format), coverage (source = `custom_components/ha_pronote`).
- Banned-API guards wired in `[tool.ruff.lint.flake8-tidy-imports.banned-api]`: `async_timeout` (D-30), `pytz` (D-31), `requests` (D-32). Lint will fail merge if any future contribution re-introduces these.
- CI test dependencies version-pinned in `requirements_test.txt`: `homeassistant==2026.4.4` (D-09), `pytest-homeassistant-custom-component==0.13.326` (D-29), `ruff==0.15.1` (D-25/D-26), `codespell==2.4.1` (D-28). Cross-file consistency verified: ruff 0.15.1 pin in requirements_test.txt aligns with `[tool.ruff] required-version = ">=0.15.1"`.
- `package.json` declares `pyright: 1.1.409` (D-27) for `npx pyright` — keeps the type checker out of the Python venv per modern HACS blueprint pattern.
- `LICENSE` (MIT, Copyright 2026 Thomas Guyader) ships from Phase 1 — resolves OQ-1.
- `README.md` is the Phase 1 placeholder (status banner, HACS custom-repo install steps, requirements section, LICENSE link). No ApexCharts/automation YAML/polling rationale (those are Phase 7 — DIST-07).
- `.gitignore` extended with all 7 entries from RESEARCH §Security Domain task 1: `.ruff_cache/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.local/`, `node_modules/`, `*.zip` (alongside the original Python/venv stub).

## Task Commits

Each task was committed atomically on the worktree branch:

1. **Task 1: pyproject.toml + .python-version** — `9e4154f` (chore)
2. **Task 2: requirements_test.txt + package.json** — `c66d1f2` (chore)
3. **Task 3: .gitignore + LICENSE + README.md** — `9b3c752` (chore)

## Files Created/Modified

- `pyproject.toml` — uv project metadata, ruff (lint+format) config copied from HA Core master with target-version=py314, pyright basic mode, pytest asyncio_mode=auto, coverage source map, banned-api guards.
- `.python-version` — `3.14` (replaces stale `3.10` uv default).
- `requirements_test.txt` — exact-pinned CI test dependencies (homeassistant, PHACC, ruff, codespell).
- `package.json` — pyright pinned via npm for `npx pyright`.
- `.gitignore` — Python/venv stub plus Phase 1 cache/build/zip exclusions.
- `LICENSE` — MIT, Copyright 2026 Thomas Guyader.
- `README.md` — Phase 1 placeholder for HACS render_readme=true.

## Decisions Made

- **OQ-1 → MIT LICENSE, Copyright 2026 Thomas Guyader.** Plan delegated this to Claude's Discretion; chose MIT as the HA custom_component community default. Trivial to relicense before public release if user disagrees.
- **Adopt HA Core's `[tool.ruff]` block verbatim** (full select/ignore, isort config, mccabe limit, pydocstyle convention) instead of a Phase-1 minimum. Rationale: Phase 5 (pre-commit hooks) and Phase 4 (CI lint job) both consume this block; shipping the final shape now avoids a later config rewrite that would invalidate cached `ruff_cache`.
- **Cross-pin ruff in two places.** `requirements_test.txt: ruff==0.15.1` and `pyproject.toml: [tool.ruff] required-version = ">=0.15.1"`. When ruff bumps, both must move together. Documented as a maintenance pattern for Phase 5 / future Renovate config.
- **`filterwarnings = ["error"]` in pytest config.** Surface deprecation warnings from `pronotepy`, `homeassistant`, `pytest-homeassistant-custom-component` as test failures, not silent log output. The autoslot deprecation comment is left in place but commented-out — flip when/if it surfaces.

## Deviations from Plan

None — plan executed exactly as written. Each task's `<action>` block produced verbatim file content from RESEARCH.md, all `<acceptance_criteria>` checks passed on first run.

Note on context: this executor ran in a worktree (base commit `ec8d332`) where `.gitignore` and `.python-version` did not exist in HEAD. The plan instructed "extend, NOT replace" `.gitignore` and "OVERWRITE" `.python-version`; in the worktree, these were equivalent to fresh creation, but the final committed content matches exactly what the plan's "extend" path required (Python/venv stub PLUS Phase 1 additions; `3.14` single line). When the worktree merges back, the result will be identical to "edit-in-place".

## Issues Encountered

None.

## Self-Check

Verifying claims against the on-disk repository state:

- **Files created (7):**
  - FOUND: `pyproject.toml`
  - FOUND: `.python-version`
  - FOUND: `requirements_test.txt`
  - FOUND: `package.json`
  - FOUND: `.gitignore`
  - FOUND: `LICENSE`
  - FOUND: `README.md`
- **Commits (3 task commits, all on `worktree-agent-ac22d11a2d7206537`):**
  - FOUND: `9e4154f` — chore(01-01): add pyproject.toml + .python-version (uv + ruff + pyright + pytest)
  - FOUND: `c66d1f2` — chore(01-01): pin CI test deps + pyright via npm
  - FOUND: `9b3c752` — chore(01-01): add MIT LICENSE, Phase-1 README, extended .gitignore
- **Locked invariant verification (D-IDs visible in artifacts):**
  - D-07 / D-11: `requires-python = ">=3.14.2"` (pyproject.toml) AND `3.14` (.python-version) — OK
  - D-09: `homeassistant==2026.4.4` (requirements_test.txt) — OK
  - D-10: `target-version = "py314"` (pyproject.toml) — OK
  - D-25 / D-26: `ruff==0.15.1` (requirements_test.txt) AND `required-version = ">=0.15.1"` (pyproject.toml) — OK
  - D-27: `"pyright": "1.1.409"` (package.json) AND `typeCheckingMode = "basic"` (pyproject.toml) — OK
  - D-28: `codespell==2.4.1` (requirements_test.txt) — OK
  - D-29: `pytest-homeassistant-custom-component==0.13.326` (requirements_test.txt) AND `asyncio_mode = "auto"` (pyproject.toml) — OK
  - D-30: `"async_timeout".msg = "use asyncio.timeout instead"` — OK
  - D-31: `"pytz".msg = "use zoneinfo instead"` — OK
  - D-32: `"requests".msg = "use pronotepy via executor (D-32)"` — OK
- **OQ-1 resolution:** `MIT License` + `Copyright (c) 2026 Thomas Guyader` in LICENSE — OK
- **Cross-file consistency:** ruff 0.15.1 pin matches between requirements_test.txt and pyproject.toml — OK
- **Format validity:** `python3 -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"` exits 0 — OK; `python3 -c "import json; json.load(open('package.json'))"` exits 0 — OK

## Self-Check: PASSED

## Known Stubs

None. The README's "Status: Early development" banner is a documented placeholder for the integration's behavior (intentional per `<deferred>`), not a code stub. Full README content (HACS install button, ApexCharts schema, automation YAML examples, polling rationale) ships in Phase 7 (DIST-07).

## TDD Gate Compliance

Not applicable — plan type is `execute` (not `tdd`). All three tasks have `tdd="false"`. No test commits required.

## Threat Flags

None. The 7 files created in this plan introduce zero runtime surface, zero credential paths, zero network endpoints, and zero schema changes at trust boundaries. The only security-relevant content is supply-chain configuration (version pins, banned-api guards, .gitignore secret-leak prevention), all of which is fully covered by the plan's existing `<threat_model>` (T-01-01 through T-01-05).

## Next Phase Readiness

- **Plan 01-02 (manifest + integration skeleton):** Pyright will type-check `custom_components/ha_pronote/` once that directory is created. `[tool.pyright].include` already lists it.
- **Plan 01-03 (smoke test scaffold):** Pytest is configured (`testpaths = ["tests"]`, `asyncio_mode = "auto"`). The `tests/` directory and `tests/conftest.py` are owned by Plan 01-03.
- **Plan 01-04 (CI workflows):** Every workflow will run `uv pip install --system -r requirements_test.txt`. The pin set is reproducible and complete.
- **Plan 01-05 (pre-commit hooks):** `astral-sh/ruff-pre-commit` `rev: v0.15.1` MUST match the `ruff==0.15.1` pin in `requirements_test.txt` (cross-file invariant established here).
- **Open dependencies on this plan:** None — the foundation is self-contained.

---
*Phase: 01-foundations-skeleton*
*Completed: 2026-05-03*
