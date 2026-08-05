# Phase 3: Coordinator & First Sensor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 03-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 3-coordinator-first-sensor
**Areas discussed:** Config Flow + child handling, Token persistence trigger, child_identifier source (ENT-02 freeze), Sensor design (TIME-01)

---

## Config Flow + child handling

### Q1 — ParentClient with multiple children

| Option | Description | Selected |
|--------|-------------|----------|
| Add child-select step now | If ParentClient.children > 1, show pick step → one entry per child. AUTH-03 ships effectively in Phase 3; Phase 6 just adds reconfigure UX and per-child auth-fail isolation. No migration when Phase 6 lands. | ✓ |
| First-child-only stub | Silently picks children[0]. Phase 6 reworks + writes a migration to split entries. Faster Phase 3 but creates a known migration cliff. | |
| Reject multi-child accounts in Phase 3 | Abort multi-child flows with "Phase 6 not ready". Works for the author's single-child use case but blocks real users until Phase 6. | |

**User's choice:** Add child-select step now (recommended)
**Notes:** AUTH-03 satisfied effectively at Phase 3 by the per-invocation = per-child entry pattern.

### Q2 — Form structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single-step async_step_user | All four fields (URL, account_type, username, password) on one form. Standard HA pattern. Transitions to pick_child only when ParentClient.children > 1. | ✓ |
| Multi-step (URL+type → credentials) | Optional probe of URL after step 1 for faster cannot_connect feedback. More UI surface area; uncommon in HA integrations. | |
| Single-step with discovery hint for parent | Same code path as option 1, just docstring/strings.json hint. | |

**User's choice:** Single-step async_step_user (recommended)

### Q3 — URL validation

| Option | Description | Selected |
|--------|-------------|----------|
| voluptuous.Url() schema only | Form-level malformed-URL rejection; reachability verified by build_client(). CLAUDE.md anti-pattern guidance. | ✓ |
| URL schema + path-shape heuristic | Adds .html/`/pronote/` heuristic — nicer error message, heuristic-fragile. | |
| URL schema + executor probe | HEAD request via aiohttp before auth — most informative, overkill given pronotepy's own connect failure already maps to cannot_connect. | |

**User's choice:** voluptuous.Url() schema only (recommended)

### Q4 — ConfigEntry unique_id

| Option | Description | Selected |
|--------|-------------|----------|
| f'{url_host}:{username}:{child_identifier}' | Catches duplicate-add of the same child even across schools / username typos. Standard HA pattern. | ✓ |
| f'{username}:{child_identifier}' | Drops URL component. Two parents with the same username at different schools would collide. | |
| Pronotepy's client.identifier alone | Minimal but undocumented in 2.14.6 — would need a spike to confirm. | |

**User's choice:** f'{url_host}:{username}:{child_identifier}' (recommended)

---

## Token persistence trigger

### Q1 — Capture trigger

| Option | Description | Selected |
|--------|-------------|----------|
| After every successful poll | Coordinator captures export_credentials() on success and updates entry.data via async_update_entry. HA debounces the storage write. Captures Pronote token rotations. | ✓ |
| Only after first auth + on session-rotate detection | Capture once, re-capture only when pronotepy raises session-expired. Adds complexity in the recovery path. | |
| Only on first auth, never again | Simplest; loses AUTH-04 the moment Pronote rotates. | |

**User's choice:** After every successful poll (recommended)

### Q2 — Restart strategy

| Option | Description | Selected |
|--------|-------------|----------|
| token_login(stored) first, fallback to username/password | Two code paths in api/client.py both shipped via the same executor wrap. Optimal AUTH-04. | ✓ |
| Always token_login if present, else fail | No silent fresh-login fallback. Breaks the "no entry brick" invariant when stored creds expire and Phase 6 reauth doesn't yet exist. | |
| Always fresh username/password | Loses AUTH-04 entirely; risks IP-suspended threshold over restart-heavy weeks. | |

**User's choice:** token_login(stored) first, fallback to username/password (recommended)

### Q3 — Storage shape

| Option | Description | Selected |
|--------|-------------|----------|
| entry.data['session'] = export_credentials() dict | Opaque pronotepy-owned blob. async_migrate_entry handles future shape changes. | ✓ |
| entry.data['credentials'] = typed wrapper with pronotepy_version | Defensive but premature for an already-opaque blob. | |
| Drop password after first successful token_login | Stronger security but breaks the silent-recovery branch in option 1 of Q2. | |

**User's choice:** entry.data['session'] = export_credentials() dict (recommended)

### Q4 — Mid-poll session-expired recovery

| Option | Description | Selected |
|--------|-------------|----------|
| Silent re-login with username/password, then retry the fetch | Maximally invisible to user; matches AUTH-04 spirit. Adds an explicit recovery branch in api/coordinator. | ✓ |
| Raise ConfigEntryAuthFailed immediately | Simpler Phase 3 but pesters user on every Pronote session rotation; reauth flow doesn't land until Phase 6. | |
| Hybrid (re-login if password stored, else reauth) | Forward-compatible with the rejected "drop password" option — equivalent to option 1 here. | |

**User's choice:** Silent re-login with username/password, then retry the fetch (recommended)

---

## child_identifier source (ENT-02 freeze)

### Q1 — pronotepy field

| Option | Description | Selected |
|--------|-------------|----------|
| Slugified pronotepy name (client.info.name / children[i].name) | Readable in entity_ids; cross-account uniqueness handled by config-entry unique_id. Standard delphiki pattern. | ✓ |
| Pronote-side stable ID (client.info.identifier / children[i].identifier) | Maximum stability, unreadable entity_ids. | |
| Username-derived (slugify(username) + index) | Semantically wrong — username belongs to parent, not child; index brittle on multi-child reorder. | |

**User's choice:** Slugified pronotepy name (recommended)

### Q2 — Freeze capture

| Option | Description | Selected |
|--------|-------------|----------|
| Capture once at config-flow time, never re-derive | Stored in entry.data['child_identifier']. Pronote name change → updates DeviceInfo.name, never unique_id. ENT-02 enforced literally. | ✓ |
| Re-derive every poll, accept entity rename on name change | Simplest code, breaks ENT-02. | |
| Capture once + add migration hook in Phase 6 reconfigure | Same Phase 3 deliverable as option 1; Phase 6 scope is out of Phase 3 boundary. | |

**User's choice:** Capture once at config-flow time, never re-derive (recommended)

### Q3 — Collision handling

| Option | Description | Selected |
|--------|-------------|----------|
| Append disambiguator suffix on collision | 2-char hex suffix from pronotepy.children[i].identifier (e.g. 'jean_dupont_a3'). Caught at flow time. Twins / blended families. | ✓ |
| Show pronotepy identifier in flow, let user pick suffix | Surfaces opaque ID in UX. | |
| Reject the collision, ask for nickname | Blocks setup until Phase 6 ships nickname; unworkable for v1. | |

**User's choice:** Append disambiguator suffix on collision (recommended)

---

## Sensor design (TIME-01)

### Q1 — Attributes in Phase 3

| Option | Description | Selected |
|--------|-------------|----------|
| State-only in Phase 3 | state = len(snapshot.lessons_today). Phase 4 adds J + J+1 attribute payload as a deliberate add. | ✓ |
| Minimal Phase 3 attributes (last_update, school_tz) | Useful for debugging polling cadence; adds attribute surface diagnostics will need to redact. | |
| Phase 4 attributes scaffolded but empty | Forward-compatible; exposes empty attribute users see in dev tools. | |

**User's choice:** State-only in Phase 3 (recommended)

### Q2 — Class hierarchy

| Option | Description | Selected |
|--------|-------------|----------|
| Base CoordinatorEntity[PronoteCoordinator] + per-sensor SensorEntity subclasses | Standard HA pattern; Phase 4 just subclasses. | ✓ |
| Single SensorEntity reading from EntityDescription tuples | Compact but obscures business logic when sensors diverge in native_value/attributes. | |
| Standalone PronoteLessonsTodaySensor (no base) | Fastest Phase 3, but Phase 4 has to refactor the entity hierarchy (delphiki #142 anti-pattern). | |

**User's choice:** Base CoordinatorEntity + per-sensor subclasses (recommended)

### Q3 — Sensor metadata

| Option | Description | Selected |
|--------|-------------|----------|
| state_class=measurement, no device_class, icon=mdi:school | Long-term statistics graphable; native_unit='lessons' (translation_key handles 'cours'). | ✓ |
| state_class=total (resets daily) | More accurate semantics; complicates the recorder with last_reset. | |
| No state_class, no device_class, icon=mdi:school | No long-term statistics; sacrifices the trend-graph use case parents will want. | |

**User's choice:** state_class=measurement, no device_class, icon=mdi:school (recommended)

### Q4 — DeviceInfo

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal device: name + identifiers + manufacturer='Pronote' | NO model field yet (Phase 4 success criterion #2 explicitly). NO sw_version, NO configuration_url. | ✓ |
| Phase 4-shaped device with model='unknown' placeholder | Marginal forward-compat benefit; introduces placeholder users see. | |
| Per-sensor devices (no parent device) | Loses 'one card per child' UX. | |

**User's choice:** Minimal device: name + identifiers + manufacturer='Pronote' (recommended)

---

## Claude's Discretion

The user delegated these sub-decisions to the planner. Recommended defaults documented in 03-CONTEXT.md `<decisions>` "Claude's Discretion":

- C-01 — `entity.py` separate file vs co-located in `sensor.py` (RECOMMEND `entity.py`)
- C-02 — `build_or_resume_client` helper signature (RECOMMEND single function with optional session)
- C-03 — coordinator captures `_previous_snapshot` already in Phase 3 (RECOMMEND yes)
- C-04 — Pronote-side device_name derivation (RECOMMEND on-the-fly from `entry.entry_id[:8]`)
- C-05 — HA-side test mock strategy (RECOMMEND MagicMock at the `build_or_resume_client` seam, not requests-mock)
- C-06 — Plan decomposition / wave structure (RECOMMEND 4 plans across 3 waves)

## Deferred Ideas

Captured in 03-CONTEXT.md `<deferred>`. Highlights:

- Reauth flow (`async_step_reauth`) — Phase 6 (AUTH-05)
- Reconfigure flow + Options Flow (refresh_interval, school_tz, nickname, adaptive toggle) — Phase 6 (AUTH-06, OPT-01..04)
- Adaptive 17h–20h polling, weekend/vacation suspension, jitter, circuit breaker, IP-ban long-backoff — Phase 5 (COORD-04..09, DIST-06)
- Bus events (`pronote_schedule_changed` etc.), full sensor suite, Calendar entity, J + J+1 attributes, model=`<class level>` on DeviceInfo — Phase 4
- Diagnostics platform, Repair Issues, full translations, daily cron against `pronotepy@main` — Phase 7
- Dropping `entry.data['password']` after first successful token_login — explicitly rejected for Phase 3 (breaks silent-recovery branch); reconsider Phase 7
- Pre-emptive nickname field at flow time — explicitly rejected (scope creeps Phase 6 OPT-03)
- HEAD probe before auth — explicitly rejected (pronotepy's connect failure is enough signal)
