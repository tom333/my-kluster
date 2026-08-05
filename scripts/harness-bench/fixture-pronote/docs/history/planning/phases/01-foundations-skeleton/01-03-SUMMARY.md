---
phase: 01-foundations-skeleton
plan: 03
subsystem: testing
tags: [pytest, phacc, pytest-homeassistant-custom-component, smoke-test, regression-contract, manifest, config-flow, asyncio]

# Dependency graph
requires:
  - phase: 01-foundations-skeleton (Plan 01)
    provides: "[tool.pytest.ini_options] in pyproject.toml (asyncio_mode=auto, asyncio_default_fixture_loop_scope=function, testpaths=['tests']) + requirements_test.txt pinning pytest-homeassistant-custom-component==0.13.326 and homeassistant==2026.4.4"
  - phase: 01-foundations-skeleton (Plan 02)
    provides: "custom_components/ha_pronote/{__init__.py exporting DOMAIN, const.py declaring DOMAIN as 'ha_pronote', config_flow.py with HaPronoteConfigFlow.async_step_user returning async_abort(reason='not_implemented'), manifest.json with all 11 locked DIST-02 fields}"
provides:
  - "Wave 0 test scaffolding: tests package marker + PHACC autouse conftest closing Pitfall 10"
  - "DOMAIN single-source-of-truth regression contract (DIST-01 / D-01) — asserts package re-export equals const.DOMAIN equals 'ha_pronote'"
  - "ConfigFlow placeholder abort regression contract (D-16) — exercises hass.config_entries.flow.async_init through the real HA flow manager and asserts type='abort', reason='not_implemented'"
  - "Per-field manifest regression contract (DIST-02) — 14 tests, one per locked decision, with D-NN traceability so a CI failure points to the specific user decision violated"
affects:
  - 01-04 (test.yml workflow runs `pytest -q` against these files; the suite is the actual regression gate)
  - 01-05 (pre-commit hooks run ruff format + ruff check over tests/ — patterns established here must satisfy the existing [tool.ruff] config: PTH compliance, no @pytest.mark.asyncio, asyncio_mode=auto)
  - 02 (Phase 2 onboards friction-free: enable_custom_integrations is already wired so any new integration test gets the hass fixture loading custom_components/ha_pronote/ on first import)
  - 03 (real ConfigFlow lands in Phase 3; the test_config_flow_placeholder_aborts test is the explicit Phase 1 contract that Phase 3 will replace — its presence documents the contract being replaced)

# Tech tracking
tech-stack:
  added:
    - "pytest-homeassistant-custom-component test pattern (autouse enable_custom_integrations + hass fixture for ConfigFlow exercise)"
    - "pathlib.Path-based JSON loading for manifest assertions (PTH-compliant — no open() calls)"
  patterns:
    - "Per-field regression contract: one test per locked manifest field, docstring tags the D-NN decision — CI failure name → user decision violated"
    - "Sync + async test interleaving without @pytest.mark.asyncio (asyncio_mode='auto' from pyproject.toml does the heavy lifting)"
    - "Dual-import DOMAIN assertion (`from custom_components.ha_pronote import DOMAIN` AND `from custom_components.ha_pronote.const import DOMAIN as DOMAIN_CONST` then assert equal) — guards against accidental re-export drift"

key-files:
  created:
    - "tests/__init__.py"
    - "tests/conftest.py"
    - "tests/test_init.py"
    - "tests/test_manifest.py"
  modified: []

key-decisions:
  - "Verbatim adoption from RESEARCH.md §Code Examples (lines 1143–1167 for tests/__init__.py + tests/conftest.py; lines 1171–1203 for tests/test_init.py) — no creative interpretation, the canonical PHACC pattern is the contract."
  - "test_manifest.py derived from VALIDATION.md per-task verification map + CONTEXT.md locked D-NN values (no verbatim source). Each test docstring cites its D-ID for regression-diff traceability."
  - "test_manifest_no_unexpected_keys locks the Phase 1 manifest surface to exactly 11 keys — a future PR adding a key (e.g. `dependencies`, `loggers`) will fail this test, forcing the regression contract to be updated in lockstep with the schema."
  - "test_manifest_config_flow_true uses `is True` (not `==`) — guards against accidental truthy values like 1 or 'true' that would silently pass an `==` comparison."

patterns-established:
  - "Pitfall 10 mitigation: every conftest.py for HA custom integrations MUST wrap the PHACC `enable_custom_integrations` fixture with `autouse=True`. Documented inline in the docstring so any future PR removing the autouse will be caught at code-review time as well as at test runtime."
  - "Phase 1 contract regression tests live alongside placeholder code — when Phase 3 ships the real ConfigFlow, test_config_flow_placeholder_aborts is the test that MUST be replaced. Its docstring explicitly documents this so the Phase 3 planner does not silently delete it."
  - "Tests use pathlib.Path with read_text(encoding='utf-8') — open() and bare path strings are forbidden by ruff's PTH ruleset (already enabled in pyproject.toml [tool.ruff.lint.select])."

requirements-completed:
  - DIST-08

# Metrics
duration: 3min
completed: 2026-05-03
---

# Phase 1 Plan 03: Test Harness Foundation Summary

**Wave 0 test scaffolding — PHACC autouse conftest (Pitfall 10), 2-test DOMAIN/ConfigFlow placeholder smoke suite (DIST-01 + D-16), and 14-test per-field manifest regression contract (DIST-02 with D-NN traceability).**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-03T06:19:44Z
- **Completed:** 2026-05-03T06:22:27Z
- **Tasks:** 3
- **Files created:** 4

## Accomplishments

- DIST-08 satisfied at the file level: the four Wave 0 gaps from VALIDATION.md (`tests/__init__.py`, `tests/conftest.py`, `tests/test_init.py`, `tests/test_manifest.py`) all exist with the locked content. Plan 04's `test.yml` will now have something to assert; Phase 1 success criterion #3 ("local dev workflow green") becomes verifiable end-to-end.
- Pitfall 10 closed: `tests/conftest.py` defines `auto_enable_custom_integrations(enable_custom_integrations)` with `@pytest.fixture(autouse=True)` and a `yield` body. Without the autouse wrap, every integration test that uses the `hass` fixture would fail with `Integration not found: ha_pronote`; with it, every test in the suite gets the PHACC custom-integrations switch flipped automatically.
- DIST-01 / D-01 regression-tested: `test_domain_constant_is_ha_pronote` imports `DOMAIN` via both the package re-export (`custom_components.ha_pronote`) and the source-of-truth (`custom_components.ha_pronote.const`) and asserts they are equal AND equal to the literal `"ha_pronote"`. Any drift in either path fails immediately.
- D-16 regression-tested: `test_config_flow_placeholder_aborts` exercises the placeholder ConfigFlow through the real HA flow manager — `await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})` — and asserts `result["type"] == "abort"` and `result["reason"] == "not_implemented"`. This proves end-to-end that the Phase 1 placeholder lands in HA's flow registry, that `async_step_user` is reachable, and that it returns a clean abort dict (never a `RuntimeError` / `UnknownStep` / stack trace).
- DIST-02 regression-tested with full D-NN traceability: 14 individual tests in `test_manifest.py`, one per locked field. Each test docstring tags the decision it guards (D-01 domain, D-04 codeowners, D-05 documentation, D-06 issue_tracker, D-12 iot_class, D-13 quality_scale, D-14 requirements [pronotepy + python-slugify pinned exactly], D-15 integration_type, D-16 config_flow, D-17 version) plus a 14th `test_manifest_no_unexpected_keys` that locks the exact 11-key Phase 1 surface so silent schema drift fails CI.
- Async/sync test interleaving works without per-test markers because `pyproject.toml` already sets `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"` (Plan 01 Task 1). Pitfall 9 closed by inheritance.
- PTH compliance verified: zero `open(` calls in `test_manifest.py` (the file uses `pathlib.Path(__file__).resolve().parent.parent / ... / "manifest.json"` with `.read_text(encoding="utf-8")`). Ruff's flake8-pathlib ruleset (already enabled in `[tool.ruff.lint.select] = [..., "PTH", ...]`) will not flag this file.

## D-NN Coverage Map (test_manifest.py)

| Test                                                        | Locked decision | Asserted value                                       |
| ----------------------------------------------------------- | --------------- | ---------------------------------------------------- |
| test_manifest_is_valid_json                                 | DIST-02 (gate)  | manifest.json parses as JSON                         |
| test_manifest_domain_is_ha_pronote                          | D-01            | domain == "ha_pronote"                               |
| test_manifest_name_is_ha_pronote                            | (display)       | name == "HA-Pronote"                                 |
| test_manifest_codeowners_is_tom333                          | D-04            | codeowners == ["@tom333"]                            |
| test_manifest_documentation_url                             | D-05            | documentation == "https://github.com/tom333/ha-pronote" |
| test_manifest_issue_tracker_url                             | D-06            | issue_tracker == "https://github.com/tom333/ha-pronote/issues" |
| test_manifest_iot_class_cloud_polling                       | D-12            | iot_class == "cloud_polling"                         |
| test_manifest_quality_scale_bronze                          | D-13            | quality_scale == "bronze"                            |
| test_manifest_integration_type_hub                          | D-15            | integration_type == "hub"                            |
| test_manifest_config_flow_true                              | D-16            | config_flow is True                                  |
| test_manifest_version_placeholder                           | D-17            | version == "0.0.1"                                   |
| test_manifest_requirements_pin_pronotepy_2_14_6             | D-14            | "pronotepy==2.14.6" in requirements                  |
| test_manifest_requirements_pin_python_slugify_8_0_4         | D-14            | "python-slugify==8.0.4" in requirements              |
| test_manifest_no_unexpected_keys                            | (surface lock)  | exactly 11 keys, set equality                        |

## Task Commits

Each task was committed atomically:

1. **Task 1: tests/__init__.py + tests/conftest.py (PHACC autouse wiring)** — `35a4f9b` (test)
2. **Task 2: tests/test_init.py (DOMAIN smoke + ConfigFlow placeholder abort contract)** — `1d3dd1a` (test)
3. **Task 3: tests/test_manifest.py (DIST-02 regression contract)** — `4f95e36` (test)

_Plan metadata commit (this SUMMARY.md) follows separately._

## Files Created/Modified

- `tests/__init__.py` — Test package marker (single docstring `"""Tests for HA-Pronote."""`). Enables `tests` as an importable package so PHACC's path-resolution heuristics work cleanly.
- `tests/conftest.py` — Autouse PHACC wiring (Pitfall 10 mitigation). Wraps `enable_custom_integrations` so every test in the suite — present and future — sees `custom_components/ha_pronote/` as an available integration.
- `tests/test_init.py` — Two tests: `test_domain_constant_is_ha_pronote` (sync, dual-import equality assertion) and `test_config_flow_placeholder_aborts` (async, exercises `hass.config_entries.flow.async_init`, asserts `{"type": "abort", "reason": "not_implemented"}`).
- `tests/test_manifest.py` — 14 tests covering every locked field + a surface-lock test. Loads JSON via `pathlib.Path.read_text(encoding="utf-8")` (PTH-compliant). Each docstring cites the D-ID it guards for regression-diff traceability.

## Decisions Made

None - plan executed exactly as specified. Verbatim content from RESEARCH.md §Code Examples reproduced cleanly for `tests/__init__.py`, `tests/conftest.py`, and `tests/test_init.py`. `tests/test_manifest.py` derived from VALIDATION.md + CONTEXT.md per the plan's instruction (this file is a Wave 0 gap, not a RESEARCH.md verbatim source).

## Deviations from Plan

None - plan executed exactly as written.

No Rule 1 (bug) auto-fixes, no Rule 2 (missing critical) additions, no Rule 3 (blocking) installs, no Rule 4 (architectural) escalations. Every acceptance criterion in all three tasks verified on the first pass; AST parsing succeeded for all four files; the manifest sanity check (`m['domain'] == 'ha_pronote' and m['iot_class'] == 'cloud_polling' and m['quality_scale'] == 'bronze' and 'pronotepy==2.14.6' in m['requirements']`) passed against the manifest shipped by Plan 02.

## Issues Encountered

None during the planned work.

**Local pytest execution sidebar (NOT a deviation):** the worktree's available `python3` does not have `pytest-homeassistant-custom-component` installed, and `uv venv --python 3.14` resolved to Python `3.14.0a6` (alpha 6), which does not satisfy the project's `requires-python = ">=3.14.2"`. Per the plan's success criterion ("local execution is a soft check; CI runs are Plan 04's responsibility"), local `pytest -q` was not run. The static checks (`ast.parse`, `grep` of acceptance-criterion strings, manifest-content sanity in pure Python) all pass; CI on Plan 04 (with `setup-python@v6` + `python-version: 3.14`) is the authoritative check.

## Threat Model Compliance

All `mitigate` dispositions from the plan's `<threat_model>` are honored by the shipped artifacts:

- **T-03-01 (Tampering, future PR drifts a manifest field away from a locked D-NN value):** mitigated by `tests/test_manifest.py` — 13 per-field assertions plus the surface-lock test. CI failure name encodes the violated decision.
- **T-03-02 (Tampering, autouse wiring removed):** mitigated. `tests/conftest.py` ships `@pytest.fixture(autouse=True)` with the docstring explaining why removal would silently break the suite. Removal would surface immediately as `test_config_flow_placeholder_aborts` failing with "Integration not found: ha_pronote" rather than a clean abort.
- **T-03-03 (Spoofing, DOMAIN re-export drift):** mitigated by the dual-import equality assertion in `test_domain_constant_is_ha_pronote`.
- **T-03-04 (Information Disclosure, secrets in test logs):** accept disposition holds — Phase 1 has no secrets. Phase 3 will own redaction (per CONTEXT.md `<deferred>` and DIAG-01).
- **T-03-05 (DoS, async loop misconfigured):** mitigated by inheritance from Plan 01 (`pyproject.toml [tool.pytest.ini_options]` ships `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"`).

No new threat surface introduced. No `threat_flag` entries.

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness

- **Plan 01-04 (CI workflows):** `test.yml` has its target. The workflow's `pytest -q` step will discover 16 tests (2 in `test_init.py` + 14 in `test_manifest.py`), run them under `asyncio_mode=auto`, and exit 0 against the manifest + ConfigFlow shipped by Plan 02 + the Python package shipped by Plan 02.
- **Plan 01-05 (devcontainer + pre-commit):** the test files already pass the [tool.ruff] block from Plan 01 (`per-file-ignores` for `tests/*` exempts S101 / PLR2004 / D so the assert-heavy and undocumented-test style is fine; PTH compliance is enforced and met).
- **Phase 2 onboarding:** new test files dropped into `tests/` will inherit the PHACC autouse fixture automatically. No copy-paste of conftest stanzas required — C-01 RECOMMEND honored end-to-end.
- **Phase 3 (real ConfigFlow):** `test_config_flow_placeholder_aborts` is the explicit Phase 1 contract that Phase 3 will replace. The test's docstring documents this so the Phase 3 planner picks it up instead of silently deleting it.

## Self-Check: PASSED

Verified files exist, commits exist in `git log`, all acceptance criteria met. Detail:

- `tests/__init__.py` — FOUND
- `tests/conftest.py` — FOUND
- `tests/test_init.py` — FOUND
- `tests/test_manifest.py` — FOUND
- Commit `35a4f9b` (Task 1) — FOUND in `git log`
- Commit `1d3dd1a` (Task 2) — FOUND in `git log`
- Commit `4f95e36` (Task 3) — FOUND in `git log`

---
*Phase: 01-foundations-skeleton*
*Completed: 2026-05-03*
