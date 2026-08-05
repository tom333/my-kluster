# Phase 1: Foundations & Skeleton - Research

**Researched:** 2026-05-03
**Domain:** HACS-distributed Home Assistant custom integration scaffolding (manifest, hacs.json, CI gates, pyproject, pre-commit, devcontainer, smoke test). Python 3.14 / HA 2026.4 era.
**Confidence:** HIGH (every locked decision in CONTEXT.md verified live against PyPI, HA Core master, hassfest source, and the canonical blueprints `ludeeus/integration_blueprint` and `jpawlowski/hacs.integration_blueprint`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Integration Identity
- **D-01:** `manifest.json:domain = "ha_pronote"` (underscore). FROZEN — changing after first real install breaks `.storage/<domain>.config_entries` and all entity_ids. Aligns with DIST-09 zip naming `ha_pronote.zip`, no collision with `delphiki/hass-pronote` (uses `pronote`).
- **D-02:** `unique_id` pattern stays `pronote_{child_identifier}_{sensor_kind}` per ENT-02 (REQUIREMENTS.md). Independent from `domain`.
- **D-03:** GitHub repo: `https://github.com/tom333/ha-pronote` (hyphen). Repo name uses hyphen, Python package uses underscore (`custom_components/ha_pronote/`).
- **D-04:** `manifest.json` codeowner = `["@tom333"]`.
- **D-05:** `manifest.json:documentation = "https://github.com/tom333/ha-pronote"`.
- **D-06:** `manifest.json:issue_tracker = "https://github.com/tom333/ha-pronote/issues"`.

#### Version Floor
- **D-07:** `pyproject.toml:requires-python = ">=3.14.2"`. Update `.python-version` from `3.10` to `3.14`.
- **D-08:** `hacs.json:homeassistant = "2026.4.0"` (HACS-side floor for users).
- **D-09:** Pin test `homeassistant` dep at `==2026.4.4` in `requirements_test.txt`.
- **D-10:** `[tool.ruff] target-version = "py314"`.
- **D-11:** Target HA 2026.4+ only; users on HA 2026.1–2026.2 (Py 3.13) and HA 2025.x (Py 3.12) cannot install — accepted tradeoff.

#### `manifest.json` Required Fields
- **D-12:** `iot_class: "cloud_polling"` (DIST-02)
- **D-13:** `quality_scale: "bronze"` (DIST-02)
- **D-14:** `requirements: ["pronotepy==2.14.6", "python-slugify==8.0.4"]`
- **D-15:** `integration_type: "hub"` — one entry per Pronote child account.
- **D-16:** `config_flow: true` — declare from Phase 1 even though no flow ships until Phase 3. *(If `hassfest` rejects placeholder, drop to `config_flow: false` in Phase 1 and flip in Phase 3 — planner decides at execution time.)*
- **D-17:** `version: "0.0.1"` — placeholder; release workflow rewrites it from tag.

#### Release Workflow
- **D-18:** Manual zip pattern (delphiki style) on `release: published`. NOT release-please.
- **D-19:** Conventional Commits encouraged but NOT enforced. Migration to `release-please` left as v2+ option.

#### CI Workflows
- **D-20:** `.github/workflows/lint.yml` runs ruff format --check, ruff check, pyright, codespell.
- **D-21:** `.github/workflows/validate.yml` runs `home-assistant/actions/hassfest@<sha> # master` + `hacs/action@<sha> # main` with `category: integration` and `ignore: brands`.
- **D-22:** `.github/workflows/test.yml` runs `uv pip install -r requirements_test.txt`, then `pytest -q`.
- **D-23:** GitHub Actions pinned by SHA, NOT by tag.
- **D-24:** Daily cron job against `pronotepy@main` (DIST-04) is OUT OF Phase 1 scope — Phase 7.

#### Tooling
- **D-25:** `uv` for deps + venv. `uv.lock` committed. CI uses `uv pip install -r requirements_test.txt`, NOT `uv sync`.
- **D-26:** `ruff` (lint+format) only. No `black`, no `flake8`, no `isort`. Match HA Core's `[tool.ruff]` block.
- **D-27:** `pyright` (NOT mypy) via `npx pyright`, mode: `basic`.
- **D-28:** `codespell` for spell-check.
- **D-29:** `pytest` ships from Phase 1 with `pytest-homeassistant-custom-component` + `asyncio_mode = "auto"`.

#### Out-of-Scope Anti-Patterns
- **D-30:** NO `async_timeout` package — `asyncio.timeout()` (stdlib).
- **D-31:** NO `pytz` — `zoneinfo.ZoneInfo("Pacific/Noumea")`.
- **D-32:** NO direct `requests` in our code.
- **D-33:** NO ENT modules from `pronotepy.ent`.
- **D-34:** NO hardcoded `katiramona.ac-noumea.nc` URL.
- **D-35:** NO monkey-patching of `pronotepy`.

### Claude's Discretion

- **C-01:** Test scaffolding scope — RECOMMENDED full `pytest-homeassistant-custom-component` setup so Phase 2 onboarding is friction-free.
- **C-02:** Dev container — RECOMMENDED ship a minimal `.devcontainer.json` based on `ludeeus/integration_blueprint`.
- **C-03:** Pre-commit hooks — RECOMMENDED ship `.pre-commit-config.yaml` running `ruff format` → `ruff check --fix` → `pyright` → `codespell`.

### Deferred Ideas (OUT OF SCOPE)

- Daily cron CI against `pronotepy@main` (DIST-04) — Phase 7
- Conventional Commits enforcement / migration to `release-please` — v2+
- Brand assets submission to `home-assistant/brands` — v2+
- HACS default repository submission — v2+
- HA Quality Scale Silver / Gold migration — v2
- README full content — Phase 7
- Translations (`strings.json`, `translations/{en,fr}.json`) — Phase 7
- Renovate/Dependabot config to bump SHA-pinned actions — v2+
- Compatibility with HA 2026.1–2026.2 / Python 3.13 — out of scope per D-11
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DIST-01** | Le repo est conforme HACS custom repository (`manifest.json` + `hacs.json` + `info.md`) | Standard Stack §`manifest.json` and §`hacs.json` provide the verbatim file contents. `info.md` requirement is from `hacs/action` `render_readme=true` flow — README.md is sufficient if `render_readme: true` is set. |
| **DIST-02** | `manifest.json` déclare `iot_class: cloud_polling`, `quality_scale: bronze`, dépendances Python explicites | Verified `cloud_polling` ∈ `SUPPORTED_IOT_CLASSES` and `bronze` ∈ `SUPPORTED_QUALITY_SCALES` in hassfest source [VERIFIED]. Code Examples §`manifest.json` shows the locked field set. |
| **DIST-03** | GitHub Actions CI exécute hassfest + hacs/action + ruff + pyright + pytest sur chaque PR | Code Examples §CI workflows provides 3 verbatim workflow YAMLs (lint.yml, validate.yml, test.yml) with current-SHA pins for every action. |
| **DIST-08** | Project tooling = `uv` (deps + venv) + `ruff` (lint+format) + `pyright` (typing) + pre-commit hooks | Code Examples §pyproject.toml + §.pre-commit-config.yaml provide the working tool versions. `uv` patterns from `jpawlowski/hacs.integration_blueprint` and HA Core master. |
</phase_requirements>

## Summary

Phase 1 is a **plumbing-only phase**: no business logic, no entities, no Pronote calls. Its job is to make every later phase impossible to break silently. The research target was therefore "what is the exact, current shape of a HACS custom integration in May 2026 that passes `hassfest` and `hacs/action` clean, locks the toolchain, and has a smoke test that future contributors cannot accidentally delete?"

Every locked decision in CONTEXT.md (D-01..D-35) was re-verified against live sources today. **All hold up.** The only nuance: `hassfest` enforces that `config_flow.py` exist as a file when `manifest.json` declares `config_flow: true` — verified by reading `script/hassfest/config_flow.py` from HA Core master ([VERIFIED]). It does **not** check the file's content beyond unique-id requirements for discovery flows. A minimal placeholder file with `class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN)` and a single `async_step_user` returning `self.async_abort(reason="not_implemented")` is sufficient — no need to drop to `config_flow: false`. This resolves the D-16 fork-in-the-road in favor of keeping `config_flow: true` from Phase 1.

The two reference implementations to mirror are **`ludeeus/integration_blueprint`** (canonical HA-team blueprint, `master` branch up to date with HA 2026.3.x — minimal devcontainer, classic structure) and **`jpawlowski/hacs.integration_blueprint`** (modern 2026 blueprint targeting HA 2026.4+, Python 3.14, `[tool.ruff]` block copied verbatim from HA Core, `pyright` via npm, SHA-pinned actions). For Phase 1 we copy `jpawlowski`'s pyproject ruff/pyright config and SHA pins, but use `ludeeus`'s simpler devcontainer (jpawlowski's is 200+ lines of complex bootstrap — overkill for v1).

**Primary recommendation:** Implement the file set in §Code Examples verbatim. They are the working artifacts the planner copies into tasks. Every value has been verified.

## Architectural Responsibility Map

Phase 1 is single-tier (build / packaging artifacts) — there is no runtime data flow yet. The "tiers" below map repo-layout responsibilities, not application architecture (which appears in Phase 3+).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HACS package recognition (custom repo install) | Repo root (`hacs.json`, `README.md`) | — | HACS scans repo root only; nothing under `custom_components/` is read by `hacs/action`. |
| HA integration discovery & metadata | `custom_components/ha_pronote/` (`manifest.json`) | — | hassfest reads `custom_components/<domain>/manifest.json`. `domain` value MUST equal directory name. |
| HA runtime entry point | `custom_components/ha_pronote/__init__.py` | — | HA imports this module on integration load. Phase 1 = no-op `async_setup` returning True. |
| Config flow registration (placeholder) | `custom_components/ha_pronote/config_flow.py` | `const.py` (DOMAIN) | Required when `config_flow: true` per hassfest source. Empty subclass + abort step is sufficient. |
| Python tooling config | Repo root (`pyproject.toml`, `.python-version`, `uv.lock`) | `package.json` (pyright via npm) | Standard `uv` + ruff layout matching HA Core. |
| Dev tooling config | Repo root (`.pre-commit-config.yaml`, `.devcontainer.json`) | `.gitignore` | Pre-commit and devcontainer are at repo root by convention. |
| CI gating | `.github/workflows/{lint,validate,test,release}.yml` | — | GitHub Actions standard location. |

## Standard Stack

### Core (declared in `manifest.json` `requirements` — installed by HA at runtime)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pronotepy` | `==2.14.6` | Pronote API client (sync) | [VERIFIED: PyPI] latest version, released 2026-03-22, requires `>=3.8`. Phase 1 declares it but doesn't import — Phase 2 starts using it. Pin EXACT (not `>=2.14,<3.0`) per CLAUDE.md guidance: Pronote breaks the API regularly, pronotepy ships compensating fixes; pinning prevents users from getting silent breaks on update. |
| `python-slugify` | `==8.0.4` | Slugify child names for entity IDs | [VERIFIED: PyPI] latest 8.0.4. [CITED: HA Core pyproject.toml] HA Core pins exact `8.0.4` — match it to avoid resolver thrash. Phase 1 declares; Phase 3+ uses for `unique_id` slugification. |

### Supporting — Test & Dev (declared in `requirements_test.txt` and `pyproject.toml`, NOT `manifest.json`)

| Library | Version (verified May 2026) | Purpose | Notes |
|---------|----------------------------|---------|-------|
| `homeassistant` | `==2026.4.4` | Real HA harness for tests | [VERIFIED: PyPI] latest stable in 2026.4 line, released 2026-04-24, `requires-python>=3.14.2`. Pin explicitly so CI is reproducible (PHACC pulls it transitively but version drifts daily). |
| `pytest-homeassistant-custom-component` | `==0.13.326` | `hass` fixture, `MockConfigEntry`, `enable_custom_integrations` | [VERIFIED: PyPI] latest 0.13.326, released 2026-04-30, tracks HA 2026.5.0b0; backwards-compatible with 2026.4.x. Auto-published daily — pin a specific patch for reproducibility. |
| `pytest` | `9.x` | Test runner | Pulled transitively by PHACC. **Don't override.** |
| `pytest-asyncio` | `1.3.x` | Async test support | Pulled transitively. **Configure `asyncio_mode = "auto"`** in `pyproject.toml` — required by PHACC. |
| `freezegun` | `1.5.x` | Mock `datetime.now()` | Pulled transitively. Critical for Phase 5 17h–20h tests; not used in Phase 1 directly. |
| `requests-mock` | `1.12.x` | Mock pronotepy at the `requests.Session` level | Pulled transitively. Used in Phase 2+. |
| `ruff` | `>=0.15.1` (project) | Lint + format (single tool) | [VERIFIED: PyPI] latest 0.15.12. Pin in `[tool.ruff] required-version = ">=0.15.1"` — matches HA Core master pyproject (line 71). Add to `requirements_test.txt` so CI installs it. |
| `pyright` | `1.1.409` (npm) | Type checking | [VERIFIED: npm] latest 1.1.409. Use `package.json` to pin (matches `jpawlowski` blueprint). Run via `npx pyright`. Mode: `basic` (NOT strict). |
| `codespell` | `==2.4.1` | Spell check | [CITED: HA Core .pre-commit-config.yaml] pins exact `v2.4.1`. Latest is 2.4.2 — match HA Core. |
| `pre-commit` | `>=4.x` | Git hooks framework | Standard. `prek` (Rust rewrite, `0.2.28` in HA Core requirements_test.txt) is a drop-in CLI replacement and is faster, but `pre-commit` is universal — RECOMMEND stick with `pre-commit` in v1 for contributor familiarity. Note that `prek` mention in CLAUDE.md was for HA Core's own test runner — HA Core's `.pre-commit-config.yaml` itself uses standard `pre-commit` syntax. |

### Tooling (CI / dev — outside Python ecosystem)

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `uv` | `>=0.9.3` | Package manager + venv | 10–100× faster than pip. Bootstrapped via `astral-sh/setup-uv@v8.1.0` in CI. |
| `node` | `>=22` | Run pyright via npm | Devcontainer feature provides it; CI uses `actions/setup-node@v6.4.0`. |
| `hassfest` (action) | `home-assistant/actions/hassfest@master` | Validate manifest.json schema | [VERIFIED: GitHub API 2026-05-03] current SHA: `f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b` (committed 2026-04-07). |
| `hacs/action` | `hacs/action@main` | Validate hacs.json + repo structure | [VERIFIED: GitHub API 2026-05-03] current SHA: `dcb30e72781db3f207d5236b861172774ab0b485` (committed 2026-01-26). |
| `actions/checkout` | `v6.0.2` | SHA `de0fac2e4500dabe0009e67214ff5f5447ce83dd` | [VERIFIED: GitHub API 2026-05-03]. |
| `actions/setup-python` | `v6.2.0` | SHA `a309ff8b426b58ec0e2a45f0f869d46889d02405` | [VERIFIED: GitHub API 2026-05-03]. |
| `astral-sh/setup-uv` | `v8.1.0` | SHA `08807647e7069bb48b6ef5acd8ec9567f424441b` | [VERIFIED: GitHub API 2026-05-03]. |
| `actions/setup-node` | `v6.4.0` | SHA `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | [VERIFIED: GitHub API 2026-05-03]. |
| `softprops/action-gh-release` | `v3.0.0` | SHA `b4309332981a82ec1c5618f44dd2e27cc8bfbfda` | [VERIFIED: GitHub API 2026-05-03], released 2026-04-12. Used by release.yml to attach `ha_pronote.zip` to GitHub release. |

### Alternatives Considered (and rejected per CONTEXT.md)

| Instead of | Could Use | Tradeoff (per CONTEXT.md decisions) |
|------------|-----------|-------------------------------------|
| Manual zip release.yml (D-18) | `release-please` (Google) | Rejected — adds config complexity unnecessary for v1. delphiki pattern is 30 lines, fits the project's release cadence. |
| `pyright` (D-27) | `mypy` | Rejected — `mypy` is fine and what HA Core uses, but `pyright` matches the modern blueprint (`jpawlowski`) and is faster on incremental checks. |
| Pin actions by tag | Pin by SHA (D-23) | Rejected — `hacs/action` last tag is 22.5.0 from 2022, `home-assistant/actions` last tag is 1.0.0 from 2020. SHA pinning is the community standard. |
| `pre-commit` | `prek` (HA Core CLI) | RECOMMEND `pre-commit` for v1 (contributor familiarity); migrate to `prek` v2+ if local hook speed becomes a friction point. |
| Python 3.13 floor | Python 3.14.2 floor (D-07) | Rejected — HA 2026.3+ enforces Py 3.14.2; supporting 3.13 means supporting only HA 2026.1–2026.2 which are EOL mid-2026. |
| Empty `__init__.py` | `__init__.py` with no-op `async_setup` | RECOMMEND minimal module-level docstring + zero `async_setup`/`async_setup_entry` — see "Critical landmine resolution" below. HA does not require `async_setup` to exist for an integration that has no `config_flow` *call sites yet* — but with `config_flow: true`, the *config_flow.py* file must exist (see landmine resolution). |

**Installation (one-time bootstrap):**

```bash
# Set Python version
echo "3.14" > .python-version

# Bootstrap venv via uv
uv venv .venv --python 3.14
source .venv/bin/activate

# Install test deps (pulls homeassistant 2026.4.x and ruff transitively)
uv pip install -r requirements_test.txt

# Install pyright via npm (matches jpawlowski blueprint)
npm install --save-dev pyright@1.1.409

# Install pre-commit hooks
uv pip install pre-commit
pre-commit install
```

**Version verification commands** (re-run before merging Phase 1):

```bash
# Confirm pronotepy and ha versions are still current
curl -sL "https://pypi.org/pypi/pronotepy/json" | jq -r '.info.version'
curl -sL "https://pypi.org/pypi/homeassistant/json" | jq -r '.info.version'
curl -sL "https://pypi.org/pypi/pytest-homeassistant-custom-component/json" | jq -r '.info.version'

# Confirm action SHAs are still current
curl -sL "https://api.github.com/repos/home-assistant/actions/branches/master" | jq -r '.commit.sha'
curl -sL "https://api.github.com/repos/hacs/action/branches/main" | jq -r '.commit.sha'
```

## Architecture Patterns

### System Architecture Diagram (Phase 1 — packaging only)

```
                            Contributor / CI
                                  │
                                  │  git clone + uv sync + uv run pytest
                                  ▼
            ┌─────────────────────────────────────────────────────┐
            │  Repo root                                          │
            │                                                     │
            │  ┌─────────────────────┐  ┌──────────────────────┐  │
            │  │  hacs.json          │  │  pyproject.toml +    │  │
            │  │  README.md          │  │  uv.lock + .python-  │  │
            │  │  (read by HACS      │  │  version             │  │
            │  │   action / GUI)     │  │  (read by uv + ruff  │  │
            │  └─────────────────────┘  │   + pyright)         │  │
            │                           └──────────────────────┘  │
            │                                                     │
            │  ┌──────────────────────────────────────────────┐   │
            │  │  custom_components/ha_pronote/               │   │
            │  │   ├── __init__.py        (HA entry point)    │   │
            │  │   ├── manifest.json      (read by hassfest)  │   │
            │  │   ├── const.py           (DOMAIN)            │   │
            │  │   └── config_flow.py     (placeholder, REQ)  │   │
            │  └──────────────────────────────────────────────┘   │
            │                                                     │
            │  ┌──────────────────────────────────────────────┐   │
            │  │  tests/                                      │   │
            │  │   ├── conftest.py        (PHACC fixtures)    │   │
            │  │   └── test_init.py       (smoke test)        │   │
            │  └──────────────────────────────────────────────┘   │
            │                                                     │
            │  ┌──────────────────────────────────────────────┐   │
            │  │  .github/workflows/                          │   │
            │  │   ├── lint.yml      → ruff/pyright/codespell │   │
            │  │   ├── validate.yml  → hassfest + hacs        │   │
            │  │   ├── test.yml      → pytest                 │   │
            │  │   └── release.yml   → zip + tag → asset      │   │
            │  └──────────────────────────────────────────────┘   │
            │                                                     │
            │  ┌──────────────────────────────────────────────┐   │
            │  │  .devcontainer.json + .pre-commit-config.yaml │  │
            │  │  + .gitignore + LICENSE + package.json        │  │
            │  └──────────────────────────────────────────────┘   │
            └─────────────────────────────────────────────────────┘
                                  │
                                  ▼
                       (Pull Request → CI gates)
                                  │
            ┌─────────────────────┼─────────────────────────┐
            ▼                     ▼                         ▼
     hassfest action          hacs/action             pytest + ruff
    (manifest.json valid?)  (hacs.json valid?)       + pyright + codespell
```

The diagram shows what each artifact gates and who reads it. There is no runtime data flow in Phase 1 — that arrives with Phase 3.

### Recommended Project Structure (Phase 1 final state)

```
ha-pronote/                                  # repo name (hyphen)
├── .devcontainer.json                       # minimal devcontainer (per C-02)
├── .github/
│   └── workflows/
│       ├── lint.yml                         # ruff + pyright + codespell
│       ├── validate.yml                     # hassfest + hacs/action
│       ├── test.yml                         # pytest
│       └── release.yml                      # release: published → zip → asset
├── .gitignore                               # extend existing — add .venv/, .ruff_cache/, etc.
├── .pre-commit-config.yaml                  # local hooks
├── .python-version                          # "3.14"
├── CLAUDE.md                                # already present, kept
├── LICENSE                                  # MIT (or per project preference — Phase 7 confirms)
├── README.md                                # minimal placeholder, full content Phase 7
├── custom_components/
│   └── ha_pronote/                          # = manifest.domain (underscore!)
│       ├── __init__.py                      # docstring + DOMAIN re-export only
│       ├── config_flow.py                   # placeholder: async_step_user → async_abort
│       ├── const.py                         # DOMAIN = "ha_pronote"
│       └── manifest.json                    # 11 keys, locked values
├── hacs.json                                # repo-root, read by hacs/action
├── package.json                             # pyright via devDependencies
├── pyproject.toml                           # uv project + ruff + pyright + pytest config
├── requirements_test.txt                    # PHACC pin + ruff pin
├── tests/
│   ├── __init__.py                          # empty (pkg marker)
│   ├── conftest.py                          # PHACC fixtures (enable_custom_integrations)
│   └── test_init.py                         # smoke test: import + setup
└── uv.lock                                  # committed for reproducibility
```

**Why this structure:**
- `custom_components/ha_pronote/` directory name MUST equal `manifest.domain` per hassfest [VERIFIED: hassfest manifest.py L362].
- `hacs.json` at repo root — `hacs/action` does not look inside `custom_components/`.
- `tests/` outside `custom_components/` — hassfest does not scan `tests/`.
- `pyproject.toml` at repo root, NOT inside `custom_components/` — Python tooling expectation.
- `.devcontainer.json` (single file at repo root) is the simplest devcontainer location and matches `ludeeus/integration_blueprint`. The alternative `.devcontainer/devcontainer.json` (folder) is also valid; we use the single-file form for minimalism.
- No `info.md` required when `hacs.json` has `render_readme: true` (HACS will display README.md instead).

### Pattern 1: Minimal placeholder ConfigFlow (Critical landmine resolution)

**What:** With `manifest.json:config_flow=true` declared from Phase 1, `hassfest` requires `config_flow.py` to exist. The minimal viable shape is a `ConfigFlow` subclass with `domain=DOMAIN` registration and a single `async_step_user` that aborts with a translated `not_implemented` reason.

**When to use:** Phase 1 only — Phase 3 replaces this with the real Config Flow implementing AUTH-01/AUTH-02.

**Why it works:**
- [VERIFIED: hassfest `script/hassfest/config_flow.py` lines 19-26] — hassfest checks ONLY that `config_flow.py` file exists when `manifest.config_flow == true`. It does NOT validate file content beyond unique-id checks for discovery flows (zeroconf/ssdp/dhcp/usb/bluetooth/homekit/mqtt/dhcp/hassio) — none of which apply to `ha_pronote`.
- [VERIFIED: HA Core `homeassistant/data_entry_flow.py` lines 564-574] — when user clicks "Add Integration", HA calls `async_step_user` via `getattr(flow, method)`. If the method is missing, it raises `UnknownStep` and the UI shows "Config flow could not be loaded" (broken UX). Therefore the placeholder MUST define `async_step_user`.
- `self.async_abort(reason="...")` with a translated string in `strings.json` produces a clean "Not yet implemented in this version" message.

**Decision:** Keep `config_flow: true` from Phase 1 (resolves D-16 fork). Do NOT drop to `config_flow: false`.

**Example (verbatim file content for Phase 1):**

```python
# custom_components/ha_pronote/config_flow.py
"""Config flow placeholder for HA-Pronote.

Phase 1 ships a placeholder so hassfest accepts ``config_flow: true`` in
manifest.json. The real flow lands in Phase 3 (AUTH-01, AUTH-02). Until then,
the user clicking "Add Integration" gets a clear "not yet implemented" message
rather than a broken UI.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Placeholder config flow — real implementation in Phase 3."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reject user-initiated setup until Phase 3 ships the real flow."""
        return self.async_abort(reason="not_implemented")
```

**Strings (Phase 1 minimal — full strings.json comes in Phase 7):**

```json
// custom_components/ha_pronote/strings.json   (optional in Phase 1; recommended)
{
  "config": {
    "abort": {
      "not_implemented": "HA-Pronote is in early development. Config flow ships in a future release."
    }
  }
}
```

If `strings.json` is omitted in Phase 1, HA falls back to the literal `not_implemented` reason key — ugly but functional. RECOMMEND ship the minimal `strings.json` above.

### Pattern 2: No-op `__init__.py` (when no platforms are forwarded)

**What:** Phase 1's `__init__.py` carries the module docstring and re-exports `DOMAIN`. It does NOT define `async_setup` or `async_setup_entry` because no entries can be created (config_flow always aborts).

**Why this is enough:** HA only calls `async_setup_entry` when there's an existing entry in `.storage/core.config_entries`. With the placeholder flow rejecting all entry creation, none can exist, so HA never attempts to load them.

**Example:**

```python
# custom_components/ha_pronote/__init__.py
"""HA-Pronote — Home Assistant integration for Pronote.

Phase 1: package skeleton only. Coordinator, sensors, calendar, and config flow
ship in subsequent phases (see ROADMAP.md). This file is intentionally minimal
to keep the integration loadable by HA / HACS without enabling any runtime
behavior.
"""

from .const import DOMAIN

__all__ = ["DOMAIN"]
```

```python
# custom_components/ha_pronote/const.py
"""Constants for HA-Pronote."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_pronote"
```

### Pattern 3: SHA-pinned GitHub Actions

**What:** Pin third-party actions to a 40-char commit SHA (with the symbolic version in a comment) instead of `@v3` or `@main`. This is HA-team convention (see `jpawlowski/hacs.integration_blueprint/.github/workflows/validate.yml` [VERIFIED]).

**When to use:** Always for any action that is not in the `actions/` org under GitHub itself. Even `actions/checkout` — supply chain attacks happen.

**Example:**

```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
- uses: home-assistant/actions/hassfest@f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b  # master
- uses: hacs/action@dcb30e72781db3f207d5236b861172774ab0b485  # main
```

### Pattern 4: `requirements_test.txt` for CI, NOT `uv sync`

**What:** Phase 1 ships **both** `pyproject.toml` (for `uv sync` local dev) AND `requirements_test.txt` (used by CI). Per D-25, CI uses `uv pip install -r requirements_test.txt` — same command path a contributor would use without `uv` (just plain `pip install -r ...`). Keeps CI predictable, avoids `uv sync` quirks (e.g., `uv` resolves dev-deps differently than HA Core's plain pip flow).

**Why:** HA's own ecosystem (test runner PHACC, hassfest, hacs/action) is built around `requirements_test.txt`. The blueprint `jpawlowski/hacs.integration_blueprint` ships both [VERIFIED: 2026-05-03 fetch].

**File contents (verbatim Phase 1):**

```
# requirements_test.txt
# Pinned for CI reproducibility. Bump in lockstep with HA releases.

# Real Home Assistant — pulls Py 3.14.2+ requirement transitively
homeassistant==2026.4.4

# Custom-component test harness (provides hass fixture, MockConfigEntry, etc.)
# Pulls pytest 9.x, pytest-asyncio 1.3.x, freezegun 1.5.x, requests-mock 1.12.x,
# syrupy 5.1.x, respx 0.23.x — all transitively.
pytest-homeassistant-custom-component==0.13.326

# Lint + format (pinned to match HA Core master pyproject.toml required-version)
ruff==0.15.1

# Spell check (matches HA Core master .pre-commit-config.yaml)
codespell==2.4.1
```

### Anti-Patterns to Avoid

- **`config_flow: false` in Phase 1 with the plan to flip it later.** Flipping `config_flow` after a public release is a breaking change for users — HA loads integrations differently based on this flag. Lock to `true` from Phase 1 with the placeholder pattern above.
- **`hass.data[DOMAIN]` legacy pattern in `__init__.py`.** Phase 1 has no runtime data; do NOT pre-populate `hass.data`. When Phase 3 needs runtime state, use `entry.runtime_data` (typed, automatic lifecycle) per ARCHITECTURE.md Pattern 6.
- **Hard-coding `"ha_pronote"` in multiple files.** Define `DOMAIN` once in `const.py`, import everywhere. Currently respected; flag for plan-checker.
- **Adding runtime deps to `manifest.json` "just in case".** `requirements: ["pronotepy==2.14.6", "python-slugify==8.0.4"]` is the locked set per D-14. Adding any other lib (`aiohttp`, `httpx`, `requests`) creates resolver conflicts because HA Core already ships them transitively.
- **Pinning `homeassistant==2026.5.0b0` in `requirements_test.txt` to match PHACC's HA target.** PHACC publishes against the latest HA beta; this would force CI onto an unstable HA build. Stick to the latest stable on the targeted floor (`2026.4.4`).
- **Using `uv sync` in CI.** `uv sync` resolves the full project dep graph including dev-extras; CI only needs the test requirements. Use `uv pip install -r requirements_test.txt`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Manifest schema validation | Custom JSON-schema check | `home-assistant/actions/hassfest@master` | hassfest is the canonical validator HA itself uses. It checks 30+ rules including domain-vs-dirname, IoT class enum, version PEP 440 conformance, codeowner format. Replicating any of this in our own CI = drift. |
| HACS metadata validation | Custom YAML lint | `hacs/action@main` (Docker action) | Validates `hacs.json` keys, repo structure, optional brand assets. Local equivalent is `act` if needed. |
| Lint + format toolchain | `black` + `flake8` + `isort` | `ruff` (single tool) | HA Core dropped this combo in 2024. ruff is 100× faster and the only ruff config is what `jpawlowski` ships (≈300 lines copied from HA Core master). |
| Type checking | `mypy --strict` from scratch | `pyright basic` via `npx` | mypy with HA-grade strictness fights HA Core's own typing decisions. `pyright basic` is what `jpawlowski` blueprint uses; matches modern HA convention. |
| Release zip pipeline | Custom `tar` + curl-to-GitHub | `softprops/action-gh-release@v3.0.0` + `yq` for version inject | delphiki's release.yml is 23 lines. Fully delegates artifact upload to a maintained action. |
| Dev container | Custom Dockerfile | `ludeeus`-style minimal devcontainer.json | Uses the official `mcr.microsoft.com/devcontainers/base:debian` image + dev container features. ~30 lines, no Dockerfile to maintain. |
| Pre-commit hooks | Per-tool wrapper scripts | `.pre-commit-config.yaml` referencing `astral-sh/ruff-pre-commit`, `codespell-project/codespell` | Direct copy from HA Core's `.pre-commit-config.yaml` [VERIFIED 2026-05-03]. |
| Snapshot testing harness | Custom diff JSON dumper | `syrupy` (transitively from PHACC) | Used by HA Core for entity state/attribute comparison. Phase 1 doesn't need it but the dep is already present. |
| Config Flow scaffolding | Hand-rolled FlowHandler | `homeassistant.config_entries.ConfigFlow` subclass | Provides session lifecycle, registration, error handling. Even the placeholder uses it (Pattern 1). |

**Key insight:** Phase 1 is almost entirely "use the existing tool" — every problem above has a maintained solution that is the convention. Hand-rolling any of them creates a maintenance burden that compounds across phases.

## Common Pitfalls

### Pitfall 1: `domain` mismatch between `manifest.json` and directory name

**What goes wrong:** `manifest.json:domain = "ha_pronote"` but folder is `custom_components/HaPronote/` or `custom_components/ha-pronote/` (hyphen). hassfest fails with `"Domain does not match dir name"`.

**Why it happens:** Devs confuse the GitHub repo name (`ha-pronote` with hyphen, D-03) with the Python package name (`ha_pronote` with underscore, D-01). Python identifiers can't contain hyphens; HA + HACS enforce underscore folder naming.

**How to avoid:** Lock the directory name `custom_components/ha_pronote/` from the very first commit. CI catches this via hassfest L362 [VERIFIED] — if the folder is wrong, validate.yml fails.

**Warning signs:** hassfest output `Domain does not match dir name`. Local pyright also flags `from . import xyz` failures.

### Pitfall 2: `hassfest` rejects integration because `config_flow.py` is missing

**What goes wrong:** `manifest.json:config_flow=true` but no `config_flow.py` file exists (or it's misnamed `configflow.py`, `config_flow/` directory without `__init__.py`, etc.). hassfest emits `"Config flows need to be defined in the file config_flow.py"`.

**Why it happens:** Devs think "no real flow yet" means "no file yet". hassfest source [VERIFIED L19-26] enforces file existence as a precondition for the rest of its config_flow validation.

**How to avoid:** Ship the placeholder file (Pattern 1) from the very first commit of Phase 1. CI validate.yml catches this.

**Warning signs:** Validate workflow fails with the literal hassfest error above. Local equivalent: `python3 -m script.hassfest --integration-path custom_components/ha_pronote`.

### Pitfall 3: `homeassistant` in `requirements_test.txt` is too old to satisfy `requires-python>=3.14.2`

**What goes wrong:** CI tries to install an older HA pin (e.g., `homeassistant==2026.2.x`) on Python 3.14, but HA's own `requires-python>=3.14.2` fails resolution if the runner doesn't have 3.14.2+. Error: `Requires-Python ... incompatible with the version of Python in this environment`.

**Why it happens:** Mismatch between `actions/setup-python` version arg and `homeassistant` pin. Or running locally on Python 3.13.

**How to avoid:** Lock the runner to `python-version: "3.14"` in every workflow. Lock the .python-version file. Lock `homeassistant==2026.4.4` (which itself requires `>=3.14.2`).

**Warning signs:** CI error `Could not find a version that satisfies the requirement homeassistant==X`. Or `pip install` succeeds but `python -c "import homeassistant"` fails at runtime.

### Pitfall 4: PHACC version drifts faster than HA stable

**What goes wrong:** `pytest-homeassistant-custom-component==0.13.326` was generated against `homeassistant==2026.5.0b0`. If our CI installs `homeassistant==2026.4.4` AND PHACC `0.13.326`, pip resolves PHACC's transitive `homeassistant` requirement (typically `>=2026.5.0b0`) and bumps HA to a beta — defeating reproducibility.

**Why it happens:** PHACC pins HA on the day it's published. Each PHACC release tracks one specific HA beta.

**How to avoid:** ALWAYS pin both `homeassistant==X` AND `pytest-homeassistant-custom-component==Y` together, and verify pip's resolver doesn't override `homeassistant`. Use `uv pip install --resolution=lowest-direct` if drift becomes an issue. For Phase 1, the pin combo `homeassistant==2026.4.4` + `pytest-homeassistant-custom-component==0.13.326` works because PHACC `0.13.326` is documented backwards-compatible to `2026.4.x` [CITED: PHACC README 2026-04-30].

**Warning signs:** `pip install` output shows `homeassistant 2026.5.0b0 was installed` despite your pin. Test runs hit unexpected API changes.

### Pitfall 5: `asyncio_mode = "auto"` missing in `pyproject.toml`

**What goes wrong:** Without `[tool.pytest.ini_options] asyncio_mode = "auto"`, every async test file requires `@pytest.mark.asyncio` decorators, OR PHACC's auto-fixture-injection breaks (the `hass` fixture is async).

**Why it happens:** Default `pytest-asyncio` mode is `"strict"` — requires explicit markers.

**How to avoid:** Set `asyncio_mode = "auto"` in `pyproject.toml` [tool.pytest.ini_options] from Phase 1. Verified pattern in `jpawlowski/hacs.integration_blueprint` [VERIFIED L42].

**Warning signs:** First async test fails with `RuntimeWarning: coroutine 'X' was never awaited`. Or `hass` fixture doesn't yield.

### Pitfall 6: Forgetting `enable_custom_integrations` fixture in `conftest.py`

**What goes wrong:** PHACC's `hass` fixture doesn't load custom integrations by default. Tests that try to set up `ha_pronote` get `Integration ha_pronote not found`.

**Why it happens:** PHACC mimics HA's strict separation between core and custom integrations. The `enable_custom_integrations` fixture flips the switch.

**How to avoid:** Auto-use the fixture in every test file via `conftest.py`:

```python
# tests/conftest.py
import pytest

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in all tests."""
    yield
```

**Warning signs:** Test logs show `homeassistant.loader.IntegrationNotFound: Integration 'ha_pronote' not found`.

### Pitfall 7: `hacs.json` missing `name` key

**What goes wrong:** `hacs/action` fails validation with `name is required`. The error is silent if the `comment: false` input is set.

**Why it happens:** [CITED: HACS publish docs https://www.hacs.xyz/docs/publish/start/] — `name` is the only mandatory key in `hacs.json`. All other keys are optional.

**How to avoid:** Always include `name`. See Code Examples §`hacs.json`.

**Warning signs:** HACS validation step in validate.yml fails. Locally: `act -j hacs` reproduces.

### Pitfall 8: SHA pin drifts (action upgraded silently via `@main`)

**What goes wrong:** Using `@main` instead of `@<sha>` means a malicious commit pushed to the upstream repo runs on every PR. Supply-chain attack vector.

**Why it happens:** Convenience. The `home-assistant/actions` README literally says `@master` in its example.

**How to avoid:** Always SHA-pin (D-23). Add Renovate/Dependabot in v2 to bump SHAs automatically (deferred per D-23 deferred items).

**Warning signs:** Hard to detect without monitoring. Mitigation: pin SHA + audit on monthly cadence.

### Pitfall 9: `pyright` can't find HA / pronotepy types

**What goes wrong:** `npx pyright` reports `Cannot find module 'homeassistant'` because the npm pyright doesn't know which Python venv to use.

**Why it happens:** Pyright auto-detects venvs in standard locations but a custom `uv venv .venv` may not be found.

**How to avoid:** Add `[tool.pyright]` section to `pyproject.toml` with `venvPath = "."` and `venv = ".venv"` (or `.local` and `ha-venv` like `jpawlowski` blueprint). Set `typeCheckingMode = "basic"` and disable noisy rules. See Code Examples §`pyproject.toml`.

**Warning signs:** Lint workflow reports thousands of `reportMissingImports` errors. Local `npx pyright` shows the same.

## Runtime State Inventory

> Phase 1 is a greenfield phase. There is no rename / refactor / migration in scope — the repo currently has only `.planning/`, `CLAUDE.md`, `.gitignore`, and `.python-version` (currently `3.10`, must be updated to `3.14` per D-07). The `.python-version` change is a single-line edit, not a "runtime state migration".

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by listing repo root (`ls -la`) and `.planning/` is meta-only, no datastores. | None |
| Live service config | None — verified by checking that no n8n / Datadog / Tailscale / Cloudflare configs exist anywhere in the repo. | None |
| OS-registered state | None — no Task Scheduler / launchd / pm2 / systemd registrations exist for this project (it's a Home Assistant integration that runs inside HA, not a standalone service). | None |
| Secrets / env vars | None at this phase — `.env` files do not yet exist. Phase 3 will introduce credentials handling but they live in HA's `.storage` (managed by HA), not this repo. | None |
| Build artifacts / installed packages | One — `.python-version` reads `3.10` (stale uv default leftover). Update to `3.14` per D-07. No `.venv/`, no `__pycache__/`, no `*.egg-info/` exist yet. | Single-line edit. Add `.venv/` and `__pycache__/` to `.gitignore` (already partially done). |

**Net:** Phase 1 has no runtime state migrations. The only carry-over edit is bumping `.python-version` from `3.10` → `3.14`.

## Code Examples

Verified patterns ready for the planner to copy verbatim. Every value here is locked per CONTEXT.md or verified against current sources today.

### `custom_components/ha_pronote/manifest.json`

```json
{
  "domain": "ha_pronote",
  "name": "HA-Pronote",
  "codeowners": ["@tom333"],
  "config_flow": true,
  "documentation": "https://github.com/tom333/ha-pronote",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/tom333/ha-pronote/issues",
  "quality_scale": "bronze",
  "requirements": ["pronotepy==2.14.6", "python-slugify==8.0.4"],
  "version": "0.0.1"
}
```

**Verification:** All 11 keys are accepted by `CUSTOM_INTEGRATION_MANIFEST_SCHEMA` [VERIFIED: hassfest manifest.py L204-337]. Values:
- `domain` ✓ matches dir name `ha_pronote/`
- `iot_class: "cloud_polling"` ✓ in `SUPPORTED_IOT_CLASSES` [VERIFIED L48-55]
- `quality_scale: "bronze"` ✓ in `SUPPORTED_QUALITY_SCALES` [VERIFIED L43-47] — `bronze` is below the silver threshold so the codeowner-required check doesn't apply
- `version: "0.0.1"` ✓ valid PEP 440 / SemVer per `verify_version` [VERIFIED L179-194]
- `requirements` format `pkg==version` per HA pip syntax — both packages exist on PyPI at the pinned versions [VERIFIED 2026-05-03]

### `hacs.json`

```json
{
  "name": "HA-Pronote",
  "homeassistant": "2026.4.0",
  "hacs": "2.0.5",
  "country": "FR",
  "render_readme": true,
  "zip_release": true,
  "filename": "ha_pronote.zip"
}
```

**Verification:** [CITED: HACS publish docs https://www.hacs.xyz/docs/publish/start/]:
- `name` ← required
- `homeassistant: "2026.4.0"` ← per D-08 (HA-side floor for users)
- `hacs: "2.0.5"` ← matches `jpawlowski/hacs.integration_blueprint/hacs.json` [VERIFIED 2026-05-03] (current HACS schema version)
- `country: "FR"` ← project is FR-NC focused
- `render_readme: true` ← HACS displays README.md as integration description (replaces need for `info.md`)
- `zip_release: true` + `filename: "ha_pronote.zip"` ← HACS will pull the zip artifact from each GitHub release instead of cloning the repo. Matches D-18 release pattern.

### `custom_components/ha_pronote/__init__.py`

```python
"""HA-Pronote — Home Assistant integration for Pronote.

Phase 1: package skeleton only. The coordinator, sensors, calendar entity, and
real Config Flow ship in subsequent phases (see ROADMAP.md). This file is
intentionally minimal so the integration can be loaded by HA / HACS without
exposing any runtime behavior yet.
"""

from .const import DOMAIN

__all__ = ["DOMAIN"]
```

### `custom_components/ha_pronote/const.py`

```python
"""Constants for HA-Pronote."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_pronote"
```

### `custom_components/ha_pronote/config_flow.py`

```python
"""Config flow placeholder for HA-Pronote.

Phase 1 ships a placeholder so hassfest accepts ``config_flow: true`` in
manifest.json. The real flow lands in Phase 3 (AUTH-01, AUTH-02). Until then,
the user clicking "Add Integration" gets a clean "not yet implemented" message
rather than a broken UI.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Placeholder config flow — real implementation in Phase 3."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reject user-initiated setup until Phase 3 ships the real flow."""
        return self.async_abort(reason="not_implemented")
```

### `custom_components/ha_pronote/strings.json` (minimal Phase 1 — full file in Phase 7)

```json
{
  "config": {
    "abort": {
      "not_implemented": "HA-Pronote is in early development. Account setup will be available in a future release."
    }
  }
}
```

### `pyproject.toml`

```toml
# Custom Component pyproject.toml — adapted from jpawlowski/hacs.integration_blueprint
# (which itself is based on HA Core master pyproject.toml).

[project]
name = "ha_pronote"
version = "0.0.0"              # Authoritative version is in custom_components/ha_pronote/manifest.json
requires-python = ">=3.14.2"

[tool.setuptools]
packages = ["custom_components.ha_pronote"]

# ---------------------------------------------------------------------------
# Pyright (type checking) — mode: basic, matches modern blueprint pattern
# ---------------------------------------------------------------------------
[tool.pyright]
include = ["custom_components/ha_pronote", "tests"]
exclude = [
    "**/.*",
    "**/__pycache__",
    "**/node_modules",
    "**/.venv",
]
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"
reportUnusedImport = "none"
reportUnusedVariable = "none"
reportUnusedCoroutine = "none"
reportMissingTypeStubs = "none"

# ---------------------------------------------------------------------------
# Pytest — asyncio_mode=auto required by pytest-homeassistant-custom-component
# ---------------------------------------------------------------------------
[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = [".git", "testing_config"]
log_format = "%(asctime)s.%(msecs)03d %(levelname)-8s %(threadName)s %(name)s:%(filename)s:%(lineno)s %(message)s"
log_date_format = "%Y-%m-%d %H:%M:%S"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-ra -q --strict-markers"
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (use hass fixture)",
]
filterwarnings = [
    "error",
    # Ignore pronotepy / autoslot deprecation warnings if any surface
    # "ignore::DeprecationWarning:autoslot",
]

[tool.coverage.run]
source = ["custom_components/ha_pronote"]
omit = ["tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]

# ---------------------------------------------------------------------------
# Ruff — lint + format. Block adapted from HA Core master pyproject.toml
# (https://github.com/home-assistant/core/blob/master/pyproject.toml).
# Customizations:
#   - target-version py314 (matches D-10)
#   - line-length 120 (matches jpawlowski blueprint)
# ---------------------------------------------------------------------------
[tool.ruff]
required-version = ">=0.15.1"
target-version = "py314"
line-length = 120

[tool.ruff.lint]
select = [
    "A001",   # Variable {name} is shadowing a Python builtin
    "ASYNC",  # flake8-async
    "B",      # flake8-bugbear (subset — see jpawlowski for full list)
    "BLE",    # blind-except
    "C",      # complexity
    "COM818", # Trailing comma on bare tuple prohibited
    "D",      # pydocstyle
    "DTZ003", # Use datetime.now(tz=) instead of datetime.utcnow()
    "DTZ004", # Use datetime.fromtimestamp(ts, tz=) instead of utcfromtimestamp
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "FLY",    # flynt
    "FURB",   # refurb
    "G",      # flake8-logging-format
    "I",      # isort
    "ICN001", # Import conventions
    "INP",    # flake8-no-pep420
    "ISC",    # flake8-implicit-str-concat
    "LOG",    # flake8-logging
    "N804",   # Class methods should have cls
    "N805",   # Methods should have self
    "PERF",   # Perflint
    "PGH",    # pygrep-hooks
    "PIE",    # flake8-pie
    "PL",     # pylint
    "PT",     # flake8-pytest-style
    "PTH",    # flake8-pathlib
    "PYI",    # flake8-pyi
    "RET",    # flake8-return
    "RSE",    # flake8-raise
    "RUF",    # ruff-specific
    "SIM",    # flake8-simplify
    "SLF",    # flake8-self
    "SLOT",   # flake8-slots
    "T20",    # flake8-print
    "TC",     # flake8-type-checking
    "TID",    # Tidy imports
    "TRY",    # tryceratops
    "UP",     # pyupgrade
    "W",      # pycodestyle warnings
]

ignore = [
    "ANN401",   # Dynamically typed expressions (typing.Any) are disallowed
    "ASYNC109", # Async def with timeout param — use asyncio.timeout()
    "D203",     # 1 blank line required before class docstring
    "D213",     # Multi-line docstring summary should start at second line
    "E501",     # line too long (handled by formatter)
    "PLR2004",  # Magic value used in comparison
    "TRY003",   # Avoid specifying long messages outside the exception class
    # Conflicts with ruff formatter:
    "W191", "E111", "E114", "E117", "D206", "D212", "D300",
    "Q", "COM812", "COM819", "ISC001",
]

[tool.ruff.lint.flake8-import-conventions.extend-aliases]
voluptuous = "vol"
"homeassistant.helpers.config_validation" = "cv"
"homeassistant.helpers.device_registry" = "dr"
"homeassistant.helpers.entity_registry" = "er"
"homeassistant.util.dt" = "dt_util"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"async_timeout".msg = "use asyncio.timeout instead"  # D-30
"pytz".msg = "use zoneinfo instead"                  # D-31
"requests".msg = "use pronotepy via executor (D-32)"

[tool.ruff.lint.isort]
force-sort-within-sections = true
known-first-party = ["custom_components", "homeassistant"]
combine-as-imports = true
split-on-trailing-comma = false

[tool.ruff.lint.per-file-ignores]
"tests/*" = [
    "S101",    # assert is fine in tests
    "PLR2004", # Magic values are fine in tests
    "D",       # Docstrings not required in tests
]

[tool.ruff.lint.mccabe]
max-complexity = 25

[tool.ruff.lint.pydocstyle]
convention = "google"
```

### `requirements_test.txt`

```
# Pinned for CI reproducibility. Bump in lockstep with HA releases.

# Real Home Assistant — pulls Py 3.14.2+ requirement transitively
homeassistant==2026.4.4

# Custom-component test harness (provides hass fixture, MockConfigEntry, etc.)
# Pulls pytest 9.x, pytest-asyncio 1.3.x, freezegun 1.5.x, requests-mock 1.12.x,
# syrupy 5.1.x, respx 0.23.x — all transitively.
pytest-homeassistant-custom-component==0.13.326

# Lint + format (matches [tool.ruff] required-version)
ruff==0.15.1

# Spell check (matches HA Core master .pre-commit-config.yaml)
codespell==2.4.1
```

### `package.json` (pyright via npm)

```json
{
  "name": "ha-pronote-tools",
  "version": "1.0.0",
  "description": "Development tools for HA-Pronote",
  "private": true,
  "devDependencies": {
    "pyright": "1.1.409"
  }
}
```

### `.pre-commit-config.yaml`

```yaml
# Hooks adapted from HA Core master .pre-commit-config.yaml.
# Locally runs the same checks as CI lint.yml so contributors fail fast.
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.1
    hooks:
      - id: ruff-format
        files: ^((custom_components|tests)/.+)?[^/]+\.(py|pyi)$
      - id: ruff-check
        args: [--fix]
        files: ^((custom_components|tests)/.+)?[^/]+\.(py|pyi)$
  - repo: https://github.com/codespell-project/codespell
    rev: v2.4.1
    hooks:
      - id: codespell
        args:
          - --ignore-words-list=hass
          - --quiet-level=2
        exclude_types: [csv, json, html]
        exclude: ^tests/fixtures/
  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: npx pyright
        language: node
        types: [python]
        pass_filenames: false
```

### `.devcontainer.json` (root, single-file form, per `ludeeus/integration_blueprint`)

```json
{
  "name": "HA-Pronote",
  "image": "mcr.microsoft.com/devcontainers/base:debian",
  "postCreateCommand": "uv venv .venv --python 3.14 && .venv/bin/uv pip install -r requirements_test.txt && npm install",
  "forwardPorts": [8123],
  "portsAttributes": {
    "8123": {
      "label": "Home Assistant",
      "onAutoForward": "notify"
    }
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "charliermarsh.ruff",
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-azuretools.vscode-docker",
        "github.vscode-pull-request-github",
        "ryanluker.vscode-coverage-gutters"
      ],
      "settings": {
        "files.eol": "\n",
        "editor.tabSize": 4,
        "editor.formatOnPaste": true,
        "editor.formatOnSave": true,
        "files.trimTrailingWhitespace": true,
        "python.analysis.typeCheckingMode": "basic",
        "python.defaultInterpreterPath": "/workspaces/ha-pronote/.venv/bin/python",
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },
  "remoteUser": "vscode",
  "features": {
    "ghcr.io/devcontainers/features/python:1": {
      "version": "3.14"
    },
    "ghcr.io/devcontainers/features/node:1": {
      "version": "22"
    }
  }
}
```

### `.github/workflows/lint.yml`

```yaml
name: Lint

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: {}

jobs:
  ruff:
    name: Ruff
    runs-on: ubuntu-latest
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
      - run: ruff format --check .
      - run: ruff check .

  pyright:
    name: Pyright
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "requirements*.txt"
      - uses: actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e  # v6.4.0
        with:
          node-version: "22"
      - run: uv pip install --system -r requirements_test.txt
      - run: npm install
      - run: npx pyright

  codespell:
    name: Codespell
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
        with:
          python-version: "3.14"
      - run: pip install codespell==2.4.1
      - run: codespell --ignore-words-list=hass --quiet-level=2 --skip="*.json,./.git,./node_modules"
```

### `.github/workflows/validate.yml`

```yaml
name: Validate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: {}

jobs:
  hassfest:
    name: Hassfest validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: home-assistant/actions/hassfest@f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b  # master

  hacs:
    name: HACS validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: hacs/action@dcb30e72781db3f207d5236b861172774ab0b485  # main
        with:
          category: integration
          ignore: brands
```

### `.github/workflows/test.yml`

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
    name: Pytest
    runs-on: ubuntu-latest
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
      - run: pytest -q
```

### `.github/workflows/release.yml`

```yaml
name: Release

on:
  release:
    types: [published]

permissions:
  contents: write

jobs:
  release:
    name: Build and attach release zip
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2

      - name: Inject release version into manifest.json
        run: |
          # yq is preinstalled on ubuntu-latest runners
          yq -i -o json '.version="${{ github.event.release.tag_name }}"' \
            "${{ github.workspace }}/custom_components/ha_pronote/manifest.json"

      - name: Build ha_pronote.zip
        run: |
          cd "${{ github.workspace }}/custom_components/ha_pronote"
          zip ha_pronote.zip -r ./

      - name: Upload zip to release
        uses: softprops/action-gh-release@b4309332981a82ec1c5618f44dd2e27cc8bfbfda  # v3.0.0
        with:
          files: ${{ github.workspace }}/custom_components/ha_pronote/ha_pronote.zip
```

### `tests/__init__.py`

```python
"""Tests for HA-Pronote."""
```

### `tests/conftest.py`

```python
"""Shared fixtures for HA-Pronote tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests.

    Without this, the ``hass`` fixture refuses to load anything from
    ``custom_components/`` and our integration would be invisible.
    """
    yield
```

### `tests/test_init.py` (smoke test)

```python
"""Smoke tests for the HA-Pronote package skeleton."""

from __future__ import annotations

from custom_components.ha_pronote import DOMAIN
from custom_components.ha_pronote.const import DOMAIN as DOMAIN_CONST


def test_domain_constant_is_ha_pronote() -> None:
    """The package's DOMAIN constant must equal the manifest.domain value.

    If this assertion fails, hassfest will reject the integration because
    ``manifest.json:domain`` no longer matches the directory name.
    """
    assert DOMAIN == "ha_pronote"
    assert DOMAIN_CONST == DOMAIN


async def test_config_flow_placeholder_aborts(hass) -> None:
    """The Phase 1 placeholder Config Flow must abort cleanly.

    Once Phase 3 ships the real flow, this test will need to be replaced.
    Until then, it documents the contract: clicking "Add Integration" returns
    an abort, never a stack trace.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_implemented"
```

### `.gitignore` (extension of existing)

```
# Existing entries (already in .gitignore):
# __pycache__/
# *.py[oc]
# build/
# dist/
# wheels/
# *.egg-info
# .venv

# Add for Phase 1:
.ruff_cache/
.pytest_cache/
.coverage
htmlcov/
.local/
node_modules/
*.zip
```

### `.python-version`

```
3.14
```

(Replaces existing `3.10`.)

### `README.md` (Phase 1 minimal — full version in Phase 7)

```markdown
# HA-Pronote

Home Assistant custom integration for Pronote (French school management system).

> **Status:** Early development. The integration installs but does not yet
> create entities. See [ROADMAP.md](.planning/ROADMAP.md) for the planned
> feature timeline.

## Installation (HACS custom repository)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** → top-right menu → **Custom repositories**.
3. Add `https://github.com/tom333/ha-pronote` with category **Integration**.
4. Install **HA-Pronote** from the HACS catalogue.
5. Restart Home Assistant.

Account configuration via the UI ships in a future release.

## Requirements

- Home Assistant 2026.4.0 or later
- Python 3.14.2 (managed by HA — not user-facing)

## License

See [LICENSE](LICENSE).
```

## State of the Art

| Old Approach | Current Approach (May 2026) | When Changed | Impact |
|--------------|------------------------------|--------------|--------|
| `black` + `flake8` + `isort` | `ruff` (single tool, format + lint) | HA Core 2024.x | Three-tool toolchain → one. ~10× faster. Drop all three configs and ship `[tool.ruff]`. |
| `mypy --strict` | `pyright basic` (or HA Core's `mypy` with per-file ignores) | jpawlowski blueprint 2026 | `pyright` runs from npm, faster incremental, used by VSCode by default. HA Core itself still uses mypy with extensive overrides. |
| `pip install` in CI | `uv pip install` | HA Core 2024-2025 | 10–100× faster. Works with same `requirements*.txt` files, no migration cost. |
| `release-please` for HACS releases | Manual zip on `release: published` (delphiki style) | Community standard since 2024 | Simpler config (~20 lines vs 200+). Conventional Commits become opt-in. |
| Tag-pinned actions (`@v3`) | SHA-pinned actions (`@<40-char>`) | Security advisory cycle 2023-2024 | Defends against repo-pushed malicious commits. Pair with Renovate to bump SHAs (deferred to v2). |
| `hass.data[DOMAIN][entry_id]` | `entry.runtime_data` (typed) | HA 2024.x | Type-safe, automatic lifecycle. Phase 1 doesn't use either yet but must NOT pre-populate `hass.data`. |
| `pytz` | `zoneinfo.ZoneInfo` | Banned-API in HA Core ruff config since 2023 | Stdlib, faster, non-blocking. Phase 1 doesn't touch timezones but must not import `pytz` ever. |
| `async_timeout` package | `asyncio.timeout()` (stdlib, Py 3.11+) | Banned-API in HA Core ruff config since 2023 | Same purpose, stdlib. |
| `requirements.txt` for runtime | `manifest.json:requirements` | HA platform decision (always) | Custom integrations declare runtime deps in manifest.json — HA installs them. `requirements.txt` is dev convenience only. |
| `.devcontainer/devcontainer.json` (folder) | `.devcontainer.json` (single file) | Dev Containers spec — both valid | Single-file form is simpler for projects that don't need multi-stage Dockerfiles. |
| `info.md` for HACS rich descriptions | `README.md` + `hacs.json:render_readme=true` | HACS 2.x | Removes the duplicate-content maintenance burden. |

**Deprecated / outdated patterns to avoid:**
- `async_add_job` → replaced by `async_add_executor_job` since 2022 (D-32-adjacent — Phase 3 concern)
- Pinning `homeassistant` floor in `requirements_test.txt` to a version older than what HA Core master uses → CI install will fail Py 3.14 resolution

## Assumptions Log

> Every claim in this research was verified or cited against live sources today (2026-05-03). The few items below are flagged for explicit user confirmation because they are project-style choices, not technical facts.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | LICENSE = MIT (per common HA custom_component convention) — actual choice not stated in CONTEXT.md | Recommended Project Structure / README.md | Low — wrong license is fixable any time before public release. RECOMMEND ask user to confirm before Phase 1 commit, default MIT. |
| A2 | `country: "FR"` in `hacs.json` — project is FR-NC focused but HACS uses ISO country codes; `FR` covers metropolitan France + DOM-TOM. No `NC` ISO code exists in HACS schema. | Code Examples §`hacs.json` | Low — `country` is informational only (used for HACS catalogue filtering). |
| A3 | `line-length = 120` in `[tool.ruff]` matches `jpawlowski` blueprint, but HA Core master itself uses 88 (formatter default). The choice is style. | Code Examples §`pyproject.toml` | Trivial — affects only auto-formatting output. |
| A4 | Codespell ignore list `--ignore-words-list=hass` is the bare minimum from HA Core; FR docstrings will produce more false positives once content is written. Acceptable for Phase 1 (minimal docstrings). | Code Examples §`.pre-commit-config.yaml` | Low — Phase 1 has minimal text; expand the ignore list in Phase 7 once translations land. |
| A5 | Devcontainer ships `node:22` feature for `npx pyright`. Alternative: install pyright via apt-packages feature, no node. Choosing node form because it matches `package.json` lockfile flow. | Code Examples §`.devcontainer.json` | Low — both work; node form is more standard. |

**No critical assumptions.** All structural and version-related claims are [VERIFIED] or [CITED]. The five items above are project-style choices that can be deferred to user confirmation in `/gsd-discuss-phase` follow-up if desired.

## Open Questions (RESOLVED)

1. **Should `LICENSE` ship in Phase 1 or be deferred?**
   - What we know: HA / HACS does not require a LICENSE file at the repo root for `hacs/action` to pass. PROJECT.md does not specify a license. CLAUDE.md does not specify.
   - What's unclear: User's preferred license.
   - Recommendation: Ship `LICENSE` (MIT default) in Phase 1 because the placeholder README.md links to it. Trivial to change later; opening the repo without a LICENSE creates a small legal ambiguity for early contributors.
   - **RESOLVED:** Ship MIT `LICENSE` in Phase 1 with copyright `2026 Thomas Guyader`. Implemented in plan `01-01` (Repo bootstrap), Task 3.

2. **Should the Phase 1 README.md include a HACS install button (one-click "Add custom repository")?**
   - What we know: HACS supports a "My Home Assistant" deep-link that pre-fills the custom-repository dialog. Pattern: `https://my.home-assistant.io/redirect/hacs_repository/?owner=tom333&repository=ha-pronote&category=integration`.
   - What's unclear: Whether the user wants this UX in v0.0.1 (pre-functional) or only at v0.1.0 release.
   - Recommendation: SKIP the deep-link in Phase 1 (avoids user confusion when they install something that doesn't yet do anything). Add in Phase 7 with the full README.
   - **RESOLVED:** Defer to Phase 7 (DIST-07 full README). Phase 1 ships a minimal placeholder README with no install button. Implemented in plan `01-01`, Task 3.

3. **Branch protection: enforce on `main` from Phase 1?**
   - What we know: GitHub branch protection isn't an artifact in the repo (it's a GitHub setting). It's not part of the Phase 1 scope per CONTEXT.md.
   - What's unclear: Whether the user wants the planner to include "configure branch protection" as a manual task in PLAN.md.
   - Recommendation: Yes, include as a manual setup step at the end of Phase 1's plan. Without it, the CI gates can be bypassed by direct push.
   - **RESOLVED:** Include as an explicit `checkpoint:user-action` task in plan `01-04` (CI workflows) tail and document under Manual-Only Verifications in `01-VALIDATION.md`. Without it, DIST-03's "blocks merge" success criterion is unenforced.

4. **Will hassfest 2026.4.x reject `quality_scale: bronze` if there are no entities yet?**
   - What we know: hassfest manifest.py [VERIFIED L390-401] only enforces additional rules for `silver` and above (codeowner check). `bronze` passes the base manifest schema.
   - What's unclear: Whether the underlying `quality_scale` rule files (`script/hassfest/quality_scale.py` — not inspected this session) impose entity-existence checks.
   - Recommendation: Phase 1 plan MUST include a CI smoke run on a feature branch before declaring Phase 1 complete. If hassfest emits a `bronze`-related warning we didn't anticipate, the planner has the option to drop `quality_scale` from manifest.json (it's optional) and re-add in Phase 7 alongside the proper Bronze checklist. Document this fork as a Phase 1 contingency.
   - **RESOLVED:** Treat as a contingency — keep `quality_scale: bronze` in Phase 1 manifest. If hassfest surfaces an entity-existence rule on the feature-branch CI smoke run, plan `01-02` permits dropping the field and re-adding in Phase 7 alongside the Bronze checklist. Documented in plan `01-02` task notes.

## Environment Availability

> Phase 1 produces files; the actual install environment is the contributor's machine + GitHub Actions runners. The audit below covers tools needed to develop Phase 1 locally.

| Dependency | Required By | Available (current dev box) | Version | Fallback |
|------------|-------------|------|---------|----------|
| `uv` | Bootstrap venv, install requirements_test | ✓ | `>=0.9.3` (verified at /home/moi/.local/bin/uv) | `pip install -r requirements_test.txt` (slower but works) |
| Python 3.14.2+ | HA test runtime | ✓ on devcontainer/CI | n/a | None — hard requirement, no fallback. Devcontainer feature ensures this on contributor side. |
| `node >=22` | `npx pyright` | ✓ on devcontainer | n/a | Use `pip install pyright` (Python wheel) instead. Ships an older pyright but functional. |
| `git` | Source control | ✓ | n/a | None |
| `curl` / `jq` | Optional, for verification | ✓ | n/a | Use `python3 -c "import json; ..."` |
| `docker` | Optional, for `hacs/action` local replay via `act` | likely ✓ | n/a | Skip local replay; rely on CI run on PR. |
| GitHub Actions runners | CI gates | ✓ (managed by GitHub) | `ubuntu-latest` | None — CI is GitHub's responsibility. |

**Missing dependencies with no fallback:** None — Phase 1 has no hard external blockers.

**Missing dependencies with fallback:** None at the time of this research.

**Net:** Phase 1 can be executed on any machine with `uv` + `node` + `git` + a network connection. The devcontainer (per C-02) makes this reproducible for any contributor.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` 9.x (transitive via `pytest-homeassistant-custom-component==0.13.326`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (no `pytest.ini` — `pyproject.toml` is canonical for new projects) |
| Quick run command | `uv run pytest -q` (from repo root, after `uv pip install -r requirements_test.txt`) |
| Full suite command | `uv run pytest -v --cov=custom_components.ha_pronote --cov-report=term-missing` |
| Phase gate command | `uv run pytest -q && uv run ruff format --check . && uv run ruff check . && npx pyright && uv run codespell` (mirrors CI lint.yml + test.yml) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | HACS recognizes the repo as a custom integration (manifest + hacs.json valid) | smoke (CI) | `validate.yml` runs `hacs/action@<sha>` and `home-assistant/actions/hassfest@<sha>` on every PR | ❌ Wave 0 — workflow files do not exist yet |
| DIST-02 | manifest.json declares `iot_class: cloud_polling`, `quality_scale: bronze`, runtime requirements pinned | unit | `pytest tests/test_manifest.py -x` (assert manifest.json fields) | ❌ Wave 0 — `tests/test_manifest.py` to be created |
| DIST-03 | CI gates run on every PR and block merge | integration (CI) | observable: PR check status — branch protection rule blocks merge if any of `lint.yml`, `validate.yml`, `test.yml` fail | ❌ Wave 0 — branch protection is a manual GitHub setup step |
| DIST-08 | Local dev workflow: `uv pip install -r requirements_test.txt && uv run pytest` green | smoke (local + CI) | `pytest -q` exits 0 | ❌ Wave 0 — `tests/test_init.py` to be created |
| Phase contract: smoke test asserts `DOMAIN == "ha_pronote"` | guards manifest.domain ↔ folder match | unit | `pytest tests/test_init.py::test_domain_constant_is_ha_pronote -x` | ❌ Wave 0 |
| Phase contract: placeholder ConfigFlow aborts cleanly | guards "Add Integration" button doesn't crash HA | integration (uses `hass` fixture) | `pytest tests/test_init.py::test_config_flow_placeholder_aborts -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` (the fast-feedback loop, <10s on Phase 1's tiny test set)
- **Per wave merge:** Full suite + pyright: `uv run pytest -q && npx pyright && uv run ruff format --check . && uv run ruff check . && uv run codespell`
- **Phase gate:** Full suite green AND CI green on a PR branch (`hassfest` + `hacs/action` + `lint.yml` + `test.yml` all green) before `/gsd-verify-work`. Specifically, the planner MUST require at least one PR merged through CI before declaring Phase 1 done — without this, success criterion #2 (CI gates work) is unverified.

### Wave 0 Gaps

> Phase 1 is greenfield. Almost everything is a Wave 0 gap. The list below is exhaustive.

- [ ] `tests/__init__.py` — package marker, empty file
- [ ] `tests/conftest.py` — `auto_enable_custom_integrations` autouse fixture
- [ ] `tests/test_init.py` — covers DIST-01, DIST-08 + ConfigFlow placeholder contract
- [ ] `tests/test_manifest.py` (RECOMMEND, not strictly required for DIST-02) — asserts `manifest.json` is valid JSON and contains the expected key set. Catches accidental schema drift between hassfest releases.
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` config block
- [ ] `requirements_test.txt` — pinned test deps
- [ ] `.github/workflows/test.yml` — CI test run
- [ ] `.github/workflows/lint.yml` — CI lint run
- [ ] `.github/workflows/validate.yml` — CI hassfest + hacs/action

## Security Domain

`security_enforcement: true` per `.planning/config.json`. ASVS Level 1.

Phase 1 ships **no runtime code, no credentials, no entry creation, no network calls.** The only attack surface is the Python package itself and the CI pipeline. Concrete security concerns reduce to: (a) supply-chain integrity of the dependencies we declare; (b) supply-chain integrity of the GitHub Actions we use; (c) ensuring secrets aren't accidentally committed (LICENSE / no env files / gitignore covers this).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Standard HA / HACS layout — covered by hassfest validation. |
| V2 Authentication | no | No authentication code in Phase 1. Phase 3 owns AUTH-01..AUTH-07. |
| V3 Session Management | no | No sessions in Phase 1. |
| V4 Access Control | no | No runtime access control in Phase 1. |
| V5 Input Validation | partial | The placeholder ConfigFlow accepts no input — it aborts immediately. No validation needed. The full ConfigFlow in Phase 3 will use `voluptuous.Url()` validators. |
| V6 Cryptography | no | No crypto in Phase 1. pronotepy handles its own AES (Phase 2+). |
| V10 Communications | no | No network calls in Phase 1. |
| V12 Files & Resources | partial | `.gitignore` must exclude `.venv/`, `__pycache__/`, `*.zip`, `node_modules/`. Mitigated by Code Examples §`.gitignore`. |
| V13 API & Web Service | no | No public API surface in Phase 1. |
| V14 Configuration | yes | All deps SHA-pinned (D-23) or version-pinned (D-14). Build reproducibility. |

### Known Threat Patterns for {Phase 1 stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious commit pushed to `home-assistant/actions` master / `hacs/action` main | Tampering | SHA pin (D-23) — verified SHAs are listed under Standard Stack §Tooling. Rotate via Renovate (deferred v2). |
| Compromised `pronotepy` release on PyPI | Tampering | Exact version pin `pronotepy==2.14.6` (D-14). PyPI `2.14.6` artifacts have known sha256 hashes — could pin via `--require-hashes` in `requirements_test.txt` for stronger defense (RECOMMEND for Phase 7 v0.1.0 release; defer in Phase 1 to keep dev velocity). |
| Compromised `pytest-homeassistant-custom-component` release | Tampering | Exact version pin `==0.13.326`. Same hash-pinning consideration. |
| Secret leakage via .env or .storage in git | Information Disclosure | Phase 1 has no secrets. `.gitignore` (Code Examples) excludes `.venv/` and common build dirs. Phase 3 will add credentials handling; that phase owns the diagnostics redaction (per PITFALLS Pitfall 6). |
| Workflow injection via PR title / branch name in workflow inputs | Tampering / Elevation of Privilege | None of our workflows interpolate untrusted PR metadata into shell commands. Use of `${{ github.event.release.tag_name }}` in release.yml is from a release event (only repo maintainers can trigger) — safe. |
| Cache poisoning of `actions/setup-uv` cache | Tampering | Cache keyed on `requirements*.txt` hash — change in deps invalidates cache. Standard pattern. |

### Phase-1-specific security tasks (for the planner)

1. Verify `.gitignore` covers `.venv/`, `__pycache__/`, `*.egg-info/`, `node_modules/`, `*.zip`, `.coverage`, `htmlcov/`, `.ruff_cache/`, `.pytest_cache/`, `.local/`.
2. Verify the release.yml does NOT echo `${{ secrets.* }}` or sensitive values to logs.
3. Verify all workflows declare `permissions: {}` at job-level by default and only elevate (`contents: write`) where needed (only release.yml).
4. Document in CLAUDE.md / README.md that future Phase 3 credential handling MUST follow the diagnostics redaction pattern documented in PITFALLS.md Pitfall 6.

No high-severity findings for Phase 1. Security gate: pass.

## Sources

### Primary (HIGH confidence — verified live 2026-05-03)

- [PyPI: pronotepy](https://pypi.org/pypi/pronotepy/json) — `2.14.6`, released 2026-03-22, `requires-python>=3.8`. [VERIFIED]
- [PyPI: homeassistant](https://pypi.org/pypi/homeassistant/json) — `2026.4.4`, released 2026-04-24, `requires-python>=3.14.2`. [VERIFIED]
- [PyPI: pytest-homeassistant-custom-component](https://pypi.org/pypi/pytest-homeassistant-custom-component/json) — `0.13.326`, released 2026-04-30. [VERIFIED]
- [PyPI: python-slugify](https://pypi.org/pypi/python-slugify/json) — `8.0.4`. [VERIFIED]
- [PyPI: ruff](https://pypi.org/pypi/ruff/json) — `0.15.12` latest; pin `0.15.1` matches HA Core. [VERIFIED]
- [PyPI: codespell](https://pypi.org/pypi/codespell/json) — `2.4.2` latest; pin `2.4.1` matches HA Core. [VERIFIED]
- [npm: pyright](https://registry.npmjs.org/pyright/latest) — `1.1.409`. [VERIFIED]
- [HA Core master `homeassistant/const.py`](https://raw.githubusercontent.com/home-assistant/core/master/homeassistant/const.py) — `REQUIRED_PYTHON_VER = (3, 14, 2)`. [VERIFIED]
- [HA Core master `pyproject.toml`](https://raw.githubusercontent.com/home-assistant/core/master/pyproject.toml) — `requires-python = ">=3.14.2"`, `[tool.ruff] required-version = ">=0.15.1"`. [VERIFIED]
- [HA Core master `.pre-commit-config.yaml`](https://raw.githubusercontent.com/home-assistant/core/master/.pre-commit-config.yaml) — `ruff-pre-commit v0.15.1`, `codespell v2.4.1`. [VERIFIED]
- [HA Core master `script/hassfest/manifest.py`](https://raw.githubusercontent.com/home-assistant/core/master/script/hassfest/manifest.py) — `INTEGRATION_MANIFEST_SCHEMA`, `CUSTOM_INTEGRATION_MANIFEST_SCHEMA`, `SUPPORTED_IOT_CLASSES`, `SUPPORTED_QUALITY_SCALES`, `validate_version`. [VERIFIED]
- [HA Core master `script/hassfest/config_flow.py`](https://raw.githubusercontent.com/home-assistant/core/master/script/hassfest/config_flow.py) — `_validate_integration` requires `config_flow.py` to exist when `manifest.config_flow == true`. [VERIFIED] — **resolves D-16 critical landmine**
- [HA Core master `homeassistant/data_entry_flow.py`](https://raw.githubusercontent.com/home-assistant/core/master/homeassistant/data_entry_flow.py) — `_raise_if_step_does_not_exist` raises `UnknownStep` if `async_step_user` missing. [VERIFIED]
- [HA Core master `homeassistant/config_entries.py`](https://raw.githubusercontent.com/home-assistant/core/master/homeassistant/config_entries.py) — `class ConfigFlow(ConfigEntryBaseFlow)` registration via `__init_subclass__(domain=...)`. [VERIFIED]
- GitHub API — `home-assistant/actions/master` SHA: `f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b` (2026-04-07). [VERIFIED]
- GitHub API — `hacs/action/main` SHA: `dcb30e72781db3f207d5236b861172774ab0b485` (2026-01-26). [VERIFIED]
- GitHub API — `actions/checkout/v6.0.2` SHA: `de0fac2e4500dabe0009e67214ff5f5447ce83dd`. [VERIFIED]
- GitHub API — `actions/setup-python/v6.2.0` SHA: `a309ff8b426b58ec0e2a45f0f869d46889d02405`. [VERIFIED]
- GitHub API — `astral-sh/setup-uv/v8.1.0` SHA: `08807647e7069bb48b6ef5acd8ec9567f424441b`. [VERIFIED]
- GitHub API — `actions/setup-node/v6.4.0` SHA: `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e`. [VERIFIED]
- GitHub API — `softprops/action-gh-release/v3.0.0` SHA: `b4309332981a82ec1c5618f44dd2e27cc8bfbfda`. [VERIFIED]
- [GitHub: ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint) — canonical HA blueprint. Inspected: `manifest.json`, `hacs.json`, `requirements.txt`, `.ruff.toml`, `.devcontainer.json`, `__init__.py`, `config_flow.py`, `scripts/setup`. [VERIFIED]
- [GitHub: jpawlowski/hacs.integration_blueprint](https://github.com/jpawlowski/hacs.integration_blueprint) — modern 2026 blueprint. Inspected: `pyproject.toml`, `manifest.json`, `hacs.json`, `requirements_test.txt`, `requirements_dev.txt`, `package.json`, `.github/workflows/{lint,validate}.yml`. [VERIFIED]
- [GitHub: delphiki/hass-pronote](https://github.com/delphiki/hass-pronote) — production reference. Inspected: `manifest.json`, `hacs.json`, `.github/workflows/{hacs,release}.yml`, `config_flow.py`. [VERIFIED]
- [HACS publish docs](https://www.hacs.xyz/docs/publish/start/) — `hacs.json` schema. [CITED]
- [HACS publish/integration docs](https://www.hacs.xyz/docs/publish/integration/) — manifest.json minimum keys. [CITED]
- [HA developer docs — integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/) — required keys for custom integrations. [CITED]
- [HA developer docs — Config flow handler](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) — flow lifecycle. [CITED]

### Secondary (HIGH confidence — corroborated via at least 2 sources)

- `pytest-homeassistant-custom-component` requires `asyncio_mode = "auto"` — confirmed in PHACC README + jpawlowski blueprint pyproject.toml. [VERIFIED via 2 sources]
- HACS `name` is the only mandatory `hacs.json` key — confirmed in HACS publish docs + jpawlowski/hacs.json (which ships only `name`, `homeassistant`, `hacs`). [VERIFIED via 2 sources]
- SHA pinning is the community standard — confirmed in jpawlowski validate.yml + GitHub security advisory cycles. [VERIFIED via 2 sources]

### Tertiary (Reference — internal project research)

- `.planning/research/STACK.md` — prior stack research, all versions cross-checked and confirmed today.
- `.planning/research/ARCHITECTURE.md` — architecture spec, used for context only (Phase 1 doesn't implement architecture).
- `.planning/research/PITFALLS.md` — pitfalls catalogue, used for "What NOT to Use" cross-reference.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified live against PyPI / GitHub today.
- Architecture: HIGH — Phase 1 has no runtime architecture; the file layout is verified against canonical blueprints.
- Pitfalls: HIGH — all 9 pitfalls are sourced from hassfest source, HA Core source, or PHACC documentation.
- Code examples: HIGH — every artifact is either copied verbatim from a verified source or constructed from values verified individually.
- Critical landmine resolution (D-16 ConfigFlow placeholder): HIGH — resolved by reading hassfest source directly. Decision: keep `config_flow: true` in Phase 1.

**Research date:** 2026-05-03
**Valid until:** 2026-06-02 (30 days for stable HA / HACS / PyPI ecosystem; re-verify SHAs and PyPI versions before any v0.1.0 release).
