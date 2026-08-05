# Phase 1: Foundations & Skeleton - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

A HACS-installable empty integration shell for HA-Pronote that:
1. Loads as a no-op `__init__.py` in a recent Home Assistant dev container (no entry creation, no entities yet — package just registers)
2. Has full CI gating every PR (`hassfest` + `hacs/action` + `ruff` + `pyright` + `pytest`) so any future merge that breaks the structure fails before merge
3. Has a working local dev workflow via `uv` (`uv sync && uv run pytest` from a clean checkout passes green)
4. Ships a `manifest.json` valid against `hassfest` and a `hacs.json` valid against `hacs/action`

**In scope (Phase 1 only):** repo structure, CI workflows, `manifest.json` + `hacs.json` + `info.md`, `pyproject.toml`, `uv.lock`, `.python-version`, ruff/pyright config, empty `__init__.py` (returns `True` from `async_setup_entry` / no `async_setup_entry` at all if no `config_flow: true` yet), `requirements_test.txt`, a single smoke test that asserts the integration imports.

**Out of scope (deferred to later phases):** Config Flow, coordinator, sensors, calendar, events, options flow, diagnostics, translations, README full content, reauth, multi-child, polling logic, diff layer.

</domain>

<decisions>
## Implementation Decisions

### Integration Identity
- **D-01:** `manifest.json:domain = "ha_pronote"` (underscore). FROZEN — changing after first real install breaks `.storage/<domain>.config_entries` and all entity_ids. Rationale: aligns with DIST-09 zip naming `ha_pronote.zip`, no collision with `delphiki/hass-pronote` (uses `pronote`), so a user who tried delphiki can install both side-by-side or migrate cleanly.
- **D-02 [informational]:** `unique_id` pattern stays `pronote_{child_identifier}_{sensor_kind}` per ENT-02 (REQUIREMENTS.md). Independent from `domain`. Keeps user-facing entity_ids short (`sensor.pronote_alice_grades`) while folder/manifest use the disambiguated `ha_pronote`. *(Phase 3 concern — Phase 1 ships no entities.)*
- **D-03:** GitHub repo: `https://github.com/tom333/ha-pronote` (hyphen). Repo name uses hyphen (GitHub convention), Python package uses underscore (`custom_components/ha_pronote/`). HACS handles the mismatch transparently.
- **D-04:** `manifest.json` codeowner = `["@tom333"]`.
- **D-05:** `manifest.json:documentation = "https://github.com/tom333/ha-pronote"`.
- **D-06:** `manifest.json:issue_tracker = "https://github.com/tom333/ha-pronote/issues"`.

### Version Floor
- **D-07:** `pyproject.toml:requires-python = ">=3.14.2"`. Update `.python-version` from current `3.10` (uv default leftover) to `3.14`.
- **D-08:** `hacs.json:homeassistant = "2026.4.0"` (HACS-side floor for users).
- **D-09:** Pin test `homeassistant` dep at `==2026.4.4` in `requirements_test.txt` for reproducible CI (latest patch on the 2026.4 line as of 2026-04-24).
- **D-10:** `[tool.ruff] target-version = "py314"`.
- **D-11:** Explicit decision: target HA 2026.4+ only. Users on HA 2026.1–2026.2 (Py 3.13) and HA 2025.x (Py 3.12) cannot install — accepted tradeoff per CLAUDE.md / STACK.md ("self-inflicted wound to dodge Python 3.14").

### `manifest.json` Required Fields (Locked from CLAUDE.md / REQUIREMENTS.md)
- **D-12:** `iot_class: "cloud_polling"` (DIST-02)
- **D-13:** `quality_scale: "bronze"` (DIST-02)
- **D-14:** `requirements: ["pronotepy==2.14.6", "python-slugify==8.0.4"]` — pin pronotepy exactly (Pronote API breaks regularly, pronotepy ships compensating fixes; pinning prevents silent break on user update). `python-slugify` matches HA Core's pinned version to avoid resolver thrash.
- **D-15:** `integration_type: "hub"` — one entry per Pronote child account (each child = one config entry, parent device, multiple sensors). Phase 1 just declares this; Phase 3+ implements.
- **D-16:** `config_flow: true` — declare from Phase 1 even though no flow ships until Phase 3, so HACS UI shows "Add Integration" button correctly. Empty placeholder flow that raises `NotImplementedError` is acceptable for Phase 1; Phase 3 fills it. *(If `hassfest` rejects placeholder, drop to `config_flow: false` in Phase 1 and flip in Phase 3 — planner decides at execution time.)*
- **D-17:** `version: "0.0.1"` — placeholder for Phase 1; release workflow rewrites it from tag.

### Release Workflow
- **D-18:** Manual zip pattern (delphiki style), NOT release-please. `.github/workflows/release.yml` triggered on `release: published` event:
  1. Checkout
  2. `sed`-replace `"version": "..."` in `custom_components/ha_pronote/manifest.json` with `${{ github.event.release.tag_name }}`
  3. `cd custom_components/ha_pronote && zip -r ../../ha_pronote.zip .`
  4. `softprops/action-gh-release@<sha>` to attach `ha_pronote.zip` as release asset
- **D-19 [informational]:** Conventional Commits encouraged but NOT enforced in v1. Migration to `release-please` left as v2+ option. Satisfies DIST-09. *(Negative decision — nothing to enforce; documented non-policy.)*

### CI Workflows (Locked from DIST-03)
- **D-20:** `.github/workflows/lint.yml` runs on `pull_request` and `push`: `ruff format --check`, `ruff check`, `pyright`, `codespell`. Uses `astral-sh/setup-uv@v8` + `uv pip install -r requirements_test.txt` (cached on `requirements*.txt` hash). Pyright via `npx pyright` (npm install in step) — matches `jpawlowski` blueprint.
- **D-21:** `.github/workflows/validate.yml` runs on `pull_request` and `push`: `home-assistant/actions/hassfest@<sha> # master` + `hacs/action@<sha> # main` with `category: integration` and `ignore: brands` (no brand assets in v1; brand submission deferred to v2+ per CLAUDE.md "What NOT to Use" guidance on `hacs/action`).
- **D-22:** `.github/workflows/test.yml` runs on `pull_request` and `push`: `uv pip install -r requirements_test.txt`, then `pytest -q`. Phase 1 has at least one trivial test (smoke test) so the workflow has something to assert.
- **D-23:** GitHub Actions pinned by SHA, NOT by tag. Tags on `home-assistant/actions` (`1.0.0`, 2020) and `hacs/action` (`22.5.0`, 2022) are stale; community pins by SHA on `master`/`main`. Renovate/dependabot bumps in v2+.
- **D-24 [deferred]:** Daily cron job against `pronotepy@main` (DIST-04) is OUT OF Phase 1 scope — deferred to Phase 7.

### Tooling (Locked from CLAUDE.md / DIST-08)
- **D-25:** `uv` for deps + venv. `uv.lock` committed. `requirements_test.txt` mirrors test deps for HA-style consumption (CI uses `uv pip install -r requirements_test.txt`, NOT `uv sync` — keeps the test workflow path identical to a future contributor's `pip install -r ...` flow if they don't have `uv`).
- **D-26:** `ruff` (lint+format) only. No `black`, no `flake8`, no `isort`. Match HA Core's `[tool.ruff]` block from `pyproject.toml` verbatim (line/select/ignore lists), adjust `target-version` to `py314`.
- **D-27:** `pyright` (NOT mypy) — matches `jpawlowski` blueprint trend per CLAUDE.md. Run via `npx pyright` so `package.json` controls the version. Mode: `basic` (NOT `strict`) — matches HA Core practice for integrations.
- **D-28:** `codespell` for spell-check (cheap insurance for FR/EN mixed docstrings).
- **D-29:** `pytest` ships from Phase 1 with `pytest-homeassistant-custom-component` even though the only test is a smoke test — sets up `asyncio_mode = "auto"` and `enable_custom_integrations` fixture so Phase 2 onboarding has zero friction.

### Out-of-Scope Anti-Patterns (Hard Locks from CLAUDE.md "What NOT to Use")
- **D-30:** NO `async_timeout` package — `asyncio.timeout()` (stdlib) when needed in later phases.
- **D-31:** NO `pytz` — `zoneinfo.ZoneInfo("Pacific/Noumea")` later.
- **D-32:** NO direct `requests` in our code — only via `pronotepy`.
- **D-33 [informational]:** NO ENT modules from `pronotepy.ent` (out of scope per PROJECT.md, would silently bloat bundle). *(Phase 3+ owns this in practice — Phase 1 has no pronotepy imports.)*
- **D-34 [informational]:** NO hardcoded `katiramona.ac-noumea.nc` URL — Config Flow text field with `voluptuous.Url()` validator (Phase 3 concern, but lock the principle now). *(Phase 1's placeholder ConfigFlow has zero URL handling.)*
- **D-35 [informational]:** NO monkey-patching of `pronotepy` in our component (CLAUDE.md "What NOT to Use") — open issues at `bain3/pronotepy` instead. *(Phase 1 has no pronotepy imports.)*

### Claude's Discretion
The user delegated three sub-decisions to the planner. Recommended defaults to apply unless planner finds a stronger argument:
- **C-01:** Test scaffolding scope at Phase 1 — RECOMMEND full `pytest-homeassistant-custom-component` setup (not bare smoke test) so Phase 2 onboarding is friction-free. Single test file `tests/test_init.py` that asserts the package imports + uses `enable_custom_integrations` fixture.
- **C-02:** Dev container — RECOMMEND ship a minimal `.devcontainer/devcontainer.json` based on `jpawlowski/hacs.integration_blueprint` (HA dev container image + uv preinstalled). Success criteria #1 says "loads in HA dev container" — devcontainer makes that test reproducible for any contributor. Low cost (~30 lines).
- **C-03:** Pre-commit hooks — RECOMMEND ship `.pre-commit-config.yaml` with `prek` (HA Core's Rust-rewritten replacement for pre-commit, adopted 2025) running `ruff format` → `ruff check --fix` → `pyright` → `codespell`. Same hooks CI runs, fail fast locally.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Core value, constraints, key decisions table (HACS custom repo, from-scratch, no ENT in v1, devoirs in v2)
- `.planning/REQUIREMENTS.md` — All 54 v1 requirements; Phase 1 covers DIST-01, DIST-02, DIST-03, DIST-08
- `.planning/ROADMAP.md` §"Phase 1: Foundations & Skeleton" — Goal, Success Criteria, dependencies
- `CLAUDE.md` — Authoritative tech stack: Python 3.14.2 floor, HA 2026.4+, ruff+pyright+uv+pronotepy 2.14.6, pinned by-SHA actions, anti-pattern list

### Research already done
- `.planning/research/STACK.md` — Why every dep version was picked; "What NOT to Use" table; full version-compatibility matrix
- `.planning/research/ARCHITECTURE.md` — Architecture spec to read before coordinator/diff phases (background for Phase 1: integration_type=hub rationale)
- `.planning/research/PITFALLS.md` — Known landmines, especially around pronotepy + executor boundary (relevant Phase 1 only for `iot_class: cloud_polling` decision)
- `.planning/research/FEATURES.md` — Feature scoping that drove the requirements
- `.planning/research/SUMMARY.md` — High-level synthesis

### External references (URL only — fetched during research, no local copy)
- HA Core `homeassistant/const.py` — `REQUIRED_PYTHON_VER = (3, 14, 2)` (verified 2026-05)
- HA Core `pyproject.toml` — `[tool.ruff]` block to copy verbatim
- HA Core `.pre-commit-config.yaml` — hooks template (`ruff-pre-commit v0.15.1`, `prek 0.2.28`)
- `jpawlowski/hacs.integration_blueprint` — modern HACS blueprint reference
- `delphiki/HomeAssistant-Pronote` — reference implementation (study `coordinator.py`'s 26 `async_add_executor_job` call sites; do NOT copy `manifest.json` `domain` value)
- HACS publish docs `https://www.hacs.xyz/docs/publish/start/` — `hacs.json` schema
- HA developer docs `https://developers.home-assistant.io/docs/creating_integration_manifest/` — manifest schema

### SPEC.md
None — `/gsd-spec-phase` was not run for Phase 1. Requirements live in REQUIREMENTS.md (DIST-01/02/03/08) and ROADMAP.md success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None.** Project root contains only `.planning/`, `.claude/`, `.gitignore`, `.python-version` (currently `3.10` — must be updated), `CLAUDE.md`. No prior `custom_components/`, no prior tests, no prior workflows. Phase 1 builds the whole repo skeleton from scratch.

### Established Patterns
- **None in this codebase yet.** External patterns to mirror:
  - `jpawlowski/hacs.integration_blueprint` — `pyproject.toml` and `.github/workflows/{lint,validate}.yml` shape
  - `delphiki/hass-pronote` — `release.yml` pattern (manual tag → version inject → zip)
  - HA Core master — `[tool.ruff]` config block (copy verbatim, override `target-version`)

### Integration Points
- **HACS install path:** `<repo-root>/custom_components/ha_pronote/` (HACS expects this exact layout for `category: integration`)
- **HA dev container:** Phase 1 testing surface is a HA dev container loading the empty integration package. `.devcontainer/devcontainer.json` is the integration point if devcontainer ships in Phase 1 (per C-02 default).
- **GitHub Actions:** Three workflows under `.github/workflows/` (`lint.yml`, `validate.yml`, `test.yml`) plus the release workflow (`release.yml` triggered on `release: published`).

</code_context>

<specifics>
## Specific Ideas

- Repo name `ha-pronote` (hyphen) on GitHub, integration domain `ha_pronote` (underscore) — accepted convention, HACS handles the mapping.
- Codeowner identity: `@tom333` GitHub handle; do NOT include real name (`Thomas Guyader`) in `manifest.json:codeowners` — that field expects GitHub handles only. Real name lives in commit history (`git config user.name`) and `LICENSE`/`README.md` if shipped.
- The `delphiki/hass-pronote` repo is a *reference*, not a fork base — STACK.md and PROJECT.md key decision both confirm "from scratch" was chosen for clean `runtime_data` + better schedule-change semantics.
- Brand assets (icon.png + logo.png to `home-assistant/brands` repo) deferred to v2+. Phase 1 keeps `hacs/action` step with `ignore: brands`.

</specifics>

<deferred>
## Deferred Ideas

These came up during the discussion but belong in later phases or post-v1:

- **Daily cron CI against `pronotepy@main`** (DIST-04) — Phase 7 (Quality, Diagnostics & Distribution).
- **Conventional Commits enforcement / migration to `release-please`** — v2+ once release cadence justifies the automation overhead.
- **Brand assets submission to `home-assistant/brands`** — v2+ requirement for HACS Silver+ quality scale.
- **HACS default repository submission** — v2+ per PROJECT.md key decision (locked).
- **HA Quality Scale Silver / Gold migration** — v2 (QUAL-V2-01, QUAL-V2-02).
- **README full content** (HACS install, ApexCharts schema, automation YAML examples, polling rationale) — Phase 7 (DIST-07). Phase 1 ships only a minimal placeholder README sufficient for `hacs/action` validation.
- **Translations (`strings.json`, `translations/{en,fr}.json`)** — Phase 7 (I18N-01, I18N-02). Phase 1 doesn't ship translations.
- **Renovate/Dependabot config to bump SHA-pinned actions** — v2+, low priority for v1.
- **Compatibility with HA 2026.1–2026.2 / Python 3.13** — explicitly out of scope per D-11. Reconsider only if a real user reports being blocked.

</deferred>

---

*Phase: 1-Foundations & Skeleton*
*Context gathered: 2026-05-03*
