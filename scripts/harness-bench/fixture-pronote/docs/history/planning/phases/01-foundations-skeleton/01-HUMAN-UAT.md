---
status: partial
phase: 01-foundations-skeleton
source: [01-VERIFICATION.md]
started: 2026-05-03T07:30:00Z
updated: 2026-05-03T07:30:00Z
---

## Current Test

[awaiting human testing — these items need operator action; code-side verification is 28/28 PASSED]

## Tests

### 1. HACS install end-to-end (success criterion #1)
expected: HA-Pronote integration visible in HA → Devices & Services list. Adding the integration triggers the placeholder ConfigFlow which returns the localised "HA-Pronote is in early development. Account setup will be available in a future release." abort message — no stack trace.
how_to_run: Bring up the devcontainer (`.devcontainer.json`) on a contributor machine, install HACS in the HA frontend, add `https://github.com/tom333/ha-pronote` as a custom repository (category Integration), install, restart HA, confirm "HA-Pronote" appears in the integrations list.
why_human: Phase 1 success criterion #1 — requires running HA dev container + HACS frontend; no automated harness for HACS frontend in CI.
result: pending

### 2. Local pytest from clean checkout (success criterion #3)
expected: All 16 tests pass (2 in tests/test_init.py + 14 in tests/test_manifest.py). pytest exit code 0.
how_to_run: On a fresh checkout of the repository, run `uv pip install --system -r requirements_test.txt && pytest -q` from the repo root.
why_human: Local pytest cannot be exercised in this verification environment because pytest + pytest-homeassistant-custom-component are not installed in the system Python here. The committed test.yml workflow will run the suite on first push to GitHub. This is the human-runnable equivalent.
result: pending

### 3. CI gates block bad PRs (success criterion #2)
expected: GitHub blocks the merge button with status "Required checks failing: Lint/Validate/Test". Direct push to main is also blocked by the branch-protection rule.
how_to_run: After pushing the repo to GitHub at `tom333/ha-pronote`, open a pull request that intentionally fails one CI check (e.g., introduces a ruff violation) and confirm the PR cannot be merged through the GitHub UI.
why_human: Workflows are committed and CI-ready, but actually running CI requires the repo to exist on GitHub. hassfest+hacs/action+ruff+pyright+pytest cannot be observed running until first push.
result: pending

### 4. Branch protection wired (Plan 01-04 Task 4 — operator checkpoint)
expected: API call returns the three required status check contexts AND `enforce_admins.enabled == true`.
how_to_run: Configure GitHub branch protection on `main` for the pushed repo (web UI or `gh api`) per `01-04-SUMMARY.md` → "Pending Operator Action — Task 4". Verify with `gh api repos/tom333/ha-pronote/branches/main/protection --jq '.required_status_checks.contexts'` returning `["Lint","Validate","Test"]`.
why_human: Plan 01-04 Task 4 is `autonomous: false`, `type: checkpoint` — the operator-only DIST-03 policy layer. The repo doesn't exist on GitHub yet; cannot be automated from the orchestrator.
result: pending

### 5. Release workflow exercise (D-18, deferred to Phase 7)
expected: GitHub release page shows `ha_pronote.zip` attached; downloading it and inspecting `manifest.json` shows `"version": "v0.0.1"` (or the actual tag value).
how_to_run: After cutting the first git tag (e.g., `v0.0.1`) on a published GitHub Release, confirm `release.yml` runs and attaches `ha_pronote.zip` as a release asset; verify the zip's `manifest.json:version` matches the tag.
why_human: release.yml (D-18) only triggers on `release: published` and cannot be exercised before a real tag exists. Workflow body is correct (verified statically), but the actual yq+zip+upload chain runs on the GitHub runner — observable only after a tag is cut. Listed as deferred to Phase 7 in VALIDATION.md "Manual-Only Verifications".
result: pending

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
