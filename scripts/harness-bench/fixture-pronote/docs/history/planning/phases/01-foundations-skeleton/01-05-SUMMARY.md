---
phase: 01-foundations-skeleton
plan: 05
subsystem: infra
tags:
  - foundations
  - devcontainer
  - pre-commit
  - tooling
  - ruff
  - codespell
  - pyright
  - uv
  - hacs

# Dependency graph
requires:
  - phase: 01-foundations-skeleton/01
    provides: "requirements_test.txt (ruff==0.15.1, codespell==2.4.1, homeassistant==2026.4.4, PHACC==0.13.326), package.json (pyright 1.1.409), pyproject.toml [tool.pyright] typeCheckingMode=basic"
provides:
  - ".devcontainer.json: single-file devcontainer at repo root (ludeeus blueprint shape) — Debian base + Python 3.14 + Node 22 + uv venv bootstrap + npm install + forwardPorts [8123]"
  - ".pre-commit-config.yaml: local hook chain (ruff-format → ruff-check --fix → codespell → npx pyright) byte-aligned to requirements_test.txt + package.json"
  - "Reproducible Phase 1 success criterion #1 (loads in HA dev container) for any contributor — no maintainer-only assumption"
  - "C-02 RECOMMEND default honored (devcontainer ships in Phase 1)"
  - "C-03 RECOMMEND default honored (pre-commit hooks mirror CI lint.yml)"
affects:
  - "01-04 (CI workflows): pre-commit hook chain mirrors `lint.yml` job order — when 01-04 lands, contributors fail fast locally before CI"
  - "All future phases: contributors clone → open in VS Code → devcontainer post-create runs `uv pip install -r requirements_test.txt && npm install` automatically"
  - "v2+ migration to SHA-pinned pre-commit revs (alongside Renovate) — current revs are tag-pinned per pre-commit ecosystem standard"

# Tech tracking
tech-stack:
  added:
    - "Dev container: mcr.microsoft.com/devcontainers/base:debian + ghcr.io/devcontainers/features/python:1@3.14 + ghcr.io/devcontainers/features/node:1@22"
    - "Pre-commit hooks: astral-sh/ruff-pre-commit v0.15.1, codespell-project/codespell v2.4.1, local pyright via npx"
    - "VSCode extensions auto-installed: charliermarsh.ruff, ms-python.python, ms-python.vscode-pylance, ms-azuretools.vscode-docker, github.vscode-pull-request-github, ryanluker.vscode-coverage-gutters"
  patterns:
    - "Single-file devcontainer at repo root (`.devcontainer.json`), NOT directory form (`.devcontainer/devcontainer.json`) — matches ludeeus blueprint and is the simpler form"
    - "`postCreateCommand` uses `uv pip install -r requirements_test.txt`, NOT `uv sync` — keeps contributor path identical to CI install (D-25)"
    - "`language: node` for the pyright pre-commit hook (NOT `language: system`) — runs against the project's `package.json`-pinned pyright, not a globally-installed binary"
    - "`pass_filenames: false` for pyright — pyright reads `pyproject.toml [tool.pyright] include`; passing filenames would override that"
    - "VSCode `python.analysis.typeCheckingMode = \"basic\"` matches `pyproject.toml [tool.pyright] typeCheckingMode = \"basic\"` (D-27) — no editor/CI drift"

key-files:
  created:
    - ".devcontainer.json"
    - ".pre-commit-config.yaml"
  modified: []

key-decisions:
  - "Adopted single-file `.devcontainer.json` at repo root (ludeeus blueprint shape, PATTERNS.md L184-192) — VS Code accepts both layouts but the single-file form needs no extra directory, matches the modern reference, and ships exactly the verbatim block from RESEARCH.md L934-982"
  - "Pyright pre-commit hook uses `language: node` + `npx pyright` (not `language: system`) so the version comes from `package.json:1.1.409` — the same version CI runs, no host-machine drift"
  - "`exclude: ^tests/fixtures/` ships now even though Phase 1 has no fixtures dir — Phase 2+ will, and codespell would otherwise flag intentional misspellings in captured Pronote payloads (forward-looking guard)"
  - "Tag-pinned pre-commit revs (`v0.15.1`, `v2.4.1`) accepted for Phase 1 — pre-commit's first-install cache stores resolved commit SHA, and the production CI gate (Plan 04) is SHA-pinned. SHA-pinning the pre-commit revs is deferred to v2+ alongside Renovate adoption"

patterns-established:
  - "Pattern: cross-file version triple-pin. Ruff `0.15.1` lives in three places (`requirements_test.txt: ruff==0.15.1`, `pyproject.toml: [tool.ruff] required-version = \">=0.15.1\"`, `.pre-commit-config.yaml: rev: v0.15.1`). All three move together when ruff bumps. Same for codespell `2.4.1` (two places: `requirements_test.txt`, `.pre-commit-config.yaml`)."
  - "Pattern: `postCreateCommand` is the single bootstrap command. Combines `uv venv .venv --python 3.14`, `uv pip install -r requirements_test.txt`, and `npm install` so a fresh devcontainer launch yields a fully-tooled environment with one `&&`-chained command. No README copy-paste step required."
  - "Pattern: VSCode editor settings inline in devcontainer (NOT `.vscode/settings.json`). Avoids a checked-in `.vscode/` folder polluting the repo while still ensuring formatOnSave + ruff-as-formatter work for any contributor opening the devcontainer."

requirements-completed:
  - DIST-08

# Metrics
duration: ~5min
completed: 2026-05-03
---

# Phase 01 Plan 05: Contributor Onboarding Chain Summary

**Single-file `.devcontainer.json` (Python 3.14 + Node 22 + uv + 6 VSCode extensions, port 8123 forwarded) plus `.pre-commit-config.yaml` mirroring CI lint.yml verbatim (ruff-format → ruff-check --fix → codespell → npx pyright), all version-pinned byte-aligned to Plan 01's `requirements_test.txt` + `package.json`.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-03T06:18Z (worktree agent spawn, approx)
- **Completed:** 2026-05-03T06:23Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- `.devcontainer.json` shipped at repo root (single-file ludeeus shape) — any contributor can clone the repo, accept the VS Code "Reopen in Container" prompt, and the `postCreateCommand` (`uv venv .venv --python 3.14 && .venv/bin/uv pip install -r requirements_test.txt && npm install`) provisions the entire toolchain automatically. Phase 1 success criterion #1 ("loads in HA dev container") is now reproducible without maintainer intervention.
- `.pre-commit-config.yaml` shipped mirroring CI's `lint.yml` chain verbatim: `ruff-format`, `ruff-check --fix`, `codespell` (with `--ignore-words-list=hass`, excluding `tests/fixtures/`), and a local `pyright` hook running via `npx`. Both `prek` (HA Core's Rust-rewritten replacement) and stock `pre-commit` parse the same YAML — contributors choose their tool.
- Cross-file version-alignment confirmed: `ruff` pinned to `0.15.1` in three places (`requirements_test.txt`, `pyproject.toml [tool.ruff] required-version`, `.pre-commit-config.yaml`); `codespell` pinned to `2.4.1` in two places (`requirements_test.txt`, `.pre-commit-config.yaml`); `pyright` pinned to `1.1.409` via `package.json` and consumed by both CI's `npx pyright` step and the local pre-commit hook.
- Editor/CI typecheck mode aligned: VSCode `python.analysis.typeCheckingMode = "basic"` in `.devcontainer.json` matches `pyproject.toml [tool.pyright] typeCheckingMode = "basic"` (D-27) — no drift between what a contributor sees inline in their editor and what CI enforces.

## Task Commits

Each task was committed atomically on the worktree branch `worktree-agent-a8163175cbce5bf8a`:

1. **Task 1: Write `.devcontainer.json` (single-file at repo root, ludeeus shape)** — `d68484b` (chore)
2. **Task 2: Write `.pre-commit-config.yaml` (local hooks mirror CI lint.yml)** — `c75ef21` (chore)

_No TDD commits — both tasks are `tdd="false"` config-only files._

## Files Created/Modified

- `.devcontainer.json` — Single-file devcontainer at repo root. Image `mcr.microsoft.com/devcontainers/base:debian`; features `ghcr.io/devcontainers/features/python:1@3.14` and `ghcr.io/devcontainers/features/node:1@22`; `postCreateCommand` chains `uv venv .venv --python 3.14`, `uv pip install -r requirements_test.txt`, `npm install`; forwards port `8123` (HA UI) with `onAutoForward: "notify"`; auto-installs 6 VSCode extensions; sets editor settings inline (formatOnSave, ruff as Python formatter, `typeCheckingMode: "basic"`); `remoteUser: "vscode"`.
- `.pre-commit-config.yaml` — Three repos: `astral-sh/ruff-pre-commit v0.15.1` (hooks `ruff-format` and `ruff-check --fix`, both scoped via `files: ^((custom_components|tests)/.+)?[^/]+\.(py|pyi)$`); `codespell-project/codespell v2.4.1` (hook `codespell` with `--ignore-words-list=hass`, `--quiet-level=2`, `exclude_types: [csv, json, html]`, `exclude: ^tests/fixtures/`); local `pyright` hook (`entry: npx pyright`, `language: node`, `types: [python]`, `pass_filenames: false`).

## Decisions Made

- **Single-file devcontainer over directory form.** PATTERNS.md L184-192 mandates the single-file shape (`.devcontainer.json` at repo root, not `.devcontainer/devcontainer.json`). Both forms work in VS Code, but the single-file form matches the ludeeus blueprint, requires no extra directory, and is the simpler reference for contributors copying patterns later.
- **`language: node` for the pyright pre-commit hook.** Using `language: system` would run whatever pyright happens to be on a contributor's host PATH — potentially a different version than `package.json:1.1.409`. `language: node` makes pre-commit install the npm package into its own cache, ensuring local pyright matches CI pyright exactly.
- **`pass_filenames: false` for pyright.** Pre-commit's default behavior of passing changed files as positional args would override pyright's `[tool.pyright] include` configuration in `pyproject.toml`. Disabling filename pass-through lets pyright read its target list from `pyproject.toml`, which keeps the local hook and the CI `npx pyright` invocation behaviorally identical.
- **`exclude: ^tests/fixtures/` ships in Phase 1 even though no fixtures dir exists yet.** Forward-looking guard for Phase 2+: when captured Pronote API responses (with intentionally misspelled French content) start landing under `tests/fixtures/`, codespell will not flag them. Adding the rule now means the Phase 2 author does not need to touch this file.
- **Tag-pinned pre-commit revs accepted for Phase 1.** `astral-sh/ruff-pre-commit@v0.15.1` and `codespell-project/codespell@v2.4.1` are tag-pinned, not SHA-pinned, per the pre-commit ecosystem standard. Pre-commit's first-install cache resolves and stores the underlying commit SHA, providing a degree of mitigation against tag-move attacks. The production CI gate (Plan 04) is SHA-pinned for actions; SHA-pinning pre-commit revs alongside Renovate adoption is deferred to v2+ (T-05-01, T-05-02 in plan threat register).

## Deviations from Plan

None — plan executed exactly as written. Both tasks produced verbatim file content from RESEARCH.md §Code Examples (L901-932 for `.pre-commit-config.yaml`, L934-982 for `.devcontainer.json`), and every `<acceptance_criteria>` check passed on first run. Cross-file invariants (`ruff==0.15.1` ↔ `rev: v0.15.1`, `codespell==2.4.1` ↔ `rev: v2.4.1`, `package.json: pyright 1.1.409` ↔ `entry: npx pyright`, `pyproject.toml: typeCheckingMode = "basic"` ↔ devcontainer `python.analysis.typeCheckingMode = "basic"`) all hold.

## Issues Encountered

None.

## Self-Check

Verifying claims against the on-disk repository state:

- **Files created (2):**
  - FOUND: `.devcontainer.json` (1282 bytes)
  - FOUND: `.pre-commit-config.yaml` (854 bytes)
- **Files NOT created (anti-pattern guard):**
  - ABSENT: `.devcontainer/devcontainer.json` (single-file form mandated per PATTERNS L184-192)
- **Commits (2 task commits, both on `worktree-agent-a8163175cbce5bf8a`):**
  - FOUND: `d68484b` — chore(01-05): add .devcontainer.json (Python 3.14 + Node 22 + uv)
  - FOUND: `c75ef21` — chore(01-05): add .pre-commit-config.yaml mirroring CI lint.yml
- **Locked invariant verification (D-IDs visible in artifacts):**
  - C-02 RECOMMEND: devcontainer single-file form at repo root — OK
  - C-03 RECOMMEND: pre-commit chain (`ruff-format` → `ruff-check --fix` → `codespell` → `pyright`) — OK
  - D-25: `postCreateCommand` uses `uv pip install -r requirements_test.txt` (NOT `uv sync`) — OK
  - D-27: `python.analysis.typeCheckingMode == "basic"` matches `pyproject.toml [tool.pyright] typeCheckingMode = "basic"` — OK
  - D-28: `codespell-project/codespell v2.4.1` matches `requirements_test.txt: codespell==2.4.1` — OK
- **Cross-file version-alignment invariants (the heart of this plan):**
  - `ruff==0.15.1` (`requirements_test.txt`) ↔ `rev: v0.15.1` (`.pre-commit-config.yaml`) — byte-equal: OK
  - `codespell==2.4.1` (`requirements_test.txt`) ↔ `rev: v2.4.1` (`.pre-commit-config.yaml`) — byte-equal: OK
  - `pyright: 1.1.409` (`package.json`) ↔ `entry: npx pyright` (`.pre-commit-config.yaml`) — consumes pinned package: OK
  - `python:3.14` devcontainer feature ↔ `requires-python = ">=3.14.2"` (`pyproject.toml`) ↔ `3.14` (`.python-version`) — Python floor agrees everywhere: OK
- **Format validity:**
  - `python3 -c "import json; json.load(open('.devcontainer.json'))"` exits 0 — OK
  - `python3 -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"` exits 0 — OK
- **Out-of-scope file safety:**
  - `git diff --name-only fe53d6a9..HEAD` returns exactly `.devcontainer.json` and `.pre-commit-config.yaml` — no scope creep: OK
  - No modifications to `STATE.md`, `ROADMAP.md`, or any file outside the two in scope: OK
- **Branch safety:**
  - HEAD is on `worktree-agent-a8163175cbce5bf8a` (per-agent branch namespace, NOT a protected ref): OK
  - All 2 commits via standard `git commit` (no `--no-verify`): OK

## Self-Check: PASSED

## Known Stubs

None. The two files shipped are configuration that becomes active immediately:
- `.devcontainer.json` is consumed the next time any contributor opens the repo in VS Code with the Dev Containers extension.
- `.pre-commit-config.yaml` is consumed the next time `prek install` or `pre-commit install` runs (no auto-install in v1; documented for Phase 7 README).

The `npx pyright` hook will trigger an auto-install of pyright `1.1.409` on first run from `package.json` — that is expected behavior, not a stub.

## TDD Gate Compliance

Not applicable — plan type is `execute` (not `tdd`). Both tasks have `tdd="false"`. No `test(...)` commits required by the plan or by `<tdd_execution>` rules.

## Threat Flags

None. The two files shipped introduce no new runtime surface beyond what the threat register in PLAN.md already covers (T-05-01 through T-05-06):

- T-05-01 (Tampering, ruff-pre-commit tag): mitigated by tag pin + cache-resolved SHA — accepted for Phase 1 per `<threat_model>` disposition.
- T-05-02 (Tampering, codespell tag): same as T-05-01.
- T-05-03 (Tampering, postCreateCommand external sources): the command consumes only `requirements_test.txt` (Plan 01 — pinned PyPI versions) and `package.json` (Plan 01 — pinned npm version). No new external sources beyond what CI already consumes.
- T-05-04 (Tampering, devcontainer base image retag): accepted — Microsoft-published image. SHA-digest pinning deferred to v2+.
- T-05-05 (Information disclosure, VSCode extensions): all 6 extensions are mainstream Microsoft / Astral / GitHub-published. No additional risk surface.
- T-05-06 (Tampering, ruff rev drifts away from `requirements_test.txt`): this Self-Check section explicitly verifies byte-equal alignment for ruff `0.15.1` and codespell `2.4.1` — drift would fail the assertion.

No new threat surface introduced — DIST-08 completion adds dev-loop convenience only, no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Next Phase Readiness

- **Plan 01-04 (CI workflows)** [parallel sibling, Wave 2]: When 01-04 lands, `lint.yml` will run the same `ruff format --check`, `ruff check`, `npx pyright`, and `codespell` invocations the local pre-commit hook runs — contributors fail fast locally before CI rejects their PR. The hook chain order (`ruff-format` → `ruff-check` → `codespell` → `pyright`) mirrors what CI runs in parallel jobs.
- **Phase 7 (DIST-07 — README full content)**: The README contributor section should document `prek install` (or `pre-commit install`) as the post-clone setup step. Devcontainer users get this for free via `postCreateCommand`; non-devcontainer contributors need the manual step.
- **v2+ migration (Renovate / SHA-pinning)**: T-05-01 / T-05-02 mitigation upgrade — switch the two pre-commit repo refs from tag pins to 40-char SHA pins, alongside Renovate config to bump them automatically.
- **Open dependencies on this plan:** None — Plan 01-05 ships independent contributor tooling. Plans 01-02 (manifest + skeleton) and 01-03 (tests) operate on disjoint file sets.

---
*Phase: 01-foundations-skeleton*
*Completed: 2026-05-03*
