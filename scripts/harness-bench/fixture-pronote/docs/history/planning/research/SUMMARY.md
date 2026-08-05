# Project Research Summary

**Project:** HA-Pronote — Home Assistant custom_component for Pronote (NC)
**Domain:** Home Assistant custom integration (HACS) wrapping a third-party scraping library (`pronotepy`) for the French school management system Pronote, with a personal-use anchor on Collège Jean Fayard, Dumbéa, Nouvelle-Calédonie (UTC+11, austral school calendar, direct Pronote login on `ac-noumea.nc`)
**Researched:** 2026-05-03
**Confidence:** HIGH

## Executive Summary

HA-Pronote is a single-household, cloud-polling HA integration whose **core value is one specific user story**: a reliable, actionable notification when a class is cancelled or modified for J or J+1. Everything else (grades, infos, multi-account) follows. The 2026 ecosystem is sharply prescribed — `pronotepy 2.14.x` is the only viable Python client (sync, in maintenance mode, no async fork), HA Core requires Python 3.14.2 since 2026.3, and `delphiki/hass-pronote` is the de-facto incumbent we're replacing. There is no architectural mystery here: the standard HA pattern (`ConfigFlow` + `DataUpdateCoordinator` per child + `runtime_data` + executor-wrapped pronotepy + pure-function diff layer firing typed bus events) is the textbook answer. The hard parts are operational, not architectural.

The recommended approach is to ship a **lean, opinionated v1** that fixes delphiki's documented papercuts (state >255 chars from `#157`, attribute payloads >16 KiB from `#136`, brittle reauth from `#133`, comma-decimal averages stored as strings from `#135`, period-multiplied entity explosion from `#134`/`#142`) while adding adaptive 17h–20h polling for the J+1 publication window — the only differentiator that directly serves the core value. Python 3.14.2 floor, HA 2026.4 floor, `pronotepy>=2.14,<3` (not pinned, with daily CI against `latest` to catch upstream drift), `ruff` + `pyright` + `pytest-homeassistant-custom-component` + `uv`, distributed as a HACS custom repository in v1 with `quality_scale: bronze` from day one and Silver as the MVP exit target.

The dominant risk is **getting the school's IP banned** — multiple academies have produced multi-week bans (`delphiki#128`), and a single demo ban kills the project's credibility. This forces conservative defaults (>=30 min polling, jitter, no week-end/vacation polling, NC austral calendar, circuit breaker on consecutive failures, hard-coded backoff up to 24h on the literal "Your IP address is suspended" message) and disciplined session reuse (`export_credentials` persisted across restarts, stable `device_name`) so the integration cannot mutually-kill the parent's own Pronote sessions. The second-largest risk is **upstream pronotepy breaking on every Pronote release** — mitigated by exception wrapping (typed `PronoteIntegrationError(reason=...)`), CI workflow against `pronotepy@main` daily, and clear user-facing messaging that distinguishes "your password is wrong" from "Pronote was updated, wait for pronotepy".

## Key Findings

### Recommended Stack

The stack is non-negotiable: HA mandates Python 3.14.2 from 2026.3, `pronotepy` is the only Python wrapper, and `pytest-homeassistant-custom-component` is the only viable test harness. Tooling tracks the modern HACS blueprint (`jpawlowski/hacs.integration_blueprint`): `ruff` (lint+format), `pyright` (typing via `node_modules`), `uv` (deps + venv), all CI actions pinned by SHA on `@main`/`@master` because tag releases are stale. The hard problem is the sync/async impedance mismatch — every single `pronotepy` call goes through `hass.async_add_executor_job`, no exceptions.

**Core technologies:**
- **Python 3.14.2+** — hard requirement of HA 2026.3+ (`REQUIRED_PYTHON_VER`); going lower locks you out of current HA
- **Home Assistant Core 2026.4.x floor** — first stable HA on Python 3.14, matches the 2026 blueprint
- **`pronotepy==2.14.6` (range `>=2.14,<3.0`)** — only viable Python Pronote client; sync-only via `requests`; pin loosely + daily CI against `latest` to absorb Pronote-side breakage
- **`DataUpdateCoordinator` (`TimestampDataUpdateCoordinator` subclass)** — standard HA polling primitive, gives `last_update_success_time` for free (used in diff bookkeeping)
- **`runtime_data` pattern** — typed `ConfigEntry[PronoteData]` alias, replaces the legacy `hass.data[DOMAIN][entry_id]` dict that delphiki still uses
- **Tooling: `uv` + `ruff` + `pyright` + `pytest-homeassistant-custom-component==0.13.326`** — matches HA Core's own `pyproject.toml`; reproducible CI with `actions/cache` on `.local/ha-venv`
- **CI: `home-assistant/actions/hassfest@<sha>` + `hacs/action@<sha>`** — both pinned on `main`/`master` by SHA (tags are stale and unused by the community)

Full details: `.planning/research/STACK.md`.

### Expected Features

The feature landscape is dominated by **one competitor** (`delphiki/hass-pronote`, 94 stars, actively maintained but with 77 open issues that read like a backlog of v1 differentiators). vingerha is deprecated. delphiki's contract — bus events, sensors per child, `DeviceInfo`, calendar entity — is the public norm. Our job is to ship the same shape with fewer papercuts and one clear functional differentiator (adaptive afternoon polling tied to J+1 publication).

**Must have (table stakes):**
- Config Flow (URL + parent/eleve + credentials, no ENT in v1) with reauth + reconfigure flows — without these, password changes break entries permanently (`delphiki#133`)
- Multi-account: one `ConfigEntry` per child, one device per child via `DeviceInfo(identifiers={(DOMAIN, child.identifier)})`
- `DataUpdateCoordinator` with HA-modern `runtime_data`, executor-wrapped pronotepy calls, default 30 min polling
- Sensor: emploi du temps J + J+1 (state = scalar count or next-lesson timestamp; attributes < 16 KiB; numeric only in state)
- Sensor: notes (state = `float` overall average — comma normalised to dot, `state_class=measurement`; attributes = N latest grades in ApexCharts-ready schema)
- Sensor: notifications/informations (state = unread count; attributes = N latest)
- `pronote_schedule_changed` typed bus event with diff payload (`change_type`, `day=today|tomorrow`, before/after) + `pronote_new_grade` + `pronote_new_information`
- Stable `unique_id = f"{entry_id}_{child.identifier}_{sensor_kind}"` + `has_entity_name = True` + translation keys
- `strings.json` + `translations/fr.json` + English fallback
- HACS-compliant repo (`manifest.json`, `hacs.json`, `info.md`, semver tags, hassfest+HACS validation in CI)
- Encrypted credential storage via `entry.data` only; no password in logs ever

**Should have (competitive differentiators):**
- **Adaptive 17h–20h polling for J+1 EDT** — the only feature that directly implements the project's core value; delphiki polls at constant 15 min and is therefore both more impolite and less effective at the actual job
- **Numeric `overall_average` sensor** (fixes `#135`) and **<16 KiB attribute discipline** enforced by CI assertion (fixes `#136`)
- **Diagnostics platform** with `async_redact_data` for `password`/`uuid`/`token`/`url` — HA Silver requirement; delphiki ships none
- **Repair issues** (`ir.async_create_issue`) for IP-ban + auth-fail — turns silent failures into actionable cards
- **No period-multiplied entities** — single `current_period` sensor + service for historical drill-down (anti-`#134`/`#142`)
- **Calendar entity** in v1.x (cheap, ~120 LOC, expected by HA users)

**Defer (v1.x then v2+):**
- Calendar entity, per-subject averages, event entities, schema migration scaffolding, brand logo PR (v1.x triggers)
- Devoirs, ENT support, QR-code auth, absences/punishments, menus, HACS default repo submission (v2+, per `PROJECT.md`)
- Bundled Lovelace card — explicitly out of scope; document ApexCharts/Mushroom YAML examples in README instead

Full details: `.planning/research/FEATURES.md`.

### Architecture Approach

A textbook HA cloud-polling integration with one twist: `pronotepy` is rigorously isolated behind a sync `api/` subpackage so the rest of the codebase never imports it. The `api/` and `diff/` subpackages have **zero HA imports** — they're plain Python tested in millisecond pytest runs. The coordinator is the only place that owns the executor boundary, the diff orchestration, the bus event firing, and the adaptive interval mutation. Entities are pure projections over `coordinator.data`. One coordinator per child, one config entry per child, sessions reused across restarts via `export_credentials`.

**Major components:**
1. **`api/` (sync, no HA imports)** — `client.py` builds pronotepy clients; `fetcher.py` returns plain dataclass `Snapshot`; `errors.py` defines typed exceptions (`AuthError`, `CommunicationError`, `RateLimitedError`, `ParseError`); `models.py` strips pronotepy back-references so snapshots are GC-friendly and serializable
2. **`diff/` (pure, no HA imports)** — `lessons.py`, `grades.py`, `notifications.py` take `(old, new)` snapshots and return `list[ChangeEvent]`; identity key (date, start, subject, teacher_initial) vs content key (canceled, room, status) separation handles the `bain3#311` cancellation-vs-room-change ambiguity
3. **`coordinator.py` — `PronoteDataUpdateCoordinator`** — one per child; owns `_async_update_data` (executor-wraps fetch, runs diff, fires `hass.bus.async_fire`), adaptive `update_interval` mutation via pure `compute_interval(now, options)`, circuit breaker, and translation of API errors to `ConfigEntryAuthFailed` / `UpdateFailed`
4. **`__init__.py` + `data.py`** — `runtime_data: PronoteData` typed via `type PronoteConfigEntry = ConfigEntry[PronoteData]`; thin orchestration only (`async_setup_entry`, `async_unload_entry`, `async_reload_entry`, optional `async_migrate_entry`)
5. **`config_flow.py`** — user / reauth / reconfigure / options steps; reauth asks only for the new password; options flow owns refresh interval, adaptive flag, afternoon interval, nickname
6. **`sensor.py` (+ later `binary_sensor.py`, `calendar.py`)** — declarative `EntityDescription` tuples + `CoordinatorEntity` subclasses reading `coordinator.data`; no business logic
7. **`diagnostics.py`** — `async_get_config_entry_diagnostics` returning `async_redact_data(snapshot, TO_REDACT)` — implemented in v1 (cheap insurance, Silver requirement)

Full details: `.planning/research/ARCHITECTURE.md`.

### Critical Pitfalls

These are the failure modes that have **already happened in production** for delphiki users. We design around them from day one rather than discovering them ourselves.

1. **IP ban from the school server (`#128`, multi-academy, multi-week recoveries)** — Defaults must be conservative: >=30 min polling, jitter +/-30s, no polling on week-end / nights / NC school vacations, circuit breaker on N=3 consecutive auth failures, explicit detection of the literal `Your IP address is suspended` message → exponential backoff to 24h cap + persistent HA notification, never a silent retry loop.
2. **Blocking calls in the event loop (`#85`)** — `pronotepy` is fully sync; every call MUST go through `hass.async_add_executor_job` (with `functools.partial` for kwargs). Use `zoneinfo.ZoneInfo("Pacific/Noumea")` not `pytz` (banned-API in HA Core). All HA timestamp work via `homeassistant.util.dt`.
3. **pronotepy breaks on Pronote upstream changes (`bain3#274`, `delphiki#94`/`#141`)** — Range pin (`>=2.14,<3.0`), wrap every pronotepy exception in a typed `PronoteIntegrationError(reason=...)`, daily CI against `pronotepy@main`, user-facing message that distinguishes "wrong password" from "Pronote was updated wait for pronotepy" — the misleading `CryptoError "Padding is incorrect"` has caused users to change passwords and self-ban.
4. **NC timezone + austral calendar (foundational)** — All datetime work via `dt_util.now()`/`dt_util.utcnow()`; localize pronotepy's naive datetimes via a config-driven `school_tz` (default `Pacific/Noumea`); 17h–20h window expressed in school tz; vacation calendar from vice-rectorat NC source (NOT métropole zones A/B/C); pytest matrix on `Europe/Paris` AND `Pacific/Noumea` to catch the angle-blind-spot of a NC author.
5. **Sensor state >255 chars and attributes >16 KiB (`#157`, `#136`)** — State = scalar only (counts, floats, short strings, ISO timestamps); attributes split per day/period; CI assertion `len(state) <= 255 and len(json.dumps(attrs)) <= 16384` against a fixture of a heavy class (50 lessons/week × 2 weeks). Non-negotiable from the first sensor commit.
6. **Unstable `unique_id` → duplicated entities after upgrade (`#157`/`#133` adjacent)** — Format is `f"{entry_id}_{child.identifier}_{sensor_kind}"` and is **frozen** before the first stable release; `async_migrate_entry` skeleton in place from day one even if no migration is needed yet; pytest fixture for the v1 → v(N) upgrade path.
7. **Mutual session kills + reauth dead-ends (`#133`, `#155`, `bain3#309`)** — Persist `client.export_credentials()` after every successful update into `entry.data`; reuse `Client(uuid=stored_uuid)` on restart so HA does ONE login per install lifetime, not per restart; stable `device_name = f"home-assistant-{entry_id[:8]}"` so users see/recognize/can revoke our session in their Pronote app; reauth flow asks only for the new password (table stake).

The full pitfall catalogue (10 critical + technical-debt patterns + integration gotchas + performance traps + security mistakes + UX pitfalls + recovery strategies + phase mapping) is in `.planning/research/PITFALLS.md` and is the primary source of acceptance criteria for the test suite.

## Implications for Roadmap

The architecture research already proposed a build order (Phases A→G). Reframed as product phases for the roadmap, with research-derived rationale:

### Phase 1: Foundations & Skeleton

**Rationale:** HA, HACS, and CI plumbing must work before any business logic — otherwise debugging is blind, and HACS validation failures late in the cycle force expensive rework. This phase is "nothing works yet but everything that runs is properly shaped."
**Delivers:** `manifest.json` + `hacs.json` + empty `__init__.py` returning `True`; `const.py` with `DOMAIN` and `PLATFORMS=[]`; minimal `config_flow.py` with the user step (no validation yet); `pyproject.toml` with `uv`, `ruff`, `pyright`; GitHub Actions running `hassfest` + `hacs/action` + `ruff` + `pytest`; `pre-commit`/`prek` hooks.
**Addresses:** "HACS-compliant repo structure", "CI: lint + tests + HACS validation", "French translations skeleton"
**Avoids:** Pitfall #6 (logger redaction baseline established before any login code is written), late-discovered hassfest schema errors, ruff/pyright config drift from HA Core
**Stack used:** `uv`, `ruff==0.15.1`, `pyright`, `pytest-homeassistant-custom-component==0.13.326`, `home-assistant/actions/hassfest@<sha>`, `hacs/action@<sha>`
**Architecture component:** repo skeleton + `__init__.py` + `const.py`

### Phase 2: API & Diff Layer (sync, HA-free)

**Rationale:** The `api/` and `diff/` subpackages contain the highest-value, most-tested code in the project. They have zero HA imports and run in plain pytest in milliseconds — building them first means we get the diff/event logic right under fast feedback, before tangling with HA's async harness. They also de-risk pronotepy: capturing real fixtures here proves the integration is feasible before we write a single coordinator.
**Delivers:** `api/errors.py` (typed exceptions); `api/models.py` (`Snapshot`, `Lesson`, `Grade`, `Information` dataclasses, frozen where possible, no pronotepy back-references); `api/client.py` (`build_client`, `test_login`, `export_credentials` wrappers); `api/fetcher.py` (`fetch_all(client, today) -> Snapshot`); `diff/lessons.py` + `diff/grades.py` + `diff/notifications.py` (pure functions returning `list[ChangeEvent]`); pytest fixtures from anonymized real Pronote responses (`pronote_snapshot_T0.json`, `T1_changed.json`).
**Addresses:** "Schedule-change detection", "Sensor: Emploi du temps", "Sensor: Notes (numeric)", "Sensor: Notifications", indirectly all event emissions
**Avoids:** Pitfall #2 (typed wrapper exceptions in place before any HA-side code consumes them), Pitfall #10 (identity key vs content key separation; explicit room-change vs cancellation handling per `bain3#311`; reorder no-op test cases) — diff has >90% coverage before it ever runs in HA
**Stack used:** `pronotepy==2.14.6`, plain pytest, `requests-mock` for fetcher tests
**Architecture component:** `api/` subpackage + `diff/` subpackage

### Phase 3: Coordinator & First Sensor (end-to-end loop)

**Rationale:** Wires Phase 2 into HA via the `DataUpdateCoordinator` + `runtime_data` pattern. A single live sensor proves the executor boundary works, the auth path works against real Pronote, and the polling cycle is non-blocking. This is the first phase whose output is demonstrably usable.
**Delivers:** `data.py` (`PronoteData` dataclass + `PronoteConfigEntry` type alias); `coordinator.py` v0 (executor-wraps `fetch_all`, no diff yet, no adaptive interval, translates errors to `ConfigEntryAuthFailed`/`UpdateFailed`); `entity.py` base class; `sensor.py` with ONE sensor (lessons-today count); `__init__.py` wired with `async_setup_entry` + `async_config_entry_first_refresh` + `async_forward_entry_setups`; `config_flow.py` actually validating credentials via `client.test_login()`.
**Addresses:** "Config Flow UI", "DataUpdateCoordinator architecture", "Encrypted credential storage", first sensor entity, "Stable `unique_id`"
**Avoids:** Pitfall #3 (executor boundary is the FIRST thing the coordinator does; pytest-homeassistant-custom-component flags blocking calls in CI), Pitfall #6 (no plaintext logging path is ever introduced — diagnostics redaction list is defined now even though diagnostics platform itself comes in Phase 7), Pitfall #8 (unique_id format frozen and documented in code comments)
**Stack used:** HA `DataUpdateCoordinator`, `runtime_data` pattern, `voluptuous` for the config-flow schema, `pytest-homeassistant-custom-component` `hass` fixture
**Architecture component:** `coordinator.py` + `__init__.py` + `entity.py` + minimal `sensor.py` + `config_flow.py` (user step only)

### Phase 4: Diff, Events & Full Sensor Suite (the core value)

**Rationale:** This is the phase where the project starts justifying its existence. The diff layer (built in Phase 2) is plugged into the coordinator's previous-snapshot bookkeeping; typed bus events fire; the three real sensors (EDT, notes, notifications) come online with the documented attribute schemas and CI-enforced size limits. The end of this phase is the first moment "modify a lesson in Pronote → notification on phone" works end-to-end.
**Delivers:** Coordinator integration of `diff_lessons`/`diff_grades`/`diff_notifications` with `previous = self.data` bookkeeping; `pronote_schedule_changed` + `pronote_new_grade` + `pronote_new_information` events with the documented payload schema; full sensor suite (timetable J + J+1, notes with numeric average, notifications with unread count); `DeviceInfo` per child; CI fixture asserting `state` <= 255 chars and JSON attributes <= 16 KiB on a heavy-class scenario; comma-decimal normalisation; documented ApexCharts attribute schema in README.
**Addresses:** "Schedule-change detection", "Sensor: EDT", "Sensor: Notes (numeric)", "Sensor: Notifications", "Pronote_schedule_changed event", "Numeric overall_average", "Attribute size guard", "ApexCharts schema", "Device per child"
**Avoids:** Pitfall #7 (state and attribute size assertions in CI), Pitfall #10 (diff plumbing is pure-function tested at Phase 2; events skip first cycle when `previous is None`), Pitfall #4 (all timestamps tz-aware via `dt_util`, school_tz config consumed in lesson sorting and "today" calculations)
**Stack used:** HA bus, `homeassistant.util.dt`, `python-slugify` for entity IDs
**Architecture component:** completes `coordinator.py` + `sensor.py` + the `diff/` integration

### Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker

**Rationale:** This phase is what makes the integration shippable to anyone other than the author. Conservative defaults, NC calendar awareness, and circuit-breaker logic protect every user from IP bans and 3 a.m. notifications. It builds on Phase 4 because the circuit breaker needs the typed exceptions, and the adaptive interval needs the diff loop to be already exercising the polling cycle.
**Delivers:** Pure `compute_interval(now, options) -> timedelta` with weekday + 17h–20h + quiet-hours + week-end + NC-vacation branches; coordinator mutates `self.update_interval` at end of `_async_update_data`; circuit breaker in `api/client.py` (consecutive-failure counter, exponential backoff to 24h cap, explicit "IP suspended" detection); jitter +/-30s on update interval; NC vacation calendar (hardcoded v1, ICS-based v1.x); pytest matrix on `Europe/Paris` AND `Pacific/Noumea`; coordinator surfaces persistent HA notification on long backoff.
**Addresses:** "Adaptive polling 17h–20h", "Polling interval (Options Flow)", "Polling intervalle paramétrable", "Vérification accrue 17h–20h"
**Avoids:** Pitfall #1 (IP ban — the entire phase is built around this), Pitfall #4 (NC calendar + Pacific/Noumea TZ baked in, not assumed), Pitfall #9 (quiet hours 22h–6h NC default; no events emitted during vacation; week-end policy)
**Stack used:** `homeassistant.util.dt`, `freezegun` / `pytest-freezer` for time-dependent unit tests, `zoneinfo`
**Architecture component:** Pattern 4 (adaptive update_interval) + Pattern 5 (circuit breaker on API client)

### Phase 6: Auth Lifecycle — Reauth, Reconfigure, Options, Multi-Account

**Rationale:** Once polling is safe, the next-largest UX failure mode is auth: changing password breaks the entry forever (the `delphiki#133` trap). This phase ships the full auth-lifecycle flows and the per-entry options that the polling layer needs to be user-tunable. Multi-account validation also belongs here because each child = one config entry, and the multi-entry coordinator independence is mostly free but must be tested.
**Delivers:** `OptionsFlow` (refresh_interval, adaptive_polling toggle, afternoon_interval, nickname, optional `school_tz`); `async_step_reauth` + `async_step_reauth_confirm` (password-only); `async_step_reconfigure` for URL/account-type migration without losing entity history; `entry.add_update_listener(reload_on_options_change)`; session persistence via `client.export_credentials()` after every successful poll, replayed on next setup via `Client(uuid=stored_uuid)`; stable `device_name = f"home-assistant-{entry_id[:8]}"`; multi-account scenario test (two entries, independent coordinators, one fails without affecting the other).
**Addresses:** "Reauth flow", "Reconfigure flow", "Multi-comptes (plusieurs enfants)", "Options Flow", "Optional child nickname", "Schema versioning + migration"
**Avoids:** Pitfall #5 (mutual session kills via export_credentials reuse + stable device_name), Pitfall #6 (validate before storing on reauth so a wrong password isn't persisted), Pitfall #8 (reconfigure preserves `unique_id` so entity history survives URL/ENT migration)
**Stack used:** HA `OptionsFlow`, `entity_registry.async_update_entity`, `ConfigEntry.async_update_entry`
**Architecture component:** completes `config_flow.py` + cross-cutting auth-lifecycle wiring in `coordinator.py` and `api/client.py`

### Phase 7: Quality, Diagnostics, Distribution

**Rationale:** Closes the loop on HA Quality Scale Bronze (already mostly satisfied by Phase 1–6) and reaches Silver. Diagnostics and Repair Issues turn the "next IP ban report" from a debugging nightmare into a one-click investigation. README and translations finalise the user-facing surface. Tagging v0.1.0 means HACS-installable as a custom repository.
**Delivers:** `diagnostics.py` with `async_redact_data(data, TO_REDACT)`; `ir.async_create_issue` for IP-ban + auth-fail (Repair Issues); `strings.json` + `translations/fr.json` + `translations/en.json` complete; full `README.md` with HACS install steps, conservative-polling rationale, multi-child guidance, ApexCharts/Mushroom YAML automation examples; quality_scale: bronze in `manifest.json`; `hacs.json` finalised; tag v0.1.0; CI quality gate (coverage threshold, blocking-call detection enabled, daily `pronotepy@main` workflow); release workflow auto-zipping `custom_components/pronote_nc/` into a release artifact.
**Addresses:** "Documentation README", "Tests unitaires", "Tests d'intégration", "CI GitHub Actions", "Diagnostics support" (Silver), "Repair Issues" (v1.x trigger), "HACS custom repo distribution"
**Avoids:** Pitfall #6 (diagnostics ship with redaction in place; no opportunity for a reporter to leak credentials into a public issue), Pitfall #2 (daily `pronotepy@main` CI workflow detects upstream regressions before users do), Pitfall #1 + Pitfall #9 (README explicitly explains the conservative defaults so users don't tighten them blindly)
**Stack used:** HA `diagnostics` platform, `homeassistant.helpers.issue_registry`, `actions/setup-python@v6`, `astral-sh/setup-uv@v8`, manual or `release-please`-style release workflow
**Architecture component:** `diagnostics.py` + repair-issue plumbing in `coordinator.py` + `translations/` + `.github/workflows/release.yml`

### Phase Ordering Rationale

- **Foundations first** so HACS validation, `hassfest`, and ruff/pyright are gates from commit #1 — late-discovered schema errors are the single biggest source of avoidable rework
- **API + diff before HA wiring** because they're pure Python tested in milliseconds; locking the diff semantics (especially the room-change vs cancellation distinction from `bain3#311`) under fast feedback is far cheaper than re-debugging it through HA's async harness
- **One sensor end-to-end before the full suite** to validate the executor boundary, runtime_data plumbing, and config-flow → coordinator → entity chain works in real HA on real Pronote — this is also when we discover any unique_id design mistakes while the cost of fixing them is zero
- **Politesse before auth lifecycle** because Phase 5's circuit breaker depends on Phase 4's typed exceptions, but conservative polling defaults are themselves the prerequisite for any wider testing (we can't ask anyone to install a polling-too-fast prototype)
- **Auth lifecycle before quality + distribution** so the v0.1.0 tag includes reauth + reconfigure (without these, every shipped version is a `delphiki#133` waiting to happen)
- **Quality + distribution last** because Bronze/Silver scoring depends on everything above being already in place; diagnostics & repair issues are LOW-cost additions on top of the mature exception hierarchy from Phase 5
- **No phase ships without** an attribute-size CI assertion (anti-`#136`), executor wrapping (anti-`#85`), tz-matrix tests (Europe/Paris + Pacific/Noumea), and the typed `PronoteIntegrationError` hierarchy — these are cross-cutting invariants, not features

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 4 (diff & events):** the `bain3#311` cancellation-vs-room-change ambiguity, the exact shape of pronotepy's `Lesson` object across pronotepy versions, and the Pronote `G` field semantics deserve a focused research pass with real captured fixtures — `/gsd-research-phase` recommended
- **Phase 5 (politesse):** the NC vice-rectorat school-calendar source (ICS feed availability, format, update cadence at `denc.gouv.nc` and `ac-noumea.nc`) is sparsely documented — `/gsd-research-phase` recommended to choose between hardcoded JSON v1 and a dynamic ICS scraper

Phases with standard, well-documented patterns (skip `/gsd-research-phase`):

- **Phase 1 (foundations):** `jpawlowski/hacs.integration_blueprint` is the canonical, copy-paste-ready reference — no further research needed
- **Phase 3 (coordinator & first sensor):** HA developer docs + `ludeeus/integration_blueprint` cover this exhaustively, and `delphiki/hass-pronote/coordinator.py` provides a 26-call-site executor-wrapping reference
- **Phase 6 (auth lifecycle):** HA Quality Scale Silver docs prescribe reauth/reconfigure verbatim; pronotepy's `export_credentials` is documented in the upstream README
- **Phase 7 (quality + distribution):** HA `diagnostics` and `issue_registry` docs are stable and exhaustive; HACS publish docs cover everything else

Phases that may need a brief targeted spike (lighter than full `/gsd-research-phase`):

- **Phase 2 (api & diff):** the pronotepy fixture-capture strategy and the snapshot stripping pattern (which delphiki had to add as `_strip_client_refs`) deserve a brief targeted check before committing

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified live against PyPI, GitHub master, and HA Core's `pyproject.toml` on the day of writing; HACS blueprint is current; `pronotepy 2.14.6` confirmed via direct `clients.py` source read (zero async, all `requests`-based); `pytest-homeassistant-custom-component 0.13.326` autoregenerated daily against HA 2026.5.0b0 |
| Features | HIGH | Based on direct source-code reading of `delphiki/hass-pronote v0.15.5` (`coordinator.py`, `sensor.py`, `calendar.py`, `config_flow.py`, `const.py`, `manifest.json`) plus parsing of 70+ open issues; HA Quality Scale documentation reviewed for Bronze/Silver/Gold/Platinum tier requirements |
| Architecture | HIGH | Pattern verified against HA developer docs (`integration_fetching_data`, `asyncio_working_with_async`, `config_entries_config_flow_handler`, `integration_events`), `ludeeus/integration_blueprint` (canonical, files read directly), and `delphiki/hass-pronote` in production (validates executor + diff + bus-event pattern); the only MEDIUM-confidence sub-point is Pattern 4 (mutating `self.update_interval`), which is widely used in HA core integrations but not officially contractual |
| Pitfalls | HIGH | Each pitfall is grounded in at least one filed issue against `delphiki/hass-pronote` or `bain3/pronotepy` (10 issues read in full: #85, #94, #128, #133, #136, #141, #151, #155, #157 + bain3 #274/#294/#309/#311), cross-referenced with HA developer docs and community threads (157 delphiki issues parsed) |

**Overall confidence:** HIGH — the four research files agree without contradiction, the de-facto incumbent's source code corroborates the architecture, and the dominant risks are documented as production incidents rather than theoretical concerns.

### Gaps to Address

- **NC school-calendar data source** — vice-rectorat publishes the calendar but the machine-readable format (ICS? JSON?) is not yet confirmed. Plan: hardcode 2026 NC academic year vacation dates in `const.py` for v1; spike the ICS feed during Phase 5 planning. If no ICS, accept yearly hand-update with a single-file PR.
- **`pronotepy` upstream stability under maintenance mode** — README confirms maintenance mode in 2026; bug fixes still being merged (last commit 2026-04-24). Risk that a future Pronote update lands without a corresponding pronotepy fix. Plan: daily CI workflow against `pronotepy@main` (Phase 7) to detect drift early; document a fork-and-patch escape hatch in CONTRIBUTING.md.
- **Pronote test instance availability for CI** — the public demo Pronote instance is rate-limited and intermittently down, unreliable for CI. Plan: capture anonymized fixtures from the author's real `katiramona.ac-noumea.nc` instance during Phase 2; commit them as JSON in `tests/fixtures/`; never rely on live Pronote in CI.
- **Memory leak observation window** — `delphiki#151` documents a real leak fixed by `_strip_client_refs`. Our `api/models.py` design avoids the root cause (no pronotepy back-references escape the `api/` subpackage) but a 24–72h soak test is the only way to confirm. Plan: optional long-running test job in CI (manual trigger) once Phase 4 lands.
- **HA brand assets PR cadence** — `home-assistant/brands` is gated by maintainer review with no SLA; logo is a v1.x nice-to-have, not blocking v1 ship. Plan: open the PR in parallel with Phase 7, treat merge timeline as out-of-band.

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md` — full stack research with verified PyPI/GitHub versions
- `.planning/research/FEATURES.md` — feature landscape, MVP definition, competitor analysis
- `.planning/research/ARCHITECTURE.md` — system overview, project structure, six architectural patterns, suggested build order
- `.planning/research/PITFALLS.md` — 10 critical pitfalls, technical debt patterns, integration gotchas, performance traps, security mistakes, UX pitfalls, recovery strategies
- HA Core `homeassistant/const.py` (Python 3.14.2 floor verified)
- HA Core `pyproject.toml` (ruff config, python-slugify pin verified)
- HA Developer Docs — DataUpdateCoordinator / Config Flow / Quality Scale / Async / Events / Diagnostics
- HACS publish docs — `manifest.json` + `hacs.json` schema
- GitHub: bain3/pronotepy — `clients.py` source-read (zero async, `requests`-based, sync), maintenance-mode README confirmed
- GitHub: delphiki/hass-pronote — production reference, `coordinator.py` 26-call-site executor pattern, `manifest.json`, 157 issues parsed
- GitHub: jpawlowski/hacs.integration_blueprint — modern 2026 HACS blueprint, all key files read
- GitHub: ludeeus/integration_blueprint — canonical HA template with `runtime_data` pattern

### Secondary (MEDIUM confidence)

- HA Community — Dynamic update_interval discussions (Pattern 4 widely adopted but not officially contractual)
- HA Community — DataUpdateCoordinator becoming unavailable after few hours
- HA Community — WTH passwords plain text in config_entries
- Vice-rectorat NC + DENC NC — calendrier scolaire (machine-readable format to confirm during Phase 5 planning)

### Tertiary (LOW confidence — to validate during implementation)

- pronotepy upstream pace under maintenance mode — to monitor via daily CI starting Phase 7
- Long-running memory profile — soak test to be designed during Phase 4

---
*Research completed: 2026-05-03*
*Ready for roadmap: yes*
