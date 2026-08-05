# HA-Pronote — Backlog

Remaining work toward v0.1.0 HACS release. Historical phase artifacts archived under `docs/history/planning/`.

## Shipped (v0.1.0-pre)

- **Foundations** — HACS-conform structure, manifest, CI workflows, pytest harness (2026-05-03)
- **API & Diff Layer** — HA-free `api/` + `diff/` packages; full pronotepy 2.14.6 wrapper, snapshot diff for cancellation/room/teacher swap; TZ-matrix (Europe/Paris × Pacific/Noumea) (2026-05-06)
- **Coordinator & First Sensor** — `DataUpdateCoordinator`, single seam `build_or_resume_client`, `ConfigFlow` per child with frozen `unique_id` = `{url_host}:{username}:{child_identifier}`, session export, AUTH-04 fallback (2026-05-15)
- **Diff, Events & Full Sensor Suite** — sensors (lessons today, grades, notifications), calendar, typed bus events (`pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_notification`), live empirical re-validation gate (2026-05-24)
- **Politesse** — adaptive polling 17h–20h, quiet hours, circuit breaker on AuthError/RateLimited with backoff, persistent notifications (2026-05-25)
- **Auth Lifecycle & Options** — reauth flow (one-click password update), reconfigure flow (URL/account_type editable, `unique_id` frozen), `HaPronoteOptionsFlow(OptionsFlowWithReload)` with 11 keys (refresh_interval, adaptive toggle, afternoon window, quiet hours, suspended/quiet cadence, nickname, school_tz), multi-child isolation (2026-05-30)

**Test suite:** 477 passed, 7 skipped, 0 failed.

## Next — Phase 7: Quality, Diagnostics & Distribution

**Goal:** v0.1.0 tag installable via HACS, diagnostics that don't leak secrets, repair issues that turn silent failures into actionable cards, full FR/EN translations. Bronze quality scale satisfied, Silver in sight.

**Depends on:** Phase 6 (done).

### Success Criteria

1. User can download a diagnostics dump from HA's UI; resulting JSON contains no `password`, `username`, `uuid`, `qr_code_uuid`, `token`, or full establishment URL — verified by automated redaction test
2. IP-suspended or repeatedly-failing auth → HA Repair Issue with localised title, description, and (for auth-fail) a button launching the reauth flow
3. HA UI fully localised: `strings.json`, `translations/fr.json`, `translations/en.json` cover config flow, options flow, errors, sensor names, repair issues — no untranslated keys
4. Daily GitHub Actions workflow installs `pronotepy@main` and reruns the test suite; opens an issue on regression. Tag → release workflow auto-zips `custom_components/ha_pronote/`
5. README documents HACS install, first-child config, polling rationale, copy-paste ApexCharts/Mushroom YAML automation example for the schedule-change event

### Items

- [x] **DIAG-01** — `async_get_config_entry_diagnostics` with `async_redact_data` for password, uuid, token, establishment URL
- [x] **DIAG-02** — Repair Issue on IP-ban (title, description, FAQ link)
- [x] **DIAG-03** — Repair Issue on repeated auth failure (button → reauth flow)
- [x] **I18N-01** — `strings.json` + `translations/fr.json` exhaustive sweep (config, options, errors, sensors, repair)
- [x] **I18N-02** — `translations/en.json` — now holds **French** (runtime fallback); project is French-only, no international version
- [x] **DIST-04** — Daily GitHub Actions canary: install `pronotepy@HEAD`, run full suite, open deduplicated issue on failure (`.github/workflows/upstream-canary.yml`)
- [x] **DIST-07** — README rewritten in French: HACS install, config UI, attribute schema, automation YAML, polling rationale
- [x] **DIST-09** — Release workflow verified: tag → `release: published` → `ha_pronote.zip` (built from `custom_components/ha_pronote/`, includes diagnostics/repairs/translations, no cruft) → HACS consumes `filename`. Already implemented; verified 2026-06-13, no changes needed.

**CI fix (prerequisite, discovered during Distribution planning):** `test.yml` had never passed — `pytest-homeassistant-custom-component==0.13.326` required `homeassistant==2026.5.0b0`, conflicting with the pinned `2026.4.4`, and runtime deps (`pronotepy`/`python-slugify`/`holidays`) were absent from the test install. Fixed: PHACC pinned to `0.13.325` + runtime deps mirrored into `requirements_test.txt`.

## v2 / Deferred

Items deliberately out of scope for v0.1.0 (tracked but not active):

- ENT-based authentication (Pronote via institutional SSO)
- `async_migrate_entry` from `entry.version=1 → 2` (skeleton present, no schema break yet)
- "Add another child" shortcut from existing entry (today: re-run Add Integration with different child_index)
- Hot-swap `school_tz` without entry reload (current reload overhead ~1s — acceptable)

## Conventions

- **Tech stack:** Python 3.14.2+ (HA 2026.3+ requirement), `pronotepy==2.14.6`, `uv` + `ruff` + `pyright`, `pytest-homeassistant-custom-component`
- **No silent exceptions on runtime/setup paths** — typed exceptions propagate raw. Config-flow form errors are the deliberate scoped exception (D-04 mapping via `_map_error` helper)
- **`data_updates=` merge in reauth/reconfigure commits** — never `data=` (would replace and lose `child_*`, `username`, etc.)
- **`unique_id` is frozen across reconfigure** — entity history is keyed on it. `inspect.getsource` regression guard locks this
- **Three permanent regression guards** in `tests/test_init.py` for the HA migration gotchas: no `add_update_listener`, no `vol.Strip`, no `OptionsFlow.__init__(config_entry)` assignment
