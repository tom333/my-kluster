# Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

The integration's safety belt. Phase 5 makes polling cadence vary by time of
day, day of week, and the NC school calendar; suppresses bus events during
night quiet-hours; and trips a circuit breaker on auth failures or the literal
`Your IP address is suspended` Pronote response — so a misconfigured install
or a fragile school server cannot get the user's IP banned.

**Phase 5 ships:**

1. **New `custom_components/ha_pronote/politesse.py`** — pure HA-free module.
   Public surface: `compute_interval(now, options, *, rng=random) -> timedelta`,
   `should_poll(now, options) -> bool`, `should_fire_event(now, options) -> bool`,
   `next_backoff(strike_index, schedule=BACKOFF_SCHEDULE) -> timedelta`,
   plus the private predicates `is_school_day`, `is_quiet_hours`,
   `is_afternoon_window`, `is_primer_window`. Imports stdlib + `holidays` only.
2. **Coordinator wired to politesse.** `_async_update_data` first checks
   backoff state + `should_poll(now, options)`. If either says "skip", it
   short-circuits: no pronotepy call, `_previous_snapshot` and
   `update_interval` mutated, but no fetch, no diff, no events; returns
   `self.data`. Otherwise normal poll, then `self.update_interval =
   compute_interval(now, options)` at the end (Pattern 4).
3. **Quiet-hours event gate.** `_fire_diff_events` queries
   `should_fire_event(now, options)` before each `hass.bus.async_fire`;
   suppressed events emit a single `_LOGGER.debug` line and are dropped (no
   queue).
4. **Circuit breaker state on the coordinator.**
   `self._consecutive_failures: int = 0` and `self._backoff_until: datetime |
   None = None`, in-memory, reset on every successful poll. Curve is the
   fixed schedule `(1h, 2h, 4h, 12h, 24h)` per PITFALLS.md §2.1.
5. **Persistent HA notification on IP-suspended and 3-strikes-auth circuit
   open.** Deduped by stable `notification_id`; auto-dismissed on recovery.
   Coordinator does NOT swallow the underlying `UpdateFailed` — the notif
   is *additive*, per the project's "no silent exceptions" feedback memory.
6. **Hardcoded NC academic-year 2026 vacation ranges** in `const.py`
   (`NC_VACATION_RANGES_2026: tuple[tuple[date, date], ...]`). Yearly
   hand-update PR.
7. **`holidays` PyPI runtime dep.** New manifest dependency
   `holidays==<pinned>`. `holidays.France(subdiv='NC')` enumerates fériés
   nationaux + NC locaux at integration setup (cached on coordinator).
   Planner verifies `subdiv='NC'` is supported and that NC-specific fériés
   (Fête de la citoyenneté 24/9) are included; if a date is missing, ship
   a hardcoded supplement in `const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT`.
8. **±30s jitter inside `compute_interval`** via `random.uniform(-30, 30)`,
   `rng` parameter injectable for deterministic tests
   (`rng=random.Random(seed=42)`). Production uses stdlib `random` global —
   non-cryptographic on purpose.
9. **TZ-matrixed pure tests** — `tests/test_politesse.py` parameterized on
   `tz=[Europe/Paris, Pacific/Noumea]` (DIST-06). Time-mocked by passing
   synthetic tz-aware `now` arguments; no `freezegun` needed because the
   functions are pure.
10. **AST guard extension** — `tests/test_no_ha_imports.py` adds
    `politesse.py` to the protected list (zero `homeassistant.*` imports,
    same invariant as `api/` and `diff/`).

**In scope (Phase 5 only):**

- `custom_components/ha_pronote/politesse.py` — NEW (pure module, ~200 LOC).
- `custom_components/ha_pronote/coordinator.py` — EXTEND `_async_update_data`
  with backoff + suspension short-circuit; EXTEND `_fire_diff_events` with
  `should_fire_event` gate; ADD `self._consecutive_failures` +
  `self._backoff_until` fields; ADD `_handle_failure(err)` /
  `_reset_breaker_on_success()` helpers; ADD persistent_notification calls
  + dismissal on recovery.
- `custom_components/ha_pronote/const.py` — APPEND `BACKOFF_SCHEDULE`,
  `JITTER_SECONDS`, `DEFAULT_AFTERNOON_INTERVAL`, `DEFAULT_AFTERNOON_WINDOW`,
  `DEFAULT_QUIET_HOURS`, `DEFAULT_SUSPENDED_CADENCE`,
  `DEFAULT_QUIET_CADENCE`, `NC_VACATION_RANGES_2026`,
  `NC_LOCAL_HOLIDAYS_SUPPLEMENT` (probably empty after `holidays` lib
  verification), `IP_SUSPENDED_NOTIFICATION_ID_SUFFIX`,
  `AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX`.
- `custom_components/ha_pronote/manifest.json` — ADD `holidays==<pin>` to
  `requirements`. Planner picks the exact version from PyPI metadata.
- `custom_components/ha_pronote/strings.json` — APPEND notification message
  keys + translation strings (`notification.ip_suspended.title`,
  `notification.ip_suspended.message`, `notification.auth_circuit.title`,
  `notification.auth_circuit.message`). Minimal `fr` + `en` text; Phase 7
  finishes the i18n polish.
- `custom_components/ha_pronote/translations/{fr,en}.json` — APPEND same keys.
- `tests/test_politesse.py` — NEW, pure unit tests + TZ matrix.
- `tests/test_coordinator.py` — EXTEND with circuit-breaker scenarios,
  suspension short-circuit, quiet-hours event gate.
- `tests/test_no_ha_imports.py` — APPEND `politesse.py` to the protected list.

**Out of scope (deferred to later phases):**

- Live fetch of NC calendar from `data.gouv.nc` or
  `fr.ftp.opendatasoft.com/openscol/.../NouvelleCaledonie.ics` — Phase 5
  v1.x or beyond. Hardcoded 2026 dates are the v1 baseline.
- ICS / JSON parser for remote calendar feeds — same deferral.
- OptionsFlow UI for thresholds (refresh_interval, afternoon_interval,
  afternoon_window, quiet_hours, etc.) — Phase 6 (OPT-01..04). Phase 5 ships
  the *runtime read path* (`entry.options.get(KEY, DEFAULT_FROM_CONST)`) so
  Phase 6 is pure UI work + `entry.add_update_listener` wiring.
- Per-entry `school_tz` override — Phase 6 (OPT-04).
- Diagnostics surface (`async_get_config_entry_diagnostics`) exposing the
  circuit-breaker state — Phase 7 (DIAG-01).
- Repair Issue on IP-banned state — Phase 7 (DIAG-02). Phase 5 ships the
  persistent notification (COORD-08 wording); the Repair Issue is the
  Phase 7 upgrade.
- Per-data-type cadence decoupling (notes 6h, EDT 30m) — anti-feature for
  v1 (one coordinator per child = one cadence). Out of REQUIREMENTS scope.
- Daily CI cron against `pronotepy@main` — Phase 7 (DIST-04).
- README documentation of polling behavior / circuit-breaker — Phase 7
  (DIST-07). Phase 5 freezes the behavior; Phase 7 documents.
- Event queueing during quiet hours (buffer + batch-fire at 6h) —
  explicitly rejected (D-09): drop with debug log, do NOT queue.

</domain>

<decisions>
## Implementation Decisions

### NC vacation calendar + fériés (Area 1)

- **D-01:** NC vacation calendar source = **hardcoded 2026 dates in
  `const.py`** as `NC_VACATION_RANGES_2026: tuple[tuple[date, date], ...]`.
  Five frozen `(start_inclusive, end_inclusive)` pairs covering:
  - `(date(2026, 4, 4), date(2026, 4, 19))` — vacances avril
  - `(date(2026, 6, 6), date(2026, 6, 21))` — vacances juin
  - `(date(2026, 8, 8), date(2026, 8, 23))` — vacances août
  - `(date(2026, 10, 10), date(2026, 10, 25))` — vacances octobre
  - `(date(2026, 12, 19), date(2027, 2, 14))` — grandes vacances austral
    (rentrée 2027 date is provisional — planner verifies against
    `data.gouv.nc` at probe time; if it shifts, update the second tuple
    member in the same PR)
  Yearly hand-update PR in Dec/Jan. Live-feed migration deferred to v1.x.
  Source verified: search confirmed `data.gouv.nc/explore/dataset/
  calendrier_scolaire_nc/` publishes this exact list + ICS export at
  `https://data.gouv.nc/api/explore/v2.1/catalog/datasets/calendrier_scolaire_nc/exports/{json,ics}`
  — captured in canonical refs for v1.x migration work.
- **D-02:** Fériés nationaux + NC locaux = **`holidays` PyPI package** via
  `holidays.France(subdiv='NC')`. Manifest dep: `holidays==<latest pinned>`
  (planner pins the exact version). Coordinator pre-fetches the set of
  fériés for the current school year once at setup and caches it on
  `runtime_data.holiday_dates: frozenset[date]`. Planner MUST verify in a
  probe step that `subdiv='NC'` is recognised by the chosen `holidays`
  version and that NC-specific dates are present (Fête de la citoyenneté
  24/9, Saint Vincent de Paul 6/12 if observed). If any date is missing
  in `holidays.France(subdiv='NC')` output, supplement via
  `const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT: frozenset[date]` (empty by
  default; populate only if the probe surfaces gaps). The supplement is
  union'd with the library output, NEVER overrides.
- **D-03:** `is_school_day(date, *, school_tz, vacation_ranges,
  holiday_dates) -> bool` returns True iff:
  - `date.weekday() < 5` (Mon-Fri), AND
  - no `(start, end)` in `vacation_ranges` satisfies `start <= date <=
    end`, AND
  - `date not in holiday_dates`.

### Adaptive interval + quiet hours semantics (Area 2)

- **D-04:** `compute_interval(now, options, *, rng=random) -> timedelta`
  branches (top-down — first match wins):
  1. If `is_quiet_hours(now)` → `options.quiet_cadence` (default 4h) + jitter
  2. Else if `not should_poll(now, options)` → `options.suspended_cadence`
     (default 6h) + jitter — value matters because HA still asks for an
     interval even though `should_poll=False` will skip the call body
  3. Else if `is_afternoon_window(now)` AND `is_school_day(now.date() +
     timedelta(days=1))` → `options.afternoon_interval` (default 15 min)
     + jitter
  4. Else → `options.refresh_interval` (default 30 min) + jitter

  Jitter: `rng.uniform(-JITTER_SECONDS, JITTER_SECONDS)` applied as
  `timedelta(seconds=jitter)`. The returned `timedelta` is clamped to a
  minimum of `timedelta(minutes=1)` so a freak negative jitter on a
  short interval never goes sub-minute.
- **D-05:** `should_poll(now, options) -> bool` returns False iff one of:
  - `now.date()` is a weekend (Sat-Sun) AND `now` is NOT inside a primer
    window
  - `now.date()` is inside a NC vacation range AND `now` is NOT inside a
    primer window
  - `now.date()` is a férié AND `now` is NOT inside a primer window

  Quiet hours do NOT make `should_poll` False — quiet hours slow the
  cadence to ~4h (D-04 branch 1) but the poll itself still runs (the
  4h-cadence keeps the credentials warm + verifies the snapshot once
  overnight). The event suppression honours COORD-06 (D-09).
- **D-06:** Primer window definition: a date `d` is a "primer day" iff
  `is_school_day(d) == False` AND `is_school_day(d + timedelta(days=1))
  == True`. The primer *time window* on a primer day is the same 17h–20h
  NC range as the regular afternoon-tightening window. This unifies the
  weekday afternoon case and the Sunday-evening / last-vacation-day case
  under a single rule: tighter polling whenever `is_school_day(tomorrow)
  AND now is 17:00–20:00 NC`. So compute_interval's branch 3 is the
  *only* place that distinguishes primer vs non-primer — no separate
  primer state.
- **D-07:** `is_afternoon_window(now, *, school_tz, window_start,
  window_end) -> bool` returns True iff the NC-local time-of-day of `now`
  is in `[window_start, window_end)` (half-open: 17:00 inclusive, 20:00
  exclusive). `school_tz` is read from `runtime_data.school_tz` (Phase 3
  D-23); Phase 6 OPT-04 wires the per-entry override.
- **D-08:** `is_quiet_hours(now, *, school_tz, quiet_start, quiet_end) ->
  bool` returns True iff the NC-local time-of-day of `now` is in
  `[quiet_start, 24:00) ∪ [00:00, quiet_end)` when `quiet_start >
  quiet_end` (the 22h–6h cross-midnight case, which is the default), OR
  in `[quiet_start, quiet_end)` when `quiet_start <= quiet_end` (degenerate
  case if a user inverts the bounds in OptionsFlow). Composes with weekend
  / vacation / férié: in any overlap, the most restrictive (skip) wins via
  D-05's `should_poll` branch, which takes precedence in
  `_async_update_data`'s control flow.
- **D-09:** `should_fire_event(now, options) -> bool` returns
  `not is_quiet_hours(now)`. Coordinator's `_fire_diff_events` runs the
  diff loop normally (so `_previous_snapshot` mutation stays correct) but
  before each `hass.bus.async_fire` it queries `should_fire_event`:
  - True → fire normally (existing Phase 4 flow)
  - False → drop the event with `_LOGGER.debug("Event suppressed during
    quiet hours: %s", event_type)`, no queue, no retry

  EVENT-04 (no events at first poll after restart) remains structurally
  enforced by diff functions returning `[]` on `previous is None` —
  unchanged by Phase 5.
- **D-10:** Suspension short-circuit in `_async_update_data`:
  ```python
  now = dt_util.now(self._school_tz)
  if self._backoff_until is not None and now < self._backoff_until:
      self.update_interval = self._backoff_until - now + jitter  # one-shot
      return self.data  # keep sensors populated
  if not should_poll(now, options):
      self.update_interval = compute_interval(now, options)  # ~6h
      return self.data  # skip executor call, keep sensors populated
  # ...existing fetch + diff + capture flow...
  self.update_interval = compute_interval(now, options)
  return snapshot
  ```
  Two key invariants:
  - On the very first poll after `async_setup_entry` (i.e. `self.data
    is None`), the coordinator MUST attempt a real fetch even if
    `should_poll` returns False. Otherwise sensors stay `unavailable`
    forever during a weekend install. Implement by gating the early
    return on `self.data is not None`.
  - `_previous_snapshot` is NOT updated during a skipped poll. Phase 4's
    diff at the next real poll compares against the snapshot from the
    previous *real* poll — exactly the desired behavior.

### Circuit breaker (Area 3)

- **D-11:** Backoff curve = fixed schedule per PITFALLS.md §2.1 verbatim:
  ```python
  BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
      timedelta(hours=1),
      timedelta(hours=2),
      timedelta(hours=4),
      timedelta(hours=12),
      timedelta(hours=24),
  )
  ```
  `next_backoff(strike_index: int) -> timedelta` returns
  `BACKOFF_SCHEDULE[min(strike_index, len(BACKOFF_SCHEDULE) - 1)]`.
  `strike_index` is 0-based (first strike → 1h).
- **D-12:** State on the coordinator instance (in-memory, resets on HA
  restart):
  - `self._consecutive_failures: int = 0`
  - `self._backoff_until: datetime | None = None` (tz-aware in school_tz)
  - HA restart resets to defaults — fine because `async_setup_entry`'s
    `async_config_entry_first_refresh()` will surface a still-broken state
    on the first poll, recreating the breaker state.
  - NOT persisted to `entry.data` (Phase 3 D-08's contract reserves
    entry.data for stable identity fields).
- **D-13:** Strike rules (called from `_handle_failure(err)` helper):
  - `RateLimitedError(IP_SUSPENDED)` from `_async_update_data` →
    `_consecutive_failures += 1`; `_backoff_until = now +
    next_backoff(_consecutive_failures - 1)`; create persistent
    notification with id `f"{DOMAIN}_{entry_id}_ip_suspended"`; raise
    `UpdateFailed` (existing Phase 3 D-22 mapping preserved verbatim).
  - `AuthError` that survives `_recover_from_auth_error` →
    `_consecutive_failures += 1`; `_backoff_until = now +
    next_backoff(_consecutive_failures - 1)`; create persistent
    notification with id `f"{DOMAIN}_{entry_id}_auth_circuit`; raise
    `ConfigEntryAuthFailed` (existing Phase 3 D-22 mapping preserved).
    The WR-04 silent-recovery cooldown (Phase 3 — 5-min gate against
    aliased CryptoError loop) stays intact; the breaker counter ticks
    only on AuthErrors that make it through that gate.
  - `RateLimitedError(reason != IP_SUSPENDED)` or `CommunicationError` or
    other `PronoteIntegrationError` → no breaker tick (transient blip,
    not an IP-ban signal). Existing Phase 3 D-22 `UpdateFailed` mapping
    unchanged.

  The user-selected "run alongside" semantics: at strike 1 the reauth
  flow fires (HA's natural behavior from `ConfigEntryAuthFailed`) AND
  the breaker silences polls for 1h. At strike 3 the breaker has
  reached 4h. The COORD-07 "3 consecutive auth failures" wording is
  over-met — we apply backoff from strike 1 as a stricter politesse
  measure.
- **D-14:** Reset rule: any successful poll (i.e. fetch returns a
  `Snapshot` without exception) calls `_reset_breaker_on_success()`:
  - `self._consecutive_failures = 0`
  - `self._backoff_until = None`
  - `persistent_notification.async_dismiss(hass,
    f"{DOMAIN}_{entry_id}_ip_suspended")`
  - `persistent_notification.async_dismiss(hass,
    f"{DOMAIN}_{entry_id}_auth_circuit")`

  Dismiss-on-success is idempotent — HA silently no-ops when the
  notification doesn't exist.
- **D-15:** Persistent HA notification lifecycle:
  - On strike: `persistent_notification.async_create(hass,
    message=<f-strung template>, title=<f-strung title>,
    notification_id=f"{DOMAIN}_{entry_id}_{kind}")` where `kind ∈
    {ip_suspended, auth_circuit}`. Re-emitting with the same
    `notification_id` is a no-op (HA's dedupe).
  - The message text is built in the coordinator with a French-default
    template ("IP suspendue par le serveur Pronote. Prochaine tentative
    à HH:MM le DD/MM (heure NC). Augmentez votre intervalle de polling
    si cela se reproduit.") and an English fallback. The two templates
    live as Python constants in `coordinator.py` for v1 — Phase 7's
    DIST-07 / I18N-* may upgrade to a `strings.json`-keyed approach if
    HA's `persistent_notification.async_create` ever supports
    translation keys natively. The `strings.json` entries added in
    Phase 5 are FOR THE NOTIFICATION UI HINT TEXT ONLY (the buttons
    "Dismiss" etc.), not the f-strung body.
  - Notification body includes:
    - Verbatim Pronote error message (`redact(err.message)` from
      Phase 2 — strips URL, token, password, uuid)
    - Next-retry timestamp formatted in school_tz: "Prochaine tentative
      à HH:MM le DD/MM (heure NC)"
    - Strike count (so the user understands escalation): "Tentative N°X"
    - Link to the Phase 7 troubleshooting README (placeholder URL —
      Phase 7 fills it: `https://github.com/<owner>/ha-pronote#
      troubleshooting-ip-suspended`)

### Code organization & forward-compat (Area 4)

- **D-16:** New module `custom_components/ha_pronote/politesse.py` —
  HA-free, pure. Imports limited to stdlib (`datetime`, `random`,
  `zoneinfo`) + `holidays` (the only new runtime dep). Public surface
  exactly as listed in the "Phase 5 ships" §1 above. The module owns
  *no state* — every function takes `now`, `options`, etc. as arguments.
  All tests live in `tests/test_politesse.py` and run in pure pytest
  (no `hass` fixture needed). AST guard: `tests/test_no_ha_imports.py`
  must be extended with `politesse.py` in the protected list to enforce
  zero `homeassistant.*` imports.
- **D-17:** Threshold reads from `entry.options.get(KEY,
  DEFAULT_FROM_CONST)`. Phase 5 reads the following keys on every
  `_async_update_data` tick:
  - `refresh_interval` — minutes int (default `DEFAULT_REFRESH_INTERVAL.
    total_seconds() / 60 = 30`)
  - `afternoon_interval` — minutes int (default 15)
  - `afternoon_window_start` — `time.isoformat()` string (default
    `"17:00:00"`)
  - `afternoon_window_end` — `time.isoformat()` string (default
    `"20:00:00"`)
  - `quiet_hours_start` — `time.isoformat()` string (default `"22:00:00"`)
  - `quiet_hours_end` — `time.isoformat()` string (default `"06:00:00"`)
  - `suspended_cadence` — minutes int (default 360 = 6h)
  - `quiet_cadence` — minutes int (default 240 = 4h)

  The serialized formats (int minutes, ISO time strings) are chosen for
  HA's `voluptuous` schema compatibility — Phase 6's OptionsFlow will
  declare schemas that accept these types directly. Phase 5 wraps the
  reads in a thin `_resolve_options(entry) -> PolitesseOptions`
  dataclass adapter (one place to parse + validate types) called from
  `_async_update_data`. The adapter applies defaults when keys are
  missing AND on parse error (e.g. malformed ISO string) — log warning,
  fall back, do NOT crash.
- **D-18:** `const.py` additions (verbatim names):
  ```python
  BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
      timedelta(hours=1), timedelta(hours=2), timedelta(hours=4),
      timedelta(hours=12), timedelta(hours=24),
  )
  JITTER_SECONDS: Final = 30
  DEFAULT_AFTERNOON_INTERVAL: Final = timedelta(minutes=15)
  DEFAULT_AFTERNOON_WINDOW: Final = (time(17, 0), time(20, 0))
  DEFAULT_QUIET_HOURS: Final = (time(22, 0), time(6, 0))
  DEFAULT_SUSPENDED_CADENCE: Final = timedelta(hours=6)
  DEFAULT_QUIET_CADENCE: Final = timedelta(hours=4)
  NC_VACATION_RANGES_2026: Final[tuple[tuple[date, date], ...]] = (
      (date(2026, 4, 4), date(2026, 4, 19)),
      (date(2026, 6, 6), date(2026, 6, 21)),
      (date(2026, 8, 8), date(2026, 8, 23)),
      (date(2026, 10, 10), date(2026, 10, 25)),
      (date(2026, 12, 19), date(2027, 2, 14)),
  )
  NC_LOCAL_HOLIDAYS_SUPPLEMENT: Final[frozenset[date]] = frozenset()
  IP_SUSPENDED_NOTIFICATION_ID_SUFFIX: Final = "ip_suspended"
  AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX: Final = "auth_circuit"
  ```
- **D-19:** Jitter generation: `compute_interval(now, options, *,
  rng=random)`. Production caller in coordinator passes no `rng` (uses
  stdlib `random` global module — non-cryptographic, fine for politesse
  randomization). Tests pass `rng=random.Random(seed=42)` (or any
  deterministic seed) for reproducible matrices. The injectable-rng
  pattern matches HA Core integration test fixtures.
- **D-20:** Test layout:
  - `tests/test_politesse.py` — NEW. Pure unit tests for every politesse
    function. Parameterized on `tz=[Europe/Paris, Pacific/Noumea]`
    (DIST-06) so the same logical scenario is verified under both
    timezones. Time-mocked by passing synthetic tz-aware `now` arguments
    — no `freezegun`/`pytest-freezer` needed for the politesse module
    itself. Branches to cover (each a parametrized test): weekday
    afternoon 17h-20h with tomorrow=school-day, weekday morning, Sunday
    evening 19h with Mon=school-day (primer), Sunday morning (suspended),
    last-day-of-vacation 19h (primer), férié day, vacation day, quiet
    hours 23h, quiet hours 5h, weekend Saturday morning. Each parametrized
    on both Paris and Nouméa.
  - `tests/test_coordinator.py` — EXTEND with: suspension short-circuit
    (should_poll=False, snapshot stays cached, no executor call, no events
    fired), backoff short-circuit (backoff_until > now, same behavior),
    3-strike auth → ConfigEntryAuthFailed + notification + backoff_until
    set, IP_SUSPENDED → UpdateFailed + notification + backoff_until set,
    successful poll → counters reset + both notifications dismissed,
    quiet-hours event suppression (diff still runs, events dropped with
    debug log).
  - `tests/test_no_ha_imports.py` — EXTEND protected list with
    `politesse.py`.

### Phase 5 → Phase 6 interface

- `entry.options` shape locked above (D-17) — Phase 6's OptionsFlow adds
  the UI for these keys and `entry.add_update_listener` for
  reload-on-options-change.
- `runtime_data.holiday_dates: frozenset[date]` — Phase 6 may add a
  per-entry override or year-rollover refresh.
- `_consecutive_failures` / `_backoff_until` fields on the coordinator —
  Phase 7's DIAG-01 reads them for diagnostics output.

### Phase 5 → Phase 7 interface

- Persistent notification body includes a placeholder troubleshooting URL
  (Phase 7 DIST-07 fills the real URL when README ships).
- The persistent notification UI is the Phase 5 deliverable for COORD-08;
  Phase 7 DIAG-02 may upgrade to a Repair Issue (which is non-dismissible
  and visible in the Repairs UI). Phase 7 layers on top; Phase 5
  notification keys stay.
- `holidays` dep version pin may need a daily-cron CI bump (Phase 7
  DIST-04) — `pronotepy` cron extends to `pronotepy + holidays` to catch
  upstream breakage on either.

### Claude's Discretion

The planner has flexibility on these; recommended defaults noted, deviate
only with a stronger argument:

- **C-01:** Plan-wave decomposition — RECOMMEND 3 plans across 2 waves:
  - **Wave 1 (parallel):**
    - Plan 05-01 — `politesse.py` + `tests/test_politesse.py` +
      `tests/test_no_ha_imports.py` extension. HA-free, no coordinator
      coupling — fastest to land + unblocks Wave 2.
    - Plan 05-02 — `manifest.json` `holidays` dep pin + `const.py`
      additions + initial probe of `holidays.France(subdiv='NC')` to
      determine if `NC_LOCAL_HOLIDAYS_SUPPLEMENT` needs populating.
  - **Wave 2 (blocked on Wave 1):**
    - Plan 05-03 — coordinator extension (`_handle_failure`,
      `_reset_breaker_on_success`, suspension + backoff short-circuits,
      `_fire_diff_events` quiet-hours gate, persistent notification
      create/dismiss) + `strings.json` notification keys + extended
      `tests/test_coordinator.py`.
  Planner may collapse 05-01 + 05-02 if it judges the dep+const work
  trivial. Wave 1 cannot collapse with Wave 2 because Wave 2 imports
  from politesse.py + const.py.
- **C-02:** Exact `holidays` version pin — RECOMMEND latest stable at
  planning time, exact pin via `==`, matching the project's
  `pronotepy==2.14.6` exact-pin discipline (Phase 1 D-14). Planner
  queries `pypi.org/pypi/holidays/json` at probe time and pins to the
  current release. Bump policy: only when a real bug or NC calendar
  change forces it.
- **C-03:** Probe step to verify `holidays.France(subdiv='NC')` output —
  RECOMMEND a one-off script `scripts/probe_nc_holidays.py` (committed)
  that prints the 2026 set of dates and any NC-specific names. Output
  captured into `tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md`
  (sibling to Phase 4's). If `holidays` doesn't include Fête de la
  citoyenneté 24/9, populate `NC_LOCAL_HOLIDAYS_SUPPLEMENT =
  frozenset({date(2026, 9, 24)})` and document.
- **C-04:** Test fixture for the coordinator backoff tests — RECOMMEND
  `freezegun` via `pytest-freezer` (already in STACK.md as a transitive
  dep). Use `freezer.move_to(...)` to advance time across the backoff
  window. Politesse pure tests don't need freezegun (they take `now` as
  arg); coordinator tests do (they assert on `dt_util.now()` being past
  `_backoff_until`).
- **C-05:** Persistent notification message localization — RECOMMEND
  Python constants in `coordinator.py` for French (primary) + English
  (fallback). Pick the language by reading `hass.config.language` at
  notification creation time (a simple if/else, two strings each).
  Phase 7 may move to a fuller i18n approach; v1 keeps it minimal.
- **C-06:** Mock strategy for the new coordinator tests — RECOMMEND
  reuse Phase 3's `mock_pronote_client` fixture pattern. Inject a
  `MagicMock` that raises `AuthError` / `RateLimitedError(IP_SUSPENDED)`
  on demand to drive the strike counter. For `persistent_notification`
  assertions, patch `homeassistant.components.persistent_notification.
  async_create` and `async_dismiss` and assert on call args.
- **C-07:** Where the coordinator stores the precomputed `holiday_dates`
  set — RECOMMEND extend `data.py:PronoteData` with `holiday_dates:
  frozenset[date]` (Phase 3 D-21 explicitly invited this growth: "Phase
  5 may grow the dataclass for circuit-breaker state"). Computed once at
  `async_setup_entry` (executor-wrapped because `holidays` may do
  module-level eager loading). The coordinator then reads
  `entry.runtime_data.holiday_dates` on each politesse call. Alternative
  — store on the coordinator instance directly — also fine, but
  `PronoteData` keeps the lifecycle (cleared on unload) honest.
- **C-08:** Where the coordinator instantiates the random number
  generator for jitter — RECOMMEND use the stdlib `random` global (no
  per-coordinator `random.Random` instance). Politesse's `compute_interval`
  accepts `rng=random` by default; the coordinator never passes `rng=`.
  Tests inject their own seeded `random.Random` when calling politesse
  directly. The coordinator-side tests that need deterministic jitter
  can patch `random.uniform` for the duration of the test.
- **C-09:** Whether to add a top-level `hass.bus.async_fire("pronote_
  politesse_state_changed", ...)` event when entering/exiting backoff
  — RECOMMEND no for v1. The persistent notification carries the user-
  facing signal; an automation-targeted event is overkill for v1 and
  could surprise users with extra noise. Phase 7's DIAG-01 may expose
  the state via diagnostics if requested.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Core Value (alerte EDT J/J+1 fiable), polling
  politesse rationale, "From scratch / not fork" stance, "Lecture seule",
  "Sécurité credentials" (no leak in logs — applies to the
  persistent-notification body). The "Polling adaptatif fin de journée"
  Key Decisions entry is the direct ROADMAP anchor for COORD-04.
- `.planning/REQUIREMENTS.md` — Phase 5 owns 7 requirements: COORD-04,
  COORD-05, COORD-06, COORD-07, COORD-08, COORD-09, DIST-06. Cross-cutting
  trackers: COORD-01..03 (Phase 3 / Phase 6 ownership; Phase 5 mutates
  `update_interval` per Phase 3 D-24 invitation, reads `entry.options`
  per Phase 6 forward-compat contract). EVENT-04 invariant (no events on
  first poll) preserved by Phase 4 diff functions and unchanged here.
- `.planning/ROADMAP.md` §"Phase 5: Politesse — Adaptive Polling, Quiet
  Hours, Circuit Breaker" — Goal statement, 4 success criteria:
  - SC#1: cadence visibly adapts (weekday 17h–20h NC → ~15min, week-ends
    + NC vacations suspend, quiet hours 22h–6h NC suppress events) —
    observable in HA logs over 24h
  - SC#2: 3 consecutive auth fails or single IP-suspended response →
    exp backoff up to 24h cap + persistent HA notification
  - SC#3: pytest matrix Paris + Nouméa both pass; time-mocked tests prove
    `compute_interval(now, options)` returns right timedelta for every
    branch (weekday/weekend/vacation/quiet/afternoon)
  - SC#4: polling intervals carry ±30s jitter
- `CLAUDE.md` — Tech stack (Python 3.14.2, HA 2026.4+, pronotepy 2.14.6
  EXACT pin, `holidays` is the only NEW runtime dep this phase
  introduces), "What NOT to Use" table (banned APIs still apply:
  no `async_timeout` — use `asyncio.timeout` if needed; no `pytz` —
  `zoneinfo.ZoneInfo` everywhere; no direct `requests`; no
  `pronotepy.ent.*`; no monkey-patching; no hardcoded URL). The "from
  scratch" stance + politesse polling discipline are direct PROJECT.md
  anchors that this phase implements structurally.
- `.planning/phases/03-coordinator-first-sensor/03-HUMAN-UAT.md` —
  Phase 3 live-UAT findings about pronotepy 2.14.6 surfaces (CryptoError
  alias for soft-rate-limit; `set_child` accepting Child or str). Phase 5
  reads to understand the WR-04 cooldown gate already in place and
  ensure the breaker counter does NOT tick on the aliased CryptoError
  recovery path.
- `/home/moi/.claude/projects/-data-projets-perso-pronote/memory/feedback_no_silent_exceptions.md` —
  Project-level feedback: NO typed catches that swallow + remap. Applies
  to `_handle_failure` (the typed exception still propagates raw via
  raise; the notification is *additive*), to politesse predicates
  (return False is explicit, never an `except`), and to the
  `_resolve_options` adapter (log warning + fall back to default on
  parse error, but never silently masquerade as success).

### Prior phase context
- `.planning/phases/01-foundations-skeleton/01-CONTEXT.md` — Phase 1
  decisions still binding in Phase 5:
  - **D-12, D-13:** `iot_class: "cloud_polling"` + `quality_scale:
    "bronze"` — Phase 5 polling discipline is exactly what Bronze
    handled-failure expects.
  - **D-14:** Exact-pin discipline on runtime deps — `holidays==<pin>`
    follows the same `==` policy.
  - **D-30..D-35:** Anti-pattern hard locks (no async_timeout, no pytz,
    no direct requests, no pronotepy.ent, no hardcoded URL, no
    monkey-patching) — every one applies.
  - **D-29:** PHACC already wired with `asyncio_mode = "auto"` — Phase 5
    HA-side tests just use the `hass` fixture.
- `.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md` — Phase 2
  decisions still binding in Phase 5:
  - **D-19, D-20:** Zero `homeassistant.*` imports in `api/` or `diff/`
    — `tests/test_no_ha_imports.py` enforces. Phase 5 extends this
    invariant to `politesse.py`.
  - **D-22:** Typed error hierarchy in `api/errors.py` (AuthError /
    RateLimitedError / CommunicationError / ParseError, ErrorReason
    StrEnum). Phase 5's `_handle_failure` matches on `isinstance(err,
    RateLimitedError) and err.reason == ErrorReason.IP_SUSPENDED`.
  - **D-23, D-24:** All datetimes tz-aware via `zoneinfo.ZoneInfo`. Phase
    5's politesse functions take tz-aware `now`; tests pass tz-aware
    datetimes; coordinator localizes via `dt_util.now(self._school_tz)`.
  - **D-25:** Pytest matrix `Europe/Paris` + `Pacific/Noumea` — Phase 5
    extends to all politesse tests via `pytest.mark.parametrize("tz",
    ["Europe/Paris", "Pacific/Noumea"])`.
- `.planning/phases/03-coordinator-first-sensor/03-CONTEXT.md` — Phase 3
  decisions still binding in Phase 5:
  - **D-19:** `TimestampDataUpdateCoordinator` subclass — Phase 5's
    `_async_update_data` extension preserves the subclass + the
    `last_update_success_time` field.
  - **D-20:** `coordinator.data: Snapshot` directly — Phase 5's
    suspension short-circuit returns `self.data` (the existing
    snapshot), keeping the type invariant.
  - **D-21:** `runtime_data: PronoteData` — Phase 5 EXTENDS PronoteData
    with `holiday_dates: frozenset[date]` (per C-07), keeping mutability
    (`PronoteData` already non-frozen for `client` reassign).
  - **D-22:** Error mapping contract — Phase 5 EXTENDS handling but
    preserves the public contract: `AuthError → ConfigEntryAuthFailed`
    (now also triggers breaker tick + notification);
    `RateLimitedError(IP_SUSPENDED) → UpdateFailed` (now also triggers
    breaker tick + notification); others → `UpdateFailed` unchanged.
  - **D-23:** `school_tz` resolution — Phase 5 reads
    `self._school_tz` for every politesse call (the canonical school
    timezone, Phase 6 OPT-04 wires per-entry override).
  - **D-24:** Hardcoded `DEFAULT_REFRESH_INTERVAL = timedelta(
    minutes=30)` — Phase 5 keeps it as the default but reads from
    `entry.options.get('refresh_interval', ...)` for the live value.
  - **D-09 / WR-04 / WR-09:** Silent-recovery cooldown semantics —
    Phase 5's breaker counter MUST tick only on AuthErrors that survive
    `_recover_from_auth_error`, not on the aliased CryptoError that
    WR-04's 5-min gate already absorbs.
  - **Phase 3 → Phase 5 interface (D-21 dataclass growth, D-24 interval
    mutation, D-22 RateLimitedError.reason read):** every interface
    point named in Phase 3's CONTEXT.md is exercised by Phase 5.
- `.planning/phases/04-diff-events-full-sensor-suite/04-CONTEXT.md` —
  Phase 4 decisions still binding in Phase 5:
  - **D-11, D-12, D-13, D-15:** `_fire_diff_events` design, payload
    wrapping, EVENT-04 first-poll invariant. Phase 5 EXTENDS
    `_fire_diff_events` only by gating each `hass.bus.async_fire` call
    on `should_fire_event(now, options)`; everything else stays.
  - **Phase 4 → Phase 5 interface note** ("`_fire_diff_events` is the
    natural seam for Phase 5's quiet-hours suppression; Phase 5 adds a
    `compute_should_fire(now)` predicate that gates the call") — Phase 5
    realizes this verbatim.
  - **D-17:** Heavy-class CI gate (16 KiB / 255-char) — Phase 5 does NOT
    modify sensor state/attrs, so the gate stays green untouched.

### Research already done
- `.planning/research/SUMMARY.md` §"Phase 5" (line 137 onwards) — direct
  blueprint: pure `compute_interval(now, options)`, coordinator mutates
  `self.update_interval` at end of `_async_update_data`, circuit breaker
  in `api/client.py` (note: Phase 5 puts it on the coordinator instead
  — see D-12 rationale, in-memory + reset on success), jitter +/-30s,
  NC vacation calendar hardcoded v1 + ICS-based v1.x, pytest matrix on
  Paris + Nouméa. The "circuit breaker in api/client.py" research
  recommendation is intentionally overridden by D-12 because the auth-
  failure counter needs to interact with `_recover_from_auth_error`
  which lives on the coordinator. The IP_SUSPENDED detection itself
  stays at `api/errors.py:RateLimitedError(IP_SUSPENDED)` per Phase 2
  D-22; the COORDINATOR enforces the backoff.
- `.planning/research/ARCHITECTURE.md` §"Pattern 4: Adaptive
  update_interval mutated in-place" (lines 279–313) — implementation
  blueprint for `compute_interval` + the `_async_update_data`
  end-of-cycle mutation. Phase 5 uses Option A verbatim.
- `.planning/research/ARCHITECTURE.md` §"Pattern 5: Politesse polling —
  circuit breaker on the API client" (lines 315–330) — the consecutive-
  failure counter idea. Phase 5 implements on the coordinator (D-12)
  rather than the API client, with a fixed schedule (D-11) rather than
  multiplicative.
- `.planning/research/PITFALLS.md` §"Pitfall 1: IP suspension by school
  server" (lines 12–60) — direct rationale for D-11's `(1h, 2h, 4h,
  12h, 24h)` schedule, D-15's notification body wording, and D-13's
  IP_SUSPENDED detection at strike 1.
- `.planning/research/PITFALLS.md` §"Pitfall 4: NC timezone + austral
  calendar" (lines 100–125) — direct rationale for D-01 (hardcode
  vacation dates), D-02 (NC fériés subdivision), D-07 (afternoon
  window expressed as `time(17,0)`–`time(20,0)` in school_tz), and the
  DIST-06 test matrix.
- `.planning/research/PITFALLS.md` §"Pitfall 9" (around line 258–270) —
  direct rationale for D-08 (quiet hours 22h–6h NC default), D-09
  (events suppressed during quiet hours), and the "no polling weekend
  Sat 18h → Mon 6h" + Sunday-evening primer (D-06).
- `.planning/research/STACK.md` line 51 — `freezegun==1.5.5` /
  `pytest-freezer 0.4.9` already available (PHACC transitive dep) for
  coordinator-side time mocking (C-04).
- `.planning/research/STACK.md` line 29 — `ConfigFlow` + `OptionsFlow`
  recommendation that "polling interval and 17h–20h window must live in
  OptionsFlow, not data". Phase 5 honours by reading from
  `entry.options` (D-17); Phase 6 wires the UI.
- `.planning/research/FEATURES.md` — Phase 5 doesn't introduce new
  features beyond what REQUIREMENTS describes; the research informs
  Phase 6's OptionsFlow surface, not Phase 5's runtime.

### External references (URL — no local copy)
- **`holidays` PyPI** — `https://pypi.org/project/holidays/` — Python
  holidays library. Phase 5 dep. Verify `holidays.France(subdiv='NC')`
  output before commit (C-03 probe).
- **`holidays` GitHub** — `https://github.com/vacanza/holidays` — Source
  of NC subdivision support. Check `holidays/locale/fr/FR.py` for the
  NC list (Fête de la citoyenneté 24/9 etc.).
- **`data.gouv.nc` school calendar dataset** —
  `https://data.gouv.nc/explore/dataset/calendrier_scolaire_nc/` — the
  authoritative NC source. ICS export at
  `https://data.gouv.nc/api/explore/v2.1/catalog/datasets/calendrier_scolaire_nc/exports/ics`
  and JSON at
  `https://data.gouv.nc/api/explore/v2.1/catalog/datasets/calendrier_scolaire_nc/exports/json`.
  Deferred to v1.x; Phase 5 ships hardcoded dates from this list.
- **OpenScol CDN** —
  `https://fr.ftp.opendatasoft.com/openscol/fr-en-calendrier-scolaire/NouvelleCaledonie.ics`
  — National-level ICS feed. Caveat surfaced in research: 2026 NC + WF
  data may lag publication. Backup migration path for v1.x.
- **HA Developer Docs §"DataUpdateCoordinator"** —
  `https://developers.home-assistant.io/docs/integration_fetching_data`
  — `update_interval` semantics, `last_update_success_time` field
  (Phase 3 D-19 already uses), early-return behavior in
  `_async_update_data`.
- **HA Developer Docs §"persistent_notification"** —
  `https://developers.home-assistant.io/docs/core/integration_quality_scale_index`
  for Bronze handled-failure expectations + the public
  `homeassistant.components.persistent_notification.async_create /
  async_dismiss / async_create_async` API surface.
- **`bain3/pronotepy/exceptions.py`** —
  `https://github.com/bain3/pronotepy/blob/main/pronotepy/exceptions.py`
  — Source of the `PronoteAPIError("Your IP address is suspended.")`
  literal string. Phase 2 D-22's `RateLimitedError(IP_SUSPENDED)`
  mapping detects this exact message.
- **`delphiki/HomeAssistant-Pronote/coordinator.py`** — reference
  implementation idea for adaptive polling. delphiki ships a single
  static interval; Phase 5's politesse is the differentiator (research
  SUMMARY line 51).

### Phase 1 / 2 / 3 / 4 shipped code (relevant Phase 5 reads)
- `custom_components/ha_pronote/coordinator.py` — Phase 3 + Phase 4
  shipped surface. Phase 5 EXTENDS `_async_update_data` (suspension +
  backoff short-circuits at the top, jittered `compute_interval` at the
  end) and `_fire_diff_events` (per-event `should_fire_event` gate).
  Phase 5 ADDS `_handle_failure`, `_reset_breaker_on_success`,
  `_consecutive_failures`, `_backoff_until`. Phase 5 PRESERVES
  `_recover_from_auth_error`, `_capture_session`, the WR-04 cooldown,
  the existing typed-exception mappings (D-22 of Phase 3).
- `custom_components/ha_pronote/data.py` — Phase 3 shipped surface.
  Phase 5 EXTENDS `PronoteData` with `holiday_dates: frozenset[date]`
  (per C-07).
- `custom_components/ha_pronote/__init__.py` — Phase 3 shipped surface.
  Phase 5 EXTENDS `async_setup_entry` with a one-shot executor call to
  `_compute_holiday_dates_for_year(now.year, school_tz)` and stores on
  `runtime_data.holiday_dates`. Year rollover (Dec 31 → Jan 1 of next
  year) handled by checking on each `_async_update_data` whether the
  cached year matches `now.year` — if not, recompute (cheap, ~ms).
- `custom_components/ha_pronote/api/errors.py` — Phase 2 shipped
  surface. Phase 5 IMPORTS `RateLimitedError`, `ErrorReason` for the
  IP_SUSPENDED branch in `_handle_failure`. NO Phase 5 change to `api/`.
- `custom_components/ha_pronote/diff/*.py` — Phase 2 + Phase 4 shipped
  surface. Phase 5 does NOT touch — `_fire_diff_events`'s diff
  invocations are unchanged; only the `bus.async_fire` calls are gated.
- `custom_components/ha_pronote/sensor.py`, `entity.py`, `calendar.py`
  — Phase 3 + Phase 4 shipped surface. Phase 5 does NOT touch (sensors
  read `coordinator.data` directly; the cached snapshot during
  suspension still makes them show the last-known values).
- `custom_components/ha_pronote/const.py` — Phase 1 + Phase 2 + Phase 3
  + Phase 4 shipped surface. Phase 5 APPENDS per D-18 (no rename, no
  removal). Existing constants stay untouched.
- `custom_components/ha_pronote/strings.json` + `translations/{fr,en}.json`
  — Phase 1 + Phase 3 + Phase 4 shipped surface. Phase 5 APPENDS
  notification message keys (`notification.ip_suspended.title`,
  `notification.ip_suspended.message`, `notification.auth_circuit.title`,
  `notification.auth_circuit.message`) — Phase 7 finalizes the i18n
  polish.
- `custom_components/ha_pronote/manifest.json` — Phase 1 shipped surface
  (`pronotepy==2.14.6`, `python-slugify==8.0.4`). Phase 5 APPENDS
  `holidays==<pin>` to `requirements`. NO change to
  `iot_class`/`quality_scale`/`config_flow`/`integration_type`.
- `tests/conftest.py` — Phase 1 + Phase 3 + Phase 4 fixtures. Phase 5
  may ADD a `mock_persistent_notification` fixture (helper around
  patching `persistent_notification.async_create` / `async_dismiss`)
  for the coordinator tests.
- `tests/test_no_ha_imports.py` — Phase 2 shipped AST guard. Phase 5
  APPENDS `politesse.py` to the protected list.
- `tests/test_coordinator.py` — Phase 3 + Phase 4 shipped tests. Phase 5
  EXTENDS with the breaker / suspension / event-gate scenarios.

### SPEC.md
None — `/gsd-spec-phase` was not run for Phase 5. Requirements live in
REQUIREMENTS.md (7 reqs: COORD-04..09 + DIST-06) + ROADMAP.md §"Phase 5"
success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **From Phase 2 (api/ shipped surface):**
  - `api/errors.py:RateLimitedError(reason: ErrorReason)` already raises
    with `reason=IP_SUSPENDED` on detecting the literal `Your IP address
    is suspended` Pronote message. Phase 5's `_handle_failure` matches
    on `err.reason == ErrorReason.IP_SUSPENDED` — no extra string parsing.
  - `api/redact.py` (or wherever `redact` lives — verified in Phase 3
    D-22 mapping at `coordinator.py:130, 144, 220`) strips URL / token
    / password / uuid from error messages. Phase 5's notification body
    re-uses `redact(err.message)` to ensure the persistent_notification
    NEVER leaks credentials.
- **From Phase 3 (HA-side runtime):**
  - `PronoteDataUpdateCoordinator(TimestampDataUpdateCoordinator[Snapshot])`
    — Phase 5 EXTENDS the same class with breaker fields + helpers, no
    subclassing.
  - `self._school_tz: ZoneInfo` field — Phase 5 reads on every politesse
    call.
  - `self._previous_snapshot: Snapshot | None` — Phase 5's suspension
    short-circuit MUST NOT update this field (so the next real poll
    diffs against the last real snapshot).
  - `self._client` / `self._child_index` / `_recover_from_auth_error` /
    `_capture_session` / WR-04 cooldown gate — all preserved verbatim.
  - `runtime_data: PronoteData` (D-21) — Phase 5 EXTENDS with
    `holiday_dates: frozenset[date]` per C-07.
- **From Phase 4 (diff + events):**
  - `_fire_diff_events(previous, new)` — Phase 5 gates each
    `hass.bus.async_fire` call on `should_fire_event(now, options)`.
    The diff loops themselves run unchanged (so `_previous_snapshot`
    mutation continues to be correct).
  - Event constants `EVENT_SCHEDULE_CHANGED`, `EVENT_NEW_GRADE`,
    `EVENT_NEW_INFORMATION` — Phase 5 doesn't add any new event type.

### Established Patterns
- Frozen `@dataclass(frozen=True)` for value types (Phase 2). Phase 5's
  politesse module probably ships zero new dataclasses — it's all
  function-level pure logic. If a `PolitesseOptions` adapter dataclass
  is added (D-17 mention), it should be frozen.
- tz-aware datetime everywhere via `zoneinfo.ZoneInfo` (Phase 2 D-23).
  Phase 5 takes tz-aware `now` arguments; politesse functions explicitly
  ASSERT tz-awareness early (raise `ValueError` on naive input — fail
  fast, no silent conversion).
- "No silent exceptions" — Phase 5's `_handle_failure` re-raises the
  typed exception (the breaker tick + notification are additive); the
  `_resolve_options` adapter logs warning on parse error but does NOT
  swallow the malformed key (the default is the fallback, the warning
  is the trace).
- Exact-pin discipline on runtime deps (Phase 1 D-14) — `holidays==<pin>`.
- AST guard on HA-free modules (Phase 2 D-20) — `politesse.py` joins
  `api/` and `diff/` as a protected module.
- PHACC `hass` fixture + `MockConfigEntry` for HA-side tests; pure
  pytest for politesse module.
- TZ matrix on datetime-sensitive tests (Phase 2 D-25).

### Integration Points
- **Phase 5 → Phase 6 interface:**
  - `entry.options` keys locked by D-17 — Phase 6's OptionsFlow declares
    voluptuous schemas matching these names + types, and wires
    `entry.add_update_listener(_async_reload_on_options_change)` so a
    change reloads the coordinator without re-running the auth flow.
  - `runtime_data.holiday_dates: frozenset[date]` — Phase 6 may
    re-compute on year rollover or per-entry tz change.
- **Phase 5 → Phase 7 interface:**
  - `_consecutive_failures` / `_backoff_until` on the coordinator —
    Phase 7's `async_get_config_entry_diagnostics` (DIAG-01) reads
    these fields and surfaces them (redacted, no URL leak) in the
    diagnostics download.
  - `notification_id` suffixes (`ip_suspended`, `auth_circuit`) —
    Phase 7's DIAG-02 may upgrade to Repair Issues using the same
    `notification_id` as a Repair Issue `issue_id`, allowing a clean
    handoff (dismiss the persistent notification + open a Repair Issue
    of the same identity).
  - `holidays` runtime dep — Phase 7's daily-cron CI (DIST-04) extends
    to validate against latest `holidays` master too.
- **Phase 5 invariants for sensors/calendar (NO change but called out):**
  - Sensor `extra_state_attributes` payloads continue under the 16 KiB
    Phase 4 D-17 cap — Phase 5 doesn't write to the snapshot during
    suspension, so the heavy-class CI gate stays green.
  - Calendar `async_get_events` works off the cached snapshot during
    suspension — user opening the calendar UI on a Saturday still sees
    the J−7 → J+14 events from Friday's last successful poll.

</code_context>

<specifics>
## Specific Ideas

- **NC academic-year 2026 dates verified during web search** (2026-05-25):
  - Rentrée teachers: Friday 13/02/2026; rentrée élèves: Monday
    16/02/2026
  - 1st vacation: Sat 04/04 → Sun 19/04
  - 2nd vacation: Sat 06/06 → Sun 21/06
  - 3rd vacation: Sat 08/08 → Sun 23/08
  - 4th vacation: Sat 10/10 → Sun 25/10
  - Summer vacation (austral): Sat 19/12/2026 → mid-Feb 2027 (rentrée
    2027 date provisional — verify against `data.gouv.nc` at probe time)
  - Hardcoded in D-01's `NC_VACATION_RANGES_2026`.
- **PITFALLS.md §2.1 exact backoff schedule** verbatim — `1h → 2h →
  4h → 12h → 24h cap`. D-11 lifts this directly.
- **`Your IP address is suspended` literal** — already detected in
  `api/errors.py` per Phase 2 D-22. Phase 5 trusts the existing detection.
- **Persistent notification body — French primary** (matches PROJECT.md
  context of a NC user base):
  - Title: "[HA-Pronote] IP suspendue par Pronote"
  - Body: "L'IP de votre instance Home Assistant a été suspendue par le
    serveur Pronote ({redacted_url}). Cela arrive lorsque trop de
    requêtes partent en peu de temps. Tentative N°{strike_count}.
    Prochaine tentative à {hh:mm} le {dd/mm} (heure NC).
    {dynamic_advice_based_on_strike}. Détail technique :
    {redact(err.message)}."
  - English fallback: same shape, translated keys.
- **Pitfall 4 vs Pitfall 9 split** — Pitfall 4 (NC TZ + austral calendar)
  drives D-01..D-03 + D-07 + DIST-06 matrix. Pitfall 9 (night/weekend
  noise) drives D-05 (weekend suspended), D-06 (Sunday primer), D-08
  (quiet hours), D-09 (event suppression).
- **`_fire_diff_events` ordering** — Phase 5 calls
  `should_fire_event(now, options)` ONCE at the top of `_fire_diff_events`
  (not per-event) and caches the result locally. Saves the per-event
  predicate call (negligible perf) and locks the gate's atomicity (every
  event in a poll fires or none — no half-suppressed batch).
- **Year-rollover for `holiday_dates`** — coordinator stores
  `(year, frozenset[date])` tuple in `runtime_data.holiday_dates` so
  each `_async_update_data` checks `runtime_data.holiday_dates[0] ==
  now.year`. On year rollover (Dec 31 → Jan 1), one executor call
  refreshes via `holidays.France(subdiv='NC', years=now.year)`. Cheap
  (~ms) but ALWAYS executor-wrapped because `holidays` module-level
  initialization is not certified async-safe.
- **Test matrix scenarios** to cover (each parametrized on Paris+Nouméa):
  - Mon-Thu 10h → base 30min branch
  - Mon-Thu 18h with Tue=school-day → afternoon-tightening 15min branch
  - Fri 18h with Sat=weekend → base 30min branch (NOT afternoon, because
    tomorrow=non-school-day)
  - Sat 10h → suspended (should_poll=False, 6h cadence)
  - Sun 19h with Mon=school-day → primer (afternoon-tightening 15min)
  - Sun 10h → suspended (Sat-Sun)
  - Last-day-of-vacation 19h with next-day=school-day → primer
  - Mid-vacation 14h → suspended
  - Férié 14h (Wed) → suspended
  - Tue 23h → quiet hours (4h cadence + event suppression)
  - Tue 5h → quiet hours (4h cadence + event suppression)
  - Quiet hours overlapping with weekend (Sat 23h) → weekend wins
    (should_poll=False)
- **Jitter test reproducibility** — seed=42 fixture; assert
  `abs(actual_interval - expected_base) < JITTER_SECONDS_AS_TIMEDELTA`
  rather than exact equality, so a future seed change doesn't break
  tests for arithmetic that happens to land at boundary.

</specifics>

<deferred>
## Deferred Ideas

These came up during discussion or research but belong in later phases /
post-v1:

- **Live `data.gouv.nc` JSON/ICS fetch** for NC vacation calendar —
  deferred to v1.x. Phase 5 v1 ships hardcoded 2026 dates +
  `data.gouv.nc` URL in canonical refs for the future migration PR.
  Decision rationale: the user accepted that yearly hand-update is
  cheaper than HTTP-cache-fallback complexity in v1.
- **OpenScol CDN ICS** — same deferral, same reason.
- **OptionsFlow UI** for refresh_interval, afternoon_interval,
  afternoon_window, quiet_hours, suspended_cadence, quiet_cadence,
  adaptive_polling toggle — Phase 6 (OPT-01..04). Phase 5 ships the
  *read path* so Phase 6 is pure UI work.
- **Per-entry `school_tz` override** in OptionsFlow — Phase 6 (OPT-04).
- **Diagnostics surface** for `_consecutive_failures` / `_backoff_until`
  — Phase 7 (DIAG-01). Phase 5 ensures the fields exist + are public-ish
  (single leading underscore = test-readable).
- **Repair Issue** on IP-banned state — Phase 7 (DIAG-02). Phase 5 ships
  the persistent notification.
- **`hass.bus.async_fire("pronote_politesse_state_changed", ...)`** —
  rejected for v1 (C-09). Reconsider if users request automation hooks
  for politesse state.
- **Event queueing during quiet hours** — rejected (D-09). Drop with
  debug log.
- **End-of-suspension warm-up poll** other than the Sunday/last-vacation-
  day primer (D-06) — no special-casing of Saturday-evening or mid-week
  férié evening primers for v1.
- **Per-data-type cadence decoupling** (notes 6h, EDT 30m, etc.) —
  rejected for v1 per REQUIREMENTS Out-of-Scope. One coordinator per
  child = one cadence.
- **Heartbeat poll during long suspension** (e.g. one poll per day
  during a 2-week vacation to keep credentials warm) — rejected for v1.
  HA's `async_config_entry_first_refresh()` on next restart catches a
  stale credential; the rentrée morning poll catches any token expiry
  in normal lifecycle.
- **Daily CI cron against `holidays@main`** — Phase 7 (DIST-04 extension).
- **README documentation** of polling behavior, circuit-breaker, NC
  calendar — Phase 7 (DIST-07). Phase 5 freezes the behavior;
  Phase 7 documents.
- **HACS Quality Scale upgrade** (bronze → silver) — Phase 7 / v2.
- **Adaptive learning of optimal polling** (e.g. record when EDT changes
  actually arrive, tighten only around historical peaks) — out of scope
  for v1. Documented in research as a v2 idea.

</deferred>

---

*Phase: 5-politesse-adaptive-polling-quiet-hours-circuit-breaker*
*Context gathered: 2026-05-25*
