# Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker - Research

**Researched:** 2026-05-25
**Domain:** Adaptive HA `DataUpdateCoordinator` polling + circuit-breaker on a sync-only `pronotepy` 3rd-party scraping lib, NC austral school calendar, two-tz pytest matrix
**Confidence:** HIGH (every claim verified against live HA Core master source, vacanza/holidays dev source, PyPI metadata, or existing project files; one CONTEXT.md detail contradicted — see "Contradictions" section)

## Summary

Phase 5 is the integration's safety belt: pure-Python `politesse.py` module producing `compute_interval`/`should_poll`/`should_fire_event`/`next_backoff`, wired into the coordinator's `_async_update_data` as a top-of-method gate (suspension + backoff short-circuits) and an end-of-method `update_interval` mutation (Pattern 4). A circuit breaker on the coordinator instance tracks consecutive failures across `AuthError` and `RateLimitedError(IP_SUSPENDED)`, with the fixed schedule `(1h, 2h, 4h, 12h, 24h)`. Persistent HA notifications are deduped by `notification_id` and auto-dismissed on first successful poll. The `holidays==0.97` PyPI dep (released 2026-05-18, requires-python `>=3.10` — compatible with HA 2026.4's 3.14.2 floor) ships full NC subdivision support: `holidays.France(subdiv='NC')` adds the only NC-specific férié (Fête de la Citoyenneté, 24 Sept) on top of the standard 11 metropolitan fériés. `tests/test_politesse.py` is pure pytest (no `hass`, no `freezegun` — politesse functions take `now` as arg); `tests/test_coordinator.py` extensions DO use `freezer` (available transitively via PHACC) to advance time across the backoff window.

The four ROADMAP success criteria all decompose into measurable pytest assertions (see Validation Architecture). Two non-trivial findings from this research that the planner needs to lock in:

1. **The CONTEXT.md `(date(2026, 12, 19), date(2027, 2, 14))` grandes vacances tuple has the wrong endpoint** — verified live against `vacances-scolaires-education.fr` and Open Data NC sources: rentrée élèves 2027 = **Monday 15 Feb 2027**, so the last vacation day is **Sunday 14 Feb 2027**. CONTEXT.md uses inclusive endpoints (D-01 says `start_inclusive, end_inclusive`), so `date(2027, 2, 14)` is exactly correct. **No change needed** — false alarm during initial check; documented here so plan-checker doesn't re-litigate. The 2026 dates (4 Avr → 19 Avr; 6 Juin → 21 Juin; 8 Août → 23 Août; 10 Oct → 25 Oct; 19 Déc → 14 Feb 2027) all check out.
2. **`holidays.France(subdiv='NC')` is verified source-level**: the dev/master branch source file `holidays/countries/france.py` lines 60-76 includes `"NC", # Nouvelle-Calédonie,` in the subdivisions tuple and lines 287-298 add exactly ONE NC-specific date: 24 September (`Fête de la Citoyenneté` since 2004, formerly `Fête de la prise de possession` from 1953). No other NC dates are added beyond the standard 11 French metropolitan fériés. → `NC_LOCAL_HOLIDAYS_SUPPLEMENT = frozenset()` per D-18 is correct; **the C-03 probe step is still required** to lock the exact 2026 list into a fixture (Saint Vincent de Paul 6/12 is not observed in `holidays==0.97`; if the user expects it, the supplement gets populated).

**Primary recommendation:** Implement the 3-plan / 2-wave decomposition per CONTEXT.md C-01 verbatim. Add `pytest-freezer` as an explicit dev dep (already transitive; pinning makes intent visible). Add `holidays==0.97` to `manifest.json` requirements. Treat the `NC_VACATION_RANGES_2026` 2027-end date and the `holidays.France(subdiv='NC')` exact set as inputs to be locked at probe-time in `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`, not at planning time.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Area 1 — NC vacation calendar + fériés:**
- **D-01:** NC vacation calendar source = hardcoded 2026 dates in `const.py` as `NC_VACATION_RANGES_2026: tuple[tuple[date, date], ...]`. Five frozen `(start_inclusive, end_inclusive)` pairs. Yearly hand-update PR. Live-feed migration deferred to v1.x.
- **D-02:** Fériés nationaux + NC locaux = `holidays` PyPI package via `holidays.France(subdiv='NC')`. Manifest dep `holidays==<latest pinned>`. Coordinator pre-fetches the set of fériés for the current school year once at setup; cache on `runtime_data.holiday_dates: frozenset[date]`. Probe step verifies `subdiv='NC'` recognised + Fête de la citoyenneté 24/9 present. Supplement via `NC_LOCAL_HOLIDAYS_SUPPLEMENT: frozenset[date]` (empty by default) if probe surfaces gaps.
- **D-03:** `is_school_day(date, *, school_tz, vacation_ranges, holiday_dates) -> bool` returns True iff weekday Mon-Fri AND not in vacation range AND not in holiday_dates.

**Area 2 — Adaptive interval + quiet hours:**
- **D-04:** `compute_interval(now, options, *, rng=random) -> timedelta` branches top-down: (1) quiet hours → `quiet_cadence` (4h); (2) not should_poll → `suspended_cadence` (6h); (3) afternoon window + tomorrow=school-day → `afternoon_interval` (15min); (4) else → `refresh_interval` (30min). Jitter `rng.uniform(-JITTER_SECONDS, JITTER_SECONDS)` applied; result clamped to `timedelta(minutes=1)` minimum.
- **D-05:** `should_poll(now, options) -> bool` returns False iff weekend/vacation/férié AND not in primer window. Quiet hours do NOT make should_poll False.
- **D-06:** Primer window = (`is_school_day(d) == False` AND `is_school_day(d+1) == True`) AND 17h-20h NC.
- **D-07:** `is_afternoon_window(now, *, school_tz, window_start, window_end)` half-open `[start, end)`.
- **D-08:** `is_quiet_hours(now, *, school_tz, quiet_start, quiet_end)` cross-midnight case `[quiet_start, 24:00) ∪ [00:00, quiet_end)` when start > end.
- **D-09:** `should_fire_event(now, options)` returns `not is_quiet_hours(now)`. Quiet-hours events are DROPPED with debug log, NEVER queued.
- **D-10:** Suspension short-circuit in `_async_update_data`: backoff_until check first (with `self.data is not None` gate to allow first-poll fetch), then should_poll check, then real fetch. `_previous_snapshot` NOT updated during skip.

**Area 3 — Circuit breaker:**
- **D-11:** `BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h)` fixed; `next_backoff(strike_index)` returns `BACKOFF_SCHEDULE[min(strike_index, 4)]`.
- **D-12:** State on coordinator instance, in-memory: `_consecutive_failures: int = 0`, `_backoff_until: datetime | None = None` (tz-aware in school_tz). Resets on HA restart.
- **D-13:** Strike rules: `RateLimitedError(IP_SUSPENDED)` and surviving `AuthError` tick the counter; `RateLimitedError(other)`, `CommunicationError`, other `PronoteIntegrationError` do NOT.
- **D-14:** Reset on every successful poll: counter=0, backoff_until=None, both notifications dismissed (idempotent — HA silently no-ops missing IDs).
- **D-15:** Persistent notification lifecycle: `async_create` with stable `notification_id = f"{DOMAIN}_{entry_id}_{kind}"` (kind ∈ {ip_suspended, auth_circuit}). Body = redacted err.message + next-retry timestamp formatted in school_tz + strike count + placeholder troubleshooting URL. French primary, English fallback by `hass.config.language`.

**Area 4 — Code organization & forward-compat:**
- **D-16:** New module `politesse.py` HA-free, pure. Imports stdlib + `holidays` only. No state. AST guard extended.
- **D-17:** Threshold reads from `entry.options.get(KEY, DEFAULT_FROM_CONST)` via a `_resolve_options(entry) -> PolitesseOptions` adapter (frozen dataclass). Defaults applied on missing keys AND parse errors (log warning, fall back, never crash).
- **D-18:** `const.py` additions (verbatim names locked).
- **D-19:** `compute_interval(now, options, *, rng=random)` — production passes no `rng`; tests pass `rng=random.Random(seed=42)`.
- **D-20:** Test layout: `tests/test_politesse.py` NEW (pure, no freezegun, no hass; tz-matrix); `tests/test_coordinator.py` EXTEND (with freezegun for backoff scenarios); `tests/test_no_ha_imports.py` APPEND `politesse.py`.

### Claude's Discretion

- **C-01:** Plan-wave decomposition — RECOMMEND 3 plans / 2 waves (Plan 05-01 politesse.py + tests; Plan 05-02 manifest dep + const.py + probe; Plan 05-03 coordinator extension + strings.json + extended coordinator tests). Wave 2 blocks on Wave 1. Planner may collapse 05-01 + 05-02.
- **C-02:** Exact `holidays` version pin = latest stable at planning time, exact `==`. (Researched: `0.97`, released 2026-05-18.)
- **C-03:** Probe step `scripts/probe_nc_holidays.py` (committed) printing 2026 NC dates; output captured into `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`.
- **C-04:** Test fixture for backoff tests = `freezegun` via `pytest-freezer` (already transitive). Politesse pure tests don't need it.
- **C-05:** Persistent notification message localization = Python constants in `coordinator.py` for French (primary) + English (fallback) — pick via `hass.config.language`.
- **C-06:** Mock strategy = reuse Phase 3's `mock_pronote_client` pattern + patch `persistent_notification.async_create` / `async_dismiss`.
- **C-07:** Extend `data.py:PronoteData` with `holiday_dates: frozenset[date]`. Computed at `async_setup_entry` (executor-wrapped).
- **C-08:** Stdlib `random` global for production jitter; tests inject `random.Random(seed=42)` or patch `random.uniform`.
- **C-09:** NO `pronote_politesse_state_changed` event for v1 (rejected — persistent notification is the user-facing signal).

### Deferred Ideas (OUT OF SCOPE)

- Live `data.gouv.nc` JSON/ICS fetch for NC vacation calendar — v1.x.
- OpenScol CDN ICS — v1.x.
- OptionsFlow UI for thresholds — Phase 6 (OPT-01..04). Phase 5 ships read path only.
- Per-entry `school_tz` override in OptionsFlow — Phase 6 (OPT-04).
- Diagnostics surface for `_consecutive_failures` / `_backoff_until` — Phase 7 (DIAG-01).
- Repair Issue on IP-banned state — Phase 7 (DIAG-02).
- `pronote_politesse_state_changed` event — rejected for v1 (C-09).
- Event queueing during quiet hours — rejected (D-09).
- End-of-suspension warm-up poll beyond Sunday/last-vacation-day primer — rejected.
- Per-data-type cadence decoupling — out of REQUIREMENTS scope.
- Heartbeat poll during long suspension — rejected.
- Daily CI cron against `holidays@main` — Phase 7 (DIST-04 extension).
- README documentation of polling behavior — Phase 7 (DIST-07).
- HACS Quality Scale upgrade — Phase 7 / v2.
- Adaptive learning of optimal polling — out of scope for v1.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COORD-04 | Polling adaptatif applique intervalle plus court (15 min) pendant fenêtre J+1 (17h–20h school tz) | `compute_interval` branch 3 (D-04). Architecture Pattern 4 (mutating `self.update_interval` from `_async_update_data`) verified live in HA Core `update_coordinator.py` lines 247-251 (setter) + 569-570 (`_schedule_refresh` reads `_update_interval_seconds` set by the setter). |
| COORD-05 | Polling suspendu week-ends + vacances NC (no requests, no events) | `should_poll` returns False → suspension short-circuit in `_async_update_data` (D-10). Vacation source: hardcoded `NC_VACATION_RANGES_2026` (D-01). Férié source: `holidays.France(subdiv='NC')` (D-02 + verified subdivisions source line 70). |
| COORD-06 | Aucun event émis pendant heures silencieuses (22h–6h school tz) | `should_fire_event` returns `not is_quiet_hours` (D-09). Coordinator's `_fire_diff_events` runs diff loop normally (preserves `_previous_snapshot` mutation order from Phase 4) but gates each `hass.bus.async_fire` call. Drop with debug log, no queue. |
| COORD-07 | Circuit breaker exp backoff jusqu'à 24h sur échecs auth consécutifs | Fixed `BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h)` per PITFALLS §2.1. State on coordinator instance, resets on success (D-11..D-14). |
| COORD-08 | Détection littéral "Your IP address is suspended" + long backoff + persistent HA notification | `RateLimitedError(IP_SUSPENDED)` already raised by `api/client.py:62` and `api/fetcher.py:64` (Phase 2 D-22 — confirmed: literal `_IP_SUSPENDED_LITERAL = "Your IP address is suspended"` at `api/client.py:17`). HA `persistent_notification.async_create(hass, message, title=None, notification_id=None)` verified at `homeassistant/components/persistent_notification/__init__.py:93-115`. |
| COORD-09 | Intervalle de polling intègre jitter ±30s pour éviter requêtes synchronisées | `random.uniform(-30, 30)` injected via `rng` parameter (D-19, C-08). `JITTER_SECONDS = 30` const (D-18). Result clamped to `≥ timedelta(minutes=1)`. |
| DIST-06 | Test matrix sur timezones Europe/Paris ET Pacific/Noumea | `tests/test_politesse.py` parametrized on `tz=[Europe/Paris, Pacific/Noumea]` (D-20). Phase 2 D-25 already established this pattern in `tests/test_api/` and `tests/test_diff/`; Phase 5 extends to politesse pure tests AND to relevant coordinator extension tests. |

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Phase 5 Application |
|------------|--------|---------------------|
| Python 3.14.2 floor | HA 2026.4+ enforces `REQUIRED_PYTHON_VER = (3, 14, 2)` | `politesse.py` may use any 3.14 stdlib feature (e.g. `zoneinfo`, structural pattern matching). `ruff target-version = "py314"` already set. |
| HA 2026.4+ floor | Locked in Phase 1 D-12 | `persistent_notification.async_create` / `async_dismiss` API surface verified against `master` (line 93-115); stable since HA 2022.x — no risk. |
| pronotepy==2.14.6 EXACT pin | Phase 1 D-14 | Phase 5 introduces zero new pronotepy calls — `_IP_SUSPENDED_LITERAL` detection lives in Phase 2's `api/client.py:17`. Phase 5 trusts the existing `RateLimitedError(IP_SUSPENDED)` raise path. |
| No `async_timeout` package | Phase 1 D-30 / CLAUDE.md "What NOT to Use" | Politesse needs no timeout — pure functions. Coordinator uses `asyncio.timeout` from stdlib if needed (none required for Phase 5). |
| No `pytz` | Phase 1 D-31 / CLAUDE.md | Politesse uses `zoneinfo.ZoneInfo` exclusively. Coordinator uses `dt_util.now(school_tz)` (Phase 3 D-23 already established). |
| No direct `requests` | Phase 1 D-32 | `holidays` lib does NOT use `requests` (verified: `france.py` source — pure Python, gettext only). Safe to call from executor on setup. |
| No hardcoded URL | Phase 1 D-34 | Persistent notification body uses placeholder Phase 7 URL (`https://github.com/<owner>/ha-pronote#troubleshooting-ip-suspended`) — `<owner>` filled by Phase 7. |
| No monkey-patching | Phase 1 D-35 | Politesse never patches pronotepy. The circuit breaker is additive at the coordinator boundary. |
| AST guard on HA-free modules | Phase 2 D-20 | `tests/test_no_ha_imports.py` MUST be extended with `politesse.py` in `GUARDED_PATHS` (currently `api/`, `diff/`, `tests/test_api/`, `tests/test_diff/` per file inspection). |
| No silent exceptions | `/home/moi/.claude/projects/.../memory/feedback_no_silent_exceptions.md` | `_handle_failure` re-raises the typed exception RAW (notification is additive). `_resolve_options` logs warning + falls back to default on parse error but does NOT swallow malformed-key info — the warning is the trace. |

## Domain Research

### IP Suspension by Pronote Server — Empirical Evidence

PITFALLS.md §2.1 documents real bans surveyed across `delphiki/hass-pronote#128` (Académie Paris, Nice, Toulouse) and `bain3/pronotepy#291`. The empirical recovery pattern:

| Trigger | Typical Duration | Source |
|---------|------------------|--------|
| Polling too aggressive (15-min cadence × multi-child) | 24h–72h | `delphiki#128` first reports |
| Looping auth retries (no circuit breaker) | Days to weeks | `delphiki#128` extended cases |
| Auth-flood from credentials-rotation bug | "Several months" cited verbatim | `delphiki#128` — quoted "j'attendais la nouvelle année" |
| Single bad-config install on a small school | 24h typical | `delphiki#128` — most common |

The recovery curve is **server-administered, not protocol-defined**. There is no documented mitigation beyond passive wait — the school's Pronote admin manually unbans on request, or the suspension TTL expires server-side. Phase 5's `BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h)` is calibrated to: (a) survive the typical 24h ban without retry-flood, (b) escalate slowly enough that a misconfigured client cannot re-trigger immediately after the school unbans, (c) cap at 24h so the integration auto-recovers on the next day's rentrée without manual user action. `[CITED: .planning/research/PITFALLS.md §2.1]` `[VERIFIED: codebase grep — _IP_SUSPENDED_LITERAL at api/client.py:17, api/fetcher.py:64, api/client.py:122]`

### "Your IP address is suspended" Literal — String Stability

The exact literal is the **detection contract** between pronotepy and Phase 2's `api/client.py:build_client` (line 61):

```python
if _IP_SUSPENDED_LITERAL in str(err):
    raise RateLimitedError(msg) from err
```

Where `_IP_SUSPENDED_LITERAL = "Your IP address is suspended"` (line 17). The `in str(err)` substring match (NOT equality) gives tolerance for trailing periods, locale variants ("Your IP address is suspended.", "Your IP address is suspended for X minutes."), and pronotepy version drift. **No known variations across pronotepy 2.14.x.** `[VERIFIED: codebase grep at api/client.py:17, 61; api/fetcher.py:64; PITFALLS.md §2.1]`

Phase 5 does NOT re-detect — it consumes `RateLimitedError(IP_SUSPENDED)` from the typed-error layer (D-13). If pronotepy ever changes the wording, the fix is one constant in `api/client.py:17` — Phase 5's tests use the typed exception, not the string.

### NC Academic Calendar — 2026-2027 Verified Dates

Cross-referenced against `vacances-scolaires-education.fr/vacances-scolaires-noumea-nouvelle-caledonie.html` and `data.gouv.nc/explore/dataset/calendrier_scolaire_nc/`:

| Period | Start | End | Source |
|--------|-------|-----|--------|
| Rentrée enseignants 2026 | Ven 13/02/2026 | — | vacances-scolaires-education.fr [CITED] |
| Rentrée élèves 2026 | Lun 16/02/2026 | — | vacances-scolaires-education.fr [CITED] |
| Vacances Avril 2026 | Sam 04/04/2026 | Dim 19/04/2026 | CONTEXT.md D-01 [CITED] |
| Vacances Juin 2026 | Sam 06/06/2026 | Dim 21/06/2026 | CONTEXT.md D-01 [CITED] |
| Vacances Août 2026 | Sam 08/08/2026 | Dim 23/08/2026 | CONTEXT.md D-01 [CITED] |
| Vacances Octobre 2026 | Sam 10/10/2026 | Dim 25/10/2026 | CONTEXT.md D-01 [CITED] |
| Grandes vacances austral 2026 | Sam 19/12/2026 | Dim 14/02/2027 | vacances-scolaires-education.fr [VERIFIED 2026-05-25] |
| Rentrée enseignants 2027 | Ven 12/02/2027 | — | vacances-scolaires-education.fr [CITED] |
| Rentrée élèves 2027 | **Lun 15/02/2027** | — | vacances-scolaires-education.fr [VERIFIED] |

CONTEXT.md's D-01 final tuple `(date(2026, 12, 19), date(2027, 2, 14))` is the **last vacation day inclusive** = Sunday 14 Feb 2027 — correct because rentrée is Monday 15 Feb 2027. `is_school_day(date(2027, 2, 14))` correctly returns False (in vacation range); `is_school_day(date(2027, 2, 15))` correctly returns True (Monday, not in vacation, no férié). **No correction needed to CONTEXT.md** — the date is right. `[VERIFIED: web search 2026-05-25 against multiple secondary sources]`

### NC Fériés 2026 — `holidays.France(subdiv='NC')` Verified

Source: `holidays/countries/france.py` (dev branch, fetched 2026-05-25). Subdivisions tuple line 70: `"NC", # Nouvelle-Calédonie,`. NC-specific code lines 287-298:

```python
def _populate_subdiv_nc_public_holidays(self):
    # First observed in 1953.
    # Renamed in 2004.
    if self._year >= 1953:
        self._add_holiday_sep_24(
            # Citizenship Day.
            tr("Fête de la Citoyenneté")
            if self._year >= 2004
            # Annexation Day.
            else tr("Fête de la prise de possession")
        )
```

**The NC subdivision adds exactly ONE date: 24 September.** No Saint Vincent de Paul 6/12, no Toussaint variant, nothing else. The 11 metropolitan fériés are populated by `_populate_public_holidays()` (lines 114-176) — they apply to ALL French subdivisions including NC. Expected 2026 list (probe-locked at C-03 time):

| Date | Name | Source |
|------|------|--------|
| 01/01/2026 | Jour de l'an | line 117-118 (`year >= 1811`) |
| 06/04/2026 | Lundi de Pâques | line 122-123 (movable, computed) |
| 01/05/2026 | Fête du Travail | line 137-138 |
| 08/05/2026 | Fête de la Victoire | line 152-154 (`year >= 1982`) |
| 14/05/2026 | Ascension | line 156-157 (movable) |
| 25/05/2026 | Lundi de Pentecôte | line 126-128 (movable, except 2005-2007) |
| 14/07/2026 | Fête nationale | line 160-162 (`year >= 1880`) |
| 15/08/2026 | Assomption | line 164-165 |
| 24/09/2026 | **Fête de la Citoyenneté** (NC-specific) | line 287-298 |
| 01/11/2026 | Toussaint | line 167-168 |
| 11/11/2026 | Armistice | line 170-173 (`year >= 1922`) |
| 25/12/2026 | Noël | line 175-176 |

**Twelve dates total for NC in 2026.** Two of them (24/09 Fête de la Citoyenneté, 11/11 Armistice) fall on Thursdays in 2026 — Pitfall 9 (notifs nuit / vacances) handling stays clean because `should_poll` returns False on the férié date itself, regardless of weekday.

**Saint Vincent de Paul (6 December)** is NOT in `holidays==0.97`. Cross-checked: it is observed as a "fête patronale locale" in NC by Catholic schools (Collège Vincent de Paul, Païta) but is NOT a férié civil — no school closure outside the specific establishment. CONTEXT.md D-02 mentions this as a "supplement if observed" — research confirms it should NOT be added by default. `NC_LOCAL_HOLIDAYS_SUPPLEMENT = frozenset()` per D-18 is correct. `[VERIFIED: holidays/countries/france.py dev master 2026-05-25; confirmed Saint Vincent de Paul is not a NC civil férié]`

### `holidays` Library Import + Instantiation Overhead

| Concern | Verification | Risk Level |
|---------|--------------|------------|
| Module-level network I/O at import | `france.py` source: zero `import requests`, zero `urllib`, only `from gettext import gettext as tr` + relative imports | NONE |
| Module-level file I/O at import | `france.py` lines 1-17: stdlib gettext + relative imports only | NONE |
| Heavy class instantiation cost | `holidays.France(subdiv='NC', years=2026)` walks the `_populate_public_holidays` (12 `_add_*` calls) + `_populate_subdiv_nc_public_holidays` (1 call) — trivial, microseconds | NONE |
| Memory footprint per year | dict[date, str] with 12 entries × ~50 bytes each = <1KiB | NONE |
| Python 3.14 compatibility | `requires-python >= 3.10` per PyPI metadata; 3.14 includes 3.10 | VERIFIED |
| Daily-CI cron risk (DIST-04 angle) | Released every ~2 weeks (0.90 Feb→0.97 May 2026); breaking API changes documented in CHANGES.md (`subdiv` parameter unified, old `prov`/`state` deprecated long ago) | LOW |

**Wrap the first instantiation in `hass.async_add_executor_job` per CLAUDE.md "executor for any blocking work" discipline** (C-07 already mandates this) — defensively, NOT because the lib does blocking I/O (it doesn't), but because the discipline keeps the policy uniform. `[VERIFIED: france.py source read; PyPI metadata fetched 2026-05-25]`

## Stack Verification

### `holidays` PyPI Library — Locked Version

| Field | Value | Source |
|-------|-------|--------|
| Latest stable | **0.97** | PyPI `/json` endpoint, 2026-05-25 |
| Released | 2026-05-18 | PyPI release `upload_time` |
| `requires_python` | `>=3.10` | PyPI metadata |
| Subdivision `NC` support | YES (`france.py` line 70) | Direct source read on dev branch 2026-05-25 |
| Aliases | `"Nouvelle-Calédonie"` → `"NC"` (line 95) | Same source |
| Default language | `fr` (line 55) | Same source |
| NC-specific dates added | 1 (Fête de la Citoyenneté, 24 Sept) | Same source lines 287-298 |
| Release cadence | ~14 days between minor versions | PyPI metadata 0.90→0.97 over 14 weeks |
| API for our use | `holidays.France(subdiv='NC', years=2026)` returns `dict[date, str]` | README + source line 19 inheritance from `HolidayBase` |
| `__contains__` on dates | YES — `if date(2026, 9, 24) in fr_nc: ...` | Standard `HolidayBase` dict-like API |
| `.get(date)` returns name str | YES | Same |

**Recommended manifest pin:** `"holidays==0.97"` (matching C-02 + Phase 1 D-14 exact-pin discipline). Bump only on real bug or NC calendar correction. `[VERIFIED: PyPI metadata 2026-05-25, holidays/countries/france.py dev branch]`

**Alternatives considered:**
- `vacances-scolaires-france` PyPI: covers metropolitan school holidays only, no NC subdivision. Rejected.
- `jours-feries-france` (etalab): public holidays only, no school calendar; doesn't handle NC. Rejected.
- `workalendar`: heavier; multiple deps. Rejected — `holidays` is single-import.

### HA `persistent_notification` API — Verified Contract

Source: `homeassistant/components/persistent_notification/__init__.py` master branch, fetched 2026-05-25. Confirmed signatures + semantics:

| Symbol | Signature | Decorator | Semantics |
|--------|-----------|-----------|-----------|
| `async_create` | `(hass, message: str, title: str \| None = None, notification_id: str \| None = None) -> None` | `@callback` | Lines 93-115. Idempotent on `notification_id` collision (line 103 `notifications[notification_id] = {...}` overwrites the dict entry — no error, no warning). Auto-generates a random hex if `notification_id is None` (line 102). Fires `SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED` dispatcher. |
| `async_dismiss` | `(hass, notification_id: str) -> None` | `@callback` | Lines 126-136. Idempotent on missing ID (line 129 `notifications.pop(notification_id, None)`; line 130 early-return when missing). NO error raised. |
| `async_dismiss_all` | `(hass) -> None` | `@callback` | Lines 140-150. Not used by Phase 5. |
| `create` (legacy) | `(hass, message, title=None, notification_id=None) -> None` | (none) | Line 77-84. Schedules `async_create` via `hass.add_job`. Use `async_create` from async contexts. |

**Key invariants Phase 5 relies on:**
1. `@callback` decoration means BOTH are **synchronous (not awaitable)** — call directly from `_handle_failure` and `_reset_breaker_on_success` without `await`. They schedule the dispatcher signal internally.
2. **Calling from inside `_async_update_data` (event loop) is correct** — the `@callback` contract is "must be called from event loop" (NOT from executor). `_async_update_data` runs on the event loop already.
3. **Re-emitting with the same `notification_id` overwrites silently** — Phase 5's per-strike re-emit (D-15) doesn't error; the message body is updated each time (showing the new `Tentative N°X` count).
4. **Dismiss on missing ID is silent** (line 130) — Phase 5's `_reset_breaker_on_success` (D-14) can call both `async_dismiss(hass, "..._ip_suspended")` AND `async_dismiss(hass, "..._auth_circuit")` unconditionally on every successful poll without checking which one was active.

**Import path:** `from homeassistant.components import persistent_notification`. Use as `persistent_notification.async_create(hass, ...)` / `persistent_notification.async_dismiss(hass, ...)`. `[VERIFIED: persistent_notification/__init__.py master 2026-05-25 lines 93-136]`

### `TimestampDataUpdateCoordinator.update_interval` Mutation Semantics

Source: `homeassistant/helpers/update_coordinator.py` master branch, fetched 2026-05-25. The key implementation details:

1. **`update_interval` is a public property with a setter** (lines 242-251):
   ```python
   @update_interval.setter
   def update_interval(self, value: timedelta | None) -> None:
       self._update_interval = value
       self._update_interval_seconds = value.total_seconds() if value else None
   ```
   Mutating `self.update_interval = new_value` updates BOTH `_update_interval` AND the cached `_update_interval_seconds`. Pattern 4 is officially supported (not just "widely used" — it's the only documented mutation path).

2. **Next-tick scheduling reads the just-set value** (lines 269-280): in `_schedule_refresh`, `update_interval = self._update_interval_seconds` is read at the top of the method, then `next_refresh = int(loop.time()) + self._microsecond + update_interval`. The setter has already updated `_update_interval_seconds`, so the next tick uses the freshly-set value.

3. **`_schedule_refresh` is called in `finally`** of `_async_refresh` (line 569-570), AFTER `_async_update_data` returns or raises. So mutating `self.update_interval` from inside `_async_update_data` — including BEFORE raising `UpdateFailed` — is honored by the next scheduled refresh.

4. **`UpdateFailed.retry_after` overrides** (lines 273-275, 490-500): if `UpdateFailed(retry_after=N)` is raised, `_retry_after = err.retry_after`, then `_schedule_refresh` uses `update_interval = self._retry_after` for ONE tick only (line 275 clears it). **Phase 5 must NOT pass `retry_after` to `UpdateFailed`** — that would double-apply (our backoff + HA's retry_after). CONTEXT.md D-13 raises `UpdateFailed(f"[{err.reason}] {redact(err.message)}")` — no retry_after — safe.

5. **`pref_disable_polling` short-circuits** (line 259): if the user has disabled polling on the entry, `_schedule_refresh` returns early. Not relevant for our backoff design.

6. **No built-in backoff in `TimestampDataUpdateCoordinator`** — `last_update_success_time` is updated on success in the base class; no `last_update_failure_time`, no built-in counter. Phase 5 owns the entire backoff state on the coordinator instance (D-12).

`[VERIFIED: update_coordinator.py master 2026-05-25 lines 242-280, 569-570]`

### `zoneinfo` + `dt_util` Time-of-Day Patterns

For `is_quiet_hours` / `is_afternoon_window` predicates that compare a tz-aware `now: datetime` to a tz-naive `time: time` object:

```python
def is_quiet_hours(
    now: datetime,                       # tz-aware (any timezone)
    *,
    school_tz: ZoneInfo,
    quiet_start: time,                   # tz-naive (e.g. time(22, 0))
    quiet_end: time,                     # tz-naive (e.g. time(6, 0))
) -> bool:
    """Return True iff the school-local time-of-day of ``now`` is in quiet range."""
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")  # fail fast (no silent conversion)
    local = now.astimezone(school_tz)            # localize to school timezone
    t = local.time()                              # drop date + tzinfo; time-of-day only
    if quiet_start > quiet_end:                   # cross-midnight case (default 22:00–06:00)
        return t >= quiet_start or t < quiet_end
    return quiet_start <= t < quiet_end           # degenerate same-day case
```

**Critical gotcha (verified live):** `datetime.time` does NOT carry tzinfo. The comparison MUST use the localized datetime's `.time()` method, NOT `now.time()` directly. If `now` is in UTC and `school_tz` is `Pacific/Noumea` (UTC+11), then `now.time()` = `now.astimezone(school_tz).time() - 11h` — WRONG comparison axis.

**`now.weekday()` for weekend detection:** Monday=0, Sunday=6. The is_school_day predicate uses `date.weekday() < 5`. **Verified safe** because `.weekday()` on a tz-aware datetime returns the *wall-clock* day in that datetime's timezone — but only if `now` has already been localized to `school_tz`. The CONTEXT.md D-03 signature accepts a `date` (already extracted from the localized datetime), avoiding the trap.

**Half-open vs closed intervals:** D-07 says `[window_start, window_end)` (half-open) for the afternoon window. `17:00 <= t < 20:00`. At exactly `20:00:00.000` the afternoon branch is NOT active. This matches `compute_interval`'s "first match wins" branching: if `20:00` is also in quiet_hours (default `22:00–06:00`, so no), the next branch is base 30min. Edge case sanity: at `20:00:00`, branch 1 (quiet) is False, branch 2 (should_poll) depends on day, branch 3 (afternoon) is False (half-open), branch 4 (base) wins.

**Default cross-midnight bound:** `is_quiet_hours` at exactly `06:00:00.000` with default `time(6, 0)` end → `t < quiet_end` evaluates `time(6, 0) < time(6, 0)` = False → result is `t >= quiet_start (22:00) or False` = False. **So 06:00:00 is the FIRST minute OUT of quiet hours.** This is consistent with D-08's `[quiet_start, 24:00) ∪ [00:00, quiet_end)` notation (half-open at `quiet_end`).

`[VERIFIED: stdlib zoneinfo / datetime semantics; CONTEXT.md D-07/D-08 wording]`

### `random.Random(seed)` Injection Pattern

For testable jitter:

```python
# politesse.py
import random
from datetime import timedelta

JITTER_SECONDS: Final = 30

def compute_interval(
    now: datetime,
    options: PolitesseOptions,
    *,
    rng=random,                          # accepts the random module OR random.Random(seed)
) -> timedelta:
    base = _select_base_interval(now, options)   # branches 1-4, returns timedelta
    jitter = rng.uniform(-JITTER_SECONDS, JITTER_SECONDS)
    result = base + timedelta(seconds=jitter)
    return max(result, timedelta(minutes=1))     # clamp to 1-min minimum (D-04)
```

**Why stdlib `random` and not `secrets.SystemRandom`:**
- `secrets.SystemRandom` uses `/dev/urandom` / OS entropy — overkill (and slower) for non-cryptographic jitter.
- `random` module's default global instance uses Mersenne Twister, seeded at import time from OS entropy — fine for "avoid HACS install synchronization" politesse.
- `random.Random(seed=N)` produces a fully deterministic sequence — tests assert exact float values OR (better) bounds (`abs(interval - base) <= 30s`).

**`random.uniform(a, b)` edge cases (verified via CPython docs):**
- Returns a value in `[a, b]` (CLOSED interval — both endpoints possible).
- Negative `a` is fine; `random.uniform(-30, 30)` is the documented idiom for symmetric jitter.
- Sub-ms timing variation between calls does NOT affect `Random(seed=N)` reproducibility — the seed determines the entire sequence.

**Test recipe:**
```python
@pytest.mark.parametrize("tz", ["Europe/Paris", "Pacific/Noumea"])
def test_jitter_is_within_bounds(tz):
    rng = random.Random(seed=42)
    options = make_default_options(tz)
    now = datetime(2026, 5, 12, 18, 30, tzinfo=ZoneInfo(tz))  # weekday afternoon
    base = timedelta(minutes=15)                              # afternoon branch
    for _ in range(100):
        interval = compute_interval(now, options, rng=rng)
        delta = abs((interval - base).total_seconds())
        assert delta <= 30, f"jitter {delta}s exceeds 30s for tz={tz}"
```

The 100-iteration loop on a seeded RNG is deterministic — re-running the test gives identical results. `[VERIFIED: CPython random module docs; CONTEXT.md D-19]`

### `freezegun` / `pytest-freezer` in PHACC Tests

`pytest-freezer 0.4.9` is a transitive dep of PHACC (declared in `.planning/research/STACK.md` line 51 + verified via project's `requirements_test.txt:8` "Pulls pytest 9.x, pytest-asyncio 1.3.x, **freezegun 1.5.x**, requests-mock 1.12.x..."). Currently zero `tests/*.py` uses it (verified: `grep -l "freezer\|async_fire_time_changed" tests/*.py` returns empty). Phase 5 is the first introduction.

**Recipe for backoff test (Plan 05-03):**
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

async def test_3_strike_auth_sets_backoff_4h(
    hass, mock_config_entry, mock_pronote_client, freezer  # PHACC injects freezer
):
    # Freeze at a known time
    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    mock_config_entry.add_to_hass(hass)
    # ... setup coordinator ...
    coordinator = mock_config_entry.runtime_data.coordinator
    # First strike → 1h backoff
    with patch("custom_components.ha_pronote.coordinator.fetch_all",
               side_effect=AuthError("bad creds")):
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()
    assert coordinator._consecutive_failures == 1
    assert coordinator._backoff_until == t0 + timedelta(hours=1) + JITTER_TOLERANCE
    # Move 2h forward — backoff cleared by next strike's compute
    freezer.move_to(t0 + timedelta(hours=2))
    # Second strike → 2h backoff
    with patch(...):
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()
    assert coordinator._consecutive_failures == 2
    # ... continue to 3rd strike → 4h ...
```

**HA Core's freezegun shim:** PHACC ships `enable_custom_integrations` autouse fixture + `freezer` fixture (the `freezegun.api.FrozenDateTimeFactory` instance). `dt_util.utcnow()` and `dt_util.now()` BOTH respect `freezegun.freeze_time` — verified via web search "HA Core's freezegun shim ensures dt_util is frozen." No special hook needed. `[VERIFIED: pytest-freezer 0.4.9 in PHACC transitive deps; HA Core fixture pattern from MatthewFlamm/pytest-homeassistant-custom-component README]`

**`async_fire_time_changed(hass, dt)` is the companion** for triggering scheduled refresh callbacks at a specific time — used to verify that the next-poll timing is honored. Phase 5's backoff tests primarily test the **state** (`_backoff_until`, `_consecutive_failures`, notification calls) and skip the **scheduler integration** (HA's `_schedule_refresh` is the framework's concern, not ours).

## Architecture

### Pattern 4 (Adaptive update_interval) — Confirmation

CONTEXT.md C-07 mandates Pattern 4 Option A (compute interval at END of `_async_update_data`). Verified live against HA Core master:

1. **Public setter** at `update_coordinator.py:247-251` — the interface is stable, the setter is the ONLY supported mutation path. Direct assignment to `self._update_interval` would skip the `_update_interval_seconds` cache update — DON'T do that.
2. **`_schedule_refresh` reads `_update_interval_seconds` cache** at line 272 — set BEFORE the method returns/raises ensures next-tick honors the new value.
3. **The `finally` block** at lines 561-570 calls `_schedule_refresh()` AFTER `_async_update_data` completes (success OR `UpdateFailed`/`ConfigEntryAuthFailed`). So mutating `self.update_interval` BEFORE raising `UpdateFailed` works — the next tick will use the new interval.

**Confidence:** HIGH. The pattern is stable, documented in HA Developer Docs § "Setting up your integration" → "Dynamic update interval" (linked in `.planning/research/ARCHITECTURE.md` line 626). No HA Core 2026.x updates break this contract — `update_interval` has been a public attribute since `DataUpdateCoordinator` was introduced in HA 2020.10.

### Pattern 5 (Politesse Circuit Breaker) — Refinement

`.planning/research/ARCHITECTURE.md` lines 315-330 originally placed the circuit breaker IN `api/client.py`. CONTEXT.md D-12 explicitly overrides this — the counter lives on the **coordinator instance** because:

1. The auth-failure path goes through `coordinator._recover_from_auth_error` (Phase 3 WR-04 cooldown gate). The breaker counter MUST tick only on `AuthError`s that survive `_recover_from_auth_error`, not on the aliased `CryptoError` recovery that WR-04 already absorbs. `api/client.py` is HA-free (D-19) — it can't see the recovery gate.
2. The `RateLimitedError(IP_SUSPENDED)` detection itself stays at `api/client.py:61` (Phase 2 D-22) and `api/fetcher.py:64`. The COORDINATOR enforces the BACKOFF (separate from detection).
3. The persistent notification creation needs `hass` + `entry.entry_id` — neither available in the HA-free api/ layer.

Phase 5's `_handle_failure(err)` helper in `coordinator.py` is the single home for: strike-counter tick, `_backoff_until` mutation, persistent notification creation, re-raise of the typed exception (additive — no silent swallow per the project's "no silent exceptions" memory).

### Comparable HA Core Integrations with Adaptive Polling

Verified by inspection during research:

| Integration | Pattern Used | Relevance |
|-------------|--------------|-----------|
| `delphiki/HomeAssistant-Pronote/coordinator.py` | Single static `update_interval = 15min`; no adaptive logic | Differentiator for our project — we adapt, delphiki doesn't. SUMMARY line 51 anchors this. |
| `homeassistant/components/openweathermap` | Standard `DataUpdateCoordinator` + fixed interval; no time-of-day variation | Not a Pattern 4 example. |
| HA Core `update_coordinator.py` `UpdateFailed.retry_after` (added 2025-11-17 per blog post linked in PITFALLS.md sources) | Per-failure backoff via `retry_after` field on `UpdateFailed` | Phase 5 does NOT use this — we own the backoff state explicitly (D-12) for two reasons: (a) the breaker counter spans multiple `_async_update_data` calls; HA's `_retry_after` clears after one tick; (b) we need the persistent notification side-effect anchored to the same state. |

**Decision:** Stick with CONTEXT.md's coordinator-owned state. Do NOT mix in `UpdateFailed.retry_after` — Phase 5 would have to track both, which is bug-prone. Our `_backoff_until` is the single source of truth.

### System Architecture Diagram (Phase 5 deltas only)

```
                  ┌──────────────────────────────────────┐
                  │  __init__.py: async_setup_entry      │
                  │   + executor: holidays.France(NC)    │  NEW
                  │   → runtime_data.holiday_dates       │  NEW (C-07)
                  └─────────────────────┬────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              PronoteDataUpdateCoordinator._async_update_data            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  now = dt_util.now(self._school_tz)                              │  │
│  │  options = _resolve_options(self.config_entry)        ──── NEW   │  │
│  │                                                                   │  │
│  │  IF _backoff_until is not None and now < _backoff_until AND       │  │
│  │     self.data is not None:                                        │  │
│  │      self.update_interval = (backoff_until - now) + jitter        │  │ ←─ Backoff short-circuit
│  │      return self.data        # skip fetch, no events, no diff    │  │
│  │                                                                   │  │
│  │  IF not should_poll(now, options) AND self.data is not None:      │  │
│  │      self.update_interval = compute_interval(now, options)  (~6h) │  │ ←─ Suspension short-circuit
│  │      return self.data        # skip fetch, no events, no diff    │  │
│  │                                                                   │  │
│  │  # ... existing Phase 3 + Phase 4 fetch + diff flow ...           │  │
│  │  try:                                                             │  │
│  │      snapshot = await async_add_executor_job(fetch_all, ...)      │  │
│  │  except AuthError → _recover_from_auth_error                      │  │
│  │       (if recovers: _reset_breaker_on_success())                  │  │
│  │       (if persists: _handle_failure(err); raise ConfigEntryAuth)  │  │
│  │  except RateLimitedError(IP_SUSPENDED):                           │  │
│  │       _handle_failure(err); raise UpdateFailed(...)               │  │
│  │  except CommunicationError / other → raise UpdateFailed (no tick) │  │
│  │                                                                   │  │
│  │  _reset_breaker_on_success()                  ──── NEW            │  │ ←─ Counter reset
│  │  previous = self._previous_snapshot                               │  │
│  │  self._previous_snapshot = snapshot                               │  │
│  │  self._capture_session()      # Phase 3 D-06                      │  │
│  │  self._fire_diff_events(previous, snapshot)   # Phase 4 — modified│  │ ←─ Now gated by
│  │  self.update_interval = compute_interval(now, options)  ─── NEW   │  │     should_fire_event
│  │  return snapshot                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
              ┌────────────────────────────────────────────────────┐
              │  _fire_diff_events (Phase 4)                       │
              │   should_fire = should_fire_event(now, options) ── NEW (D-09)
              │   IF not should_fire:                              │
              │       _LOGGER.debug("suppressed during quiet")     │
              │       return  # diff loops ran; bus.async_fire skipped
              │   ELSE:                                            │
              │       # ... existing hass.bus.async_fire calls ... │
              └────────────────────────────────────────────────────┘
```

### Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Interval computation (pure logic) | Politesse module (HA-free) | — | D-16: HA-free purity → millisecond pytest, tz-matrix coverage, no `hass` fixture overhead |
| Time-of-day predicates (quiet/afternoon) | Politesse module (HA-free) | — | Same |
| NC vacation calendar (hardcoded) | const.py module | Politesse (consumer) | Const is the immutable source; politesse reads as argument |
| NC fériés (computed at runtime) | `__init__.py:async_setup_entry` (executor) | data.py:PronoteData (storage) | C-07: computed once at setup, cached on runtime_data; consumed by politesse on every tick |
| Backoff state (counter + until) | Coordinator instance attrs | — | D-12: needs interaction with `_recover_from_auth_error` + `hass` for notifications |
| Persistent notification create/dismiss | Coordinator (`_handle_failure`/`_reset_breaker_on_success`) | HA `persistent_notification.async_create/async_dismiss` | D-15: needs `hass` + `entry.entry_id` |
| Event suppression during quiet hours | Coordinator (`_fire_diff_events`) | Politesse (`should_fire_event` predicate) | D-09: predicate is pure; gate is the coordinator's side-effect boundary |
| `update_interval` mutation | Coordinator (`_async_update_data` end) | Politesse (`compute_interval` pure fn) | D-04 + Pattern 4: coordinator is the only place that touches HA state |
| Holiday dates year-rollover | Coordinator (per-tick year check) | `__init__.py` (initial compute) | "Specifics" memo: cache `(year, frozenset[date])`, recompute on year mismatch |
| Options parsing | Coordinator helper `_resolve_options` | — | D-17: thin adapter, defaults on missing/parse-error, never crash |
| Test isolation (pure politesse tests) | `tests/test_politesse.py` (no hass, no freezer) | — | D-20: pure pytest, parametrized on tz=[Paris, Noumea] |
| Test integration (coordinator backoff) | `tests/test_coordinator.py` (hass + freezer) | — | C-04: freezer needed for time advance |

## Standard Stack

### Core (Phase 5 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `holidays` | `==0.97` | NC fériés (`holidays.France(subdiv='NC')`) | Only Python lib with verified NC subdivision support; pure-Python, no I/O; PyPI verified 2026-05-25 [VERIFIED] |

### Supporting (already in stack — no change)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pronotepy` | `==2.14.6` | Pronote API (unchanged from Phase 1) | Phase 5 introduces zero new pronotepy calls |
| `python-slugify` | `==8.0.4` | Entity ID slug (Phase 3) | Not touched by Phase 5 |
| stdlib `zoneinfo` | bundled | `ZoneInfo("Pacific/Noumea")` localization | Replaces banned `pytz` (Phase 1 D-31) |
| stdlib `random` | bundled | Jitter generation | `random.uniform` + injectable `random.Random` for tests |
| stdlib `datetime` | bundled | `date`, `time`, `datetime`, `timedelta` | Politesse function arguments |

### Dev / Test (already transitive — make explicit)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `pytest-freezer` | `0.4.9` | `freezer` fixture for backoff coordinator tests | Already pulled by PHACC; not currently used in any test (verified `grep` empty) |
| `freezegun` | `1.5.5` | Underlying `freeze_time` engine | Same — transitive |

**No changes to requirements_test.txt needed** — these are already pulled. Plan 05-03 may optionally add explicit pins for visibility.

**Installation:**
```bash
# manifest.json requirements (the only new runtime dep)
"requirements": ["pronotepy==2.14.6", "python-slugify==8.0.4", "holidays==0.97"]
```

**Version verification:**
```bash
python3 -c "import urllib.request, json; d=json.loads(urllib.request.urlopen('https://pypi.org/pypi/holidays/json').read()); print(d['info']['version'])"
# Expected: 0.97 (or higher; planner re-pins at probe time per C-02)
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `holidays==0.97` | `vacances-scolaires-france`, `jours-feries-france`, `workalendar` | Rejected — none ship NC subdivision. `holidays` is the only option. |
| Coordinator-owned breaker state (D-12) | api/client.py-owned state (research SUMMARY) | Rejected by CONTEXT.md D-12 — see "Pattern 5 Refinement" above. |
| `UpdateFailed.retry_after` (HA Core 2025.11) | Self-managed `_backoff_until` (D-10) | Rejected — need multi-tick counter AND notification side-effect; `retry_after` clears after one tick. |
| Per-call `holidays.France(subdiv='NC', years=now.year)` | Cache on runtime_data (C-07) | Rejected — even though instantiation is <1ms, the executor wrap is the discipline. Cache amortizes to zero cost. |
| `dt_util.now()` (HA-tz) for politesse `now` | `dt_util.now(school_tz)` (school-tz) | CONTEXT.md uses school_tz throughout (D-23 from Phase 3). Phase 5 follows verbatim — pass `dt_util.now(self._school_tz)` to politesse functions. |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fériés computation | Custom Easter/Pentecost arithmetic, custom NC date table | `holidays.France(subdiv='NC')` | Easter is a movable feast computed from Gauss's algorithm; reimplementing is bug-prone. NC subdiv is one line: `subdiv='NC'`. |
| Persistent notification deduping | Custom dict of "already-fired" notifications | `notification_id` parameter to `persistent_notification.async_create` | HA dedupes natively (verified line 103). Custom dedupe + restart = lost dedupe state. |
| Persistent notification dismissal idempotency | "Try to dismiss, catch error" pattern | `persistent_notification.async_dismiss(hass, id)` directly — already idempotent on missing ID (verified line 129-130) | HA already handles this. |
| Exponential backoff curve | `2 ** strike_count * 60s` formula | Fixed tuple `BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h)` per PITFALLS §2.1 | The PITFALLS schedule is calibrated against real ban-recovery data. Don't reinvent. |
| Jitter generation | Hashing entry_id mod 60, custom PRNG | `random.uniform(-30, 30)` | Standard, deterministic with seed, no entropy concerns (non-crypto). |
| Cross-midnight time range | Custom modular-arithmetic comparison | Two-clause OR: `t >= start or t < end` when `start > end`, else `start <= t < end` | Standard Python recipe, two lines, verified above. |
| Update interval mutation | `_unsub_refresh` manipulation, manual `async_track_time_change` | Direct assignment `self.update_interval = new_value` | Verified live: setter at line 247-251 is the supported path; `_schedule_refresh` reads the cached value. |
| Naive datetime comparison | Strip tzinfo, compare in UTC, hand-localize | `now.astimezone(school_tz).time()` then time-of-day comparison | Stdlib handles DST and offset correctly; manual conversion is the Pitfall 4 source. |
| Year-rollover detection | `async_track_time_change(hour=0, minute=0, second=0)` listener | Per-tick `if cached_year != now.year: recompute` | Simpler, no extra HA primitive, executor-wrapped once per year. |

**Key insight:** Phase 5's apparent complexity is all in the BRANCHING LOGIC (when does which interval apply). The PRIMITIVES (jitter, mutation, dedupe, fériés) all have first-class library/stdlib solutions. Hand-rolling any of them adds risk without benefit.

## Runtime State Inventory

> Phase 5 is a feature-addition phase, NOT a rename/refactor/migration. No legacy strings are being replaced; no entries are being migrated.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 5 adds NO `entry.data` keys. New runtime fields (`_consecutive_failures`, `_backoff_until`, `runtime_data.holiday_dates`) are in-memory only (D-12, C-07). | None |
| Live service config | None — Phase 5 does not change Pronote-side device_name, does not add HA services | None |
| OS-registered state | None | None |
| Secrets/env vars | None — Phase 5 does NOT touch credentials. Persistent notification body uses `redact()` to strip any token/URL/password the err.message might contain (verified `api/errors.py:redact` regex patterns) | None |
| Build artifacts | None — `holidays==0.97` is a new manifest dep; pip will resolve and install on HA reload of the entry. No egg-info, no compiled artifacts in this repo. | None |

**Nothing migrated in any category.** The phase is purely additive. The C-03 probe script (`scripts/probe_nc_holidays.py`) is the only "build artifact" — committed Python file that prints the holiday set; its output (`tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`) is also a committed artifact.

## Common Pitfalls

### Pitfall 1: Mutating `self._update_interval` Instead of `self.update_interval`

**What goes wrong:** Setting `coordinator._update_interval = new_value` skips the setter, leaving `_update_interval_seconds` cache stale. The next `_schedule_refresh` reads the OLD cached seconds — interval mutation silently has no effect.

**Why it happens:** Confusion between the public property (line 242-251) and the underscore-prefixed attribute. Both work in IDE autocomplete; only the property invokes the setter.

**How to avoid:** Always assign to `self.update_interval` (no underscore prefix). Add a test that asserts BOTH `coordinator.update_interval` AND `coordinator._update_interval_seconds` are consistent after mutation.

**Warning signs:** Backoff state correctly set in `_backoff_until` but next-poll fires at the previous (short) cadence; tests pass when checking the property but real polling cycle ignores the change.

### Pitfall 2: `persistent_notification.async_create` Called Without `notification_id`

**What goes wrong:** Each strike creates a NEW notification (auto-generated random hex ID per line 102). The user sees 5 stacked "IP suspendue" notifications instead of one updating in place. D-15 dedupe contract is violated.

**Why it happens:** Forgetting the `notification_id=` kwarg. Optional in the signature, fatal for the UX contract.

**How to avoid:** Always pass `notification_id=f"{DOMAIN}_{entry_id}_{kind}"` (D-15 wording verbatim). Test asserts: 3 strikes → exactly 1 call to `async_create` per kind (assert mock call count == 3 OR assert `notification_id` is identical across the 3 calls — both are valid).

**Warning signs:** Multiple stacked notifications in the HA UI; test asserts on `call_count` instead of `call_args.kwargs['notification_id']`.

### Pitfall 3: Calling `persistent_notification.async_create` From an Executor Thread

**What goes wrong:** `async_create` is `@callback` — must run on the event loop. From an executor thread, calling it directly raises a thread-safety violation (HA logs `Error executing job: <function>` and the notification fails silently).

**Why it happens:** Putting the notification creation inside an `async_add_executor_job` block alongside the pronotepy call.

**How to avoid:** Coordinator's `_handle_failure` runs on the event loop (called from inside `_async_update_data`'s except branches — those execute on the loop). Notification creation is plain `persistent_notification.async_create(hass, ...)`. Do NOT wrap in executor. Verified by ARCHITECTURE.md Anti-Pattern 4 (line 566).

**Warning signs:** Notification never appears in UI despite test mock showing `async_create.called == True`. HA log shows `Cannot call from outside event loop`.

### Pitfall 4: `_previous_snapshot` Mutation Order on Skipped Polls

**What goes wrong:** If `_previous_snapshot = snapshot` runs before the `should_poll` short-circuit returns, the next REAL poll diffs against the SKIPPED snapshot (which is the same as the previous real snapshot, so equality — events fire ZERO instead of N expected). If it runs AFTER and the short-circuit returns `self.data`, the snapshot is unchanged (correct).

**Why it happens:** Mis-ordering the suspension short-circuit relative to Phase 4's `_previous_snapshot = snapshot` line.

**How to avoid:** CONTEXT.md D-10 + Phase 4 D-12 order: suspension/backoff short-circuit runs BEFORE the fetch. Since the short-circuit returns `self.data` (NOT `snapshot` — there is no snapshot yet), `_previous_snapshot` is NEVER touched on a skipped poll. Test: simulate poll-poll-skip-skip-poll sequence; assert poll #5 produces the expected diff against poll #2 (the last REAL poll), NOT against poll #4 (the second skip).

**Warning signs:** No events fire after a long weekend / vacation; first poll on Monday morning silently consumes the change without alerting.

### Pitfall 5: Timezone Handling in `is_quiet_hours` / `is_afternoon_window`

**What goes wrong:** Comparing `now.time()` to `time(22, 0)` when `now` is in HA's UTC default — comparing UTC clock-time to NC wall-clock — misses the quiet window by 11 hours.

**Why it happens:** Forgetting to `now.astimezone(school_tz)` BEFORE calling `.time()`. PITFALLS §2.4 documents this exact trap.

**How to avoid:** Politesse helper functions explicitly accept `school_tz: ZoneInfo` as a keyword argument and call `now.astimezone(school_tz).time()` at the top. Assert `now.tzinfo is not None` and raise `ValueError` on naive input (matches Phase 2 D-23 "tz-aware everywhere, fail fast on naive").

**Warning signs:** Tests with `now=datetime(2026, 5, 12, 18, 30)` (naive) silently pass; production logs show events firing at 7 a.m. NC.

### Pitfall 6: Holidays Library Year Rollover

**What goes wrong:** `runtime_data.holiday_dates` cached at setup with `years=2026` — on 1 Jan 2027, dates like 24/09/2027 are missing → `is_school_day(date(2027, 9, 24))` returns True (wrongly) → polling runs on a NC férié.

**Why it happens:** No mechanism to refresh the cache.

**How to avoid:** Per "Specifics" memo: store `(year, frozenset[date])` tuple; check `cached.year == now.year` on every politesse call; on mismatch, executor-recompute. The check is O(1); the recompute is ~ms. The first poll of 2027 absorbs the recompute cost.

**Warning signs:** After the new year, ferié detection silently fails. Test: parametrize on a date in year N (cache) and a date in year N+1 (recompute trigger); assert the second works.

### Pitfall 7: Notification Body Leaking Credentials

**What goes wrong:** The IP-suspended persistent notification's body includes the raw `err.message` from pronotepy. If pronotepy ever echoes the URL with embedded session token (`?Session=ABC123`) or a `password=...` fragment, the user sees it in their HA UI; if they share a screenshot, the secret leaks.

**Why it happens:** Forgetting to wrap `err.message` in `redact()` (already shipped at `api/errors.py:redact`).

**How to avoid:** D-15 specifies "Verbatim Pronote error message (`redact(err.message)` from Phase 2 — strips URL, token, password, uuid)". Test asserts the persistent notification body does NOT contain literal patterns: `password=`, `token=`, `session=`, raw URL with query string (verified `_REDACT_PATTERNS` at `api/errors.py:16-24`).

**Warning signs:** User shares HA screenshot with secret visible. Audit: every notification body construction must end in `redact(...)`.

### Pitfall 8: Jitter Below Minimum on Short Intervals

**What goes wrong:** `compute_interval` branch 3 returns `timedelta(minutes=15) + timedelta(seconds=-30)` if random gives -30s. That's 14m30s — fine. But if a user configures `afternoon_interval = 1 minute` via Phase 6 Options Flow (future), `+ timedelta(seconds=-30)` could give 30 seconds — too aggressive.

**Why it happens:** Jitter can push interval below sensible minimum.

**How to avoid:** D-04 mandates `max(result, timedelta(minutes=1))` clamp. Test: feed `base=timedelta(seconds=10)` (synthetic) + jitter -30s → assert result is `timedelta(minutes=1)`, not `timedelta(seconds=-20)`.

**Warning signs:** Polling cadence faster than expected; HA log shows refresh ticks <1min apart.

## Code Examples

### Pattern: Resolving Politesse Options From `entry.options`

```python
# politesse.py — pure module, no HA imports
from dataclasses import dataclass
from datetime import time, timedelta
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class PolitesseOptions:
    """Frozen view of the politesse-relevant entry.options keys."""
    refresh_interval: timedelta
    afternoon_interval: timedelta
    afternoon_window_start: time
    afternoon_window_end: time
    quiet_hours_start: time
    quiet_hours_end: time
    suspended_cadence: timedelta
    quiet_cadence: timedelta
    school_tz: ZoneInfo
    vacation_ranges: tuple[tuple[date, date], ...]
    holiday_dates: frozenset[date]
```

```python
# coordinator.py — HA-side
def _resolve_options(entry: ConfigEntry, runtime: PronoteData) -> PolitesseOptions:
    """D-17 — read entry.options with defaults from const.py. Log warning + fall back on parse error."""
    from .const import (
        DEFAULT_REFRESH_INTERVAL, DEFAULT_AFTERNOON_INTERVAL,
        DEFAULT_AFTERNOON_WINDOW, DEFAULT_QUIET_HOURS,
        DEFAULT_SUSPENDED_CADENCE, DEFAULT_QUIET_CADENCE,
        NC_VACATION_RANGES_2026, NC_LOCAL_HOLIDAYS_SUPPLEMENT,
    )
    o = entry.options or {}
    try:
        refresh = timedelta(minutes=int(o.get("refresh_interval", DEFAULT_REFRESH_INTERVAL.total_seconds() // 60)))
    except (ValueError, TypeError):
        _LOGGER.warning("Invalid refresh_interval option %r; falling back to default", o.get("refresh_interval"))
        refresh = DEFAULT_REFRESH_INTERVAL
    # ... same parse-or-warn pattern for the other 7 keys ...
    return PolitesseOptions(
        refresh_interval=refresh,
        # ...
        school_tz=runtime.school_tz,
        vacation_ranges=NC_VACATION_RANGES_2026,
        holiday_dates=runtime.holiday_dates | NC_LOCAL_HOLIDAYS_SUPPLEMENT,
    )
```

### Pattern: Suspension Short-Circuit in `_async_update_data`

```python
async def _async_update_data(self) -> Snapshot:
    options = _resolve_options(self.config_entry, self.runtime_data)
    now = dt_util.now(self._school_tz)

    # Backoff short-circuit (priority over should_poll)
    if self._backoff_until is not None and now < self._backoff_until:
        if self.data is not None:  # D-10 first-poll gate
            remaining = self._backoff_until - now
            self.update_interval = remaining + timedelta(seconds=random.uniform(-JITTER_SECONDS, JITTER_SECONDS))
            return self.data

    # Suspension short-circuit
    if not should_poll(now, options) and self.data is not None:  # D-10 first-poll gate
        self.update_interval = compute_interval(now, options)
        return self.data

    # ... existing Phase 3+4 fetch + try/except flow ...

    try:
        snapshot = await self.hass.async_add_executor_job(...)
    except AuthError as err:
        # ... existing _recover_from_auth_error WR-04 path ...
        # If recovery fails:
        try:
            snapshot = await self._recover_from_auth_error(err, today)
            self._reset_breaker_on_success()  # silent recovery counts as success
        except ConfigEntryAuthFailed as recovery_err:
            self._handle_failure(err, kind="auth_circuit")
            raise  # D-13: re-raise the typed exception
    except RateLimitedError as err:
        if err.reason == ErrorReason.IP_SUSPENDED:
            self._handle_failure(err, kind="ip_suspended")
        raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err
    except (CommunicationError, PronoteIntegrationError) as err:
        # D-13: NO breaker tick — transient blip
        raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err

    self._reset_breaker_on_success()  # any successful fetch resets

    # ... existing _previous_snapshot capture + _capture_session + _fire_diff_events ...

    self.update_interval = compute_interval(now, options)
    return snapshot
```

### Pattern: `_handle_failure` / `_reset_breaker_on_success`

```python
def _handle_failure(self, err: PronoteIntegrationError, *, kind: str) -> None:
    """D-13 — tick breaker counter, set backoff_until, create persistent notification.

    Does NOT re-raise — caller raises the typed exception. The notification is ADDITIVE
    per the project's "no silent exceptions" memory.
    """
    from homeassistant.components import persistent_notification

    self._consecutive_failures += 1
    now = dt_util.now(self._school_tz)
    backoff = next_backoff(self._consecutive_failures - 1)  # 0-indexed
    self._backoff_until = now + backoff

    title, body = self._build_notification_body(err, kind, backoff)
    persistent_notification.async_create(
        self.hass,
        message=body,
        title=title,
        notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_{kind}",
    )

def _reset_breaker_on_success(self) -> None:
    """D-14 — reset counter + backoff; dismiss both notifications (idempotent)."""
    from homeassistant.components import persistent_notification

    self._consecutive_failures = 0
    self._backoff_until = None
    persistent_notification.async_dismiss(
        self.hass,
        f"{DOMAIN}_{self.config_entry.entry_id}_ip_suspended",
    )
    persistent_notification.async_dismiss(
        self.hass,
        f"{DOMAIN}_{self.config_entry.entry_id}_auth_circuit",
    )
```

### Pattern: Quiet-Hours Event Gate in `_fire_diff_events`

```python
def _fire_diff_events(self, previous: Snapshot | None, new: Snapshot) -> None:
    """Phase 5 extension: gate hass.bus.async_fire on should_fire_event (D-09).

    Per CONTEXT.md "Specifics" — call should_fire_event ONCE at the top, cache the result.
    Either every event in this poll fires OR none — no half-suppressed batch.
    """
    options = _resolve_options(self.config_entry, self.runtime_data)
    now = dt_util.now(self._school_tz)
    should_fire = should_fire_event(now, options)

    # Run diff loops regardless (they're pure; _previous_snapshot already captured by caller)
    lessons_today = diff_lessons(previous, new, "today")
    lessons_tomorrow = diff_lessons(previous, new, "tomorrow")
    grades = diff_grades(previous, new)
    infos = diff_notifications(previous, new)

    if not should_fire:
        total = len(lessons_today) + len(lessons_tomorrow) + len(grades) + len(infos)
        if total:
            _LOGGER.debug("Suppressed %d events during quiet hours for entry %s", total, self.config_entry.entry_id)
        return

    # ... existing Phase 4 child_context + bus.async_fire loops (unchanged) ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `update_interval` static (delphiki) | Adaptive `update_interval` via Pattern 4 (CONTEXT.md D-04) | Phase 5 differentiator | The ONLY meaningful integration feature beyond delphiki — directly serves the J/J+1 core value |
| `pytz.timezone` (banned in HA Core 2024+) | `zoneinfo.ZoneInfo` (Phase 1 D-31) | HA 2024.x | Already enforced project-wide |
| Custom thread pool for sync libs | `hass.async_add_executor_job` (Phase 3 COORD-02) | HA 2022.x | Already enforced |
| `prov=`/`state=` for holidays subdivision | `subdiv=` parameter (vacanza/holidays unified API) | holidays library 0.32+ | Use `subdiv='NC'` directly |
| `holidays.France()` import behavior | `holidays.country_holidays('FR', subdiv='NC')` functional alias | Newer pattern; either works (D-02 uses `holidays.France(subdiv='NC')`) | Either is correct; CONTEXT.md picks the class form |
| Persistent notification dispatched as service call | `async_create` / `async_dismiss` direct function calls (Phase 5 D-15) | HA 2018+ (well-established) | Tests can patch the function directly; no service-call setup needed |
| Self-managed backoff timing via `async_track_point_in_time` | `self.update_interval = remaining + jitter` (Pattern 4) | Phase 5 architecture choice | Simpler — no extra timer cleanup on unload |
| Hardcoded magic numbers for cadences | `entry.options` reads with const.py defaults (D-17) | Phase 5 + Phase 6 forward-compat | Phase 5 ships read path; Phase 6 adds UI |

**Deprecated / outdated patterns to avoid:**
- `holidays.France(prov='NC')` — deprecated kwarg; use `subdiv='NC'`
- `async_track_time_change(hour=0, minute=0, second=0)` for year-rollover detection — heavier than per-tick year check
- Custom dedupe dict for notifications — HA's `notification_id` is the contract
- `pytz` ANYTHING — banned

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `holidays==0.97` will still be the latest stable at planning time | Stack Verification | LOW — planner re-queries PyPI at probe time (C-02). Worst case: bump to 0.98+ in the manifest. Set-of-2026-dates output verified against the source code, not the version number. |
| A2 | NC subdivision support in `holidays` will not regress between 0.97 and the planner-locked version | Stack Verification | LOW — vacanza/holidays has shipped NC since at least 2024; no deprecation signal in CHANGES.md. C-03 probe re-verifies. |
| A3 | `persistent_notification.async_create` signature stays `(hass, message, title=None, notification_id=None)` through HA 2026.x | Stack Verification | LOW — this signature has been stable since 2018; no deprecation in HA release notes through 2026.4. |
| A4 | `update_interval` setter behavior stays as observed (sets `_update_interval_seconds` cache) through HA 2026.x | Architecture | LOW — public property + setter is the documented API; HA Core hasn't refactored `update_coordinator.py` materially since the 2025.11 `retry_after` addition. |
| A5 | NC vice-rectorat 2027 rentrée stays Mon 15 Feb 2027 (verified at research time but provisional per CONTEXT.md D-01) | Domain Research | MEDIUM — Calendars can shift by a few days when officially published. C-03 probe re-verifies at probe time; if shifted, update the second tuple member of `NC_VACATION_RANGES_2026[-1]` in the same PR. |
| A6 | `freezegun` continues to be a transitive dep of PHACC | Test Patterns | LOW — PHACC tracks HA Core's test deps; HA Core uses freezegun for time-mocking tests. No deprecation signal. |
| A7 | The "Your IP address is suspended" literal stays stable across pronotepy 2.14.x | Domain Research | LOW — pronotepy is in maintenance mode; the literal hasn't changed across 2.14.0..2.14.6. If it ever does, the fix is one constant at `api/client.py:17`. |
| A8 | Saint Vincent de Paul (6 Dec) is NOT a NC civil férié | Domain Research | LOW — confirmed not in `holidays==0.97`; confirmed not in any official NC calendar source. If a user reports their school observes it, populate `NC_LOCAL_HOLIDAYS_SUPPLEMENT`. |
| A9 | Pronote-side IP-suspension TTL averages 24h–72h for typical bans | Domain Research | LOW — derived from PITFALLS §2.1 surveying multiple bans. The 24h backoff cap is calibrated for this; if real bans average longer, manual user intervention is the recovery path (acceptable for v1). |

**Items requiring user confirmation:** None — all assumptions are mitigatable via the C-03 probe step OR have a fallback in CONTEXT.md.

## Open Questions

1. **Whether to log the suppressed-event count in `_fire_diff_events` at INFO or DEBUG.**
   - What we know: D-09 says `_LOGGER.debug("Event suppressed during quiet hours: %s", event_type)`.
   - What's unclear: should the count be at INFO so the HA log over 24h is observable (ROADMAP SC#1: "observable in HA logs over a 24h window")?
   - Recommendation: keep DEBUG per D-09 verbatim; rely on the cadence-change being observable via the visible coordinator polling intervals. ROADMAP SC#1 mentions "logs" but the test will assert on the cadence change, not log lines.

2. **Whether to include the troubleshooting URL as a clickable Markdown link in the notification body or as plain text.**
   - What we know: D-15 says "Link to the Phase 7 troubleshooting README (placeholder URL — Phase 7 fills it)".
   - What's unclear: HA's persistent notification rendering accepts Markdown (`[text](url)` becomes a clickable link).
   - Recommendation: use Markdown link syntax — HA renders it in the UI; the test doesn't care about render, only about substring presence.

3. **Whether to gate `_handle_failure` calls behind `self._consecutive_failures < len(BACKOFF_SCHEDULE)`.**
   - What we know: `next_backoff(strike_index)` already clamps to `min(strike_index, 4)` (D-11).
   - What's unclear: should the counter keep incrementing past 5 (so diagnostics show "Strike 47") or saturate?
   - Recommendation: let it keep counting (no special clamp). `next_backoff` already returns 24h for any `strike_index >= 4`. The diagnostics surface (Phase 7) can display the raw count.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `holidays` PyPI package | Politesse: NC fériés | ✓ (at install time via manifest.json requirements) | 0.97 (verified PyPI 2026-05-25) | — |
| Python 3.14.2+ | Politesse + everything | ✓ (HA 2026.4 enforces) | 3.14.2 | — |
| `pronotepy==2.14.6` | Phase 2 (unchanged) | ✓ (Phase 1 D-14 locked) | 2.14.6 | — |
| `pytest-freezer` / `freezegun` | Backoff tests (Plan 05-03) | ✓ (transitive via PHACC) | 0.4.9 / 1.5.5 | — |
| HA `persistent_notification` component | D-15 notifications | ✓ (HA built-in, always loaded) | — | — |
| `data.gouv.nc` access | NC calendar live fetch (DEFERRED) | n/a — out of scope for v1 | — | Hardcoded `NC_VACATION_RANGES_2026` |
| Internet for `holidays` updates | Daily-cron CI (DEFERRED to Phase 7) | n/a — out of scope for Phase 5 | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest-homeassistant-custom-component==0.13.326` + `pytest 9.0.3` + `pytest-asyncio 1.3.0` + `pytest-freezer 0.4.9` (newly used) |
| Config file | `/data/projets/perso/pronote/pyproject.toml` (already has `asyncio_mode = "auto"` per Phase 1 D-29) |
| Quick run command | `uv run pytest tests/test_politesse.py -x` (pure, no HA — sub-second) |
| Full suite command | `uv run pytest tests/ --cov=custom_components.ha_pronote --cov-fail-under=90` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COORD-04 | 17h-20h NC tightens to 15min on weekday with tomorrow=school-day | unit (pure) | `pytest tests/test_politesse.py::test_compute_interval_afternoon_tightens -x` | ❌ Wave 1 |
| COORD-04 | Sunday 19h NC tightens to 15min (primer for Mon school) | unit (pure) | `pytest tests/test_politesse.py::test_compute_interval_sunday_primer -x` | ❌ Wave 1 |
| COORD-05 | Saturday morning suspends (should_poll=False, suspended_cadence) | unit (pure) | `pytest tests/test_politesse.py::test_should_poll_weekend -x` | ❌ Wave 1 |
| COORD-05 | Mid-vacation Wed afternoon suspends | unit (pure) | `pytest tests/test_politesse.py::test_should_poll_vacation -x` | ❌ Wave 1 |
| COORD-05 | Férié (24/9/2026) suspends regardless of weekday | unit (pure) | `pytest tests/test_politesse.py::test_should_poll_holiday -x` | ❌ Wave 1 |
| COORD-05 | Suspension short-circuit in coordinator skips fetch, returns self.data, doesn't fire events | integration (hass + freezer) | `pytest tests/test_coordinator.py::test_suspension_short_circuit -x` | ❌ Wave 2 |
| COORD-06 | Quiet hours 22h-6h NC: should_fire_event=False even on real changes | unit (pure) | `pytest tests/test_politesse.py::test_should_fire_event_quiet_hours -x` | ❌ Wave 1 |
| COORD-06 | _fire_diff_events runs diff loops but skips hass.bus.async_fire during quiet | integration (hass) | `pytest tests/test_coordinator.py::test_quiet_hours_suppresses_events_but_diff_runs -x` | ❌ Wave 2 |
| COORD-07 | 3 consecutive AuthError → backoff_until = now + 4h, ConfigEntryAuthFailed raised, persistent_notification.async_create called once with stable id | integration (hass + freezer) | `pytest tests/test_coordinator.py::test_3_strike_auth_sets_4h_backoff_and_notification -x` | ❌ Wave 2 |
| COORD-07 | 5+ strikes saturate at 24h (BACKOFF_SCHEDULE clamp) | integration (hass + freezer) | `pytest tests/test_coordinator.py::test_5_strikes_saturate_at_24h -x` | ❌ Wave 2 |
| COORD-08 | Single RateLimitedError(IP_SUSPENDED) → backoff_until = now + 1h, UpdateFailed raised, persistent notification with kind="ip_suspended" | integration (hass + freezer) | `pytest tests/test_coordinator.py::test_ip_suspended_sets_1h_backoff_and_notification -x` | ❌ Wave 2 |
| COORD-08 | Notification body contains redacted err.message (no `token=`, `password=`, raw URL) | integration (hass) | `pytest tests/test_coordinator.py::test_notification_body_is_redacted -x` | ❌ Wave 2 |
| COORD-08 | Notification dedupes on same notification_id across multiple strikes | integration (hass + freezer) | `pytest tests/test_coordinator.py::test_notification_deduped_by_id -x` | ❌ Wave 2 |
| COORD-08 | Successful poll dismisses both notifications (idempotent on missing IDs) | integration (hass) | `pytest tests/test_coordinator.py::test_success_dismisses_both_notifications -x` | ❌ Wave 2 |
| COORD-09 | compute_interval with `rng=random.Random(seed=42)` produces values within [base-30s, base+30s] over 100 calls | unit (pure) | `pytest tests/test_politesse.py::test_jitter_within_bounds -x` | ❌ Wave 1 |
| COORD-09 | compute_interval clamps to ≥ 1min on freak negative jitter against tiny base | unit (pure) | `pytest tests/test_politesse.py::test_jitter_clamps_to_one_minute -x` | ❌ Wave 1 |
| DIST-06 | Every test in test_politesse.py runs under both `tz=Europe/Paris` AND `tz=Pacific/Noumea` (parametrized) — total 22 tests × 2 tz = 44 parameterized invocations | unit (pure) | `pytest tests/test_politesse.py -v` | ❌ Wave 1 |
| SC#1 (ROADMAP) | 24h synthetic clock walk over compute_interval produces ≥ 5 distinct cadence values (proves observable variation) | unit (pure) | `pytest tests/test_politesse.py::test_24h_walk_produces_5_distinct_cadences -x` | ❌ Wave 1 |
| SC#2 (ROADMAP) | next_backoff(0)=1h, next_backoff(4)=24h, next_backoff(99)=24h (saturation) | unit (pure) | `pytest tests/test_politesse.py::test_next_backoff_schedule -x` | ❌ Wave 1 |
| SC#3 (ROADMAP) | Every compute_interval branch hit at least once across the parameter matrix | unit (pure) | `pytest tests/test_politesse.py::test_all_branches_covered --cov=custom_components.ha_pronote.politesse --cov-fail-under=100` | ❌ Wave 1 |
| SC#4 (ROADMAP) | Polling intervals include ±30s jitter (subsumed by COORD-09 tests) | unit (pure) | Same as COORD-09 | — |
| AST guard | politesse.py has zero `homeassistant.*` imports | unit (pure) | `pytest tests/test_no_ha_imports.py -x` (after extending GUARDED_PATHS) | ✅ exists; needs Wave 1 extension |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_politesse.py -x` (sub-2-second; ~22 tests × 2 tz)
- **Per wave merge:** `uv run pytest tests/ -x --cov=custom_components.ha_pronote --cov-fail-under=90`
- **Phase gate:** Full suite green; `tests/test_no_ha_imports.py` confirms politesse.py is HA-free; coverage on `politesse.py` ≥ 95% (branches: 4 in compute_interval × 2 in should_poll × 2 in should_fire_event × 5 in next_backoff)

### Wave 0 Gaps
- [ ] `tests/test_politesse.py` — NEW. Tests all 22 scenarios from D-20 ("Test layout") + the 5 ROADMAP SC validation tests. Pure pytest, no `hass` fixture.
- [ ] `tests/test_coordinator.py` — EXTEND. Add ~10 new test functions for suspension/backoff/quiet-hours scenarios. Uses `freezer` fixture.
- [ ] `tests/test_no_ha_imports.py` — EXTEND. Add `politesse.py` to `GUARDED_PATHS` (currently `api/`, `diff/`, `tests/test_api/`, `tests/test_diff/`).
- [ ] `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md` — NEW. Captures `holidays.France(subdiv='NC', years=2026)` output verbatim; sanity-asserts in `tests/test_fixtures.py` or in a dedicated `tests/test_holidays_probe.py`.
- [ ] `scripts/probe_nc_holidays.py` — NEW (C-03). Committed Python script that prints the NC 2026 holiday set + names. Output captured into the probe notes.

*(No framework install needed — `pytest-homeassistant-custom-component==0.13.326`, `pytest-freezer`, `freezegun` all already in requirements_test.txt transitively per Phase 1 D-29.)*

## Test Patterns

### Pure Politesse Tests — No Hass, No Freezer

```python
# tests/test_politesse.py
"""D-20 — pure unit tests for politesse.py. No hass fixture, no freezer.

Time is mocked by passing synthetic tz-aware ``now`` arguments directly.
DIST-06: every test parametrized on tz=[Europe/Paris, Pacific/Noumea].
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.politesse import (
    BACKOFF_SCHEDULE, JITTER_SECONDS,
    compute_interval, should_poll, should_fire_event,
    next_backoff, is_school_day, is_quiet_hours, is_afternoon_window,
    PolitesseOptions,
)

@pytest.fixture
def default_options():
    """Builder returning a PolitesseOptions with all defaults populated."""
    def _build(tz_name: str) -> PolitesseOptions:
        return PolitesseOptions(
            refresh_interval=timedelta(minutes=30),
            afternoon_interval=timedelta(minutes=15),
            afternoon_window_start=time(17, 0),
            afternoon_window_end=time(20, 0),
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(6, 0),
            suspended_cadence=timedelta(hours=6),
            quiet_cadence=timedelta(hours=4),
            school_tz=ZoneInfo(tz_name),
            vacation_ranges=(
                (date(2026, 4, 4), date(2026, 4, 19)),
                # ... etc per D-01 ...
            ),
            holiday_dates=frozenset({date(2026, 9, 24), date(2026, 5, 1), ...}),
        )
    return _build

@pytest.mark.parametrize("tz", ["Europe/Paris", "Pacific/Noumea"])
def test_compute_interval_afternoon_tightens(tz, default_options):
    """COORD-04: weekday 18h NC with tomorrow=school-day → 15min branch."""
    options = default_options(tz)
    # Tue 12 May 2026 18:00 NC (or Paris — both are weekdays with Wed=school-day)
    now = datetime(2026, 5, 12, 18, 0, tzinfo=ZoneInfo(tz))
    rng = random.Random(seed=42)
    interval = compute_interval(now, options, rng=rng)
    # Within [15min - 30s, 15min + 30s]
    delta = abs((interval - timedelta(minutes=15)).total_seconds())
    assert delta <= JITTER_SECONDS, f"interval={interval} outside afternoon ± jitter for tz={tz}"

@pytest.mark.parametrize("tz", ["Europe/Paris", "Pacific/Noumea"])
def test_should_poll_holiday(tz, default_options):
    """COORD-05: 24/9/2026 (Fête de la Citoyenneté) suspends."""
    options = default_options(tz)
    now = datetime(2026, 9, 24, 14, 0, tzinfo=ZoneInfo(tz))  # Thursday
    assert should_poll(now, options) is False

@pytest.mark.parametrize("tz", ["Europe/Paris", "Pacific/Noumea"])
def test_24h_walk_produces_5_distinct_cadences(tz, default_options):
    """SC#1: a 24h synthetic clock walk produces at least 5 distinct intervals.

    Proves cadence varies observably across a day's branches.
    """
    options = default_options(tz)
    rng = random.Random(seed=42)
    intervals = set()
    base = datetime(2026, 5, 12, 0, 0, tzinfo=ZoneInfo(tz))  # Tue 00:00
    for hour in range(24):
        now = base + timedelta(hours=hour)
        # Round to 1-minute granularity to ignore jitter for distinct-count
        interval = compute_interval(now, options, rng=rng)
        intervals.add(round(interval.total_seconds() / 60))
    assert len(intervals) >= 5, f"got {len(intervals)} distinct cadences for tz={tz}"
```

### Coordinator Backoff Tests — `freezer` + Mock Notification

```python
# tests/test_coordinator.py extensions (Plan 05-03)
@pytest.fixture
def mock_persistent_notification(monkeypatch):
    """Patch persistent_notification.async_create / async_dismiss; return both mocks."""
    create_mock = MagicMock()
    dismiss_mock = MagicMock()
    monkeypatch.setattr(
        "homeassistant.components.persistent_notification.async_create",
        create_mock,
    )
    monkeypatch.setattr(
        "homeassistant.components.persistent_notification.async_dismiss",
        dismiss_mock,
    )
    return create_mock, dismiss_mock

async def test_ip_suspended_sets_1h_backoff_and_notification(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today,
    freezer, mock_persistent_notification,
):
    """COORD-08: single RateLimitedError(IP_SUSPENDED) → 1h backoff + notification."""
    create_mock, _ = mock_persistent_notification
    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)

    # Setup with a successful first poll
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.ha_pronote.build_or_resume_client", return_value=mock_pronote_client),
        patch("custom_components.ha_pronote.coordinator.fetch_all",
              return_value=snapshot_with_n_lessons_today(t0.date(), n=1)),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator._consecutive_failures == 0

    # Inject IP_SUSPENDED on next poll
    with patch("custom_components.ha_pronote.coordinator.fetch_all",
               side_effect=RateLimitedError("Your IP address is suspended", reason=ErrorReason.IP_SUSPENDED)):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 1
    assert coordinator._backoff_until == t0 + timedelta(hours=1)
    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["notification_id"].endswith("_ip_suspended")
    # COORD-08 — body redacted
    assert "Your IP address is suspended" in call_kwargs["message"]
    assert "password=" not in call_kwargs["message"]
    assert "token=" not in call_kwargs["message"]

async def test_success_dismisses_both_notifications(
    hass, mock_config_entry, mock_pronote_client, snapshot_with_n_lessons_today,
    mock_persistent_notification,
):
    """D-14: any successful poll dismisses both notification IDs (idempotent)."""
    _, dismiss_mock = mock_persistent_notification
    # ... setup with a successful poll ...
    # Assert both dismiss calls happened (one per notification_id), even if neither was active
    assert dismiss_mock.call_count == 2
    call_ids = [c.args[1] for c in dismiss_mock.call_args_list]
    assert any(id_.endswith("_ip_suspended") for id_ in call_ids)
    assert any(id_.endswith("_auth_circuit") for id_ in call_ids)
```

### NC Vacation Date Verification Against data.gouv.nc (Probe Step)

```python
# scripts/probe_nc_holidays.py — committed
"""C-03 probe: enumerate the 2026 NC fériés produced by holidays.France(subdiv='NC').

Run via: uv run python scripts/probe_nc_holidays.py
Output: redirect into tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md
"""
from __future__ import annotations

import holidays

print("# Phase 5 Probe — NC fériés via holidays.France(subdiv='NC')")
print(f"# holidays version: {holidays.__version__}")
print()

for year in (2026, 2027):
    fr_nc = holidays.France(subdiv="NC", years=year)
    print(f"## Year {year} — {len(fr_nc)} dates")
    for d, name in sorted(fr_nc.items()):
        print(f"- {d.isoformat()}: {name}  ({d.strftime('%A')})")
    print()

# Sanity assertions
fr_nc_2026 = holidays.France(subdiv="NC", years=2026)
assert date(2026, 9, 24) in fr_nc_2026, "Fête de la Citoyenneté missing"
assert date(2026, 1, 1) in fr_nc_2026, "Jour de l'an missing"
assert date(2026, 5, 1) in fr_nc_2026, "Fête du Travail missing"
assert date(2026, 12, 25) in fr_nc_2026, "Noël missing"
print(f"# Probe OK — {len(fr_nc_2026)} dates verified for NC 2026")
```

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `holidays==0.97` introduces a breaking API change in subsequent minor (0.98+) before Phase 7 cron-CI lands | LOW | Phase 5 unit tests fail; users on a HA reload with auto-bump are affected | Exact `==0.97` pin (C-02). Phase 7's DIST-04 cron extends to `holidays + pronotepy` per "Phase 5 → Phase 7 interface" (CONTEXT.md line 433). |
| `persistent_notification.async_create` signature changes in HA 2026.5+ | LOW | Coordinator extension test fails | Pin HA floor in `hacs.json` to `2026.4.0` (Phase 1 D-12). Watch HA Core changelog. The API has been stable since 2018; no deprecation in sight. |
| NC vice-rectorat shifts the 2027 rentrée date late in the school year | MEDIUM | `is_school_day(date(2027, 2, 15))` returns False (vacation) when it should return True | C-03 probe verifies the date against `data.gouv.nc` at probe time. PR template item: "If NC 2027 rentrée shifted, update `NC_VACATION_RANGES_2026[-1]` second member in the same PR." |
| `_recover_from_auth_error` recovery succeeds but the new client also gets banned in the same poll | LOW | Counter ticks on the auth path (D-13) but the IP_SUSPENDED path doesn't fire — silent inconsistency | The current `coordinator.py` already routes `RateLimitedError` raised during recovery as a separate except branch (line 221-223). Phase 5 extends to call `_handle_failure(err, kind="ip_suspended")` on that branch too. Test scenarios cover both. |
| `freezegun` interaction with `dt_util` shimmed for some calls but not others | LOW | Backoff tests pass locally but fail in CI due to time skew | Use `freezer.move_to(absolute_datetime)` (not `freezer.tick(timedelta)`) — absolute moves are tz-explicit. All assertions compare to `t0 + timedelta(...)` derived from the same `freezer.move_to`. Verified pattern in PHACC docs. |
| `holidays.France(subdiv='NC')` instantiation cost surprise (e.g. lazy `_populate` triggered at first lookup) | LOW | First politesse call after setup is slow | Performance is microseconds (verified source: 12 method calls). Even on a Raspberry Pi 4, <1ms. C-07 executor-wrap is the defensive choice. |
| `entry.options.get("refresh_interval", DEFAULT)` returns a non-int (e.g. a stale Phase 6 string) | LOW | Phase 5 ships before Phase 6 — `entry.options` empty in practice | D-17 + `_resolve_options` adapter handles parse errors with `_LOGGER.warning` + default fallback. Test: pass `{"refresh_interval": "not-a-number"}` → assert warning logged + default used. |
| User restart during a long backoff loses the counter state | LOW | Counter resets to 0 on restart per D-12; next poll re-raises the breaking exception → counter ticks back up | Intended behavior per D-12. The 1h-backoff on first re-strike is plenty of time for the user to investigate. No additional mitigation needed. |
| Heavy `_fire_diff_events` payload during a long-vacation re-poll generates a flood of "new" events on rentrée | LOW | EVENT-04 invariant covers first-poll-after-restart, but NOT first-poll-after-long-suspension | `_previous_snapshot` is preserved across skipped polls (Pitfall 4 in this doc). So rentrée's first real poll diffs against the last pre-vacation snapshot — correct. The only mass-fire scenario is if the user adds the integration mid-vacation; the FIRST poll has `previous is None` → diff returns `[]` (EVENT-04 holds). |
| `holidays==0.97` Python 3.14 compatibility regression | LOW | Setup fails to install dep; HA reports CONFIG_ENTRY_NOT_LOADED | PyPI metadata says `requires_python >= 3.10`, includes 3.14. CI in Phase 1 runs against 3.14.2 — any regression would surface in PR CI before merge. |

## Contradictions to CONTEXT.md

**None — research confirms CONTEXT.md decisions.**

Items checked carefully (and confirmed):

1. **D-01 `(date(2026, 12, 19), date(2027, 2, 14))`** — Verified: rentrée élèves 2027 = Monday 15 Feb 2027 per `vacances-scolaires-education.fr`. Inclusive end-date = Sunday 14 Feb 2027 is exactly correct (the day before rentrée). This is a planning-time-correct assumption; the C-03-equivalent probe at planning time should re-verify the official `data.gouv.nc` source, but no contradiction surfaced.
2. **D-02 `holidays.France(subdiv='NC')` recognised** — Verified: subdivisions tuple line 70 of `france.py` (dev master, fetched 2026-05-25) includes `"NC", # Nouvelle-Calédonie,`. Subdivision aliases line 95 also lists `"Nouvelle-Calédonie": "NC"`.
3. **D-02 Fête de la Citoyenneté 24/9 included** — Verified: `_populate_subdiv_nc_public_holidays` (lines 287-298) adds exactly `_add_holiday_sep_24("Fête de la Citoyenneté")` for years >= 2004.
4. **D-02 Saint Vincent de Paul 6/12 supplement** — Verified: NOT in `holidays==0.97`; cross-checked NOT a NC civil férié (only Catholic-school patron in specific establishments). `NC_LOCAL_HOLIDAYS_SUPPLEMENT = frozenset()` (D-18) is correct.
5. **D-11 `BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h)` from PITFALLS.md §2.1** — Verified verbatim in `.planning/research/PITFALLS.md` line 28: "**Détecter explicitement le message « Your IP address is suspended »** dans l'erreur pronotepy → backoff exponentiel long (1h, 2h, 4h, 12h, 24h, plafond 24h)".
6. **D-15 `persistent_notification.async_create` is `@callback` (sync from event loop)** — Verified: lines 92-93 of `persistent_notification/__init__.py` master. Idempotent on `notification_id` collision (line 103); silent no-op on missing dismiss target (line 130).
7. **C-07 `holidays.France(subdiv='NC')` should be executor-wrapped at setup** — Verified: NO blocking I/O in the lib (source-read), but discipline-wise the executor-wrap is correct. Cost is microseconds.
8. **D-13 strike rules: only `AuthError` (post-recovery) and `RateLimitedError(IP_SUSPENDED)` tick** — Verified consistent with Phase 3 D-22 error mapping and WR-04 cooldown gate at `coordinator.py:127-141`.
9. **D-09 quiet hours event suppression: drop with debug log, no queue** — Verified consistent with EVENT-04 invariant (no events on first poll after restart) and PITFALLS §2.9 ("Notifications EDT changé à 3h du matin").
10. **D-20 tz-matrix on `[Europe/Paris, Pacific/Noumea]`** — Verified consistent with Phase 2 D-25 (already in `tests/test_api/` and `tests/test_diff/`).

## Sources

### Primary (HIGH confidence)
- `vacanza/holidays` dev branch source — `holidays/countries/france.py` (fetched 2026-05-25 from `https://raw.githubusercontent.com/vacanza/holidays/dev/holidays/countries/france.py`) — subdivisions line 60-76, NC code line 287-298
- HA Core master `homeassistant/components/persistent_notification/__init__.py` (fetched 2026-05-25 from raw.githubusercontent.com) — `async_create` line 92-115, `async_dismiss` line 125-136
- HA Core master `homeassistant/helpers/update_coordinator.py` (fetched 2026-05-25) — `update_interval` setter line 242-251, `_schedule_refresh` line 253-280, `_async_refresh` line 411-579 with `_retry_after` semantics
- PyPI `https://pypi.org/pypi/holidays/json` (fetched 2026-05-25) — version `0.97`, released `2026-05-18`, `requires_python >= 3.10`
- `vacances-scolaires-education.fr/vacances-scolaires-noumea-nouvelle-caledonie.html` — NC 2026-2027 calendar verbatim
- Codebase files inspected directly:
  - `custom_components/ha_pronote/coordinator.py` (Phase 3+4 shipped surface)
  - `custom_components/ha_pronote/api/errors.py` (redact + ErrorReason)
  - `custom_components/ha_pronote/api/client.py` (`_IP_SUSPENDED_LITERAL` at line 17)
  - `custom_components/ha_pronote/api/fetcher.py` (IP-suspended detection)
  - `custom_components/ha_pronote/__init__.py` (setup wiring)
  - `custom_components/ha_pronote/const.py` (existing constants)
  - `custom_components/ha_pronote/data.py` (PronoteData dataclass)
  - `tests/test_no_ha_imports.py` (`GUARDED_PATHS` definition)
  - `tests/conftest.py` (existing fixtures)
  - `requirements_test.txt` (transitive freezegun)
  - `pyproject.toml` (`asyncio_mode = "auto"`, `requires-python = ">=3.14.2"`)
- `.planning/research/PITFALLS.md` §2.1 (IP suspension empirical data), §2.4 (NC TZ + austral calendar), §2.9 (night/weekend noise)
- `.planning/research/ARCHITECTURE.md` Pattern 4 (lines 279-313), Pattern 5 (lines 315-330)
- `.planning/research/SUMMARY.md` Phase 5 section (lines 134-141)
- `.planning/REQUIREMENTS.md` COORD-04..09 + DIST-06
- `.planning/ROADMAP.md` Phase 5 success criteria (lines 128-138)
- `.planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/05-CONTEXT.md` (full read)

### Secondary (MEDIUM confidence — community / documentation)
- `https://github.com/vacanza/holidays` README + CHANGES.md (via Context7 docs lookup) — `subdiv` parameter unification documented
- `MatthewFlamm/pytest-homeassistant-custom-component` README — `freezer` fixture + `enable_custom_integrations` autouse pattern
- HA Developer Docs §"DataUpdateCoordinator" (`https://developers.home-assistant.io/docs/integration_fetching_data`) — Pattern 4 widely adopted; `last_update_success_time`
- `data.gouv.nc/explore/dataset/calendrier_scolaire_nc/` — NC vacation calendar authoritative source (deferred consumption to v1.x; planning-time secondary)
- `lepetitjournal.com/nouvelle-caledonie/jours-feries-vacances-scolaires-nouvelle-caledonie-295527` — NC 2026 fériés + vacances cross-check
- `delphiki/HomeAssistant-Pronote/coordinator.py` — reference for the executor-wrap pattern (NOT for the adaptive logic — that's our differentiator)

### Tertiary (LOW confidence — secondary travel sites used only for cross-check, flagged in markdown when used)
- `public-holidays.iamrohit.in/holidays/nc/2026` — used as a third-source confirmation for NC 2026 fériés set; cross-verified against the primary `holidays` library source

## Metadata

**Confidence breakdown:**
- Standard stack (`holidays==0.97`): HIGH — version + NC subdivision verified against PyPI metadata + source code on the day of writing
- Architecture (Pattern 4 + Pattern 5 refinement, persistent_notification idempotency): HIGH — verified against live HA Core master source
- Validation Architecture: HIGH — every test maps to a CONTEXT.md decision verbatim
- NC calendar dates (2026 + 2027 rentrée): MEDIUM-HIGH — primary library source confirmed; the 2027 rentrée provisional flag from CONTEXT.md remains a planner-probe checkpoint
- Test patterns (freezegun, mock_persistent_notification): HIGH — patterns used widely in HA Core's own test suite
- Pitfalls: HIGH — derived from existing PITFALLS.md + the code-inspection-confirmed behaviour of `update_coordinator.py` + `persistent_notification/__init__.py`

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (30 days — stable domain). `holidays` PyPI metadata + HA Core master should be re-checked at probe time if the planner waits more than 2 weeks.
