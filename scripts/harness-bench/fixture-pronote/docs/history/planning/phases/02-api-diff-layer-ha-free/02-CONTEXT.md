# Phase 2: API & Diff Layer (HA-free) - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure-Python `custom_components/ha_pronote/api/` and `custom_components/ha_pronote/diff/` subpackages that:

1. Wrap `pronotepy==2.14.6` behind a typed sync facade — `api/{client,fetcher,models,errors}.py` — that returns plain serializable dataclasses (`Snapshot`, `Lesson`, `Grade`, `Information`) and raises a typed exception hierarchy (`AuthError`, `CommunicationError`, `RateLimitedError`, `ParseError`).
2. Implement `diff/lessons.py` with comprehensive identity-vs-content key logic that distinguishes a cancellation from a room change and emits zero events on first poll (`previous is None`) or pure reorder.
3. Stub `diff/grades.py` and `diff/notifications.py` with `NewGrade` / `NewInformation` dataclass types only — Phase 4 fills the diff function bodies. The dataclass types are locked in Phase 2 so Phase 4 cannot drift.
4. Ship a one-shot `scripts/snapshot.py` CLI that authenticates against a real Pronote instance (the author's `katiramona.ac-noumea.nc`), captures three real T0/T1 fixture pairs (cancellation, room change, teacher swap), anonymizes them to `tests/fixtures/real/`, and produces a `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` document of observed pronotepy 2.14.6 semantics that the diff/lessons.py plan reads.
5. Run `pytest tests/test_api/ tests/test_diff/` in under 2 seconds with **zero HA imports** anywhere in `api/`, `diff/`, or their tests, on the **`Europe/Paris` AND `Pacific/Noumea` matrix** (the NC-author blind-spot guard), with **≥ 90 % branch coverage on the `diff/` subpackage** (CI-enforced).

**In scope (Phase 2 only):**
- `custom_components/ha_pronote/api/{__init__,client,fetcher,models,errors}.py`
- `custom_components/ha_pronote/diff/{__init__,lessons}.py` + dataclass-only stubs in `diff/grades.py`, `diff/notifications.py`
- `scripts/snapshot.py` (real-Pronote spike + anonymizer)
- `tests/fixtures/real/{cancellation,room_change,teacher_swap}_T{0,1}.json` (3 anonymized real captures)
- `tests/fixtures/synthetic/*.json` (combinatorics edge cases: empty→empty, reorder no-op, multi-change, vacation, first-poll-after-restart)
- `tests/fixtures/SPIKE-FINDINGS-bain3-311.md`
- `tests/test_api/`, `tests/test_diff/`
- `requirements_test.txt` extension: `requests-mock` for hermetic api/ tests
- pytest matrix configuration (`Europe/Paris` + `Pacific/Noumea` parameterized)
- ≥ 90 % coverage gate on `custom_components/ha_pronote/diff/` in CI

**Out of scope (deferred to later phases):**
- Coordinator (Phase 3 — needs `api/` + `data.py`)
- `data.py` runtime container & `PronoteConfigEntry` type alias (Phase 3)
- Any `__init__.py` async wiring beyond Phase 1's no-op (Phase 3)
- `diff/grades.py` and `diff/notifications.py` BODIES — only types ship in Phase 2 (Phase 4)
- Bus event firing on `hass.bus.async_fire` (Phase 4 — diff layer just returns `LessonChange` objects)
- Calendar entity, sensors, ConfigFlow validation against Pronote (Phase 3+)
- Token persistence / `client.export_credentials()` round-trip into `entry.data` (Phase 3)
- Adaptive interval, quiet hours, circuit breaker (Phase 5)
- Heavy-class fixture for HA size limits (Phase 4 — sensors are what hit the 16 KiB / 255 char ceilings)

</domain>

<decisions>
## Implementation Decisions

### Diff Scope (Area 1)
- **D-01:** Phase 2 ships the FULL `diff/lessons.py` module — identity-vs-content key matching, room-change-vs-cancellation discrimination, first-poll skip, multi-change handling. This is the hardest diff and the one ROADMAP success criterion #3 explicitly tests.
- **D-02:** Phase 2 ships `diff/grades.py` and `diff/notifications.py` with **typed dataclass stubs only** — `NewGrade` and `NewInformation` dataclasses are defined and exported, but the diff functions either don't exist yet or raise `NotImplementedError`. Phase 4 implements the bodies. Rationale: locks the type contract early so Phase 4 cannot drift; keeps Phase 2 focused on the bain3#311 bug-class.
- **D-03:** `NewGrade` and `NewInformation` types live in `custom_components/ha_pronote/diff/types.py` (or, if the planner prefers, alongside `LessonChange` in a single `diff/events.py`). `api/models.py` continues to host the `Lesson` / `Grade` / `Information` raw data types. Type-vs-event separation: `api/models.py` = "what we read from Pronote", `diff/events.py` = "what we emit on a transition". Planner picks the exact filename.
- **D-04:** The `>= 90 %` diff-layer coverage gate (DIST-05, ROADMAP success criterion #4) is measured against `custom_components/ha_pronote/diff/` as the line-coverage scope — `lessons.py` carries the bulk; the empty stubs in `grades.py` / `notifications.py` are excluded from the coverage scope (via `# pragma: no cover` on the `NotImplementedError` raisers, or via `[tool.coverage.run] omit = ["*/diff/grades.py", "*/diff/notifications.py"]` until Phase 4). Planner picks one of those two mechanics.

### Diff Algorithm — Identity, Content, and bain3#311 (Area 2)
- **D-05:** **Spike-first.** The first plan slice in Phase 2 is a real-Pronote spike — NOT the diff/lessons.py implementation. The spike runs `scripts/snapshot.py` against the author's instance, captures 3 fixture pairs covering: (a) a real lesson cancellation, (b) a real room change, (c) a real teacher swap. The output is the 3 fixture pairs in `tests/fixtures/real/` AND a written analysis document `tests/fixtures/SPIKE-FINDINGS-bain3-311.md`.
- **D-06:** `SPIKE-FINDINGS-bain3-311.md` documents what pronotepy 2.14.6 *actually* returns for each scenario — including the exact field shapes for `canceled`, `status`, paired-vs-unpaired lessons at the same datetime, teacher representation under substitution. This is the source of truth that subsequent diff plans read. Pitfall 10 / PITFALLS.md §"Pitfall 10" is the *prior hypothesis* — the spike either confirms or refines it.
- **D-07:** The diff/lessons.py implementation plan slice **depends on** D-05's spike output. Order is: (plan 02-01 = api/ skeleton + scripts/snapshot.py + spike + SPIKE-FINDINGS) → (plan 02-02 = diff/lessons.py reading the findings). Planner enforces this dependency in the Plans section.
- **D-08:** Identity key starting hypothesis (subject to spike confirmation): `(date, start_time, end_time, subject)` — drop `teacher_initial` from identity since substitute teachers are a *content* change ("teacher swap" is one of the four `change_type` values per ROADMAP Phase 4 success criterion #1: `canceled / modified / teacher / room`). Content key starting hypothesis: `(canceled, status, classroom, teacher_full_name)`. **Final keys are spike-locked, not pre-locked.**
- **D-09:** The four `change_type` values produced by `diff_lessons` are frozen by ROADMAP Phase 4 success criterion #1: `canceled`, `modified`, `teacher`, `room`. Phase 2 emits `LessonChange` dataclasses with one of those four values; Phase 4 routes them onto `hass.bus.async_fire("pronote_schedule_changed", ...)`. The exact JSON payload schema for the bus event (per ARCHITECTURE.md Pattern 3) is locked here so Phase 4 only routes — Phase 2 already produces the right shape.

### Fixture Sourcing (Area 3)
- **D-10:** Hybrid fixture layout. `tests/fixtures/real/` holds the 3 anonymized real captures from the spike (cancellation, room_change, teacher_swap). `tests/fixtures/synthetic/` holds hand-crafted JSON for combinatorics edge cases that real-Pronote can't reliably reproduce on demand: (a) empty → empty (vacation), (b) identical lessons reordered → no events, (c) multiple changes in one poll, (d) `previous is None` first-poll-after-restart, (e) lesson removed (period rollover noise — should be silent), (f) lesson added.
- **D-11:** Both fixture roots conform to the **same JSON schema** — the `Snapshot` dataclass's `to_dict()` shape. Synthetic fixtures are authored manually but must round-trip through `Snapshot.from_dict()` cleanly so a refactor of the dataclass shape forces every fixture to be revalidated in CI (planner adds a `tests/test_fixtures.py` schema-roundtrip test).
- **D-12:** `scripts/snapshot.py` doubles as the anonymizer. It reads real credentials from `.env` (or env vars) and outputs both raw + anonymized JSON. The anonymizer replaces: child first/last names → `Eleve Test`, teacher names → `M. Prof / Mme Profa / ...`, classroom IDs → `Salle A1 / B2 / ...`, school URL → `pronote.example.fr`, `establishment` field → `Établissement Test`, any UUIDs → fixed placeholders. **Only the anonymized output is git-committed.** Raw output is gitignored.
- **D-13:** `scripts/snapshot.py` is a **one-shot dev tool**, not a tested code surface. It lives in `scripts/`, not `custom_components/`. It is excluded from `ruff` strict checks, from `pyright`, and from coverage. A single integration test in `tests/test_scripts/test_snapshot.py` smoke-tests that the anonymization function is deterministic and removes all PII from a fixture pair (i.e. tests the anonymizer, not the network roundtrip).
- **D-14:** A `.env.example` ships at repo root documenting the required env vars (`PRONOTE_URL`, `PRONOTE_USERNAME`, `PRONOTE_PASSWORD`, `PRONOTE_ACCOUNT_TYPE`). README documents the spike workflow ("how to refresh fixtures when Pronote breaks").

### Snapshot Fetch Window (Area 4)
- **D-15:** `api.fetcher.fetch_all(client, today, school_tz)` returns a `Snapshot` covering **J−7 → J+14** from day 1 — wide enough that Phase 4's Calendar entity (CAL-01) reuses the exact same fetch surface without refactor.
- **D-16:** `Snapshot` exposes convenience slice properties: `snapshot.lessons_today: list[Lesson]` and `snapshot.lessons_tomorrow: list[Lesson]` (both filtered from the wider `snapshot.lessons: list[Lesson]`). `diff/lessons.py` operates on the slices, not the full window. Phase 4's Calendar entity reads `snapshot.lessons` directly.
- **D-17:** `today` is passed in as a `date` argument (NOT computed inside `fetch_all` from `datetime.now()`) — keeps the function pure-deterministic for testing and avoids any `dt_util` dependency. The coordinator (Phase 3) injects `today=dt_util.now(school_tz).date()`.
- **D-18:** `school_tz` is also passed in as a `zoneinfo.ZoneInfo` argument — `fetch_all` uses it to localize the naive `datetime` objects pronotepy returns. **No `pytz`** (CLAUDE.md anti-pattern, Phase 1 D-31). **No global `school_tz` constant** — always passed in, default `ZoneInfo("Pacific/Noumea")` lives in const.py / config_flow only, NOT in `api/`. Pure-Python `api/` has no ambient state.

### Pure-Python Boundary (Cross-cutting)
- **D-19:** **Zero `homeassistant.*` imports** in `api/` or `diff/` or their tests. Enforced by `tests/test_no_ha_imports.py` (a static check that walks `custom_components/ha_pronote/{api,diff}/` and asserts no module imports start with `homeassistant`). Same check on `tests/test_api/` and `tests/test_diff/`.
- **D-20:** `api/` and `diff/` import only stdlib (`datetime`, `zoneinfo`, `dataclasses`, `typing`, `enum`, `json`) plus `pronotepy` (api only) plus `python-slugify` (api/client.py for child slug). NO `aiohttp`, NO `requests` directly (per CLAUDE.md / Phase 1 D-32 — only via pronotepy), NO `dt_util`, NO `voluptuous`.
- **D-21:** `api/client.py` exposes `build_client(url, account_type, username, password) -> pronotepy.Client | pronotepy.ParentClient`. **No `pronotepy.ent.*` imports** (Phase 1 D-33, PROJECT.md key decision: Pronote direct only in v1). The function returns the appropriate pronotepy client subclass for the requested `account_type` ("eleve" → `Client`, "parent" → `ParentClient`). For parent accounts, child selection (`set_child(...)`) lives in `api/fetcher.py` and accepts a `child_index_or_identifier` argument — Phase 3's coordinator decides which child to fetch.

### Error Hierarchy & Cross-cutting Invariants (Cross-cutting)
- **D-22:** `api/errors.py` defines:
  - `PronoteIntegrationError(reason: ErrorReason, message: str)` — the cross-cutting wrapper from CLAUDE.md.
  - `class ErrorReason(StrEnum)`: `AUTH_FAILED`, `IP_SUSPENDED`, `PROTOCOL_BROKEN`, `SERVER_DOWN`, `SESSION_EXPIRED`, `RATE_LIMITED`, `PARSE_ERROR`.
  - Convenience subclasses for HA mapping: `AuthError(PronoteIntegrationError)`, `CommunicationError(PronoteIntegrationError)`, `RateLimitedError(PronoteIntegrationError)`, `ParseError(PronoteIntegrationError)` — each forces the appropriate `ErrorReason` in `__init__`.
  - The literal pronotepy message `Your IP address is suspended` (PITFALLS.md §"Pitfall 1") is detected in `api/client.py` (and/or `api/fetcher.py`) and surfaced as `RateLimitedError(reason=IP_SUSPENDED)` — Phase 5 wires this into the long-backoff persistent-notification flow; Phase 2 just guarantees the typed exception is raised.
- **D-23:** Every `pronotepy` field that is a `datetime` returned by the server is **localized to `school_tz`** before storage in our dataclass — pronotepy returns naive datetimes in school local time (per PITFALLS.md §"Pitfall 4"). Localization happens in `api/fetcher.py` at parse time, NOT in `api/models.py` constructors (constructors stay reach-free). All `datetime` fields on `Lesson` / `Grade` / `Information` dataclasses are tz-aware (TIME-04). A unit test asserts that no fixture has a naive datetime after `Snapshot.from_dict()`.
- **D-24:** `api/fetcher.py` calls the `_strip_client_refs` pattern from `delphiki/hass-pronote` after every pronotepy fetch — pronotepy attaches large `client` back-references on every `Lesson` / `Grade` object, which leaks memory and prevents JSON serialization. The fetcher's job is to walk the returned objects and copy the relevant fields into our plain dataclasses, dropping the back-refs. ARCHITECTURE.md "Phase B step 8" calls this out as a "non-trivial gotcha worth budgeting for".

### Tests, Tooling & CI (Cross-cutting)
- **D-25:** `tests/test_diff/test_lessons.py` is parameterized over the **timezone matrix** `("Europe/Paris", "Pacific/Noumea")` — every diff scenario runs on both. The fixture-local `school_tz` is part of each fixture file (a top-level `"school_tz": "Pacific/Noumea"` field). The test fixture loader rebuilds tz-aware datetimes from the fixture's `school_tz`. This is the NC-author blind-spot guard (ROADMAP cross-cutting invariant; DIST-06 lands officially in Phase 5 but the matrix STARTS in Phase 2).
- **D-26:** `requests-mock` (already a transitive dep via PHACC) is added explicitly to `requirements_test.txt` for `tests/test_api/test_client.py` and `tests/test_api/test_fetcher.py` — hermetic mocking of pronotepy's underlying `requests.Session`. No demo Pronote instance contact in CI (CLAUDE.md guidance).
- **D-27:** Coverage is enforced in CI via `pytest --cov=custom_components/ha_pronote/diff --cov-fail-under=90` in the existing `.github/workflows/test.yml` (added by Phase 1 D-22). Phase 2's planner appends the `--cov` flag — Phase 1 already proves the workflow runs pytest. The test workflow runs each timezone matrix branch as a separate job (or matrix axis) so coverage reports are merged.
- **D-28:** Sub-2-second runtime gate (ROADMAP success criterion #1) — `pytest tests/test_api/ tests/test_diff/` runs in under 2 s on a clean checkout. `pytest-timeout==2.4.0` (transitive via PHACC) enforces a per-test 1 s timeout in `pyproject.toml [tool.pytest.ini_options]` so a single slow test fails CI loudly.

### Claude's Discretion
The user delegated these sub-decisions to the planner. Recommended defaults to apply unless the planner finds a stronger argument:

- **C-01:** Filename for `LessonChange` / `NewGrade` / `NewInformation` dataclasses — D-03 leaves it open between `diff/types.py`, `diff/events.py`, or co-located in each module. RECOMMEND `diff/events.py` (single import surface, mirrors the "this is what we emit" mental model). Planner can also split per-module if the type list grows.
- **C-02:** Coverage exclusion mechanic for grades/notifications stubs (D-04) — RECOMMEND `[tool.coverage.run] omit` in `pyproject.toml` over `# pragma: no cover` (cleaner, single source of truth, easy to revisit in Phase 4).
- **C-03:** Anonymization implementation in `scripts/snapshot.py` (D-12) — RECOMMEND a `replacements: dict[str, str]` config + a single `walk_and_replace(obj, replacements)` recursive function. Avoid regex-based redaction; explicit name-list is brittle but auditable. Planner can suggest a `faker`-based approach if the brittleness shows up.
- **C-04:** Whether `account_type` is an `enum.StrEnum` or a `Literal["eleve", "parent"]` — RECOMMEND `Literal` (no enum import, plays nicely with `voluptuous` schemas Phase 3 will write, and pronotepy itself has no enum equivalent).
- **C-05:** Where the `_strip_client_refs` walker lives (D-24) — RECOMMEND `api/_strip.py` as a private helper imported only by `api/fetcher.py`. Tests in `tests/test_api/test_strip.py` against a fixture that has back-refs.
- **C-06:** Whether to ship `python-slugify` *use* in Phase 2 or just keep it declared in `manifest.json` — RECOMMEND lazy: only `api/client.py` may need it for `child_slug` derivation, and only if multi-child happens in the spike. If the parent spike account has no other child or the spike target is `eleve`, defer the import to Phase 3.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Core value, constraints, "From scratch (not fork)", "Pronote direct only in v1 (no ENT)" key decisions
- `.planning/REQUIREMENTS.md` — Phase 2 covers TIME-04, EVENT-05, DIST-05; cross-cutting tracker for AUTH-04 (token persistence, Phase 3 owner) and CAL-01 (J−7→J+14 window, Phase 4 owner)
- `.planning/ROADMAP.md` §"Phase 2: API & Diff Layer (HA-free)" — Goal, 4 success criteria, "depends on Phase 1" gate, cross-cutting invariants in ROADMAP Overview
- `CLAUDE.md` — Tech stack (Python 3.14.2, HA 2026.4+, pronotepy 2.14.6 EXACT pin, ruff/pyright/uv); the "What NOT to Use" table is binding (NO `async_timeout`, NO `pytz`, NO direct `requests`, NO `pronotepy.ent`, NO monkey-patching, NO hardcoded URL); cross-cutting invariants (executor boundary, tz-aware via `dt_util`, `PronoteIntegrationError(reason=...)` hierarchy, sensor size limits enforced on heavy-class fixture, Paris+Nouméa pytest matrix)

### Prior phase context
- `.planning/phases/01-foundations-skeleton/01-CONTEXT.md` — Phase 1 decisions still binding in Phase 2:
  - **D-14:** `pronotepy==2.14.6` exact pin in `manifest.json` requirements
  - **D-30:** NO `async_timeout`
  - **D-31:** NO `pytz` — use `zoneinfo.ZoneInfo`
  - **D-32:** NO direct `requests` (only via pronotepy)
  - **D-33:** NO `pronotepy.ent.*` modules
  - **D-34:** NO hardcoded `katiramona.ac-noumea.nc` URL — all URLs flow through the API surface as parameters
  - **D-35:** NO monkey-patching of pronotepy
  - **D-26 / D-27:** ruff (lint+format) + pyright (basic mode) configured against `target-version = "py314"`
  - **D-29:** `pytest-homeassistant-custom-component` already wired with `asyncio_mode = "auto"` — Phase 2 tests are plain pytest (no HA fixture needed) but PHACC's transitive deps (pytest, pytest-asyncio, pytest-cov, pytest-timeout, freezegun) are ALL available
- `.planning/phases/01-foundations-skeleton/01-PLAN.md` and 01-{01..05}-PLAN.md — Phase 1 plans for surrounding-file context (the actual `manifest.json`, `pyproject.toml`, `tests/conftest.py` Phase 2 will extend live there)

### Research already done
- `.planning/research/STACK.md` — Why `pronotepy==2.14.6` (only viable Python wrapper, sync-only, maintenance mode), why `pyright basic`, why `requests-mock`, why pytest-timeout
- `.planning/research/ARCHITECTURE.md` — **Critical for Phase 2 planning:**
  - §"Recommended Project Structure" — `custom_components/ha_pronote/{api,diff}/` exact layout
  - §"Pattern 1" — sync library + `async_add_executor_job` (Phase 3 wiring; Phase 2 just exposes the sync surface correctly)
  - §"Pattern 3" — diff-as-pure-function fired from coordinator (Phase 2 produces the pure function; Phase 4 wires the firing)
  - §"Pattern 6" — `runtime_data` not `hass.data[DOMAIN]` (Phase 3 concern, but explains why `data.py` is a Phase 3 deliverable, not Phase 2)
  - §"Suggested Build Order — Phase B (api/) and Phase D (diff/lessons.py)" — directly maps to Phase 2 plan slices
  - §"Anti-Pattern 1" (executor wrap), §"Anti-Pattern 5" (no pronotepy refs leaking out of coordinator) — Phase 2's `_strip_client_refs` pattern (D-24) is the *prevention* of Anti-Pattern 5
- `.planning/research/PITFALLS.md` — **Critical for Phase 2 planning:**
  - §"Pitfall 1" (IP suspension) — Phase 2 detects the literal `Your IP address is suspended` string in `api/client.py` and raises `RateLimitedError(IP_SUSPENDED)` (D-22); the *handling* (long backoff, persistent notif) is Phase 5
  - §"Pitfall 2" (pronotepy breakage) — Phase 2 wraps every pronotepy exception in the typed `PronoteIntegrationError` hierarchy (D-22); the daily-cron CI against `pronotepy@main` is Phase 7 (D-24 of Phase 1)
  - §"Pitfall 3" (blocking calls) — Phase 2 keeps `api/` purely sync; the executor wrap is Phase 3's coordinator's job
  - §"Pitfall 4" (timezone NC) — Phase 2 tz-aware datetimes via `zoneinfo` (D-23), pytest matrix on `Europe/Paris` + `Pacific/Noumea` (D-25)
  - §"Pitfall 8" (unique_id stability) — Phase 3 concern; Phase 2 lays the groundwork by exposing a stable `child_identifier` field on `Lesson`/`Grade`/`Information`/`Snapshot`
  - §"Pitfall 10" (EDT diff false +/−) — **the single most important pitfall for Phase 2.** Pitfall 10's recipe (identity vs content keys, room-change handling, payload-hash dedup) is the *prior hypothesis* the spike (D-05) confirms or refines
- `.planning/research/FEATURES.md` §"Rich `pronote_schedule_changed` events with diff payload" — locks the `change_type` taxonomy (`canceled / modified / teacher / room`) consumed in D-09
- `.planning/research/SUMMARY.md` — High-level synthesis (read once for orientation)

### External references (URL — fetched during research, no local copy)
- `delphiki/HomeAssistant-Pronote` — reference implementation:
  - `coordinator.py` lines 26 `async_add_executor_job` call sites (Phase 3 will reuse the count; Phase 2 ensures every `api.*` function is wrappable in `partial(...)`)
  - `_strip_client_refs` pattern (D-24, C-05) — copy the *idea*, not the code (it's coupled to `delphiki`'s data shape; we own ours via `api/models.py`)
  - `compare_data` + `trigger_event` — the diff-and-fire pattern (Phase 4, but Phase 2 produces the right `LessonChange` shape)
- `bain3/pronotepy#311` — "Inability to distinguish canceled lessons from room changes" — **the issue the spike (D-05) and SPIKE-FINDINGS-bain3-311.md (D-06) directly address**. https://github.com/bain3/pronotepy/issues/311
- `bain3/pronotepy` README — confirms maintenance-mode disclaimer (relevant for Phase 7's daily-cron CI; Phase 2 only consumes the API surface)
- `pronotepy 2.14.6` API surface — `Client`, `ParentClient`, `Client.lessons(date_from, date_to)`, `Client.current_period.grades`, `Client.information_and_surveys`, `Client.export_credentials()` — Phase 2's `api/client.py` and `api/fetcher.py` wrap these. Source: PyPI `https://pypi.org/pypi/pronotepy/json` and the `bain3/pronotepy/clients.py` source

### Phase 1 plans / shipped code (relevant Phase 2 reads)
- `custom_components/ha_pronote/__init__.py` — currently a no-op `from .const import DOMAIN`; Phase 3 fills `async_setup_entry`. **Phase 2 does NOT modify this file.**
- `custom_components/ha_pronote/const.py` — currently holds `DOMAIN`. Phase 2 may *append* `DEFAULT_SCHOOL_TZ = "Pacific/Noumea"` and `DEFAULT_LOOKBACK_DAYS = 7` / `DEFAULT_LOOKAHEAD_DAYS = 14` if those constants are needed in `api/`. RECOMMEND keeping them in `const.py` (single source) rather than duplicating in `api/`.
- `custom_components/ha_pronote/manifest.json` — `pronotepy==2.14.6`, `python-slugify==8.0.4` already declared (Phase 1 D-14); Phase 2 does not touch.
- `custom_components/ha_pronote/config_flow.py` — placeholder (Phase 1 D-16); Phase 3 fills. **Phase 2 does NOT modify.**
- `tests/conftest.py` — PHACC autouse fixture wiring (Phase 1 01-03). Phase 2 may add `tests/test_api/conftest.py` and `tests/test_diff/conftest.py` (local fixtures) but does NOT modify the root conftest.
- `pyproject.toml` — Phase 2 appends `[tool.pytest.ini_options]` parameters (timeout, marker) and `[tool.coverage.run] omit` for stub modules (D-04 / C-02).
- `requirements_test.txt` — Phase 2 appends `requests-mock==1.12.1` (already pinned in CLAUDE.md as transitive — make it explicit).
- `.github/workflows/test.yml` — Phase 2 amends the pytest invocation to pass `--cov=custom_components/ha_pronote/diff --cov-fail-under=90`. Phase 1 D-22 wired the workflow shell.

### SPEC.md
None — `/gsd-spec-phase` was not run for Phase 2. Requirements live in REQUIREMENTS.md (TIME-04, EVENT-05, DIST-05) and ROADMAP.md success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **From Phase 1:**
  - `custom_components/ha_pronote/const.py:DOMAIN = "ha_pronote"` — Phase 2 reuses unchanged. Phase 2 may append a few module-level defaults (`DEFAULT_SCHOOL_TZ`, fetch-window defaults).
  - `custom_components/ha_pronote/manifest.json` — `requirements=["pronotepy==2.14.6", "python-slugify==8.0.4"]` is the dependency contract Phase 2's `api/` consumes. No additions needed.
  - `tests/conftest.py` (PHACC autouse `enable_custom_integrations`) — Phase 2's `tests/test_api/` and `tests/test_diff/` do NOT need the HA fixture (pure-Python tests), so they can rely on plain pytest features. PHACC remains available transitively for any test that wants it.
  - `pyproject.toml` `[tool.ruff] target-version = "py314"` and `[tool.pyright]` config — applies automatically to `api/` and `diff/`.
  - `requirements_test.txt` — already pulls `pytest-timeout==2.4.0`, `freezegun==1.5.5`, `syrupy==5.1.0` transitively via PHACC; Phase 2 only needs to ADD an explicit `requests-mock` line.
  - `.github/workflows/test.yml` — already runs `pytest -q` on PR + push (Phase 1 D-22). Phase 2 amends the invocation, doesn't add a new workflow.

### Established Patterns
- **From Phase 1:**
  - `pronotepy==X` exact-pin discipline (D-14) — Phase 2 doesn't need to bump but if a bug-class is found in 2.14.6 the planner can lift to 2.14.7 in the same phase.
  - All planner-level `Read` of CLAUDE.md "What NOT to Use" before any tooling call (Phase 1 set the precedent — Phase 2 inherits).
- **External patterns to mirror:**
  - `delphiki/hass-pronote` `coordinator.py` — `_strip_client_refs` walker (D-24, C-05). Idea, not code.
  - `delphiki/hass-pronote` `compare_data` — diff produces ChangeEvents on transitions; we follow the same shape but with cleaner identity-vs-content keys (Pitfall 10 + spike).
  - `pronotepy/clients.py` — `Client.__init__(url, username, password)` and `Client.token_login(...)` — Phase 2's `api/client.py:build_client` wraps these directly.

### Integration Points
- **Phase 2 → Phase 3 interface:**
  - `api/client.py:build_client(...)` → consumed by Phase 3's `__init__.py:async_setup_entry` via `await hass.async_add_executor_job(partial(build_client, ...))`.
  - `api/fetcher.py:fetch_all(client, today, school_tz, child_index_or_identifier=None)` → consumed by Phase 3's `coordinator.py:_async_update_data` via `await hass.async_add_executor_job(partial(fetch_all, client, today=today, school_tz=tz, child_index_or_identifier=child_index))`. The 4th argument is ParentClient-only (D-21, PC-02-03): when set, `client.set_child(...)` runs before any fetch; when None, pronotepy defaults to the first child; ignored for eleve `Client`.
  - `api/errors.py:AuthError / CommunicationError / RateLimitedError` → mapped by Phase 3's coordinator to `ConfigEntryAuthFailed` / `UpdateFailed`.
- **Phase 2 → Phase 4 interface:**
  - `diff/lessons.py:diff_lessons(previous, new, day) -> list[LessonChange]` → consumed by Phase 4's coordinator `_async_update_data` to fire `pronote_schedule_changed` events. The `LessonChange` dataclass includes a `to_payload() -> dict` method that produces the bus-event-ready dict (per ARCHITECTURE.md Pattern 3 schema).
  - `diff/events.py:NewGrade` and `NewInformation` types → Phase 4 fills the function bodies of `diff_grades(old, new)` and `diff_notifications(old, new)`.
- **Phase 2 → Phase 5 interface:**
  - `api/errors.py:RateLimitedError(reason=IP_SUSPENDED)` is raised when the literal `Your IP address is suspended` string appears (D-22). Phase 5's circuit breaker keys on this `reason` to enter the long-backoff branch.
- **Phase 2 → Phase 7 interface:**
  - `api/models.py` field schema is what `diagnostics.py` (Phase 7) redacts. Phase 7's `TO_REDACT` list will reference field names defined here. Phase 2 should keep credential-bearing fields out of `Snapshot` (only the user-facing data; `client.export_credentials()` lives in `api/client.py` as an opaque pass-through that Phase 3 stores into `entry.data`).

</code_context>

<specifics>
## Specific Ideas

- The author's real Pronote instance is `katiramona.ac-noumea.nc` (PROJECT.md context). The spike runs against this instance only. The `scripts/snapshot.py` URL is **not** hardcoded — it reads from `.env` (D-14), keeping Phase 1 D-34 ("NO hardcoded `katiramona.ac-noumea.nc` URL") intact.
- The "spike-first" pattern (D-05) is borrowed from /gsd-spike but executed inline in Phase 2 — no separate `/gsd-spike` invocation, since the output (fixtures + findings doc) is itself a Phase 2 deliverable.
- "EDT" stays the user-facing French term in code comments and event payloads; the API surface uses English (`Lesson`, `lessons_today`, `lessons_tomorrow`) per HA convention.
- The `change_type` enum values (`canceled / modified / teacher / room`) are spelled in English and lower-snake to match HA's bus event payload conventions (delphiki uses lower-snake too).
- **Anonymization deterministic check** (D-13's smoke test) is a single-line invariant: `assert no_pii(anonymize(fixture)) is True` where `no_pii` walks the JSON and asserts no value matches the PII allowlist (real first/last names from `.env`, real teacher names if known, the school URL). Cheap insurance against accidental commits of un-anonymized data.

</specifics>

<deferred>
## Deferred Ideas

These came up during the discussion but belong in later phases or post-v1:

- **`diff/grades.py` and `diff/notifications.py` BODIES** — Phase 4 (the bodies are simple "set difference on `(date, subject)` for grades, `(id, date)` for informations" but conceptually Phase 4 owns event firing). Phase 2 only ships the dataclass types.
- **Heavy-class fixture (50 lessons/week × 2 weeks, 100 grades) for HA size-limit assertions** — Phase 4 (the size-limit assertion lives on the SENSOR layer, not the diff layer; Phase 2's `Snapshot` has no 16 KiB ceiling).
- **Token persistence** (`client.export_credentials()` round-tripped into `entry.data`) — Phase 3 (AUTH-04). Phase 2 just exposes `api/client.py:export_credentials_dict(client) -> dict` so Phase 3 has a stable surface to call.
- **Adaptive interval, quiet hours, vacation calendar, jitter** — Phase 5 (COORD-04..09, DIST-06). Phase 2 owns NONE of this.
- **NC vice-rectorat school-calendar machine-readable format research** — Phase 5 (STATE.md flagged).
- **Calendar entity (`CAL-01`, J−7→J+14)** — Phase 4. Phase 2 already exposes the wide-window snapshot (D-15) so Phase 4 only renders.
- **Numeric grade normalization ("14,5" → 14.5)** — Phase 4 (GRADE-01). Phase 2's `Grade.value` field stays a `str` (the raw pronotepy field) OR a `Decimal` (planner discretion); the *normalization for sensor state* is Phase 4's concern.
- **`async_migrate_entry` skeleton** — Phase 3 (ENT-04).
- **Diagnostics redaction** — Phase 7 (DIAG-01). Phase 2 keeps `Snapshot` PII-aware but doesn't ship the redactor.
- **Daily cron CI against `pronotepy@main`** — Phase 7 (DIST-04). Phase 1 D-24 already deferred this.
- **Brand assets for HACS** — v2+ (Phase 1 deferred this).
- **pronotepy upgrade beyond 2.14.6** — only when the spike or a real bug forces it. Phase 2 commits to 2.14.6 as the spike-validated version.

</deferred>

---

*Phase: 2-API & Diff Layer (HA-free)*
*Context gathered: 2026-05-03*
