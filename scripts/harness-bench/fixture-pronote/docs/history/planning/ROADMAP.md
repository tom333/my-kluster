# Roadmap: HA-Pronote

## Overview

HA-Pronote is built bottom-up across seven phases that each end in a runnable, demonstrable artifact. We start with HACS/CI plumbing so every commit is gated by `hassfest`, `ruff`, and `pyright`. We then build the pure-Python `api/` and `diff/` layers in isolation (zero HA imports, millisecond pytest), wire them into HA via a single end-to-end sensor to validate the executor boundary, then expand to the full sensor suite + typed bus events that deliver the project's core value (a reliable J/J+1 schedule-change notification). Only once the data path works do we ship the politesse layer (adaptive polling, quiet hours, circuit breaker) that makes the integration safe to install on any school's network. Auth lifecycle (reauth, reconfigure, multi-child, options) lands before the v0.1.0 tag so password changes never brick an entry. Phase 7 closes the loop with diagnostics, repair issues, full translations, and the HACS release workflow.

Cross-cutting invariants apply to every phase from day one: every `pronotepy` call wrapped in `hass.async_add_executor_job`, every datetime tz-aware via `dt_util`, every error funnelled through a typed `PronoteIntegrationError(reason=...)` hierarchy, and every sensor under HA's hard limits (`state ≤ 255` chars, `attributes ≤ 16 KiB`) enforced by CI on a heavy-class fixture. The pytest matrix runs against `Europe/Paris` AND `Pacific/Noumea` to guard the NC-author blind spot.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundations & Skeleton** - HACS-compliant repo, CI gates, no-op `__init__.py` that loads in HA dev container
- [ ] **Phase 2: API & Diff Layer (HA-free)** - Pure-Python `api/` (pronotepy wrapper) + `diff/` (lessons/grades/notifs) tested in plain pytest
- [ ] **Phase 3: Coordinator & First Sensor** - End-to-end loop: Config Flow validates credentials, coordinator polls Pronote, one lessons-today sensor displays in HA
- [x] **Phase 4: Diff, Events & Full Sensor Suite** - The core value: typed bus events fire on schedule changes, plus full EDT/grades/notifs sensors and the calendar entity (completed 2026-05-24)
- [x] **Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker** - Conservative defaults safe to install: NC-aware calendar, 17h–20h tighter polling, IP-ban circuit breaker (completed 2026-05-25)
- [ ] **Phase 6: Auth Lifecycle & Options** - Reauth, reconfigure, multi-child support, Options Flow — no entry ever bricks on password change
- [ ] **Phase 7: Quality, Diagnostics & Distribution** - Diagnostics with redaction, repair issues, full translations, README, v0.1.0 HACS-installable tag

## Phase Details

### Phase 1: Foundations & Skeleton
**Goal**: A HACS-compliant repo that loads as an empty integration in HA, with CI gates blocking any merge that would break later phases.
**Depends on**: Nothing (first phase)
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-08
**Success Criteria** (what must be TRUE):
  1. User can clone the repo, point HACS at it as a custom repository, install it, and see "HA-Pronote" listed under integrations (no entry creation yet — just the package loads)
  2. Every PR runs `hassfest` + `hacs/action` + `ruff` + `pyright` + `pytest` in GitHub Actions and blocks merge on any failure
  3. Local dev workflow works: `uv sync && uv run pytest` from a clean checkout green-passes
  4. `manifest.json` declares `iot_class: cloud_polling`, `quality_scale: bronze`, `pronotepy>=2.14,<3.0`, codeowners, and issue tracker — `hassfest` validates clean
**Plans:** 5 plans
Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Repo bootstrap: pyproject.toml + ruff/pyright/pytest config, requirements_test.txt, package.json, .gitignore, LICENSE, README.md (Wave 1, DIST-08)
- [x] 01-02-PLAN.md — Integration skeleton: manifest.json, hacs.json, __init__.py, const.py, placeholder config_flow.py, strings.json (Wave 1, DIST-01 + DIST-02)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-03-PLAN.md — Test scaffolding: tests/__init__.py, tests/conftest.py (PHACC autouse), tests/test_init.py, tests/test_manifest.py (Wave 2, DIST-08)
- [x] 01-04-PLAN.md — CI workflows: .github/workflows/{lint,validate,test,release}.yml with SHA-pinned actions (Wave 2, DIST-03)
- [x] 01-05-PLAN.md — Local devloop: .devcontainer.json + .pre-commit-config.yaml mirroring CI (Wave 2, DIST-08)

**Cross-cutting constraints:**
- D-28: codespell ships from Phase 1 for FR/EN docstring spell-check
**UI hint**: no

### Phase 2: API & Diff Layer (HA-free)
**Goal**: Pure-Python `api/` and `diff/` subpackages that fetch a Pronote snapshot and produce typed `ChangeEvent`s, fully tested in plain pytest with zero HA imports.
**Depends on**: Phase 1
**Requirements**: EVENT-05, TIME-04, DIST-05
**Success Criteria** (what must be TRUE):
  1. `pytest tests/test_api/ tests/test_diff/` runs in under 2 seconds and passes — no HA harness involved
  2. A local CLI script (`scripts/snapshot.py`) authenticates against the author's real Pronote instance via `api.client.build_client` and dumps an anonymized JSON snapshot — proves pronotepy integration works end-to-end before any HA wiring
  3. Diff layer correctly distinguishes a cancellation (lesson canceled=True) from a room change (same identity key, different content key) on captured fixtures from `tests/fixtures/pronote_snapshot_T0.json` → `T1_changed.json`
  4. Diff layer coverage ≥ 90% (CI-enforced) and emits zero events when `previous is None` or when only lesson order changed
**Plans:** 4 plans
Plans:

**Wave 1**
- [x] 02-01-api-skeleton-and-spike-tooling-PLAN.md — api/ subpackage (errors/models/_strip/client/fetcher) + scripts/snapshot.py + .env.example + tests/test_api/ + tests/test_scripts/ (Wave 1, TIME-04)

**Wave 2** *(blocked on Wave 1)*
- [x] 02-02-real-pronote-spike-PLAN.md — Real-Pronote spike RUN: 3 anonymized fixture pairs (cancellation, room_change, teacher_swap) + SPIKE-FINDINGS-bain3-311.md (Wave 2, EVENT-05; **autonomous: false** — needs human .env + live server)

**Wave 3** *(blocked on Wave 2)*
- [x] 02-03-diff-layer-PLAN.md — diff/ subpackage (events/lessons/grades-stub/notifications-stub) reading SPIKE-FINDINGS + 11 synthetic fixtures + tests/test_diff/ (Wave 3, EVENT-05)

**Wave 4** *(blocked on Wave 3)*
- [x] 02-04-tz-matrix-and-coverage-gates-PLAN.md — tests/test_no_ha_imports.py + tests/test_fixtures.py + tz matrix test + pyproject.toml timeout/coverage-omit + .github/workflows/test.yml matrix axis + --cov-fail-under=90 (Wave 4, DIST-05)

**UI hint**: no

### Phase 3: Coordinator & First Sensor
**Goal**: User can add a Pronote account via Config Flow and see one live sensor (lessons-today count) updating on the polling interval — the executor boundary, runtime_data plumbing, and entity identity all proven end-to-end.
**Depends on**: Phase 2
**Requirements**: AUTH-01, AUTH-02, AUTH-04, AUTH-07, COORD-01, COORD-02, TIME-01, ENT-02, ENT-03, ENT-04
**Success Criteria** (what must be TRUE):
  1. User can click "Add Integration" → "HA-Pronote" → enter URL + parent/eleve + username + password → entry is created only if credentials validate against Pronote (wrong password produces a clear error in the form, no entry persisted)
  2. After HA restart, the entry comes back online without a fresh login (session restored from `client.export_credentials()` stored in `entry.data`); the device named `home-assistant-{entry_id[:8]}` is visible in the user's Pronote app
  3. One sensor `sensor.pronote_<child>_lessons_today` shows a numeric count that refreshes on the configured interval; HA Developer Tools shows zero "Detected blocking call" warnings during a poll
  4. `unique_id` format is `pronote_{child_identifier}_{sensor_kind}` — frozen and documented in code; `async_migrate_entry` skeleton is present (returns True) so future schema changes preserve entity history
**Plans:** 4 plans
Plans:

**Wave 1**
- [x] 03-01-PLAN.md — Real Config Flow + strings.json (`async_step_user` + `async_step_pick_child` + entry.data D-08 keys + ENT-02 child_identifier freeze) (Wave 1, AUTH-01 + AUTH-02 + ENT-02)
- [x] 03-02-PLAN.md — Runtime core: data.py (PronoteData) + coordinator.py (TimestampDataUpdateCoordinator + executor + token capture + silent recovery) + __init__.py (real async_setup_entry/unload/migrate) + const.py append + api/client.py:build_or_resume_client (Wave 1, AUTH-04 + AUTH-07 + COORD-01 + COORD-02 + ENT-04)

**Wave 2** *(blocked on Plan 02)*
- [x] 03-03-PLAN.md — entity.py (PronoteEntity base) + sensor.py (PronoteLessonsTodaySensor — state-only, unique_id frozen, mdi:school + MEASUREMENT) (Wave 2, TIME-01 + ENT-02 + ENT-03)

**Wave 3** *(blocked on Plans 01 + 02 + 03)*
- [x] 03-04-PLAN.md — Full HA-side test suite: conftest fixtures + test_init extension + test_config_flow + test_coordinator (incl. blocking-call detector for COORD-02/SC#3) + test_sensor + test_token_persistence (Wave 3, all 10 phase req IDs)

**UI hint**: yes

### Phase 4: Diff, Events & Full Sensor Suite
**Goal**: The moment HA-Pronote justifies its existence — modify a lesson in Pronote, get a typed `pronote_schedule_changed` event with a clean payload; full EDT, grades, notifications sensors and the calendar entity ship together with CI-enforced size limits.
**Depends on**: Phase 3
**Requirements**: TIME-02, TIME-03, GRADE-01, GRADE-02, GRADE-03, NOTIF-01, NOTIF-02, CAL-01, CAL-02, EVENT-01, EVENT-02, EVENT-03, EVENT-04, ENT-01
**Success Criteria** (what must be TRUE):
  1. User can modify or cancel a lesson in Pronote and within one polling cycle see a `pronote_schedule_changed` event in HA Developer Tools → Events with `change_type` (canceled/modified/teacher/room), `day` (today/tomorrow), and before/after lesson payloads — and zero events fire on the very first poll after restart
  2. Each child has a HA Device with `manufacturer="Pronote"`, `model=<class level>`, grouping a timetable sensor (J + J+1 attributes), grades sensor (numeric `overall_average` state, ApexCharts-shaped attributes), notifications sensor (unread count + recent items), and a calendar entity exposing lessons J–7 → J+14 with cancelled lessons visually distinct
  3. CI fixture for a heavy class (50 lessons/week × 2 weeks, 100 grades) asserts every sensor's `len(state) <= 255` and `len(json.dumps(attributes)) <= 16384` — no sensor falls back to `unknown` and no recorder warning fires
  4. New grades and new informations emit `pronote_new_grade` and `pronote_new_information` events with documented payload schemas; comma-decimal Pronote averages (e.g. "14,5") are normalised to numeric `14.5` in state
**Plans:** 7/7 plans complete
Plans:

**Wave 1** *(no interdependencies — pure-Python work + fixture generation)*
- [x] 04-01-PLAN.md — Diff layer bodies: fill `diff/grades.py` + `diff/notifications.py`; write `tests/test_diff/test_grades.py` + `tests/test_diff/test_notifications.py`; delete `tests/test_diff/test_stubs.py` (Wave 1)
- [x] 04-02-PLAN.md — Model + fetcher extensions: extend `models.Grade` (class_average/min/max/comment) + `models.Snapshot` (overall_average/period_name); extend `fetcher._grade_from_raw` + `fetch_all` to capture them in executor (Wave 1, GRADE-02)
- [x] 04-03-PLAN.md — Heavy fixture + probe: generate `tests/fixtures/synthetic/heavy_class.json` (126+ lessons, 100 grades, 30 infos); run `scripts/probe_config_flow.py` + fill `PHASE-4-PROBE-NOTES.md` — **autonomous: false** (Wave 1, TIME-03 + GRADE-03)

**Wave 2** *(blocked on 04-02 + 04-03)*
- [x] 04-04-PLAN.md — Constants + entity: append Phase 4 constants to `const.py` (EVENT_*, CLASS_LEVEL_ATTR, NOTIFICATIONS_WINDOW, GRADE_COMMENT_MAX_LEN); replace PLATFORMS; extend `entity.py` device_info with `model=class_label or None` (Wave 2, ENT-01)
- [x] 04-05-PLAN.md — Full sensor suite: add `_to_float` helper; add `extra_state_attributes` to `PronoteLessonsTodaySensor`; add `PronoteGradesSensor` + `PronoteNotificationsSensor`; update `async_setup_entry`; CI attribute-size gate (Wave 2, TIME-02, TIME-03, GRADE-01, GRADE-02, GRADE-03, NOTIF-01, NOTIF-02)
- [x] 04-06-PLAN.md — Calendar platform: create `calendar.py` (`PronoteCalendar` with `event` property + `async_get_events` + cancelled-lesson formatting); CI size extension (Wave 2, CAL-01, CAL-02)

**Wave 3** *(blocked on all prior plans)*
- [x] 04-07-PLAN.md — Coordinator event firing: capture `previous` before overwrite; add `_fire_diff_events`; wire `diff_grades` + `diff_notifications` + `diff_lessons`; 4 coordinator tests; full suite green (Wave 3, EVENT-01, EVENT-02, EVENT-03, EVENT-04)

**UI hint**: yes

### Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker
**Goal**: Conservative-by-default polling that's safe to install on any school's network — the integration cannot get the user's IP banned even under misconfiguration.
**Depends on**: Phase 4
**Requirements**: COORD-04, COORD-05, COORD-06, COORD-07, COORD-08, COORD-09, DIST-06
**Success Criteria** (what must be TRUE):
  1. Polling cadence visibly adapts: weekday 17h–20h NC tightens to ~15 min, week-ends and NC school vacations suspend polling entirely, quiet hours 22h–6h NC suppress all bus events — observable in the HA logs over a 24h window
  2. Three consecutive auth failures or a single `Your IP address is suspended` response triggers exponential backoff (up to 24h cap) and creates a persistent HA notification with actionable instructions; the coordinator does not retry in a tight loop
  3. The pytest matrix runs every test on `Europe/Paris` AND `Pacific/Noumea` and both pass; time-mocked tests prove `compute_interval(now, options)` returns the right `timedelta` for every branch (weekday/weekend/vacation/quiet/afternoon)
  4. Polling intervals carry ±30s jitter so multiple HACS users hitting the same school server don't synchronise their requests
**Plans:** 4 plans
Plans:

**Wave 1** *(parallel — HA-free politesse module + manifest/const groundwork)*
- [x] 05-01-PLAN.md — politesse.py (pure HA-free) + tests/test_politesse.py (tz-matrix) + tests/test_no_ha_imports.py extension (Wave 1, COORD-04 + COORD-05 + COORD-06 + COORD-09 + DIST-06)
- [x] 05-02-PLAN.md — manifest.json holidays==0.97 + const.py Phase 5 additions (D-18) + scripts/probe_nc_holidays.py + PHASE-5-PROBE-NOTES.md HUMAN-UAT (Wave 1, COORD-05) — **autonomous: false** (probe sign-off checkpoint)

**Wave 2** *(blocked on Wave 1 — coordinator wiring + i18n + integration tests)*
- [x] 05-03-PLAN.md — coordinator.py extension (atomic event gate + suspension/backoff short-circuits + _handle_failure + _reset_breaker_on_success + adaptive update_interval) + data.py holiday_dates field + __init__.py executor precompute + strings.json/translations/{en,fr}.json notification keys (fr.json CREATED) + tests/conftest.py mock_persistent_notification fixture + tests/test_coordinator.py 12 new tests (Wave 2, COORD-04 + COORD-05 + COORD-06 + COORD-07 + COORD-08 + COORD-09 + DIST-06)

**Wave 3** *(gap closure — fix 14 broken tests caused by Plan 05-03's should_poll short-circuit colliding with real-clock Pentecôte 2026-05-25)*
- [x] 05-04-PLAN.md — gap-closure: module-level autouse `_frozen_school_day` freezegun fixture in tests/test_coordinator.py + tests/test_sensor.py + tests/test_token_persistence.py pinned to Thu 2026-05-07 14:00 Pacific/Noumea + widen `test_update_interval_is_30_minutes` jitter envelope assertion + contingency `_handle_failure` production-fix arm for V-08 if the freezegun fix is insufficient (Wave 3, gap_closure=true, COORD-04 + COORD-05 + COORD-06 + COORD-07 + COORD-08 + COORD-09 + DIST-06)

**UI hint**: no

### Phase 6: Auth Lifecycle & Options
**Goal**: A user whose password changes can recover in one click; a user with two children sees two independent integrations; every per-entry knob is editable from the UI without recreating the entry.
**Depends on**: Phase 5
**Requirements**: AUTH-03, AUTH-05, AUTH-06, COORD-03, OPT-01, OPT-02, OPT-03, OPT-04
**Success Criteria** (what must be TRUE):
  1. User can add a second child via "Add Integration" again and the two coordinators run independently — one child's auth failure leaves the other's sensors fully functional
  2. After a Pronote password change, HA fires a reauth flow that asks ONLY for the new password (URL/account-type/username preserved); on success the entry resumes without losing any entity history or breaking existing automations
  3. User can open Options on an existing entry and change `refresh_interval` (15/30/60), toggle adaptive polling, set an afternoon interval, set an optional child nickname, and override `school_tz` — the coordinator reloads automatically without needing an HA restart
  4. User can change URL or account-type via the reconfigure flow without losing entity history (`unique_id` preserved across the migration)
**Plans:** 6 plans
Plans:

**Wave 1** *(parallel — pure foundations + read paths, no file overlap)*
- [x] 06-01-PLAN.md — const.py (DEFAULT_ADAPTIVE_POLLING_ENABLED, NICKNAME_MAX_LEN) + politesse.py (PolitesseOptions.adaptive_enabled + compute_interval short-circuit) + tests/test_politesse_tz_matrix.py (Wave 1, OPT-02 + OPT-03 + OPT-04)
- [x] 06-02-PLAN.md — coordinator._resolve_options (adaptive_polling_enabled read) + __init__.async_setup_entry (school_tz override via entry.options + ZoneInfo validation) + entity.device_info (nickname fallback) + tests (Wave 1, COORD-03 + OPT-03 + OPT-04)

**Wave 2** *(blocked on Wave 1 — config_flow.py reauth surface)*
- [x] 06-03-PLAN.md — Reauth flow (D-01..D-04): async_step_reauth + async_step_reauth_confirm + _REAUTH_SCHEMA + i18n keys (EN + FR) + 5 tests (Wave 2, AUTH-05)

**Wave 3** *(blocked on Wave 2 — config_flow.py reconfigure surface; file conflict with 06-03)*
- [x] 06-04-PLAN.md — Reconfigure flow (D-05..D-08): async_step_reconfigure + _RECONFIGURE_SCHEMA + set_active_child typed-wrap + child_identifier mismatch abort + i18n keys + 6 tests (Wave 3, AUTH-06)

**Wave 4** *(blocked on Wave 3 — OptionsFlow on top of all read paths + flows)*
- [x] 06-05-PLAN.md — OptionsFlow multi-step (D-09..D-16): HaPronoteOptionsFlow(OptionsFlowWithReload) + _POLLING_SCHEMA (9 fields) + _DISPLAY_SCHEMA (2 fields, lambda v: v.strip()) + _options_schema_defaults helper + async_get_options_flow + i18n keys + 7 tests + test_options_change_triggers_reload + test_no_deprecated_add_update_listener_in_production (Wave 4, COORD-03 + OPT-01 + OPT-02 + OPT-03 + OPT-04)

**Wave 5** *(blocked on Waves 2-4 — verifies multi-child invariants hold through all three mutation flows)*
- [x] 06-06-PLAN.md — Multi-child isolation tests (4 tests) — OptionsFlow / reauth / reconfigure / coordinator independence (Wave 5, AUTH-03)

**Cross-cutting:**
- D-12 REVISED (RESEARCH Critical Gotcha #1): OptionsFlowWithReload, NOT entry.add_update_listener (deprecated 2026-05-07)
- D-16 REVISED (Gotcha #2): nickname schema uses `lambda v: v.strip()`, NOT `vol.Strip` (doesn't exist)
- OptionsFlow __init__ (Gotcha #3): NO config_entry arg, NO self.config_entry assignment (read-only property since HA 2025.12)
**UI hint**: yes

### Phase 7: Quality, Diagnostics & Distribution
**Goal**: A v0.1.0 tag installable via HACS, with diagnostics that don't leak secrets, repair issues that turn silent failures into actionable cards, and full FR/EN translations — Bronze quality scale satisfied, Silver in sight.
**Depends on**: Phase 6
**Requirements**: DIAG-01, DIAG-02, DIAG-03, I18N-01, I18N-02, DIST-04, DIST-07, DIST-09
**Success Criteria** (what must be TRUE):
  1. User can download a diagnostics dump from HA's UI and the resulting JSON contains no `password`, `username`, `uuid`, `qr_code_uuid`, `token`, or full establishment URL — verified by an automated test that asserts redaction on a populated entry
  2. When the IP is suspended or auth has been failing repeatedly, a HA Repair Issue appears with a localised title, description, and (for auth-fail) a button that launches the reauth flow
  3. The HA UI displays the integration entirely in the user's locale: `strings.json`, `translations/fr.json`, and `translations/en.json` cover the config flow, options flow, errors, sensor names, and repair issues with no untranslated keys
  4. A daily GitHub Actions workflow installs `pronotepy@main` and reruns the test suite, opening an issue automatically on regression; on every git tag, a release workflow auto-zips `custom_components/ha_pronote/` as a release artifact
  5. A user reading the README can install via HACS, configure their first child, understand why polling defaults are conservative, and copy-paste a working ApexCharts/Mushroom YAML automation example for the schedule-change event
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundations & Skeleton | 5/5 | Complete | 2026-05-03 |
| 2. API & Diff Layer | 4/4 | Complete | 2026-05-06 |
| 3. Coordinator & First Sensor | 0/4 | Not started | - |
| 4. Diff, Events & Full Sensor Suite | 7/7 | Complete   | 2026-05-24 |
| 5. Politesse | 4/4 | Complete | 2026-05-25 |
| 6. Auth Lifecycle & Options | 0/6 | Not started | - |
| 7. Quality, Diagnostics & Distribution | 0/TBD | Not started | - |
