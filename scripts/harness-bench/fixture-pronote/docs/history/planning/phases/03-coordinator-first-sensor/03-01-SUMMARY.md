---
phase: 03-coordinator-first-sensor
plan: 01
subsystem: auth
tags: [config_flow, ha_pronote, auth, strings, slugify, voluptuous, urlparse, pronotepy]

# Dependency graph
requires:
  - phase: 01-foundations-skeleton
    provides: "HaPronoteConfigFlow scaffold (placeholder), DOMAIN constant, manifest.json with config_flow=true"
  - phase: 02-api-and-diff
    provides: "api.build_client(url, account_type, username, password) + typed errors AuthError/RateLimitedError/CommunicationError/PronoteIntegrationError"
provides:
  - "Real two-step config flow (async_step_user + async_step_pick_child) with executor-wrapped pronotepy auth"
  - "ConfigEntry data shape (8 keys: url, account_type, username, password, session, child_identifier, child_index, child_name) consumed by Plan 02 coordinator"
  - "Frozen child_identifier (slugify name with underscore separator) anchoring ENT-02 unique_id stability"
  - "unique_id format == f'{url_host.lower()}:{username}:{child_identifier}' with _abort_if_unique_id_configured guard"
  - "D-12 collision suffix (first 2 hex chars of pronotepy child identifier) for same-slug different-child cases"
  - "strings.json full Phase 3 schema (4 user-step fields + pick_child + 4 error keys + already_configured abort + lessons_today entity translation_key)"
affects: [03-02-coordinator, 03-03-sensor, 03-04-tests, 06-auth-lifecycle]

# Tech tracking
tech-stack:
  added:
    - "voluptuous (already in HA Core; first use in this project's config_flow)"
    - "python-slugify (declared in manifest.json since Phase 1; first import here)"
    - "urllib.parse.urlparse (stdlib; for D-05 host normalization)"
  patterns:
    - "Executor-wrapped pronotepy via hass.async_add_executor_job(partial(...)) (Pitfall 6) — 5 call sites: build_client, set_child, export_credentials"
    - "Form-level error mapping (errors=dict) instead of raising into UI (D-04) — never echoes server-side detail"
    - "Frozen identifier pattern: slugify at flow time, store verbatim in entry.data, never re-derive (D-11)"
    - "Collision-suffix pattern: hex-prefix from upstream identifier when slug clash (D-12)"

key-files:
  created: []
  modified:
    - "custom_components/ha_pronote/config_flow.py — REPLACED Phase 1 placeholder (29 lines, async_abort('not_implemented')) with the real 170-line two-step flow"
    - "custom_components/ha_pronote/strings.json — REPLACED 7-line legacy schema (single not_implemented abort key) with full Phase 3 schema (config + entity sections)"

key-decisions:
  - "D-01 verbatim: single async_step_user with vol.Url() + vol.In(['eleve','parent']) + str username/password; build_client wrapped in executor"
  - "D-02 verbatim: async_step_pick_child shown only when isinstance(client, ParentClient) and len(client.children) > 1"
  - "D-03 verbatim: vol.Url() validation only (no HEAD probe); pronotepy connect failure is the reachability signal"
  - "D-04 verbatim: 4-row error mapping AuthError->invalid_auth, RateLimitedError->ip_suspended, CommunicationError->cannot_connect, PronoteIntegrationError->unknown"
  - "D-05 verbatim: unique_id == f'{urlparse(url).hostname.lower()}:{username}:{child_identifier}' + async_set_unique_id + _abort_if_unique_id_configured"
  - "D-08 verbatim: entry.data has 8 keys (url, account_type, username, password, session, child_identifier, child_index, child_name)"
  - "D-10/D-11 verbatim: child_identifier = slugify(child_name, separator='_'), frozen at flow time, stored verbatim"
  - "D-12 verbatim: collision precheck against existing entries' child_identifier; suffix = first 2 hex chars of pronotepy child.identifier when collision detected"

patterns-established:
  - "Pattern: Config flow inter-step state stored as instance attributes (self._client, self._user_input) initialised in __init__"
  - "Pattern: Defensive abort('unknown') if pick_child reached without ParentClient (handles state corruption)"
  - "Pattern: existing_slugs computed from self.hass.config_entries.async_entries(DOMAIN) for cross-entry collision detection"

requirements-completed: [AUTH-01, AUTH-02, ENT-02]

# Metrics
duration: 4min
completed: 2026-05-07
---

# Phase 03 Plan 01: Config Flow Auth + strings.json Summary

**Real two-step Pronote config flow (URL + creds + optional pick_child) with executor-wrapped pronotepy auth, frozen slugify-based child_identifier, and full Phase 3 i18n schema replacing the Phase 1 not_implemented placeholder.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-07T01:20:19Z
- **Completed:** 2026-05-07T01:24:02Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced Phase 1's 29-line placeholder `HaPronoteConfigFlow` (which always aborted with `not_implemented`) with the real 170-line two-step flow defined by D-01..D-05 and D-10..D-13.
- Wired `build_client` via `hass.async_add_executor_job(partial(...))` so the sync pronotepy auth never blocks HA's event loop (Pitfall 6).
- Mapped all four `PronoteIntegrationError` subclasses to the D-04 form-level error keys (`invalid_auth`, `ip_suspended`, `cannot_connect`, `unknown`); zero `_LOGGER` calls leak credentials.
- Froze `child_identifier = slugify(child_name, separator="_")` at flow time per D-10/D-11/D-13 — anchors ENT-02 entity-id stability across every later phase.
- Implemented D-12 collision precheck: when the slug would collide with an existing entry's `child_identifier`, append the first 2 hex chars of the upstream `pronotepy.children[idx].identifier`.
- Replaced `strings.json` with the full Phase 3 schema: two flow steps, four user-step data fields, `pick_child.child_index`, four error keys, `already_configured` abort, and the `entity.sensor.lessons_today.name` translation_key (consumed by Plan 03's sensor).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the real Config Flow** — `a19fd64` (feat)
2. **Task 2: Replace strings.json with Phase 3 schema** — `e23cccb` (feat)

## Files Created/Modified

- `custom_components/ha_pronote/config_flow.py` — REPLACED. Module docstring cites D-01..D-05/D-10..D-13. Two `async_step_*` methods + `_create_entry` helper. 5 `async_add_executor_job` call sites (build_client + set_child + export_credentials wrappers). Ruff (lint + format) clean.
- `custom_components/ha_pronote/strings.json` — REPLACED. Legacy `config.abort.not_implemented` REMOVED. Top-level keys are exactly `{config, entity}`. JSON-valid, ends with newline.

## Hand-off Shape (Plan 02 reads)

The eight `entry.data` keys produced by `_create_entry` are the read-only contract Plan 02's coordinator consumes (D-08):

| Key | Type | Origin | Used by |
|---|---|---|---|
| `url` | str | user_input | coordinator's `build_client` retry, sensor `DeviceInfo.configuration_url` |
| `account_type` | "eleve"/"parent" | user_input | coordinator's `build_client` |
| `username` | str | user_input | coordinator's `build_client` retry |
| `password` | str | user_input | coordinator's AUTH-04 fallback when session is dead |
| `session` | dict | `client.export_credentials()` (executor-wrapped) | coordinator's first `Client.token_login(...)` attempt |
| `child_identifier` | str (slug) | `slugify(child_name, "_")` + D-12 suffix | sensor `unique_id`, device `identifiers` |
| `child_index` | int \| None | parent client only | coordinator's `set_child(idx)` after re-auth |
| `child_name` | str | `client.info.name` (eleve) or `client.children[idx].name` (parent) | sensor `DeviceInfo.name` |

## Decisions Made
None new — all 13 cited decisions (D-01..D-05, D-08, D-10..D-13, plus references to D-06 token capture and Pitfall 6 executor wrap) were already locked in `03-CONTEXT.md`. This plan implements them verbatim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Ruff `I001` import-sort autocorrection on first save**
- **Found during:** Task 1 (Write the real Config Flow)
- **Issue:** After writing the file with the import order specified in the plan code block, `ruff check` reported `I001 [*] Import block is un-sorted or un-formatted` (per the project's `[tool.ruff.lint.isort]` `force-sort-within-sections=true` config).
- **Fix:** Ran `ruff check --fix` followed by `ruff format` and re-ran both verifications. The fix only re-ordered imports within sections; the import set itself is unchanged. Final ordering matches the project's existing convention.
- **Files modified:** `custom_components/ha_pronote/config_flow.py`
- **Verification:** `ruff check` exits 0; `ruff format --check` reports "1 file already formatted"; all grep-based acceptance criteria still pass.
- **Committed in:** `a19fd64` (Task 1 commit, autocorrection applied before commit).

---

**Total deviations:** 1 auto-fixed (1 blocking — ruff autocorrection)
**Impact on plan:** Cosmetic only — the import set and module behaviour are byte-identical to the plan's code block; only intra-section ordering changed. No scope creep.

## Issues Encountered

**1. Plan-text bug: ruff invocation includes a `.json` argument**

The plan's `<verification>` block contains:
```bash
ruff check custom_components/ha_pronote/config_flow.py custom_components/ha_pronote/strings.json
```
Ruff is a Python linter; passing `strings.json` causes ruff to parse JSON-as-Python and emit spurious `B018` ("Found useless expression") and `D100` ("Missing docstring in public module") errors. The check **passes** when invoked on `config_flow.py` alone, which is the only file ruff is meant to lint here. This is a documentation bug in the plan's verification recipe, not a code defect. The `<verify><automated>` element on Task 1 correctly references `.py` only and passes.

**Resolution:** Logged in this Issues Encountered section. Recommended fix for the plan author: drop `strings.json` from the verification command in 03-01-PLAN.md. The Plan 04 test wave will validate `strings.json` via JSON parsing + key-shape assertions (already covered by Task 2's acceptance criteria).

**2. Local test environment lacks `pytest-homeassistant-custom-component`**

Verification step 5/6 in the plan (`pytest tests/test_no_ha_imports.py` and `pytest tests/test_manifest.py`) requires PHACC's `enable_custom_integrations` fixture. `test_no_ha_imports.py` ran clean (27 tests passing, 100%) — it doesn't need the HA fixture. `test_manifest.py` errored at fixture setup time with `fixture 'enable_custom_integrations' not found` because `pytest-homeassistant-custom-component` is not installed in `.venv`. This is a pre-existing environment limitation, not caused by this plan's changes (the file `manifest.json` was not modified). CI will run with the proper venv.

**Resolution:** Out of scope (Rule 3 fix attempt limit / scope boundary). Logged for future plans that need the HA test harness; tracked at the phase level via Plan 04 which will re-bootstrap the venv before adding tests.

**3. `pyright` not available locally**

The plan's verification step 2 calls `pyright custom_components/ha_pronote/config_flow.py`. Pyright is declared in `package.json` (`devDependencies.pyright = "1.1.409"`) but `node_modules` is not installed in this worktree. The plan acknowledged this is acceptable: "or only reports errors for symbols defined in Plan 02/03 files — that is acceptable for this plan since runtime files are not yet shipped; flag as a known cross-plan issue if any."

**Resolution:** Flagged as a known cross-plan issue. CI will run pyright with full deps. Manual review confirms the file's types are sound: `pronotepy.Client | pronotepy.ParentClient` discriminated by `isinstance`, `child_index: int | None` widened to `int` after the None-branch sets it to 0, all `.hass` and `.async_*` usages are HA-Core public API.

## Threat Surface Scan

No new security-relevant surface introduced beyond the plan's `<threat_model>`. Threats T-03-01 through T-03-07 are addressed exactly as specified:
- T-03-01 (URL tampering): `vol.Url()` + `urlparse(...).hostname.lower()` — applied.
- T-03-02 (info disclosure via errors): `errors["base"]` always uses static keys, never `.message` — applied.
- T-03-03 (logging): zero `_LOGGER.*` calls in this file — applied.
- T-03-04 (duplicate entry): `async_set_unique_id` + `_abort_if_unique_id_configured` with lower-cased host — applied.
- T-03-05 (DoS via unbounded retry): accepted per plan; Phase 5 owns runtime-side IP-suspended.
- T-03-06 (child_identifier change repudiation): identifier frozen in `entry.data["child_identifier"]` — applied.
- T-03-07 (cross-account child collision): unique_id includes username, scoping the slug — applied.

No threat flags raised.

## User Setup Required

None — no external service configuration required for this plan. Users will exercise the flow once Plans 02 + 03 ship runtime; Plan 04's tests validate the flow logic via mocked `build_client`.

## Next Phase Readiness

- **Plan 02 (coordinator)** can now read the 8-key `entry.data` shape from `_create_entry` to wire `build_client(url, account_type, username, password)` retry + `Client.token_login(session)` first-attempt.
- **Plan 03 (sensor)** can now consume `entry.data["child_identifier"]` (frozen slug) for the `unique_id` and `entry.data["child_name"]` for `DeviceInfo.name`.
- **Plan 04 (test wave)** owns the rewrite of `tests/test_init.py:test_config_flow_placeholder_aborts` (currently EXPECTED to fail because the placeholder is gone — the plan explicitly forbade deleting it in this plan to keep the diff per-file scoped).

**Known cross-plan issue:** `pyright` and `pytest-homeassistant-custom-component` are not installed locally. CI on `main` already runs them per Phase 1's workflows; the venv bootstrap is a Plan 04 prerequisite.

## Self-Check

**Verifying claims before proceeding.**

Files claimed created/modified:
- `custom_components/ha_pronote/config_flow.py`: FOUND (170 lines, ruff-clean)
- `custom_components/ha_pronote/strings.json`: FOUND (43 lines, JSON-valid)

Commits claimed:
- `a19fd64` (Task 1): FOUND in `git log`
- `e23cccb` (Task 2): FOUND in `git log`

End-of-plan invariants:
- `config_flow.py >= 100 lines`: 170 lines — PASS
- `strings.json` does not contain `not_implemented`: PASS
- Only `files_modified` changed (`git diff --name-only` since base): exactly `config_flow.py` + `strings.json` — PASS

## Self-Check: PASSED

---
*Phase: 03-coordinator-first-sensor*
*Completed: 2026-05-07*
