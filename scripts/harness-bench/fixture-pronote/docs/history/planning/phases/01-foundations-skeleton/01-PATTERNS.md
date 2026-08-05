# Phase 1: Foundations & Skeleton - Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 22 (20 to create, 2 to modify)
**Analogs found:** 22 / 22 (all external — greenfield repo, zero internal analogs)

## Greenfield Notice

The current repo contains only `.planning/`, `.claude/`, `CLAUDE.md`, `.gitignore` (8-line stub), `.python-version` (`3.10`). There are **no internal analogs**. Every pattern below points to an external reference cited in `01-RESEARCH.md` (`ludeeus/integration_blueprint`, `jpawlowski/hacs.integration_blueprint`, `delphiki/hass-pronote`, HA Core master). RESEARCH.md §Code Examples (lines 577–1264) ships the verbatim file content; this PATTERNS.md is a quick-lookup table the planner uses to assign each file to its source section.

**Planner directive:** for each file, copy the body from the cited `RESEARCH.md` line range. Do NOT re-fetch external repos — RESEARCH.md already verified them on 2026-05-03.

---

## File Classification

| Artifact | Role | Data Flow | Closest External Analog | RESEARCH.md §Code Examples Lines | Match Quality |
|----------|------|-----------|--------------------------|----------------------------------|----------------|
| `custom_components/ha_pronote/manifest.json` | config (HA integration manifest) | declarative | `jpawlowski/hacs.integration_blueprint/custom_components/<x>/manifest.json` + `delphiki/hass-pronote/manifest.json` (delphiki for the Pronote runtime requirement; jpawlowski for the modern key set) | 581–605 | exact |
| `hacs.json` | config (HACS metadata) | declarative | `jpawlowski/hacs.integration_blueprint/hacs.json` (modern schema with `hacs: 2.0.5`) + `delphiki/hass-pronote/hacs.json` (zip-release pattern) | 606–627 | exact |
| `custom_components/ha_pronote/__init__.py` | package (no-op skeleton) | request-response (currently inert) | `ludeeus/integration_blueprint/custom_components/integration_blueprint/__init__.py` (canonical minimal form) | 628–642 | role-match (we ship a no-op; ludeeus ships full setup — copy ludeeus's docstring + import shape, drop `async_setup_entry`) |
| `custom_components/ha_pronote/const.py` | package (constants module) | declarative | `ludeeus/integration_blueprint/custom_components/integration_blueprint/const.py` | 644–654 | exact |
| `custom_components/ha_pronote/config_flow.py` | package (placeholder ConfigFlow) | request-response (aborts) | HA Core `homeassistant/config_entries.py:ConfigFlow` registration pattern + `ludeeus/integration_blueprint/.../config_flow.py` (subclass shape) | 656–687 | role-match (we abort, ludeeus implements; copy class declaration + `async_step_user` signature, replace body with `async_abort`) |
| `custom_components/ha_pronote/strings.json` | config (i18n strings — minimal Phase 1) | declarative | HA developer docs §"Config flow handler" abort-reason pattern | 689–699 | exact (minimal subset — full strings.json deferred to Phase 7) |
| `pyproject.toml` | tooling (uv project + ruff + pyright + pytest config) | declarative | `jpawlowski/hacs.integration_blueprint/pyproject.toml` (overall layout + pyright + pytest blocks) + HA Core master `pyproject.toml` (`[tool.ruff]` block verbatim, `target-version` overridden to `py314`) | 701–865 | exact (jpawlowski for layout, HA Core for ruff content) |
| `requirements_test.txt` | tooling (CI deps) | declarative | `jpawlowski/hacs.integration_blueprint/requirements_test.txt` | 867–885 | exact |
| `package.json` | tooling (pyright via npm) | declarative | `jpawlowski/hacs.integration_blueprint/package.json` | 887–899 | exact |
| `.pre-commit-config.yaml` | tooling (local hooks) | event-driven (git pre-commit) | HA Core master `.pre-commit-config.yaml` | 901–932 | exact |
| `.devcontainer.json` | tooling (dev container) | declarative | `ludeeus/integration_blueprint/.devcontainer.json` (single-file form at repo root) | 934–982 | role-match (ludeeus ships minimal form; we extend with `node:22` feature for `npx pyright`) |
| `.github/workflows/lint.yml` | workflow (CI lint) | event-driven (push/PR) | `jpawlowski/hacs.integration_blueprint/.github/workflows/lint.yml` | 984–1043 | exact |
| `.github/workflows/validate.yml` | workflow (CI hassfest + hacs/action) | event-driven (push/PR) | `jpawlowski/hacs.integration_blueprint/.github/workflows/validate.yml` | 1045–1075 | exact |
| `.github/workflows/test.yml` | workflow (CI pytest) | event-driven (push/PR) | `jpawlowski/hacs.integration_blueprint/.github/workflows/test.yml` (extrapolated — jpawlowski has lint+validate; test pattern follows same shape) | 1077–1105 | role-match (same shape as lint.yml; the `pytest -q` step is the only divergence) |
| `.github/workflows/release.yml` | workflow (release automation) | event-driven (release: published) | `delphiki/hass-pronote/.github/workflows/release.yml` (manual zip pattern, NOT release-please per D-18) | 1107–1141 | exact |
| `tests/__init__.py` | test (package marker) | n/a (empty) | HA Core test layout convention (`tests/__init__.py` ships only the docstring) | 1143–1147 | exact |
| `tests/conftest.py` | test (shared fixtures) | declarative (pytest fixtures) | `pytest-homeassistant-custom-component` README §"Enable custom integrations" autouse fixture pattern | 1149–1167 | exact |
| `tests/test_init.py` | test (smoke + ConfigFlow contract) | unit + integration (`hass` fixture) | `ludeeus/integration_blueprint/tests/test_init.py` (smoke test pattern) + PHACC docs (`hass.config_entries.flow.async_init`) | 1169–1203 | exact |
| `.gitignore` (modify) | config (git exclusions) | declarative | HA Core master `.gitignore` (subset) + Python community standard | 1205–1225 | exact (extends existing 8-line stub) |
| `.python-version` (modify) | config (uv/pyenv pin) | declarative | uv convention; value forced by `manifest.json` requires-python | 1227–1233 | exact (single-line replacement `3.10` → `3.14`) |
| `README.md` | docs (placeholder) | declarative | HACS publish docs §"Repository setup" (minimal install instructions) — full README deferred to Phase 7 | 1235–1264 | role-match (Phase 1 ships minimal placeholder; full version Phase 7) |
| `LICENSE` | docs (legal) | declarative | MIT template (per A1 — RECOMMEND default in Open Question 1) | not in §Code Examples — standard MIT template | role-match (open question OQ-1 — planner must confirm or default to MIT) |

---

## Pattern Assignments

### `custom_components/ha_pronote/manifest.json` (config, declarative)

**External analog:** `jpawlowski/hacs.integration_blueprint/.../manifest.json` (modern shape) + `delphiki/hass-pronote/.../manifest.json` (Pronote runtime requirements pinning style)
**Source:** `01-RESEARCH.md` lines 581–605 — copy verbatim.

**Locked values per CONTEXT.md:**
- `domain: "ha_pronote"` (D-01)
- `codeowners: ["@tom333"]` (D-04)
- `documentation: "https://github.com/tom333/ha-pronote"` (D-05)
- `issue_tracker: ".../issues"` (D-06)
- `iot_class: "cloud_polling"` (D-12)
- `quality_scale: "bronze"` (D-13)
- `requirements: ["pronotepy==2.14.6", "python-slugify==8.0.4"]` (D-14)
- `integration_type: "hub"` (D-15)
- `config_flow: true` (D-16) — **REQUIRES `config_flow.py` to exist** [hassfest landmine, RESEARCH.md §Pitfalls]
- `version: "0.0.1"` (D-17)

**Verification rule:** every key cross-referenced against hassfest `CUSTOM_INTEGRATION_MANIFEST_SCHEMA` (RESEARCH.md L599 / hassfest manifest.py L204-337). If hassfest CI fails on `quality_scale: bronze`, fork to OQ-4 (drop the field; re-add Phase 7).

---

### `hacs.json` (config, declarative)

**External analog:** `jpawlowski/hacs.integration_blueprint/hacs.json` (current schema version) + `delphiki/hass-pronote/hacs.json` (zip_release pattern matching D-18)
**Source:** `01-RESEARCH.md` lines 606–627 — copy verbatim.

**Locked values:**
- `name: "HA-Pronote"` (only HACS-required key)
- `homeassistant: "2026.4.0"` (D-08)
- `hacs: "2.0.5"` (matches modern blueprint)
- `country: "FR"` (per A2)
- `render_readme: true` (avoids `info.md` duplication)
- `zip_release: true` + `filename: "ha_pronote.zip"` (matches D-18 release.yml pattern)

---

### `custom_components/ha_pronote/__init__.py` (package, inert skeleton)

**External analog:** `ludeeus/integration_blueprint/custom_components/integration_blueprint/__init__.py`
**Source:** `01-RESEARCH.md` lines 628–642 — copy verbatim.

**Pattern:** Module docstring + single import (`from .const import DOMAIN`) + `__all__ = ["DOMAIN"]`. **NO** `async_setup`, **NO** `async_setup_entry` (placeholder ConfigFlow rejects all entry creation, so HA never calls these — see RESEARCH.md L361-382 §Pattern 2 for the rationale).

**Anti-pattern guard (RESEARCH.md L439):** Do NOT pre-populate `hass.data[DOMAIN]`. Phase 3 will use `entry.runtime_data` (typed) per ARCHITECTURE.md Pattern 6.

---

### `custom_components/ha_pronote/const.py` (package, declarative)

**External analog:** `ludeeus/integration_blueprint/custom_components/integration_blueprint/const.py`
**Source:** `01-RESEARCH.md` lines 644–654 — copy verbatim.

**Pattern:** `from __future__ import annotations` + `from typing import Final` + `DOMAIN: Final = "ha_pronote"`. Single source of truth for the domain string (anti-pattern guard L440 — never hardcode `"ha_pronote"` outside this file).

---

### `custom_components/ha_pronote/config_flow.py` (package, placeholder flow)

**External analog:** HA Core `homeassistant/config_entries.py` (ConfigFlow `__init_subclass__(domain=...)` registration, RESEARCH.md L1443) + ludeeus blueprint config_flow.py (subclass shape)
**Source:** `01-RESEARCH.md` lines 656–687 — copy verbatim.

**Pattern (resolves D-16 critical landmine, RESEARCH.md L299-344):**
- Subclass `ConfigFlow` with `domain=DOMAIN` keyword arg
- `VERSION = 1` class attribute
- `async def async_step_user(self, user_input=None) -> ConfigFlowResult` MUST exist (HA's `_raise_if_step_does_not_exist` raises `UnknownStep` otherwise — RESEARCH.md L1442)
- Body returns `self.async_abort(reason="not_implemented")`

**Why placeholder is mandatory:** `manifest.json:config_flow=true` ⇒ hassfest checks `config_flow.py` exists (RESEARCH.md L306, hassfest config_flow.py L19-26). User clicking "Add Integration" must hit `async_step_user` cleanly.

---

### `custom_components/ha_pronote/strings.json` (config, i18n minimal)

**External analog:** HA developer docs §"Config flow handler"
**Source:** `01-RESEARCH.md` lines 689–699 — copy verbatim.

**Pattern:** Minimal `config.abort.not_implemented` key only. Full translations (`translations/{en,fr}.json`) deferred to Phase 7 per CONTEXT.md `<deferred>`.

**Optional in Phase 1:** if omitted, HA falls back to literal `not_implemented` reason (ugly but functional). RECOMMEND ship per RESEARCH.md L359.

---

### `pyproject.toml` (tooling, multi-block config)

**External analogs (composite):**
- Layout & pyright/pytest blocks: `jpawlowski/hacs.integration_blueprint/pyproject.toml`
- `[tool.ruff]` block: HA Core master `pyproject.toml` (RESEARCH.md L1438) — copy verbatim, override `target-version = "py314"` per D-10 and `line-length = 120` per A3

**Source:** `01-RESEARCH.md` lines 701–865 — copy verbatim. The block is already pre-merged in RESEARCH.md (jpawlowski layout + HA Core ruff content + Phase-1-specific banned-API entries).

**Phase-1-specific banned-API entries to keep (RESEARCH.md L842-846, enforcing D-30/D-31/D-32):**
```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"async_timeout".msg = "use asyncio.timeout instead"  # D-30
"pytz".msg = "use zoneinfo instead"                  # D-31
"requests".msg = "use pronotepy via executor (D-32)"
```

**Pyright config knob:** `typeCheckingMode = "basic"` per D-27 (NOT `strict`).

**Pytest config knob:** `asyncio_mode = "auto"` per D-29 / RESEARCH.md L503-512 (PHACC requires this — Pitfall 9).

---

### `requirements_test.txt` (tooling, pinned CI deps)

**External analog:** `jpawlowski/hacs.integration_blueprint/requirements_test.txt`
**Source:** `01-RESEARCH.md` lines 867–885 — copy verbatim.

**Locked pins (D-09 / D-26):**
```
homeassistant==2026.4.4
pytest-homeassistant-custom-component==0.13.326
ruff==0.15.1
codespell==2.4.1
```

**Anti-pattern guard (RESEARCH.md L442):** Do NOT pin `homeassistant==2026.5.0b0` to match PHACC's beta target — PHACC tracks beta but is backwards-compatible with 2026.4.x stable.

---

### `package.json` (tooling, npm/pyright)

**External analog:** `jpawlowski/hacs.integration_blueprint/package.json`
**Source:** `01-RESEARCH.md` lines 887–899 — copy verbatim.

**Pattern:** `private: true`, single `devDependencies` entry `"pyright": "1.1.409"`. Used by lint workflow `npx pyright` step.

---

### `.pre-commit-config.yaml` (tooling, hooks)

**External analog:** HA Core master `.pre-commit-config.yaml` (RESEARCH.md L1439)
**Source:** `01-RESEARCH.md` lines 901–932 — copy verbatim.

**Hook chain (per C-03):** `ruff-format` → `ruff-check --fix` → `codespell` → local `pyright` (via `npx pyright`). Same checks CI runs (lint.yml). Use `astral-sh/ruff-pre-commit v0.15.1` and `codespell-project/codespell v2.4.1` to match HA Core's pinned revs.

---

### `.devcontainer.json` (tooling, dev container — single-file form at repo root)

**External analog:** `ludeeus/integration_blueprint/.devcontainer.json`
**Source:** `01-RESEARCH.md` lines 934–982 — copy verbatim.

**Pattern (per C-02):** `mcr.microsoft.com/devcontainers/base:debian` image + `python:3.14` feature + `node:22` feature + `postCreateCommand` that runs `uv venv .venv --python 3.14 && uv pip install -r requirements_test.txt && npm install`. VSCode extensions: `charliermarsh.ruff`, `ms-python.python`, `ms-python.vscode-pylance`. Forwards port 8123 (HA UI).

**Why single-file at root (not `.devcontainer/devcontainer.json`):** matches ludeeus blueprint and is the simpler form (RESEARCH.md L296, L1279).

---

### `.github/workflows/lint.yml` (workflow, CI lint)

**External analog:** `jpawlowski/hacs.integration_blueprint/.github/workflows/lint.yml`
**Source:** `01-RESEARCH.md` lines 984–1043 — copy verbatim.

**Pattern (per D-20):** Three jobs (`ruff`, `pyright`, `codespell`), each `runs-on: ubuntu-latest`, `permissions: {}` at top level (security per RESEARCH.md L1421), SHA-pinned actions (D-23). `ruff` runs both `format --check` and `check`. `pyright` installs npm + runs `npx pyright`. `codespell` uses bare `pip install codespell==2.4.1`.

**SHA pins to copy verbatim (RESEARCH.md L1444-1450):**
- `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2`
- `actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0`
- `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0`
- `actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e  # v6.4.0`

---

### `.github/workflows/validate.yml` (workflow, hassfest + hacs/action)

**External analog:** `jpawlowski/hacs.integration_blueprint/.github/workflows/validate.yml`
**Source:** `01-RESEARCH.md` lines 1045–1075 — copy verbatim.

**Pattern (per D-21):** Two jobs:
- `hassfest`: just `home-assistant/actions/hassfest@f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b  # master`
- `hacs`: `hacs/action@dcb30e72781db3f207d5236b861172774ab0b485  # main` with `category: integration` and `ignore: brands` (brand assets deferred to v2+ per CONTEXT.md `<deferred>`)

**Anti-pattern guard (RESEARCH.md L543-552):** SHA pin drift — neither action publishes meaningful tags (`home-assistant/actions:1.0.0` is from 2020, `hacs/action:22.5.0` is from 2022). Pin by SHA on `master`/`main`, accept Renovate bumps in v2+.

---

### `.github/workflows/test.yml` (workflow, pytest)

**External analog:** Same shape as lint.yml ruff job (jpawlowski blueprint), with `pytest -q` instead of ruff
**Source:** `01-RESEARCH.md` lines 1077–1105 — copy verbatim.

**Pattern (per D-22):** Single `pytest` job, `uv pip install --system -r requirements_test.txt` then `pytest -q`. `permissions: {}`. SHA-pinned actions same as lint.yml.

---

### `.github/workflows/release.yml` (workflow, release: published trigger)

**External analog:** `delphiki/hass-pronote/.github/workflows/release.yml` (manual zip pattern, NOT release-please per D-18)
**Source:** `01-RESEARCH.md` lines 1107–1141 — copy verbatim.

**Pattern (per D-18):**
1. `actions/checkout@<sha>`
2. `yq -i -o json '.version="${{ github.event.release.tag_name }}"' custom_components/ha_pronote/manifest.json` (yq is preinstalled on `ubuntu-latest`)
3. `cd custom_components/ha_pronote && zip ha_pronote.zip -r ./`
4. `softprops/action-gh-release@b4309332981a82ec1c5618f44dd2e27cc8bfbfda  # v3.0.0` to attach `ha_pronote.zip`

**Permissions:** `contents: write` at job level (only release.yml elevates — per RESEARCH.md L1423).

---

### `tests/__init__.py` (test, empty package marker)

**External analog:** HA Core test layout convention
**Source:** `01-RESEARCH.md` lines 1143–1147 — copy verbatim.

**Pattern:** Single docstring line `"""Tests for HA-Pronote."""`. No imports, no code.

---

### `tests/conftest.py` (test, shared fixtures)

**External analog:** PHACC README §"Enable custom integrations" autouse fixture
**Source:** `01-RESEARCH.md` lines 1149–1167 — copy verbatim.

**Pattern (per Pitfall 10, RESEARCH.md L513-522):**
```python
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
```
Without this autouse wrap, the `hass` fixture refuses to load `custom_components/` and our integration is invisible (test failures with `Integration not found: ha_pronote`).

---

### `tests/test_init.py` (test, smoke + ConfigFlow contract)

**External analog:** `ludeeus/integration_blueprint/tests/test_init.py` (smoke pattern) + PHACC `hass.config_entries.flow.async_init` test pattern
**Source:** `01-RESEARCH.md` lines 1169–1203 — copy verbatim.

**Two tests:**
1. `test_domain_constant_is_ha_pronote` — sync, asserts `DOMAIN == "ha_pronote"` (covers DIST-01, the manifest.domain ↔ folder ↔ const.py invariant)
2. `test_config_flow_placeholder_aborts` — async (uses `hass` fixture), calls `hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})`, asserts `result["type"] == "abort"` and `result["reason"] == "not_implemented"` (Phase 1 contract — to be replaced in Phase 3)

---

### `.gitignore` (modify — extend existing 8-line stub)

**External analog:** HA Core master `.gitignore` (subset relevant to custom integration)
**Source:** `01-RESEARCH.md` lines 1205–1225 — append the Phase-1 block to the existing file.

**Existing entries (already present):** `__pycache__/`, `*.py[oc]`, `build/`, `dist/`, `wheels/`, `*.egg-info`, `.venv`.

**Append (security per RESEARCH.md L1419):** `.ruff_cache/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.local/`, `node_modules/`, `*.zip`.

---

### `.python-version` (modify — single-line replacement)

**External analog:** uv convention; value forced by `manifest.json:requires-python = ">=3.14.2"` and HA Core `REQUIRED_PYTHON_VER = (3, 14, 2)`
**Source:** `01-RESEARCH.md` lines 1227–1233.

**Action:** Overwrite content `3.10` → `3.14` (one line, no trailing newline issues per uv convention).

---

### `README.md` (docs, Phase 1 placeholder)

**External analog:** HACS publish docs §"Repository setup" (minimal install instructions for HACS-discoverable repos)
**Source:** `01-RESEARCH.md` lines 1235–1264 — copy verbatim.

**Phase 1 scope:** project name + status banner ("Early development, installs but no entities yet") + HACS custom-repository install steps + minimum HA version + LICENSE link. **Out of scope:** ApexCharts schema, automation YAML, polling rationale (all Phase 7 per `<deferred>`).

**Open question OQ-2 (RESEARCH.md L1307-1310):** Skip the "My Home Assistant" deep-link in v0.0.1 (avoids confusion when integration is non-functional); add in Phase 7.

---

### `LICENSE` (docs, legal)

**External analog:** Standard MIT template (per A1 / OQ-1 — RESEARCH.md L1292, L1302-1306)
**Source:** Not in §Code Examples. Use canonical MIT template with `Copyright (c) 2026 Thomas Guyader`.

**Open question OQ-1:** Planner must confirm license choice with user OR default to MIT and proceed. RESEARCH.md recommends MIT.

---

## Shared Patterns

### SHA-Pinned GitHub Actions (D-23)

**Source:** `01-RESEARCH.md` §Pattern 3 (L395-407) and SHA list at L1444-1450.
**Apply to:** `lint.yml`, `validate.yml`, `test.yml`, `release.yml`.

**Verified SHAs (2026-05-03):**
| Action | SHA | Symbolic version |
|---|---|---|
| `actions/checkout` | `de0fac2e4500dabe0009e67214ff5f5447ce83dd` | v6.0.2 |
| `actions/setup-python` | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | v6.2.0 |
| `astral-sh/setup-uv` | `08807647e7069bb48b6ef5acd8ec9567f424441b` | v8.1.0 |
| `actions/setup-node` | `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | v6.4.0 |
| `home-assistant/actions/hassfest` | `f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b` | master |
| `hacs/action` | `dcb30e72781db3f207d5236b861172774ab0b485` | main |
| `softprops/action-gh-release` | `b4309332981a82ec1c5618f44dd2e27cc8bfbfda` | v3.0.0 |

**Format:** `uses: <owner>/<repo>@<40-char-sha>  # <symbolic version>` (comment is the only place the symbolic version lives — readable, audit-friendly).

---

### Workflow Permissions Pattern (Security)

**Source:** RESEARCH.md L1421-1423.
**Apply to:** all four workflow files.

**Rule:** `permissions: {}` at top level. Elevate **only** in `release.yml` to `permissions: contents: write` (needed by `softprops/action-gh-release` to attach the zip asset). All other jobs need zero token scopes.

---

### `requirements_test.txt`-Driven CI (D-25, NOT `uv sync`)

**Source:** RESEARCH.md §Pattern 4 (L409-434).
**Apply to:** all CI workflows that install Python deps (`lint.yml`, `test.yml`).

**Command:** `uv pip install --system -r requirements_test.txt`. Same path a contributor without `uv` would use (`pip install -r requirements_test.txt`). NOT `uv sync` (resolves dev-extras differently, breaks reproducibility).

---

### Banned-API Imports (D-30/D-31/D-32/D-33)

**Source:** RESEARCH.md `[tool.ruff.lint.flake8-tidy-imports.banned-api]` block (L842-846).
**Apply to:** `pyproject.toml` (single source of truth — ruff enforces across all `custom_components/` and `tests/`).

**Banned:**
- `async_timeout` → `asyncio.timeout()` (stdlib)
- `pytz` → `zoneinfo.ZoneInfo`
- `requests` → use `pronotepy` only (Phase 3+ via executor)

**Phase 1 has no Python runtime code that touches any of these — the bans exist preemptively to fail any future PR that violates them.**

---

### Domain Constant — Single Source of Truth (D-01)

**Source:** Anti-pattern guard at RESEARCH.md L440.
**Apply to:** every Python file in `custom_components/ha_pronote/`.

**Rule:** `DOMAIN = "ha_pronote"` declared exactly once in `const.py`. All other modules import it (`from .const import DOMAIN`). Never hardcode the literal string. Test `test_domain_constant_is_ha_pronote` enforces this at the module level (asserts `DOMAIN == "ha_pronote"` — guards manifest.domain ↔ folder ↔ const.py drift).

---

### `asyncio_mode = "auto"` (Pitfall 9)

**Source:** RESEARCH.md L503-512 (Pitfall 9, PHACC mandatory config).
**Apply to:** `pyproject.toml` `[tool.pytest.ini_options]`.

**Rule:** Set `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"`. Without `auto`, async tests need explicit `@pytest.mark.asyncio` decoration and PHACC's auto-fixtures break.

---

## No Analog Found

**None.** Every Phase 1 artifact has a high-quality external analog cited in RESEARCH.md §Code Examples. The greenfield nature of this phase means "no internal analog" is universal but "no external analog" is empty.

| File | Role | Reason |
|------|------|--------|
| (none) | — | All 22 files map to verified external sources. |

---

## Metadata

**Analog search scope:**
- Internal codebase: scanned via `ls -la /home/moi/projets/perso/pronote/` — confirmed greenfield (only `.planning/`, `.claude/`, `CLAUDE.md`, 8-line `.gitignore`, `.python-version=3.10`).
- External references: NOT re-fetched. All citations are pulled from `01-RESEARCH.md` §Code Examples (lines 577–1264) and §Sources (lines 1426–1463), which were verified live on 2026-05-03 by `gsd-phase-researcher`.

**Files scanned:** 5 in repo root + reading `01-CONTEXT.md` (167 lines) and targeted ranges of `01-RESEARCH.md` (1481 lines total, read 257–456 + 560–1264 + structural grep).

**Pattern extraction date:** 2026-05-03

**Quick-lookup convention for the planner:** when writing each PLAN.md task, cite the file with the format `"copy from 01-RESEARCH.md §Code Examples §<file_name> (lines X–Y)"` — the planner does not need to re-derive any pattern; RESEARCH.md ships verbatim file content.

## PATTERN MAPPING COMPLETE
