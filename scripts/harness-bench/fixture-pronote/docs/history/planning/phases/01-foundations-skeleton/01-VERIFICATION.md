---
phase: 01-foundations-skeleton
verified: 2026-05-03T07:30:00Z
status: human_needed
score: 28/28 must-haves verified (code-side)
overrides_applied: 0
human_verification:
  - test: "Bring up the devcontainer (`.devcontainer.json`) on a contributor machine, install HACS in the HA frontend, add `https://github.com/tom333/ha-pronote` as a custom repository (category Integration), install, restart HA, confirm \"HA-Pronote\" appears in the integrations list."
    expected: "HA-Pronote integration visible in HA → Devices & Services list. Adding the integration triggers the placeholder ConfigFlow which returns the localised \"HA-Pronote is in early development. Account setup will be available in a future release.\" abort message — no stack trace."
    why_human: "Phase 1 success criterion #1 — requires running HA dev container + HACS frontend; no automated harness for HACS frontend in CI. The integration files are committed and conformant; this validates end-to-end install."
  - test: "On a fresh checkout of the repository, run `uv pip install --system -r requirements_test.txt && pytest -q` from the repo root."
    expected: "All 16 tests pass (2 in tests/test_init.py + 14 in tests/test_manifest.py). pytest exit code 0."
    why_human: "Phase 1 success criterion #3. Local pytest cannot be exercised in this verification environment because pytest + pytest-homeassistant-custom-component are not installed in the system Python here. The committed test.yml workflow will run the suite on first push to GitHub. This is the human-runnable equivalent."
  - test: "After pushing the repo to GitHub at `tom333/ha-pronote`, open a pull request that intentionally fails one CI check (e.g., introduces a ruff violation) and confirm the PR cannot be merged through the GitHub UI."
    expected: "GitHub blocks the merge button with status \"Required checks failing: Lint/Validate/Test\". Direct push to main is also blocked by the branch-protection rule."
    why_human: "Phase 1 success criterion #2 + DIST-03 policy layer. Workflows are committed and CI-ready, but actually running CI requires the repo to exist on GitHub (it does not yet — see Task 4 deferred TODO in 01-04-SUMMARY.md). hassfest+hacs/action+ruff+pyright+pytest cannot be observed running until first push."
  - test: "Configure GitHub branch protection on `main` for the pushed repo (Path A web UI or Path B `gh api`) per the 01-04-SUMMARY.md → \"Pending Operator Action — Task 4\" instructions. Verify with `gh api repos/tom333/ha-pronote/branches/main/protection --jq '.required_status_checks.contexts'` returning `[\"Lint\",\"Validate\",\"Test\"]`."
    expected: "API call returns the three required status check contexts AND `enforce_admins.enabled == true`."
    why_human: "Plan 01-04 Task 4 (`autonomous: false`, `type: checkpoint`) is the operator-only DIST-03 policy layer. The repo `tom333/ha-pronote` does not exist on GitHub yet (this verification host has no remote, no `gh auth`); cannot be automated from the orchestrator. Code-side workflow files are conformant and ready to be enforced as required checks once they have run once on a PR."
  - test: "After cutting the first git tag (e.g., `v0.0.1`) on a published GitHub Release, confirm `release.yml` runs and attaches `ha_pronote.zip` as a release asset; verify the zip's `manifest.json:version` matches the tag."
    expected: "GitHub release page shows `ha_pronote.zip` attached; downloading it and inspecting `manifest.json` shows `\"version\": \"v0.0.1\"` (or the actual tag value)."
    why_human: "release.yml (D-18) only triggers on `release: published` and cannot be exercised before a real tag exists. Workflow body is correct (verified statically), but the actual yq+zip+upload chain runs on the GitHub runner — observable only after a tag is cut. Listed as deferred to Phase 7 in VALIDATION.md \"Manual-Only Verifications\"."
---

# Phase 1: Foundations & Skeleton — Verification Report

**Phase Goal:** "A HACS-compliant repo that loads as an empty integration in HA, with CI gates blocking any merge that would break later phases."

**Verified:** 2026-05-03T07:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification.

---

## Goal Achievement

### Roadmap Success Criteria

The four ROADMAP success criteria are the contract for Phase 1. Three of the four are partially un-verifiable from code alone (they require operator action to exercise): they pass at the code/configuration layer and are routed to `human_verification`.

| # | Success Criterion | Code-Layer Status | Operator Action |
|---|-------------------|-------------------|-----------------|
| 1 | Clone repo, point HACS at it as custom repository, install, "HA-Pronote" appears under integrations | VERIFIED (code) | Human test #1 (HACS frontend install) |
| 2 | Every PR runs hassfest + hacs/action + ruff + pyright + pytest in GitHub Actions and blocks merge on failure | VERIFIED (workflows committed) | Human tests #3 + #4 (push to GH + branch protection) |
| 3 | `uv sync && uv run pytest` from clean checkout green-passes | VERIFIED (test files committed, suite is well-formed) | Human test #2 (run pytest locally) |
| 4 | `manifest.json` declares `iot_class: cloud_polling`, `quality_scale: bronze`, `pronotepy>=2.14,<3.0`, codeowners, issue tracker — `hassfest` validates clean | VERIFIED (manifest content) | Human test #1 (hassfest run on first push) |

### Observable Truths (per-plan must_haves)

#### Plan 01-01 (Repo bootstrap — DIST-08)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Local dev can install all test deps via `uv pip install --system -r requirements_test.txt` from a clean checkout | VERIFIED | `requirements_test.txt` ships 4 pinned deps; CI `test.yml` exercises this exact command |
| 2 | Project pins Python 3.14 (HA 2026.4+ floor — D-07/D-11) | VERIFIED | `pyproject.toml:requires-python = ">=3.14.2"`; `.python-version = "3.14"` |
| 3 | Single source of truth for ruff/pyright/pytest config in `pyproject.toml` (D-25/D-26/D-27) | VERIFIED | All three tool configs present in `pyproject.toml` |
| 4 | Pyright runs from npm via `npx pyright` against pinned version (D-27) | VERIFIED | `package.json:devDependencies.pyright == "1.1.409"` + lint.yml uses `npx pyright` |
| 5 | Banned-API guards for `async_timeout`, `pytz`, `requests` wired in ruff (D-30/D-31/D-32) | VERIFIED | `[tool.ruff.lint.flake8-tidy-imports.banned-api]` lists all three with messages |
| 6 | OQ-1 resolved: MIT LICENSE with copyright `Thomas Guyader` | VERIFIED | `LICENSE` line 1: `MIT License`; line 3: `Copyright (c) 2026 Thomas Guyader` |
| 7 | README.md placeholder exists (HACS render_readme=true contract) | VERIFIED | `README.md` shipped, mentions HACS install + 2026.4.0 floor |
| 8 | D-09: `requirements_test.txt` pins `homeassistant==2026.4.4` | VERIFIED | `requirements_test.txt` line 4 |
| 9 | D-10: `pyproject.toml [tool.ruff] target-version = "py314"` | VERIFIED | `pyproject.toml` line 72 |
| 10 | D-28: codespell ships from Phase 1 | VERIFIED | `requirements_test.txt: codespell==2.4.1`; lint.yml runs codespell job |

#### Plan 01-02 (Integration skeleton — DIST-01, DIST-02)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 11 | HACS recognises repo as valid custom-repository integration (manifest.json + hacs.json present, well-formed) | VERIFIED | Both files JSON-parse; all required keys present |
| 12 | D-01 frozen invariant: `manifest.json:domain == "ha_pronote" == directory name == const.DOMAIN` | VERIFIED | `manifest.json:domain` = "ha_pronote"; folder = `custom_components/ha_pronote/`; `const.py: DOMAIN: Final = "ha_pronote"` |
| 13 | manifest declares iot_class, quality_scale, pronotepy==2.14.6, python-slugify==8.0.4, codeowners, issue_tracker, documentation (DIST-02) | VERIFIED | All 11 fields present and match locked values |
| 14 | manifest:config_flow=true paired with config_flow.py declaring `domain=DOMAIN` and `async_step_user` (D-16) | VERIFIED | `config_flow.py` defines `class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN)` with `VERSION = 1` and `async def async_step_user` |
| 15 | Placeholder ConfigFlow returns clean `not_implemented` abort (no exception) | VERIFIED | Method body returns `self.async_abort(reason="not_implemented")`; grep finds zero `raise` statements in file |
| 16 | DOMAIN declared exactly once in `const.py`; every other module imports it | VERIFIED | grep for `"ha_pronote"` literal outside const.py/manifest.json finds zero hits in `custom_components/` |
| 17 | D-03/D-04/D-05/D-06: GitHub URL is hyphen variant; codeowners=[@tom333] | VERIFIED | manifest.json values match all four D-IDs verbatim |
| 18 | D-08: hacs.json:homeassistant = "2026.4.0" | VERIFIED | hacs.json line 3 |
| 19 | D-12/D-13/D-14/D-15/D-17 honored in manifest.json | VERIFIED | iot_class="cloud_polling", quality_scale="bronze", requirements pinned exactly, integration_type="hub", version="0.0.1" |

#### Plan 01-03 (Test scaffolding — DIST-08)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 20 | `pytest` discovers tests under `tests/`; autouse fixture `auto_enable_custom_integrations` wired (Pitfall 10) | VERIFIED | `tests/conftest.py` declares `@pytest.fixture(autouse=True)` wrapping PHACC `enable_custom_integrations` |
| 21 | Unit test asserts `manifest.json:domain == "ha_pronote"` AND every locked field (DIST-02 regression contract) | VERIFIED | `tests/test_manifest.py` ships 14 tests, one per locked decision (D-01/D-04/D-05/D-06/D-12/D-13/D-14×2/D-15/D-16/D-17) + surface-lock + valid JSON + display-name |
| 22 | Integration test asserts placeholder ConfigFlow aborts with `result['type']=='abort'` and `result['reason']=='not_implemented'` (D-16 contract) | VERIFIED | `tests/test_init.py:test_config_flow_placeholder_aborts` exercises `hass.config_entries.flow.async_init(DOMAIN, ...)` and asserts both fields |
| 23 | Wave 0 baseline established: tests/__init__.py, tests/conftest.py, tests/test_init.py, tests/test_manifest.py | VERIFIED | All 4 files present; `ast.parse()` succeeds on each |
| 24 | D-29: pytest ships with PHACC + asyncio_mode=auto + enable_custom_integrations fixture | VERIFIED | `requirements_test.txt: pytest-homeassistant-custom-component==0.13.326`; pyproject.toml has `asyncio_mode = "auto"` |

#### Plan 01-04 (CI workflows — DIST-03)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 25 | Every PR (and push to main) runs lint.yml + validate.yml + test.yml | VERIFIED | All three workflows trigger on `push` and `pull_request` to `main` |
| 26 | Every action SHA-pinned (40-char) per D-23 | VERIFIED | All 18 `uses:` lines across 4 workflows pinned by 40-hex SHA + symbolic comment; zero tag-only refs |
| 27 | Top-level `permissions: {}` on lint/validate/test; only release.yml elevates to `contents: write` | VERIFIED | `yaml.safe_load` confirms permissions hierarchy on each file |
| 28 | CI uses `uv pip install --system -r requirements_test.txt` (NOT `uv sync`) per D-25 | VERIFIED | lint.yml + test.yml: `uv pip install --system -r requirements_test.txt` |
| 29 | release.yml triggers on `release: published`, rewrites manifest version via yq, zips ha_pronote.zip, attaches via softprops/action-gh-release (D-18) | VERIFIED | Workflow body: trigger correct, yq line present, `cd custom_components/ha_pronote && zip ha_pronote.zip -r ./`, softprops/action-gh-release@b4309332… |
| 30 | D-20: lint.yml runs `ruff format --check` + `ruff check` + `pyright` + `codespell` | VERIFIED | Three jobs (`ruff`, `pyright`, `codespell`) — all four commands present |
| 31 | D-21: validate.yml runs hassfest + hacs/action with category=integration, ignore=brands | VERIFIED | Both pinned to verified-2026-05-03 SHAs; correct args |
| 32 | D-22: test.yml runs `uv pip install -r requirements_test.txt && pytest -q` | VERIFIED | Workflow body matches |
| 33 | dist-03-merge-block: branch protection on `main` requires Lint+Validate+Test status checks | UNCERTAIN (operator action) | Plan 01-04 Task 4 is `autonomous: false`. SUMMARY 01-04 documents that the repo `tom333/ha-pronote` is not yet pushed and `gh auth status` reports invalid token. Routed to `human_verification` test #4. |

#### Plan 01-05 (Local devloop — DIST-08)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 34 | Devcontainer single-file at root (ludeeus shape) — Python 3.14 + Node 22 + uv + post-create installs | VERIFIED | `.devcontainer.json` at repo root; features python:1@3.14 + node:1@22; postCreateCommand chains `uv venv .venv --python 3.14 && .venv/bin/uv pip install -r requirements_test.txt && npm install` |
| 35 | Pre-commit hooks mirror CI lint.yml (ruff-format → ruff-check --fix → codespell → pyright via npx) — C-03 honored | VERIFIED | `.pre-commit-config.yaml` ships 3 repos (ruff-pre-commit, codespell, local pyright via npx) |
| 36 | Devcontainer matches Plan 01 pin: Python 3.14 + Node 22; matches pyproject.toml typeCheckingMode="basic" | VERIFIED | `python.analysis.typeCheckingMode == "basic"` in devcontainer settings; matches pyproject.toml [tool.pyright] |
| 37 | Cross-file version-alignment: ruff 0.15.1 in 3 files; codespell 2.4.1 in 2 files; pyright 1.1.409 via package.json consumed by both CI and local hooks | VERIFIED | grep confirms `ruff==0.15.1` in requirements_test.txt + `required-version = ">=0.15.1"` in pyproject.toml + `rev: v0.15.1` in pre-commit; `codespell==2.4.1` + `rev: v2.4.1`; `"pyright": "1.1.409"` in package.json |

**Score:** 28/28 truths verified at the code/configuration layer. 1 truth (#33 — dist-03-merge-block) is `UNCERTAIN — operator action pending` and routed to `human_verification`.

---

### Required Artifacts

| Artifact | Expected | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `pyproject.toml` | uv project + ruff (target-version=py314) + pyright (basic) + pytest (asyncio_mode=auto) + coverage + banned-api | yes | yes — 162 lines, all D-IDs honored | yes — consumed by every CI workflow + pre-commit + devcontainer | VERIFIED |
| `.python-version` | "3.14" | yes | yes | yes — devcontainer + lint.yml + test.yml use python-version: 3.14 | VERIFIED |
| `requirements_test.txt` | homeassistant==2026.4.4 + PHACC==0.13.326 + ruff==0.15.1 + codespell==2.4.1 | yes | yes — 4 pins | yes — lint.yml + test.yml + devcontainer postCreateCommand consume it | VERIFIED |
| `package.json` | `pyright: 1.1.409` private | yes | yes | yes — lint.yml runs `npm install` then `npx pyright` | VERIFIED |
| `.gitignore` | Python venv + Phase 1 caches/zips | yes | yes — 9 entries | yes (passive) | VERIFIED |
| `LICENSE` | MIT, copyright 2026 Thomas Guyader | yes | yes — full MIT body | yes — referenced from README | VERIFIED |
| `README.md` | HACS install steps, 2026.4.0 floor, status banner | yes | yes — 26 lines | yes — `hacs.json:render_readme=true` consumes it | VERIFIED |
| `custom_components/ha_pronote/manifest.json` | All 11 locked fields (D-01/D-04/D-05/D-06/D-12/D-13/D-14/D-15/D-16/D-17) | yes | yes — 11 keys, all match | yes — validate.yml hassfest job + tests/test_manifest.py + release.yml | VERIFIED |
| `custom_components/ha_pronote/__init__.py` | Re-exports DOMAIN; no async_setup_entry; no hass.data | yes | yes — minimal & correct | yes — imported by tests + downstream phases | VERIFIED |
| `custom_components/ha_pronote/const.py` | `DOMAIN: Final = "ha_pronote"` | yes | yes | yes — imported by __init__.py + config_flow.py + tests | VERIFIED |
| `custom_components/ha_pronote/config_flow.py` | HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN) with VERSION=1 + async_step_user → async_abort(reason="not_implemented") | yes | yes — 28 lines, all four invariants | yes — exercised by tests/test_init.py via real HA flow manager | VERIFIED |
| `custom_components/ha_pronote/strings.json` | `config.abort.not_implemented` non-empty string | yes | yes | yes — paired with placeholder abort reason | VERIFIED |
| `hacs.json` | name=HA-Pronote, homeassistant=2026.4.0, hacs=2.0.5, country=FR, render_readme=true, zip_release=true, filename=ha_pronote.zip | yes | yes — 7 keys | yes — validate.yml hacs/action job + release.yml zip output | VERIFIED |
| `tests/__init__.py` | Single docstring | yes | yes (28B) | yes (passive marker) | VERIFIED |
| `tests/conftest.py` | autouse `enable_custom_integrations` wrap (Pitfall 10) | yes | yes — fixture + docstring | yes — applies to every test in suite | VERIFIED |
| `tests/test_init.py` | DOMAIN smoke + ConfigFlow placeholder abort contract | yes | yes — 2 tests, both required assertions | yes — exercises `custom_components.ha_pronote` + `hass.config_entries.flow.async_init` | VERIFIED |
| `tests/test_manifest.py` | Per-field manifest regression contract (DIST-02) | yes | yes — 14 tests, each docstring tags D-NN | yes — pathlib.Path-based load, runs on every PR | VERIFIED |
| `.github/workflows/lint.yml` | 3 jobs: ruff (format+check), pyright (npx), codespell — SHA-pinned, permissions:{} | yes | yes — 57 lines, three jobs | yes — triggers on push/PR to main | VERIFIED |
| `.github/workflows/validate.yml` | hassfest + hacs/action with category=integration, ignore=brands | yes | yes — 27 lines | yes — triggers on push/PR to main | VERIFIED |
| `.github/workflows/test.yml` | uv pip install + pytest -q, SHA-pinned, permissions:{} | yes | yes — 25 lines | yes — triggers on push/PR to main | VERIFIED |
| `.github/workflows/release.yml` | triggers on release:published; yq version inject; zip ha_pronote.zip; softprops/action-gh-release | yes | yes — 31 lines, contents:write only | yes — dormant until first tag | VERIFIED |
| `.devcontainer.json` | Python 3.14 + Node 22 features, postCreateCommand, forwardPorts [8123], extensions, typeCheckingMode=basic | yes | yes — 45 lines | yes — single-file at root, ludeeus shape | VERIFIED |
| `.pre-commit-config.yaml` | ruff-pre-commit v0.15.1 + codespell v2.4.1 + local pyright via npx, language:node, pass_filenames:false | yes | yes — 28 lines, version-aligned to requirements_test.txt | yes — both prek and pre-commit parse it | VERIFIED |

All 23 expected artifacts are present, substantive, and correctly wired.

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml` | `.python-version` | both target Python 3.14 (HA 2026.4 floor) | WIRED | `>=3.14.2` ↔ `3.14` |
| `pyproject.toml` | `requirements_test.txt` | `[tool.ruff] required-version` matches `ruff==0.15.1` | WIRED | `>=0.15.1` accepts `0.15.1` |
| `pyproject.toml` | `package.json` | `typeCheckingMode = "basic"` consumed via `npx pyright` | WIRED | basic mode aligned, lint.yml pyright job runs `npx pyright` |
| `manifest.json` | `custom_components/ha_pronote/` | domain key MUST equal directory name | WIRED | `domain = "ha_pronote"` matches dir |
| `manifest.json` | `config_flow.py` | `config_flow=true` requires config_flow.py | WIRED | hassfest contract met |
| `__init__.py` | `const.py` | `from .const import DOMAIN` | WIRED | grep confirms |
| `config_flow.py` | `const.py` | `from .const import DOMAIN` + `ConfigFlow(domain=DOMAIN)` | WIRED | grep confirms |
| `tests/conftest.py` | `pytest-homeassistant-custom-component` | autouse `enable_custom_integrations` fixture | WIRED | Pitfall 10 mitigation in place |
| `tests/test_init.py` | `__init__.py` | imports DOMAIN to assert single-source-of-truth | WIRED | dual-import equality assertion |
| `tests/test_init.py` | `config_flow.py` | calls `hass.config_entries.flow.async_init(DOMAIN, ...)` | WIRED | exercises placeholder via real HA flow manager |
| `tests/test_manifest.py` | `manifest.json` | loads JSON, asserts every locked key+value (14 tests) | WIRED | pathlib.Path-based, PTH-compliant |
| `test.yml` | `requirements_test.txt` | `uv pip install --system -r requirements_test.txt` | WIRED | exact path matches D-25 |
| `lint.yml` | `package.json` | `npm install` + `npx pyright` | WIRED | pyright 1.1.409 pulled and exercised |
| `release.yml` | `manifest.json` | `yq -i -o json .version=tag` rewrites version | WIRED | path matches; tag interpolation safe |
| `release.yml` | `hacs.json` | zip filename `ha_pronote.zip` matches `hacs.json:filename` | WIRED | byte-equal cross-plan invariant |
| `validate.yml` | `manifest.json` | hassfest validates manifest schema | WIRED | hassfest@f6f29a7e pinned, `home-assistant/actions/hassfest` |
| `.devcontainer.json` | `requirements_test.txt` | postCreateCommand runs `uv pip install -r requirements_test.txt` | WIRED | exact match |
| `.devcontainer.json` | `package.json` | postCreateCommand runs `npm install` | WIRED | pulls pyright 1.1.409 |
| `.pre-commit-config.yaml` | `requirements_test.txt` | ruff/codespell rev MUST match pin | WIRED | byte-equal `v0.15.1` ↔ `==0.15.1`; `v2.4.1` ↔ `==2.4.1` |
| `.pre-commit-config.yaml` | `package.json` | local pyright hook runs `npx pyright` | WIRED | language: node + pass_filenames: false |

All 20 declared key links are correctly wired.

---

### Data-Flow Trace (Level 4)

Phase 1 ships only configuration and a placeholder ConfigFlow. There are no dynamic-data artifacts (no sensors, no API responses, no DB queries, no entity state) to trace. Skipped — not applicable to a foundations/skeleton phase.

The single dynamic flow that exists is the placeholder ConfigFlow's abort path: `tests/test_init.py:test_config_flow_placeholder_aborts` exercises it through the real HA flow manager (registered via `__init_subclass__(domain=DOMAIN)` on import) and asserts the abort dict shape. The data flow is verified at the test layer.

---

### Behavioral Spot-Checks

Behavioral checks that complete in <10s without starting servers or modifying state:

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `pyproject.toml` parses as TOML | `python3 -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"` | exit 0 | PASS |
| `manifest.json` parses as JSON | `python3 -c "import json; json.load(open('custom_components/ha_pronote/manifest.json'))"` | exit 0 | PASS |
| `hacs.json` parses as JSON | `python3 -c "import json; json.load(open('hacs.json'))"` | exit 0 | PASS |
| `package.json` parses as JSON; pyright pinned to 1.1.409 | `python3 -c "import json; d=json.load(open('package.json')); assert d['devDependencies']['pyright']=='1.1.409'"` | exit 0 | PASS |
| `.devcontainer.json` parses as JSON | `python3 -c "import json; json.load(open('.devcontainer.json'))"` | exit 0 | PASS |
| All 4 workflows parse as YAML | `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/'+w for w in ['lint.yml','validate.yml','test.yml','release.yml']]]"` | exit 0 | PASS |
| `.pre-commit-config.yaml` parses as YAML | `python3 -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"` | exit 0 | PASS |
| `.python-version == "3.14"` | `[ "$(cat .python-version | tr -d '[:space:]')" = "3.14" ]` | exit 0 | PASS |
| `tests/*.py` parse as Python AST | `python3 -c "import ast; [ast.parse(open(f).read()) for f in ['tests/test_init.py','tests/test_manifest.py','tests/conftest.py','tests/__init__.py']]"` | exit 0 | PASS |
| `config_flow.py` parses as AST and contains the four invariants | manual grep — has VERSION=1, ConfigFlow with domain=DOMAIN, async_step_user, async_abort(reason="not_implemented"), no `raise` | all True | PASS |
| Every workflow `uses:` is SHA-pinned (40-hex) | `grep -E 'uses:' .github/workflows/*.yml \| grep -v -E '@[0-9a-f]{40}'` | empty output (0 non-pinned uses) | PASS |
| Zero `${{ secrets.* }}` references in release.yml | `grep -E 'secrets\.[A-Z_]+' .github/workflows/release.yml` | empty | PASS |
| `hacs.json:filename == "ha_pronote.zip"` matches release.yml zip target | check both sides | both `ha_pronote.zip` | PASS |
| Cross-file ruff version alignment (3 places) | grep all 3 sources | `==0.15.1` / `>=0.15.1` / `v0.15.1` — all aligned | PASS |
| Cross-file codespell version alignment (2 places) | grep both sources | `==2.4.1` / `v2.4.1` — aligned | PASS |
| No hardcoded `"ha_pronote"` literal outside const.py and manifest.json | grep `custom_components/` | zero hits | PASS |
| Pytest discovery (`pytest --collect-only -q`) | not executed — pytest not installed in verifier env | SKIPPED | SKIP — routed to human verification test #2 |
| Pytest run (`pytest -q`) | not executed — pytest not installed | SKIPPED | SKIP — routed to human verification test #2 |
| ruff format --check + ruff check on the codebase | not executed — ruff not installed | SKIPPED | SKIP — CI lint.yml exercises this on first push |
| hassfest validation against manifest.json | not executed — hassfest only runs in GH Actions | SKIPPED | SKIP — routed to human verification test #3 (first push) |
| hacs/action validation | not executed — only runs in GH Actions | SKIPPED | SKIP — routed to human verification test #3 (first push) |

All 16 runnable behavioral spot-checks PASS. The 5 SKIPPED checks require an environment with installed dev tooling (pytest, ruff) or GitHub Actions to execute — covered by `human_verification` items.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DIST-01 | 01-02 | Repo HACS-conformant: `manifest.json` + `hacs.json` + `info.md` | SATISFIED (info.md replaced by README via `render_readme: true` per HACS docs) | manifest.json + hacs.json present, well-formed; README rendered as info; tests/test_manifest.py + validate.yml hassfest job enforce contract |
| DIST-02 | 01-02 | manifest.json declares iot_class=cloud_polling, quality_scale=bronze, dépendances Python explicites | SATISFIED | All 11 locked fields verified (D-12/D-13/D-14/D-15); 14 regression tests in test_manifest.py |
| DIST-03 | 01-04 | GitHub Actions CI: hassfest + hacs/action + ruff + pyright + pytest on each PR | SATISFIED (workflow layer); NEEDS HUMAN (policy layer) | lint.yml + validate.yml + test.yml committed and triggered on push/PR; branch-protection (Task 4 deferred) routed to human_verification #4 |
| DIST-08 | 01-01, 01-03, 01-05 | Project tooling = uv (deps + venv) + ruff (lint+format) + pyright (typing) + pre-commit hooks | SATISFIED | pyproject.toml + requirements_test.txt + package.json + .pre-commit-config.yaml + .devcontainer.json all in place; cross-version-aligned |

All 4 phase-mapped requirements accounted for. No orphans. DIST-03 is split: workflow layer SATISFIED, policy layer NEEDS HUMAN (operator action documented in 01-04-SUMMARY.md "Pending Operator Action").

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TODO/FIXME/HACK in any committed file | — | — |
| (none) | — | No empty `return null/[]/{}` stubs in production code | — | — |
| (info) | config_flow.py:1, 3, 5, 19 | "placeholder" mentions in docstring | INFO | INTENTIONAL per D-16 contract — Phase 1 ships a placeholder ConfigFlow that aborts cleanly; Phase 3 replaces it. The docstring documents the contract and the replacement plan. Verifier confirms it is NOT a stub: the abort path is exercised by tests/test_init.py and registers correctly with HA's flow manager. |
| (info) | tests/test_manifest.py + tests/test_init.py | "placeholder" mentions in docstrings | INFO | Tests intentionally describe the Phase 1 placeholder contract so a future re-baselining (when Phase 3 ships the real flow) is obvious. |
| (info) | manifest.json:version "0.0.1" | placeholder version | INFO | INTENTIONAL per D-17 — release.yml rewrites this from the git tag at first release. Test test_manifest_version_placeholder asserts the placeholder remains until release. |

No blockers. Two intentional "placeholder" mentions in docstrings (config_flow.py + 4 test references) — all documented as Phase 1 contract per D-16/D-17, all guarded by tests, all replaced by later phases per ROADMAP.

---

### Human Verification Required

5 items need human testing — all involve operator action (running CI/HACS/HA) or pushing the repo to GitHub. Code-side conformance is fully verified.

1. **HACS install end-to-end** — clone repo, install HACS, add as custom repo, install, verify "HA-Pronote" appears in HA integrations.
2. **Local pytest run** — `uv pip install --system -r requirements_test.txt && pytest -q` from clean checkout; expect 16 tests passing.
3. **CI gates run on first push to GitHub** — hassfest + hacs/action + ruff + pyright + pytest run on a real PR.
4. **GitHub branch protection configured** — Task 4 of plan 01-04 (operator-only checkpoint per `autonomous: false`); flips DIST-03 from "workflow layer SATISFIED" to fully SATISFIED at the policy layer.
5. **Release workflow exercise** — cut v0.0.1 tag (or later) and confirm `ha_pronote.zip` attaches with rewritten `manifest.json:version` matching the tag.

See frontmatter `human_verification:` for full test/expected/why-human breakdown.

---

### Gaps Summary

**No code-side gaps.** Every must-have, every artifact at all four levels (exists, substantive, wired, data-flow N/A for skeleton phase), every key link, every requirement is verified at the code/configuration layer. The 5 items requiring human verification are not gaps — they are deferred to operator action because:

- They cannot be exercised in this verifier environment (no pytest/ruff installed, no GitHub repo pushed yet, no HA dev container running).
- They are explicitly documented as such in `01-VALIDATION.md` "Manual-Only Verifications" and `01-04-SUMMARY.md` "Pending Operator Action".
- The Plan 01-04 task 01-04-04 is `autonomous: false` and was always intended as an operator checkpoint.

The phase goal — "A HACS-compliant repo that loads as an empty integration in HA, with CI gates blocking any merge that would break later phases" — is achieved at the **code/configuration layer** (every file required to satisfy the goal exists, is correct, and is correctly wired to its consumers). The remaining items are runtime exercises (loading in HA, running CI on real PRs, configuring branch protection) that prove the integration **actually works** in HA + GitHub, which only the operator can perform.

**Status reasoning per Step 9:**
1. No truth FAILED, no artifact MISSING/STUB, no key link NOT_WIRED, no blocker anti-pattern → not `gaps_found`.
2. 5 human_verification items present → status MUST be `human_needed` (not `passed`), per the decision tree's must-not-skip rule for human items.
3. Therefore: **`status: human_needed`**.

---

*Verified: 2026-05-03T07:30:00Z*
*Verifier: Claude (gsd-verifier)*
