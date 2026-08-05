# Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 5-politesse-adaptive-polling-quiet-hours-circuit-breaker
**Areas discussed:** NC vacation calendar source, Adaptive-interval thresholds & quiet-hours semantics, Circuit breaker schedule & reauth interaction, Code organization & forward-compat

---

## NC vacation calendar source

### Q1.1 — Source for the NC school-vacation calendar in v1?

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcode 2026 NC dates in const.py | Frozen tuple of (start, end) pairs covering the 5 NC vacation periods. Yearly hand-update PR. Matches research §"NC school-calendar data source" v1 plan. | |
| Spike vice-rectorat NC ICS first | Probe denc.gouv.nc / ac-noumea.nc for a machine-readable feed. Fall back to hardcode if not found. Adds spike risk. | ✓ (user preference, but redirected — see notes) |
| Python `holidays` library | Covers fériés nationaux only, NOT school vacations. Misses the use case. | |

**User's choice:** Free-text — "à approfondir en faisant des recherches, je préférerai la solution 2, mais je ne trouve pas de fichier ics sur les sites https://www.ac-noumea.nc/spip.php?article24 et https://denc.gouv.nc/calendrier-scolaire"

**Notes:** WebSearch surfaced THREE viable ICS/JSON sources:
1. `https://data.gouv.nc/explore/dataset/calendrier_scolaire_nc/` (NC's own Opendatasoft portal — most authoritative + locally published; JSON + ICS exports via `data.gouv.nc/api/explore/v2.1/catalog/datasets/calendrier_scolaire_nc/exports/{json,ics}`)
2. `https://fr.ftp.opendatasoft.com/openscol/fr-en-calendrier-scolaire/NouvelleCaledonie.ics` (national CDN — but 2026 NC + WF data may lag publication)
3. `https://data.education.gouv.fr/api/v2/catalog/datasets/fr-en-calendrier-scolaire` with `location=Nouvelle-Calédonie` filter (same lag caveat)

Findings shared with user; followed up with Q1.2 to nail down the fetch + fallback strategy.

### Q1.2 — Given that data.gouv.nc + openscol CDN both publish the NC calendar, what's the fetch + fallback strategy for Phase 5?

| Option | Description | Selected |
|--------|-------------|----------|
| data.gouv.nc API + hardcoded 2026 fallback | HTTP GET on integration setup + weekly background refresh, cached in HA Store helper. const.py NC_VACATION_RANGES_2026 hardcoded baseline if API unreachable. | |
| Hardcoded 2026 NC dates only | Skip HTTP fetch in v1. Bake the 5 vacation periods into const.py. Yearly hand-update PR. Simplest. Migrate to feed in v1.x if maintenance hurts. | ✓ |
| openscol ICS CDN + ICS parser fallback | Fetch fr.ftp.opendatasoft.com ICS; stdlib parser; same hardcoded fallback. 2026 NC data may not be published on CDN yet. | |

**User's choice:** Hardcoded 2026 NC dates only.

**Notes:** Pragmatic — zero new HTTP dependency, no caching/Store complexity. data.gouv.nc URL kept in CONTEXT.md canonical refs for the v1.x migration PR.

### Q1.3 — Should the suspension include French/NC jours fériés during the school year (14 juillet, 1er mai, Fête de la citoyenneté NC 24/9, etc.) on top of weekends + vacations?

| Option | Description | Selected |
|--------|-------------|----------|
| No — weekends + vacations only | COORD-05 literally says "week-ends et vacances scolaires NC". Fériés = no school = polling them is wasteful but not harmful. | |
| Yes — include fériés nationaux + NC locaux via `holidays` PyPI | Use `holidays.France(subdiv='NC')` to enumerate fériés. New runtime dep; small risk of skew between lib and actual NC calendar. | ✓ |
| Yes — hardcode fériés NC in const.py too | List the ~12 jours fériés as frozen dates. No new dep but more yearly maintenance. | |

**User's choice:** Yes — include fériés nationaux + NC locaux via `holidays` PyPI.

**Notes:** New runtime dep `holidays==<pin>` added to manifest.json. Planner verifies `subdiv='NC'` support + NC-specific dates (Fête de la citoyenneté 24/9) during a probe step. If gaps surface, fall back to a `NC_LOCAL_HOLIDAYS_SUPPLEMENT` frozenset in const.py (defaults to empty).

---

## Adaptive-interval thresholds & quiet-hours semantics

### Q2.1 — How should a "suspended" poll (weekend / vacation / férié) actually behave in the coordinator?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip the network call, return cached Snapshot | compute_interval returns a long timedelta; should_poll(now) returns False; _async_update_data short-circuits before pronotepy call. Sensors stay populated, recorder doesn't churn, zero network. | ✓ |
| Just slow the cadence — update_interval = 6h or 12h | Suspension = huge timedelta; poll still runs (~once every 6-12h). Less code change. Still 4 wasted HTTP calls/weekend. | |
| Set update_interval = 24h — single daily heartbeat | One poll per day during vacation, keeps connection warm. | |

**User's choice:** Skip the network call, return cached Snapshot.

**Notes:** Triggered the introduction of `should_poll(now, options)` predicate in politesse.py. Coordinator short-circuits at top of `_async_update_data`; `_previous_snapshot` is NOT updated during a skipped poll. First-poll-after-setup guarded: even if should_poll=False, the very first poll runs (else sensors stuck on `unavailable` during weekend install).

### Q2.2 — Should the coordinator do an end-of-suspension PRIMER — one poll on Sunday evening (or last day of vacation) to refresh the Snapshot before Monday/rentrée?

| Option | Description | Selected |
|--------|-------------|----------|
| No primer — first poll of Monday 6h is the warm-up | Don't special-case. Normal cadence picks up the new EDT. Simpler. Core value not lost. | |
| Yes — prime polling Sunday 18h-20h and last-day-of-vacation evening | One or two polls in the last 4h of any suspension window. Reuses the 17h-20h afternoon-tightening window. | ✓ |

**User's choice:** Yes — prime polling Sunday 18h-20h and last-day-of-vacation evening.

**Notes:** Drove the "primer day" definition (D-06): tighter polling whenever tomorrow is a school day AND now is 17h–20h NC. Unifies weekday afternoons + Sunday/end-of-vacation evenings under a single rule. No new state field.

### Q2.3 — Quiet hours (22h–6h NC) — what does it actually suppress?

| Option | Description | Selected |
|--------|-------------|----------|
| Suppress bus events AND slow polling to ~4h cadence | compute_interval returns ~4h during 22h-6h NC; _fire_diff_events drops events with debug log. Matches PITFALLS.md §2.4 explicit recipe. | ✓ |
| Suppress bus events only — polling continues at normal cadence | Diff still runs, snapshot updated; only bus.async_fire gated. | |
| Queue events during quiet hours, fire at 6h | Buffer events, batch-fire at 6h. Preserves observability, adds state + edge cases. | |

**User's choice:** Suppress bus events AND slow polling to ~4h cadence.

**Notes:** quiet hours composes with weekends/vacations: in any overlap, weekend/vacation wins (should_poll=False takes precedence over the 4h-cadence branch). Drove the `should_fire_event(now, options)` gate in `_fire_diff_events`.

---

## Circuit breaker schedule & reauth interaction

### Q3.1 — Exponential backoff curve for the circuit breaker?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed schedule: 1h → 2h → 4h → 12h → 24h cap | Matches PITFALLS.md §2.1 verbatim. Predictable, 5-step sequence, easy to test, easy to explain to users in the notification. | ✓ |
| Multiplicative: base × 1 → ×2 → ×4 → ×8 → ×16 → 24h cap | Standard exp backoff. Recovers faster from transient blip. Research says "long backoff" though. | |
| Two separate curves: auth-failure (fast 5m-1h cap) vs IP-suspended (slow 1h-24h cap) | Different urgency for different signals. Adds second state machine. | |

**User's choice:** Fixed schedule: 1h → 2h → 4h → 12h → 24h cap.

### Q3.2 — Should the 3-consecutive-auth-failure circuit replace or run alongside HA's existing ConfigEntryAuthFailed reauth flow?

| Option | Description | Selected |
|--------|-------------|----------|
| Run alongside — backoff slows polling, reauth still fires at strike 1 | Each genuine AuthError adds to counter, raises ConfigEntryAuthFailed, AND mutates update_interval per backoff curve. Reauth flow + backoff both active. | ✓ |
| Replace — backoff first, reauth only after circuit opens | Strikes 1-2 silently backoff; strike 3+ raises ConfigEntryAuthFailed. Avoids "password changed" being a one-strike trip into reauth. Hides errors from HA's UI for 2 strikes. | |
| Pure parallel — backoff for IP_SUSPENDED only, never gates auth | Circuit activates only on RateLimitedError(IP_SUSPENDED). AuthError straight to reauth. Skips COORD-07 trigger — non-compliant with the requirement text. | |

**User's choice:** Run alongside — backoff slows polling, reauth still fires at strike 1.

**Notes:** Backoff applies from strike 1 (over-meets COORD-07's "3 consecutive" wording with a stricter politesse). The WR-04 5-min recovery cooldown from Phase 3 stays intact; breaker counter ticks only on AuthErrors that survive `_recover_from_auth_error`.

### Q3.3 — Where should the circuit-breaker counter + backoff state live?

| Option | Description | Selected |
|--------|-------------|----------|
| On the coordinator instance — self._consecutive_failures, self._backoff_until | Two private fields. Pure in-memory; resets on HA restart. | ✓ |
| Extend PronoteData dataclass (runtime_data) | Cleaner separation, easier diagnostics surface. More types. | |
| Persist to entry.data so it survives restarts | Survives HA restart. Violates Phase 3 D-08 contract (entry.data = stable identity only). | |

**User's choice:** On the coordinator instance.

**Notes:** In-memory only. HA restart resets — fine because `async_config_entry_first_refresh()` will surface a still-broken state on the first poll. Phase 7's DIAG-01 reads these fields for diagnostics.

### Q3.4 — Persistent HA notification for IP-suspended and circuit-open states — lifecycle?

| Option | Description | Selected |
|--------|-------------|----------|
| One notification per entry, dedupe by id, auto-dismiss on recovery | persistent_notification.async_create with stable notification_id; HA dedupes natively. On first successful poll: async_dismiss. Includes next-retry time + strike count + troubleshooting link. | ✓ |
| One notification per backoff escalation step | Fire new notification each escalation. Spammy. | |
| Defer notifications to Phase 7 (Repair Issues / DIAG-02) | COORD-08 explicitly requires persistent notification — non-compliant. | |

**User's choice:** One notification per entry, dedupe by id, auto-dismiss on recovery.

**Notes:** Two separate notifications: one for IP_SUSPENDED state (`{DOMAIN}_{entry_id}_ip_suspended`), one for 3-strikes-auth (`{DOMAIN}_{entry_id}_auth_circuit`). Body includes redacted Pronote error message, next-retry timestamp in school_tz, strike count, link to Phase 7 troubleshooting README (placeholder URL — Phase 7 fills the real one).

---

## Code organization & forward-compat

### Q4.1 — Where should compute_interval + should_poll + should_fire_event + circuit-breaker pure helpers live?

| Option | Description | Selected |
|--------|-------------|----------|
| New `custom_components/ha_pronote/politesse.py` — pure, HA-free | Greenfield module with pure functions, stdlib + `holidays` only, AST guard extended. Easy unit testing in milliseconds across Paris+Nouméa matrix. ~150-200 LOC. | ✓ |
| Grow coordinator.py with private methods | Zero new file, all state co-located. Harder to TZ-matrix test without HA fixtures. | |
| Module per concern — politesse/interval.py + politesse/breaker.py | Premature split for ~200 LOC. | |

**User's choice:** New politesse.py — pure, HA-free.

### Q4.2 — Thresholds & defaults — read from entry.options (Phase 6 wires the UI) or hardcode in const.py?

| Option | Description | Selected |
|--------|-------------|----------|
| entry.options.get(KEY, DEFAULT_FROM_CONST) on every read | Phase 5 ships the runtime read path; Phase 6 becomes pure UI work. Today (no OptionsFlow yet), all reads fall to const.py defaults. | ✓ |
| Hardcode in const.py only — Phase 6 refactors | compute_interval reads consts directly. More Phase 6 work. | |
| Mix — polling thresholds in options, NC vacation list in const | Reflects what's user-tweakable vs structurally fixed. | |

**User's choice:** entry.options.get with const.py defaults.

**Notes:** Drove the D-17 options key shape (int minutes for intervals, ISO time strings for windows). Phase 6's OptionsFlow declares matching voluptuous schemas + `entry.add_update_listener` for reload-on-change.

### Q4.3 — Jitter source for the ±30s offset (COORD-09) — how is it generated + made testable?

| Option | Description | Selected |
|--------|-------------|----------|
| random.uniform(-30, 30) inside compute_interval, injectable rng | Default `rng=random` module; tests pass `random.Random(seed=42)`. Non-cryptographic by design. | ✓ |
| Apply jitter outside compute_interval — inside coordinator | compute_interval stays jitter-free; coordinator adds it. Couples jitter logic to HA layer. | |
| Seed jitter from entry_id hash — stable per install | Deterministic by install. No within-install randomisation but still desynchronises between installs. | |

**User's choice:** random.uniform inside compute_interval, injectable rng.

---

## Q5 — More gray areas or ready for context?

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context | Write CONTEXT.md with the decisions captured + Claude's discretion. | ✓ |
| Explore more gray areas | Test fixture strategy, holidays version verification, i18n keys, hassfest impact. | |

**User's choice:** Ready for context.

**Notes:** Remaining sub-questions (holidays version pin, probe script for NC subdivision, test mocks for persistent_notification, message localization) captured under Claude's Discretion (C-01 through C-09 in CONTEXT.md).

---

## Claude's Discretion (captured in CONTEXT.md)

- **C-01:** Plan-wave decomposition (recommend 3 plans across 2 waves).
- **C-02:** Exact `holidays` version pin (latest stable at planning time, `==` exact pin matching project policy).
- **C-03:** Probe step to verify `holidays.France(subdiv='NC')` output + populate `NC_LOCAL_HOLIDAYS_SUPPLEMENT` if gaps surface.
- **C-04:** Test fixture for coordinator backoff tests (freezegun via pytest-freezer — already a PHACC transitive dep).
- **C-05:** Persistent notification message localization (Python constants in coordinator.py for fr+en in v1; Phase 7 may upgrade).
- **C-06:** Mock strategy for new coordinator tests (reuse Phase 3's mock_pronote_client pattern).
- **C-07:** `holiday_dates` storage location (extend PronoteData per Phase 3 D-21's explicit invitation).
- **C-08:** RNG instantiation in coordinator (use stdlib `random` global; tests inject seeded RNG).
- **C-09:** No `pronote_politesse_state_changed` bus event in v1.

---

## Deferred Ideas (captured in CONTEXT.md `<deferred>`)

- Live `data.gouv.nc` JSON/ICS fetch (v1.x)
- OpenScol CDN ICS (v1.x)
- OptionsFlow UI (Phase 6)
- Per-entry `school_tz` override (Phase 6)
- Diagnostics surface for breaker state (Phase 7)
- Repair Issue on IP-banned state (Phase 7)
- `hass.bus.async_fire("pronote_politesse_state_changed", ...)` (rejected for v1)
- Event queueing during quiet hours (rejected)
- Heartbeat poll during long suspension (rejected)
- Per-data-type cadence decoupling (rejected — out of REQUIREMENTS scope)
- Daily CI cron against `holidays@main` (Phase 7 DIST-04 extension)
- README documentation (Phase 7 DIST-07)
- HACS Quality Scale silver upgrade (Phase 7 / v2)
- Adaptive learning of optimal polling (v2)
