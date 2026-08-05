---
phase: 01-foundations-skeleton
plan: 02
subsystem: infra
tags: [hacs, manifest, config-flow, integration-skeleton, home-assistant, pronotepy]

# Dependency graph
requires: []
provides:
  - HACS-recognisable repo skeleton (manifest.json + hacs.json)
  - Python package skeleton (custom_components/ha_pronote/) with DOMAIN single source of truth
  - Placeholder ConfigFlow that aborts cleanly with reason=not_implemented (resolves D-16 hassfest landmine)
  - Minimal strings.json key for the not_implemented abort
affects:
  - 01-03 (tests will assert against this manifest + DOMAIN constant + abort contract)
  - 01-04 (validate.yml runs hassfest + hacs/action against these files)
  - 03 (real ConfigFlow replaces placeholder; preserves domain=DOMAIN registration)
  - 07 (translations under translations/{en,fr}.json extend strings.json)

# Tech tracking
tech-stack:
  added:
    - "manifest.json schema for HA custom integration (domain, requirements, iot_class, quality_scale, integration_type, config_flow, version)"
    - "hacs.json schema (HACS 2.0.5, render_readme, zip_release)"
  patterns:
    - "DOMAIN as Final constant in const.py — single source of truth (anti-pattern guard: no hardcoded literal outside const.py)"
    - "Phase 1 placeholder ConfigFlow returning async_abort(reason=...) — never raise from async_step_user (avoids UnknownStep landmine)"
    - "manifest.json:config_flow=true paired with config_flow.py defining async_step_user (hassfest contract)"

key-files:
  created:
    - "custom_components/ha_pronote/manifest.json"
    - "custom_components/ha_pronote/__init__.py"
    - "custom_components/ha_pronote/const.py"
    - "custom_components/ha_pronote/config_flow.py"
    - "custom_components/ha_pronote/strings.json"
    - "hacs.json"
  modified: []

key-decisions:
  - "D-01 honored: domain=ha_pronote (FROZEN — must equal directory name)"
  - "D-04/D-05/D-06 honored: codeowners=[@tom333], documentation+issue_tracker URLs use repo hyphen variant (tom333/ha-pronote)"
  - "D-08 honored: hacs.json:homeassistant=2026.4.0 (HA-side floor for users)"
  - "D-12/D-13/D-14/D-15/D-17 honored: iot_class=cloud_polling, quality_scale=bronze, requirements pinned exactly (pronotepy==2.14.6, python-slugify==8.0.4), integration_type=hub, version=0.0.1"
  - "D-16 critical landmine resolved: config_flow=true paired with config_flow.py whose async_step_user returns async_abort cleanly — hassfest will accept skeleton; user clicking 'Add Integration' gets clean message, not stack trace"
  - "D-18 alignment: hacs.json:filename=ha_pronote.zip matches release.yml zip target (Plan 04)"

patterns-established:
  - "Single source of truth for DOMAIN: declared once in const.py, imported by __init__.py and config_flow.py — no other module hardcodes 'ha_pronote'"
  - "Phase 1 __init__.py is intentionally minimal — no async_setup, no async_setup_entry, no hass.data[DOMAIN] init (Phase 3 will use entry.runtime_data typed pattern per ARCHITECTURE Pattern 6)"
  - "Placeholder ConfigFlow contract: subclass ConfigFlow with domain=DOMAIN, declare VERSION=1, define async_step_user that returns async_abort (never raise) — compatible with future Phase 3 real implementation"
  - "strings.json:config.abort.<reason> i18n key shipped from day one so abort messages are human-readable (literal reason string is functional but ugly fallback)"

requirements-completed:
  - DIST-01
  - DIST-02

# Metrics
duration: 2min
completed: 2026-05-03
---

# Phase 1 Plan 02: HACS Integration Skeleton Summary

**HACS-recognisable Pronote integration package with locked manifest fields (pronotepy==2.14.6, iot_class=cloud_polling, quality_scale=bronze) and placeholder ConfigFlow that aborts cleanly to satisfy hassfest's config_flow.py landmine.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-03T06:09:29Z
- **Completed:** 2026-05-03T06:11:23Z
- **Tasks:** 3
- **Files created:** 6

## Accomplishments

- HACS skeleton in place: `custom_components/ha_pronote/` package + `hacs.json` at repo root, both parsing as valid JSON with all required schema keys present.
- DIST-01 satisfied: `manifest.json:domain == "ha_pronote"` matches the directory name (D-01 frozen invariant) and the constant in `const.py`.
- DIST-02 satisfied: manifest declares `iot_class=cloud_polling`, `quality_scale=bronze`, `integration_type=hub`, `config_flow=true`, `version=0.0.1`, exact-pinned requirements, codeowners, documentation, issue_tracker.
- D-16 critical landmine resolved: `config_flow.py` defines `HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN)` with `VERSION=1` and `async_step_user` returning `self.async_abort(reason="not_implemented")` — no `raise` statement, so HA's `_raise_if_step_does_not_exist` won't fire and the user gets a clean abort, not a stack trace.
- Single-source-of-truth pattern enforced: `DOMAIN` declared exactly once in `const.py`; `__init__.py` and `config_flow.py` both import it via `from .const import DOMAIN`. No hardcoded `"ha_pronote"` literal exists anywhere outside `const.py` and `manifest.json`.
- Anti-pattern guards held: `__init__.py` ships zero `async_setup`/`async_setup_entry` and no `hass.data[DOMAIN]` init (Phase 3 will use the typed `entry.runtime_data` pattern from ARCHITECTURE Pattern 6).

## Task Commits

Each task was committed atomically:

1. **Task 1: manifest.json + hacs.json (DIST-01, DIST-02)** — `5cb6f71` (feat)
2. **Task 2: Python package skeleton (const.py, __init__.py)** — `548fb67` (feat)
3. **Task 3: Placeholder ConfigFlow + strings.json (resolves D-16)** — `8ba977e` (feat)

_Plan metadata commit (this SUMMARY.md) follows separately._

## Files Created/Modified

- `custom_components/ha_pronote/manifest.json` — HA integration manifest valid against hassfest CUSTOM_INTEGRATION_MANIFEST_SCHEMA. Declares all 11 locked fields.
- `custom_components/ha_pronote/__init__.py` — Package marker. Re-exports `DOMAIN`. No `async_setup_entry` (placeholder ConfigFlow rejects all entries; Phase 3 owns runtime).
- `custom_components/ha_pronote/const.py` — Single source of truth: `DOMAIN: Final = "ha_pronote"`.
- `custom_components/ha_pronote/config_flow.py` — `HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN)` with `VERSION=1`; `async_step_user` returns `async_abort(reason="not_implemented")`.
- `custom_components/ha_pronote/strings.json` — Minimal i18n key for the `not_implemented` abort message (full translations deferred to Phase 7).
- `hacs.json` — HACS metadata at repo root: `homeassistant=2026.4.0`, `hacs=2.0.5`, `country=FR`, `render_readme=true`, `zip_release=true`, `filename=ha_pronote.zip`.

## Decisions Made

None - plan executed exactly as specified. All values are verbatim from RESEARCH.md §Code Examples (lines 580–699) and honor every locked decision (D-01, D-04, D-05, D-06, D-08, D-12, D-13, D-14, D-15, D-16, D-17) cited in CONTEXT.md.

## Deviations from Plan

None - plan executed exactly as written.

The verbatim content from RESEARCH.md §Code Examples reproduced cleanly in all six files; every acceptance criterion verified on first pass; no auto-fixes (Rules 1–3) needed; no architectural concerns (Rule 4) raised.

## Issues Encountered

None.

## Threat Model Compliance

All `mitigate` dispositions from the plan's `<threat_model>` are honored by the shipped artifacts:

- **T-02-01 (Tampering, requirements):** `pronotepy==2.14.6` and `python-slugify==8.0.4` exact pins present in `manifest.json:requirements`.
- **T-02-02 (Tampering, domain mismatch):** `manifest.json:domain == "ha_pronote"` matches directory name `custom_components/ha_pronote/` and `const.DOMAIN`. Plan 03 tests will regression-protect this; Plan 04 hassfest will independently verify.
- **T-02-03 (Information Disclosure, codeowners PII):** `codeowners == ["@tom333"]` (GitHub handle only, no real name).
- **T-02-04 (Denial of Service, broken UI):** `async_step_user` is defined and returns `async_abort` (no `raise` statement) — verified via AST scan.
- **T-02-06 (Tampering, zip filename mismatch):** `hacs.json:filename == "ha_pronote.zip"` matches D-18 release.yml target (Plan 04 will commit the zip step).

## User Setup Required

None - no external service configuration required for this plan. Phase 3 will introduce the real ConfigFlow (Pronote credentials), which is when user setup becomes relevant.

## Next Phase Readiness

- Plan 01-03 (test scaffold) can proceed: it will assert `DOMAIN == "ha_pronote"`, that `manifest.json:domain` matches, and that calling `hass.config_entries.flow.async_init(DOMAIN, context={"source":"user"})` returns `{"type":"abort","reason":"not_implemented"}`.
- Plan 01-04 (CI) can proceed: `validate.yml` will run hassfest and hacs/action against these files; both should pass since every schema constraint is honored.
- Phase 3 (auth) entry checklist note from the plan: when `__init__.py` later imports `homeassistant.config_entries.ConfigEntry`, the bare `python3 -c "from custom_components.ha_pronote import DOMAIN"` smoke-import will need to be re-baselined to `pytest tests/test_init.py::test_domain_constant_is_ha_pronote -x`. Documented for the Phase 3 plan.

## Self-Check: PASSED

Verified files exist, commits exist in `git log`, all acceptance criteria from the plan met. Detail:

- `custom_components/ha_pronote/manifest.json` — FOUND
- `custom_components/ha_pronote/__init__.py` — FOUND
- `custom_components/ha_pronote/const.py` — FOUND
- `custom_components/ha_pronote/config_flow.py` — FOUND
- `custom_components/ha_pronote/strings.json` — FOUND
- `hacs.json` — FOUND
- Commit `5cb6f71` (Task 1) — FOUND in `git log`
- Commit `548fb67` (Task 2) — FOUND in `git log`
- Commit `8ba977e` (Task 3) — FOUND in `git log`

---
*Phase: 01-foundations-skeleton*
*Completed: 2026-05-03*
