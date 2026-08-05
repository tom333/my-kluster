---
phase: 01-foundations-skeleton
plan: 04
subsystem: infra
tags:
  - foundations
  - ci
  - github-actions
  - hassfest
  - hacs
  - release-automation
  - sha-pinning
  - workflow-permissions

# Dependency graph
requires:
  - phase: 01-01
    provides: "requirements_test.txt + package.json (consumed by lint.yml + test.yml)"
  - phase: 01-02
    provides: "manifest.json + hacs.json (consumed by validate.yml; manifest rewritten by release.yml; hacs.json:filename matches release.yml zip output)"
provides:
  - "lint.yml: ruff format/check + pyright (npx) + codespell — three jobs, SHA-pinned, permissions: {}"
  - "validate.yml: hassfest@<sha> + hacs/action@<sha> with category: integration, ignore: brands"
  - "test.yml: uv pip install --system -r requirements_test.txt + pytest -q"
  - "release.yml: dormant until first tag; rewrites manifest version via yq, zips ha_pronote.zip, attaches to release"
  - "DIST-03 enforcement at the workflow layer (CI runs on every PR + push to main)"
affects:
  - "01-05 (pre-commit hooks): same ruff/codespell/pyright tools — local hooks must agree with CI to avoid CI-only failures"
  - "Phase 7 (release): cutting v0.1.0 tag triggers release.yml automatically — no separate release plan needed"
  - "All future phases: PRs merging to main are gated by Lint + Validate + Test status checks (once branch protection set by operator — Task 4)"

# Tech tracking
tech-stack:
  added:
    - "GitHub Actions runtime (ubuntu-latest)"
    - "actions/checkout@de0fac2e (v6.0.2)"
    - "actions/setup-python@a309ff8b (v6.2.0)"
    - "astral-sh/setup-uv@08807647 (v8.1.0) with cache-dependency-glob: requirements*.txt"
    - "actions/setup-node@48b55a01 (v6.4.0) for pyright via npx"
    - "home-assistant/actions/hassfest@f6f29a7e (master)"
    - "hacs/action@dcb30e72 (main) with category: integration, ignore: brands"
    - "softprops/action-gh-release@b4309332 (v3.0.0) for release asset upload"
    - "yq (preinstalled on ubuntu-latest) for JSON in-place edit"
  patterns:
    - "SHA-pinning every external action with trailing comment for symbolic version (audit readability + reproducibility)"
    - "Top-level permissions: {} on read-only workflows (lint, validate, test); contents: write only on release.yml"
    - "Triggers: push + pull_request to main on lint/validate/test; release.yml triggers exclusively on release: published"
    - "CI install path identical to a non-uv contributor's path: uv pip install --system -r requirements_test.txt (D-25, NOT uv sync)"
    - "Cross-plan filename invariant: release.yml zip output (ha_pronote.zip) MUST equal hacs.json:filename"

key-files:
  created:
    - ".github/workflows/lint.yml"
    - ".github/workflows/validate.yml"
    - ".github/workflows/test.yml"
    - ".github/workflows/release.yml"
  modified: []

key-decisions:
  - "All seven external actions pinned by 40-char SHA per D-23 (no tag-only refs — action repo tags are stale)"
  - "Permissions hierarchy enforced: read-only workflows declare permissions: {}, only release.yml elevates to contents: write (RESEARCH §Security Domain task 3)"
  - "release.yml uses delphiki-style manual zip pattern (D-18) — release-please migration deferred to v2+"
  - "yq for the manifest version rewrite (RESEARCH-recommended) instead of sed — yq is JSON-aware and is preinstalled on ubuntu-latest runners"
  - "validate.yml retains ignore: brands — brand asset submission to home-assistant/brands deferred to v2+ per CONTEXT.md <deferred>"

patterns-established:
  - "Pattern: SHA-pinned actions with symbolic-version trailing comment. `uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2`. Every uses: line in this phase follows this shape; future Renovate config bumps SHAs but preserves the comment for audit."
  - "Pattern: zero-default GITHUB_TOKEN scopes. Top-level permissions: {} prevents inherited contents: read / packages: read / etc. Workflows that genuinely need a scope opt in explicitly (release.yml has contents: write — the minimum needed for softprops/action-gh-release)."
  - "Pattern: release-event metadata as trusted input. github.event.release.tag_name is interpolated into yq's JSON value, but releases can only be published by repo maintainers — the value is from a trusted boundary (T-04-04 mitigation)."
  - "Pattern: cross-plan filename invariant. Plan 02 declared hacs.json:filename: ha_pronote.zip; Plan 04 produces ha_pronote.zip via `cd custom_components/ha_pronote && zip ha_pronote.zip -r ./`. Drift between the two = HACS install breakage; the verification automated check enforces equality."

requirements-completed:
  - DIST-03

# Metrics
duration: ~5min (Tasks 1–3; Task 4 awaiting operator)
completed: 2026-05-03 (Tasks 1–3); 2026-05-03 (pending Task 4 operator action)
---

# Phase 01 Plan 04: GitHub Actions CI/CD Workflows Summary

**Four SHA-pinned, zero-default-permissions GitHub Actions workflows shipping the Phase 1 CI enforcement layer (lint + validate + test gating every PR; release.yml dormant until first tag rewrites manifest version via yq and attaches `ha_pronote.zip` to the release).**

## Performance

- **Duration:** ~5 min (Tasks 1–3 automated)
- **Started:** 2026-05-03T06:18Z
- **Completed (Tasks 1–3):** 2026-05-03T06:22Z
- **Tasks:** 3 of 4 automated; Task 4 (branch protection) awaiting operator action
- **Files created:** 4

## Accomplishments

- **lint.yml** — three independent jobs gating every PR and push to `main`:
  - `ruff` job: `ruff format --check .` then `ruff check .` (D-20)
  - `pyright` job: `setup-node@<sha>` (Node 22) + `npm install` + `npx pyright` (D-27 — pyright via npm, not Python venv)
  - `codespell` job: `codespell --ignore-words-list=hass --quiet-level=2 --skip="*.json,./.git,./node_modules"` (D-28)
- **validate.yml** — `hassfest@<sha>` validates `manifest.json` against HA Core's `CUSTOM_INTEGRATION_MANIFEST_SCHEMA`; `hacs/action@<sha>` validates `hacs.json` and repo structure with `category: integration` + `ignore: brands` (D-21).
- **test.yml** — `uv pip install --system -r requirements_test.txt` then `pytest -q` (D-22, D-25 — install path identical to a non-uv contributor's `pip install -r ...`).
- **release.yml** — dormant workflow that triggers on `release: published`. Uses `yq -i -o json '.version="${{ github.event.release.tag_name }}"' …/manifest.json` to rewrite the version field, builds `ha_pronote.zip` from `custom_components/ha_pronote/`, attaches it to the GitHub release via `softprops/action-gh-release@<sha>` (D-18). Phase 7 cuts the first tag — declaring this workflow now means tagging just works.
- **D-23 SHA pinning enforced across all seven external actions:**

  | Action | SHA | Symbolic |
  |---|---|---|
  | `actions/checkout` | `de0fac2e4500dabe0009e67214ff5f5447ce83dd` | v6.0.2 |
  | `actions/setup-python` | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | v6.2.0 |
  | `astral-sh/setup-uv` | `08807647e7069bb48b6ef5acd8ec9567f424441b` | v8.1.0 |
  | `actions/setup-node` | `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | v6.4.0 |
  | `home-assistant/actions/hassfest` | `f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b` | master |
  | `hacs/action` | `dcb30e72781db3f207d5236b861172774ab0b485` | main |
  | `softprops/action-gh-release` | `b4309332981a82ec1c5618f44dd2e27cc8bfbfda` | v3.0.0 |

- **Permissions hierarchy enforced** (RESEARCH §Security Domain task 3):
  - lint.yml: `permissions: {}` (top-level, empty) — zero default scopes
  - validate.yml: `permissions: {}`
  - test.yml: `permissions: {}`
  - release.yml: `permissions: contents: write` — only workflow elevating, minimum needed by `softprops/action-gh-release` to attach assets
- **Zero `${{ secrets.* }}` references** anywhere — Phase 1 has no secrets to consume; verified by `! grep -E 'secrets\.[A-Z_]+' .github/workflows/release.yml` (T-04-05 mitigation).
- **Cross-plan invariant honored:** `release.yml`'s zip output `ha_pronote.zip` matches `hacs.json:filename: "ha_pronote.zip"` from Plan 01-02 (T-04-08 mitigation).

## Task Commits

Each task was committed atomically on the worktree branch `worktree-agent-a501655662385b271`:

1. **Task 1: lint.yml + test.yml** — `d646089` (ci) — three lint jobs + pytest, SHA-pinned, permissions: {}
2. **Task 2: validate.yml** — `c0f6c07` (ci) — hassfest + hacs/action with category=integration, ignore=brands
3. **Task 3: release.yml** — `fbe3bff` (ci) — yq version inject + zip + softprops/action-gh-release on release: published
4. **Task 4: branch protection (DIST-03 policy layer)** — **NOT YET COMPLETE.** Operator-only checkpoint. See "Pending Operator Action" below.

_Plan metadata commit (this SUMMARY.md) follows separately._

## Files Created/Modified

- `.github/workflows/lint.yml` — 3 jobs (ruff, pyright, codespell). Triggers on push + pull_request to main. SHA-pinned. Empty top-level permissions.
- `.github/workflows/validate.yml` — 2 jobs (hassfest, hacs). Triggers on push + pull_request to main. SHA-pinned. Empty top-level permissions.
- `.github/workflows/test.yml` — 1 job (pytest). Triggers on push + pull_request to main. SHA-pinned. Empty top-level permissions.
- `.github/workflows/release.yml` — 1 job (build + attach zip). Triggers exclusively on `release: published`. SHA-pinned. `contents: write` (the only elevated workflow).

No files outside `.github/workflows/` were touched (per phase-context constraint).

## Decisions Made

None — plan executed exactly as specified for the three automatable tasks. All four workflow YAML bodies are verbatim from `01-RESEARCH.md` §Code Examples (lines 984–1141) plus the SHA pin table at L1444–1450; every locked decision (D-18, D-20–D-23, D-25, D-27, D-28) was honored without deviation.

## Pending Operator Action — Task 4 (Branch Protection)

**Status: AWAITING USER INPUT.** Task 4 is operator-only and cannot be automated from this worktree:

- The worktree has no `git remote` configured (the `tom333/ha-pronote` GitHub repo has not yet been pushed from this machine).
- `gh auth status` reports "The token in default is invalid" — no working credentials to call `gh api repos/tom333/ha-pronote/branches/main/protection`.
- A direct API call returned HTTP 401 ("Requires authentication").

**What the operator must do** (one of two paths):

### Path A — GitHub Web UI

1. Open https://github.com/tom333/ha-pronote/settings/branches
2. Click "Add classic branch protection rule"
3. Branch name pattern: `main`
4. Enable: "Require a pull request before merging" (Required approving reviews: `0` — single-maintainer repo for v1)
5. Enable: "Require status checks to pass before merging"
   - "Require branches to be up to date before merging": yes
   - Required status checks (search and add each — must run on a PR at least once before they appear in the picker):
     - `Lint` (job from `lint.yml`)
     - `Validate` (job from `validate.yml`)
     - `Test` (job from `test.yml`)
6. Enable: "Do not allow bypassing the above settings"
7. Save changes

### Path B — `gh` CLI (after `gh auth login`)

```bash
gh api repos/tom333/ha-pronote/branches/main/protection \
  -X PUT \
  -f required_status_checks.strict=true \
  -f required_status_checks.contexts[]=Lint \
  -f required_status_checks.contexts[]=Validate \
  -f required_status_checks.contexts[]=Test \
  -f enforce_admins=true \
  -F required_pull_request_reviews.required_approving_review_count=0 \
  -f restrictions=
```

### Verification (any path)

```bash
gh api repos/tom333/ha-pronote/branches/main/protection --jq '.required_status_checks.contexts'
# Expected: ["Lint","Validate","Test"] (any order)

gh api repos/tom333/ha-pronote/branches/main/protection --jq '.enforce_admins.enabled'
# Expected: true
```

When the orchestrator spawns the continuation agent, the operator should reply with `done` (after configuring) or `skipped` (track as a deferred TODO and DIST-03 policy layer remains incomplete).

**Why this gate matters:** DIST-03 success criterion ("blocks merge on failure") needs both the workflow layer (this plan, complete) AND the policy layer (branch protection on `main`). Without Path A or B, a maintainer could still bypass failing CI checks via direct push to `main` or merging a PR with red checks.

## Deviations from Plan

None for the three automatable tasks. Plan executed exactly as written:

- All four workflow files use the verbatim YAML bodies from RESEARCH.md §Code Examples
- All seven SHA pins match the verified-2026-05-03 table in RESEARCH.md L1444–1450
- All acceptance criteria automated checks passed on first run (no auto-fixes / Rules 1–3 triggered)
- No architectural decisions (Rule 4) raised

## Authentication Gate (Task 4)

Task 4 is an operator-only checkpoint — not an authentication failure of an automated step. The executor recognized at the start of the task that the worktree environment lacks the GitHub credentials and remote required to flip the branch-protection setting, and it surfaced the checkpoint as designed by the plan (`type=checkpoint autonomous=false`). This is the planned, expected path for `01-04-04`; no deviation rule applies.

## Issues Encountered

None during automated tasks. The pending Task 4 is a deliberate operator-only handoff documented in the plan itself.

## Threat Model Compliance

All `mitigate` dispositions from the plan's `<threat_model>` are honored by the shipped artifacts:

- **T-04-01 (Tampering — hassfest/hacs upstream):** SHA pins on both (`f6f29a7e…` and `dcb30e72…`) verified 2026-05-03.
- **T-04-02 (Tampering — supporting actions):** All five remaining actions SHA-pinned (`actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`, `actions/setup-node`, `softprops/action-gh-release`).
- **T-04-03 (EoP — default token scopes):** `permissions: {}` at top level on lint.yml, validate.yml, test.yml. Only release.yml elevates to `contents: write` (minimum for asset upload).
- **T-04-04 (Tampering — workflow injection):** No PR metadata interpolated into shell. Only template expansion is `${{ github.event.release.tag_name }}` from a maintainer-only trusted boundary.
- **T-04-05 (InfoDisclosure — secrets in logs):** Zero `${{ secrets.* }}` references in any of the four workflows. Verified by `! grep -E 'secrets\.[A-Z_]+'`.
- **T-04-06 (Tampering — cache poisoning):** `cache-dependency-glob: "requirements*.txt"` on `astral-sh/setup-uv` invalidates the cache automatically when deps change.
- **T-04-07 (DoS — `quality_scale: bronze` rejection):** Out-of-band: not directly testable from this worktree. The first hassfest run on a real PR will surface any rejection; PATTERNS L63 documents the OQ-4 fork (drop the field temporarily, re-add in Phase 7).
- **T-04-08 (Tampering — zip filename drift):** Cross-plan invariant verified at acceptance: `python3 -c "import json; assert json.load(open('hacs.json'))['filename'] == 'ha_pronote.zip'"` returns 0.

## Self-Check

Verifying claims against the on-disk repository state:

- **Files created (4):**
  - FOUND: `.github/workflows/lint.yml`
  - FOUND: `.github/workflows/validate.yml`
  - FOUND: `.github/workflows/test.yml`
  - FOUND: `.github/workflows/release.yml`
- **Commits (3 task commits, on `worktree-agent-a501655662385b271`):**
  - FOUND: `d646089` — ci(01-04): add lint.yml + test.yml (D-20, D-22, D-23)
  - FOUND: `c0f6c07` — ci(01-04): add validate.yml (D-21, D-23 — DIST-01 + DIST-02 gate)
  - FOUND: `fbe3bff` — ci(01-04): add release.yml (D-18, D-23 — manual zip on release: published)
- **Acceptance criteria invariants (sample of must-haves):**
  - `permissions: {}` present in lint.yml — OK
  - `permissions: {}` present in validate.yml — OK
  - `permissions: {}` present in test.yml — OK
  - `contents: write` present in release.yml — OK
  - `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd` referenced — OK (lint, test, validate, release)
  - `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b` referenced — OK (lint, test)
  - `actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` referenced — OK (lint pyright job)
  - `home-assistant/actions/hassfest@f6f29a7ee3fa0eccadf3620a7b9ee00ab54ec03b` referenced — OK (validate)
  - `hacs/action@dcb30e72781db3f207d5236b861172774ab0b485` referenced — OK (validate)
  - `softprops/action-gh-release@b4309332981a82ec1c5618f44dd2e27cc8bfbfda` referenced — OK (release)
  - `category: integration` + `ignore: brands` — OK (validate)
  - `yq -i -o json` + `github.event.release.tag_name` + `ha_pronote.zip` — OK (release)
  - `hacs.json:filename == 'ha_pronote.zip'` — OK (matches release.yml zip target)
  - All four files parse as valid YAML (`python3 -c "import yaml; yaml.safe_load(open(p))"`) — OK
  - All `uses:` SHA pins are exactly 40 hex chars — OK (verified by regex over all four files)
  - No `${{ secrets.* }}` references in release.yml — OK
- **Task 4 status:** NOT COMPLETE. Operator action required (see "Pending Operator Action" above). DIST-03 policy layer is unsatisfied until then.

## Self-Check: PASSED (for Tasks 1–3); Task 4 awaiting operator

## Known Stubs

None. All four workflows are functionally complete and will run successfully the first time they fire on a PR / release. No placeholder values, no TODOs, no mock data.

## TDD Gate Compliance

Not applicable — plan type is `execute` (not `tdd`). All three automated tasks have `tdd="false"`. No test commits required.

## Threat Flags

None. The four workflow files do not introduce security-relevant surface beyond what the plan's `<threat_model>` already lists. The release.yml `contents: write` elevation is the only non-default behavior, and it is explicitly enumerated in T-04-03 with a documented mitigation rationale (minimum scope for asset upload).

## Next Phase Readiness

- **Plan 01-05 (pre-commit hooks):** The pre-commit config will run `ruff format` then `ruff check --fix` then `pyright` then `codespell`. These tools and versions MUST agree with what `lint.yml` runs (ruff==0.15.1 from `requirements_test.txt`, pyright 1.1.409 from `package.json`, codespell==2.4.1 from `requirements_test.txt`). Cross-pin already established in Plan 01-01.
- **Phase 7 (release):** Cutting the first tag (e.g., `v0.1.0`) on the GitHub UI publishes a release event, which triggers `release.yml` automatically. No separate "release plumbing" plan is needed in Phase 7 — only the changelog / version bump narrative.
- **Phase 1 wave 2 completion:** Once the operator completes Task 4 (branch protection), DIST-03 is fully satisfied at both workflow and policy layers.
- **Operator handoff:** This worktree has no GitHub remote configured. After all worktrees in this wave are merged back to `main` and the orchestrator pushes to `tom333/ha-pronote`, opening any PR will trigger Lint + Validate + Test. The status checks must run at least once on a PR before they appear as required-status-check options in the GitHub Settings → Branches picker (per the operator instructions in Task 4).

---
*Phase: 01-foundations-skeleton*
*Tasks 1–3 completed: 2026-05-03*
*Task 4 (branch protection): pending operator action*
