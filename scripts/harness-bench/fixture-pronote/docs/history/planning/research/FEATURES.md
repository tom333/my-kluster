# Feature Research

**Domain:** Home Assistant custom_component (HACS) — Pronote scraping integration
**Researched:** 2026-05-03
**Confidence:** HIGH (based on direct source-code reading of `delphiki/hass-pronote` v0.15.5 + reading 70+ open issues + official HA dev docs)

## Existing Integrations Benchmarked

### `delphiki/hass-pronote` (the de facto incumbent)
- **Reach:** 94 stars, 17 forks, 77 open issues, last push 2026-03-20 — actively maintained, mature
- **HACS:** Yes (HACS default repository), v0.15.5
- **Stack:** `pronotepy==2.14.5`, `python-slugify`, `DataUpdateCoordinator` (`TimestampDataUpdateCoordinator`), 15 min default poll
- **Auth:** Username/password OR QR code (PIN), parent or eleve, ENT optional. `VERSION = 2` config flow, has reauth via re-importing QR code (still painful — see issue #133)
- **Sensors per child** (prefixed `sensor.pronote_LASTNAME_FIRSTNAME_*`):
  - `class`, `today_s_timetable`, `tomorrow_s_timetable`, `next_day_s_timetable`, `period_s_timetable` (15 days), `timetable_ical_url`, `next_alarm` (timestamp device class)
  - `grades`, `homework`, `period_s_homework`, `absences`, `evaluations`, `averages`, `punishments`, `delays`, `overall_average`, `information_and_surveys`, `menus`
  - `current_period`, `periods`, `previous_periods`, `active_periods`
  - For each previous period: `grades_trimestre_1`, `averages_trimestre_1`, etc. (multiplied by N periods)
- **Calendar entity:** Yes — `PronoteCalendar` exposes `lessons_period` as `CalendarEvent` list; cancelled lessons prefixed "Annulé -"
- **Events:** Single bus event `pronote_event` with `{type, data, child_name, child_nickname, child_slug}`. Types fired by `compare_data()`: `new_grade`, `new_homework`, `new_absence`, `new_delay`, `new_evaluation`, `new_punishment`, `new_lesson` (changes), `new_information`. Comparison uses configured key tuples (e.g. grades compared on `["date", "subject", "grade_out_of"]`)
- **Device model:** ONE device per child (`identifiers={(DOMAIN, child_info.name)}`, manufacturer "Pronote"), all sensors attached to that device → multi-child = multi-device
- **Companion Lovelace cards:** `delphiki/lovelace-pronote` (separate HACS repo) with custom cards: `pronote-timetable-card`, `pronote-homework-card`, `pronote-grades-card`, `pronote-averages-card`, `pronote-evaluations-card`, `pronote-absences-card`, `pronote-delays-card`. These cards consume the sensor `attributes` directly — they are tightly coupled to the integration's attribute schema

### `vingerha/pronote2mqtt` (deprecated as of Dec 2024)
- Different architecture: docker container + MQTT discovery (not a HA custom_component)
- Author explicitly recommends migrating to `delphiki/hass-pronote`
- Used SQLite for history. Confirms "device per student" design pattern (`Student`, `Grade`, `Average`, `Absence`, `Homework`, `Evaluation`, `Punishment`)

### `dathosim/Pronote2Homeassistant`
- Tutorial / snippet repo, not a packaged integration. Negligible. Confirms domain interest but not a competitor.

### Take-aways
- **delphiki is the only real competitor.** Going from-scratch (per project decision) means having to ship something genuinely better — its Achilles heel is **cluttered/fragile UX** (everything in attributes, period-multiplied entities exploding state-attribute size, brittle reauth, missing direct sensors for moyennes — see issues #134, #135, #136, #133).
- **Companion Lovelace card ecosystem is ripe for differentiation** (or for compatibility, if we mirror delphiki's attribute keys, users can reuse `delphiki/lovelace-pronote` — but PROJECT.md scope explicitly excludes shipping cards).

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Config Flow UI (Settings → Devices & Services → Add) | HA standard since 2021; YAML config is now considered legacy | LOW | `manifest.json` `"config_flow": true`; `voluptuous` schema |
| Multi-account / multi-child support | Most French families have ≥1 enfant; delphiki supports it; baseline expectation | MEDIUM | One `ConfigEntry` per child (delphiki pattern). Parent account select-child step in flow. |
| Encrypted credential storage | HA `ConfigEntry.data` is stored encrypted in `.storage/`; never log plaintext | LOW | Use `entry.data` for secrets, `entry.options` for tunables |
| **Reauth flow** (`async_step_reauth`) | When credentials expire (token rotation, password change), user gets a clean re-prompt — not a deleted entry that breaks all entities. delphiki's #1 pain point (issue #133, #155). HA Quality Scale: **Silver requirement**. | MEDIUM | Implement `async_step_reauth` + `async_step_reauth_confirm`. Triggered by raising `ConfigEntryAuthFailed` from coordinator. |
| Reconfigure flow (`async_step_reconfigure`) | Change URL/ENT/credentials without losing entity IDs (HA 2024.11+). Solves "broken entry" problem from delphiki #133. | MEDIUM | Keep same `unique_id`, update `entry.data`. |
| Options Flow for polling interval | User control over politeness (15/30/60 min). Users on slow servers / shared IPs need this. | LOW | `async_get_options_flow` returning `OptionsFlow` |
| `DataUpdateCoordinator` (async, single coordinated poll) | HA Quality Scale Bronze rule (`appropriate-polling`); avoids per-sensor polls | LOW | `TimestampDataUpdateCoordinator` if "next update" timestamp is exposed; else plain `DataUpdateCoordinator` |
| One **device per child** (`DeviceInfo`) | HA Quality Scale Gold rule (`devices`). All entities for child Alice grouped under "Pronote — Alice" device card. | LOW | `identifiers={(DOMAIN, child_id)}`, `manufacturer="Pronote"`, `model=child class/level`, `via_device` if needed |
| Stable `unique_id` per entity | HA Quality Scale Bronze rule (`entity-unique-id`). Without it, users can't rename/customize from UI. | LOW | `f"{child_id}_{sensor_key}"` — must NOT change across HA restarts or Pronote re-auths |
| `has_entity_name = True` + `_attr_translation_key` | HA modern naming (entity name = device name + entity name auto-composed) | LOW | Required for clean Gold/Platinum scoring; future-proofs against HA naming conventions |
| Numeric `state` for averages (not string) | French uses comma decimal (`17,87`). delphiki ships it as text → useless for ApexCharts/templates without manual replace (issue #135) | LOW | Convert `,` → `.`, cast to `float`, `state_class=measurement` |
| Sensor attribute payload < 16 KiB | HA `recorder` rejects attributes > 16384 bytes ("Attributes will not be stored"). delphiki blows this on `period_s_timetable` (issue #136) | LOW | Trim to last N items; never put full HTML descriptions in attributes |
| Fired events for "something new" | Users want automations: "if new_information, notify telegram". delphiki fires `pronote_event` → community already automates on this | MEDIUM | Single event domain `pronote_event` with `{type, child_id, payload}` (see Architecture research) |
| HACS-compliant repo structure | `manifest.json`, `hacs.json`, `info.md`, `custom_components/pronote/`, GitHub releases with semver tags | LOW | HACS validation runs in CI |
| French-language UI / `strings.json` | Target audience is 100% French families | LOW | `translations/fr.json` + English fallback |
| Logos / brand integration (`brands` repo) | HA Quality Scale Gold rule. Pronote logo in integration card | LOW | PR to `home-assistant/brands` repo, deferred to v1.x |

### Differentiators (Competitive Advantage vs delphiki)

Features that set us apart. Aligned with PROJECT.md Core Value: "fiable et exploitable dès qu'un cours est annulé ou modifié".

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Adaptive polling 17h–20h for J+1 EDT** | delphiki uses constant 15-min polling. We poll less the rest of the day (politeness, reduce IP-ban risk per issue #148) AND more aggressively in the EDT-publication window. **Direct alignment with PROJECT.md core value.** | MEDIUM | Override `update_interval` based on `datetime.now()` in coordinator; or schedule via `async_track_time_change`. |
| **Rich `pronote_schedule_changed` events** with diff payload | delphiki fires `new_lesson` only. We fire structured events with `{change_type: cancelled/moved/teacher_changed/added, day: J|J+1, before: {...}, after: {...}, child_id}` so automations can branch. | MEDIUM | Diff algorithm in coordinator; comparable lesson signature based on `(date, start, subject)` |
| **Dedicated event entities** (HA Event entity component) | HA has a first-class `event` platform (introduced ~2023.8). Better for history/automation than bus events alone. Few integrations use it; would feel modern. | MEDIUM | `event.pronote_alice_schedule_change`, `event.pronote_alice_new_grade`, etc. Optional, complementary to bus events. |
| **Direct numeric sensor for moyenne générale** (no string, comma fixed, `state_class=measurement`) | Solves delphiki issue #135 + #134. Users want graphable averages out of the box, not via template helpers. | LOW | + per-subject `sensor.pronote_alice_average_math` if cheap (pronotepy exposes `period.averages` per subject) |
| **Compact, ApexCharts-ready attribute schema for grades** | Document explicit attribute shape: `attributes.grades = [{date: ISO8601, subject, grade: float, out_of: float, coefficient: float, average_class: float}]` so users can do `data_generator: "return entity.attributes.grades.map(g => [Date.parse(g.date), g.grade])"`. delphiki's schema is undocumented & oversized. | LOW | Just discipline + README example |
| **Diagnostics support** (`async_get_config_entry_diagnostics`) | HA Quality Scale Silver rule. One-click "Download Diagnostics" from device card → JSON with redacted creds, last poll status, child info. delphiki does NOT implement this → debugging issues is currently miserable. | LOW | Use `homeassistant.components.diagnostics.util.async_redact_data` for `password`, `qr_code_json`, `jeton` |
| **Repair Issues** (`ir.async_create_issue`) | HA Quality Scale Gold rule. When IP is banned, surface a user-actionable repair card ("Your IP is suspended. Increase polling interval and try again in 24h. [Open settings]") instead of silent failure. | MEDIUM | `homeassistant.helpers.issue_registry`. Trigger on `pronotepy.PronoteAPIError("Your IP address is suspended.")` + auth failures. |
| **No period-multiplied entities by default** | delphiki creates `grades_trimestre_1`, `grades_trimestre_2`, ... → users get 30+ entities per child. We expose a single `sensor.pronote_alice_grades` whose attributes contain ALL grades (trimmed if size limit), with a `period` filter via service call. | MEDIUM | Service `pronote.get_grades_for_period(period: str)` returning data; or template-friendly attribute layout |
| **Calendar entity in v1** | delphiki has it; HA users expect "lessons" to appear in standard Calendar dashboard / `calendar.list_events` automations. Also a Quality Scale "platinum" booster. | MEDIUM | `CalendarEntity` subclass implementing `async_get_events(start, end)` |
| **Attribute size guard** (built-in tests) | Unit test verifies serialized attribute size < 16 KiB for every sensor at realistic data scale (40 lessons/week × 2 weeks). Prevents regression of delphiki #136. | LOW | pytest assertion, part of CI quality gate |
| **No-op idempotent reauth** (button on device card) | delphiki users on issue #133 have to delete + recreate the entry, breaking all dashboards. Our reauth keeps `unique_id` stable. | MEDIUM | Combination of reauth flow + reconfigure flow |
| **Optional child nickname** (Options Flow) | delphiki has it; expected by users with full-name children for entity readability. `Lemoine` → `Anatole` | LOW | `entry.options["nickname"]` consumed by `_attr_name` |
| **Schema versioning + migration** (`async_migrate_entry`) | HA Quality Scale Silver rule. Pronote returns may change between pronotepy versions; we'll need migrations. Plan from day 1. | LOW | Boilerplate `async_migrate_entry` skeleton even if v1→v2 not yet needed |
| **Logbook integration** (entity events appear in HA logbook) | Power users love this — schedule changes show up in logbook with friendly text. | LOW | `homeassistant.components.logbook.async_describe_event` + named event types |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Bundled custom Lovelace card** | Users want pretty UI out of the box | Maintaining a frontend card = JS toolchain, frontend HACS submission, breaking HA frontend changes; doubles maintenance surface. PROJECT.md already excludes it. | Document an example ApexCharts/markdown/Mushroom YAML config in README. Users can also use `delphiki/lovelace-pronote` if attribute schema is mirrored — but mirroring constrains us. **Decision: don't mirror, document our schema.** |
| **Push / webhook-based updates** | "Real-time" appeal | Pronote has no push API. pronotepy is HTTP scraping. Pretending otherwise is a lie. | Smart adaptive polling (see differentiator above) |
| **OCR / parsing notification HTML/PDF attachments** | "Read everything Pronote sends" | Brittle, locale-dependent, 80% of effort for 5% of cases | Expose `attachments_url[]` in attributes; user can use HA `downloader` if they really want |
| **Write actions (mark-read, send-message, justify-absence)** | "Why is it read-only?" | (a) IP-ban risk doubles, (b) pronotepy write support is partial/unstable, (c) legal liability if a homework gets marked done by mistake. PROJECT.md explicitly excludes. | Read-only contract; users open Pronote app for writes |
| **Devoirs (homework) sensor in v1** | "delphiki has it" | Adds parser surface area, not in critical-path Core Value (EDT changes). PROJECT.md defers to v2. | Defer v2; the EDT calendar + notes + infos cover the parent-monitoring use case |
| **Automatic mobile push** | "I want to be notified on my phone" | HA already provides this via `notify.mobile_app_*` services + automations triggered by our events. Building our own is reinventing wheels. | Document a copy-paste automation YAML in README ("when `event_type=pronote_schedule_changed` → notify mobile_app") |
| **Per-period sensor explosion** | "I want my T1 average separately" | Multiplies entities by N periods × M children → 30+ entities for one family; pollutes entity registry; harder to find what matters | Single `current_period_average` sensor + service `pronote.get_period_data(period_id)` for ad-hoc queries |
| **Storing Pronote HTML descriptions verbatim in attributes** | "I want full content" | Blows past the 16 KiB attribute limit (delphiki #136); recorder drops history silently | Truncate at ~500 chars in attribute, expose `id` so users can fetch full content via service call if needed |
| **Multi-school / multi-Pronote-instance via single config_entry** | "My kid is at two schools" | One config entry = one Pronote login. Mixing logins multiplies failure modes. | Just add another integration entry per school |
| **Caching across HA restarts (persistent state)** | "Don't refetch on every restart" | HA already restores last sensor state via `RestoreEntity`; persistent caches add bug surface and stale-data risk | Use `RestoreSensor` mixin where it makes sense |
| **Auto-detect ENT** | "Just figure out my school" | Pronote URL → ENT mapping is non-deterministic; pronotepy has 30+ ENT functions; mis-detection = silent auth failure | User picks ENT explicitly in config flow (Out-of-scope in v1 anyway — Pronote direct only) |
| **Submitting to HACS default repo in v1** | Distribution reach | Submission process is bureaucratic, requires repo polish & tests-passing CI; iterate first as custom repo. PROJECT.md decision. | Default repo in v2+ once mature |
| **Supporting iCal subscription URL re-export** | "Like delphiki's `timetable_ical_url`" | The Calendar entity gives users this natively via HA's `/api/calendars/<entity_id>` endpoint. Re-exporting Pronote's URL bypasses our processing (cancellations, formatting). | Calendar entity is the answer; `ical_url` would be a leaky abstraction |

---

## Feature Dependencies

```
Config Flow (auth)
    ├──requires──> Pronote client wrapper (pronotepy)
    ├──enables───> Reauth Flow
    ├──enables───> Reconfigure Flow
    └──enables───> Options Flow

DataUpdateCoordinator
    ├──requires──> Config Flow (entry data)
    ├──requires──> Pronote client wrapper
    └──enables───> all sensors, calendar, events

Multi-child Support
    ├──requires──> Config Flow (parent: select child step OR one entry per child)
    └──enables───> Device per child grouping

Sensor: Timetable J/J+1
    ├──requires──> DataUpdateCoordinator
    └──enables───> Schedule-change Detection

Schedule-change Detection (diff between polls)
    ├──requires──> Timetable sensor
    ├──requires──> Previous poll snapshot in coordinator
    ├──enables───> pronote_schedule_changed event
    └──enables───> Event entity (optional)

Adaptive Polling 17h-20h
    ├──requires──> DataUpdateCoordinator with dynamic update_interval
    └──enhances──> Schedule-change Detection (catch J+1 publication faster)

Calendar Entity
    ├──requires──> Lessons fetched in DataUpdateCoordinator (period_lessons, ~14 days)
    └──enhances──> User automations on lesson start/end times

Sensor: Notes (with numeric state)
    ├──requires──> DataUpdateCoordinator
    ├──requires──> Decimal-comma normalisation
    └──enables───> ApexCharts grade evolution chart

Sensor: Notifications (information_and_surveys)
    ├──requires──> DataUpdateCoordinator
    └──enables───> "new_information" event

Diagnostics
    ├──requires──> DataUpdateCoordinator (snapshots last poll status)
    └──requires──> Credential redaction utility

Repair Issues
    ├──requires──> Coordinator catching specific exceptions (IP ban, auth fail)
    └──conflicts──> silent retry forever (would mask the problem)

Reauth Flow
    ├──requires──> ConfigEntryAuthFailed raised by coordinator
    └──conflicts──> "delete and recreate entry" workflow (delphiki #133)

Logo on integration card
    └──requires──> PR merged to home-assistant/brands repo (defer to v1.x)
```

### Dependency Notes

- **Reauth + Reconfigure must ship together (or reauth alone first).** Otherwise users hit `auth failed → delete entry → broken automations`, the delphiki #133 trap. Stable `unique_id` strategy must be set in stone before v1.0.
- **Adaptive polling and schedule-change detection compose:** weak adaptive polling + good detection = J+1 changes seen the next morning, not the night before → kills core value. Both must work for v1.
- **Diagnostics + Repair Issues both depend on coordinator exception handling:** design `async_update_data` to raise typed exceptions (`ConfigEntryAuthFailed`, custom `IpBannedError`, `PronoteUnavailableError`) so both diagnostics dump and repair issues can react. One implementation, two consumers.
- **Calendar entity is independent of sensor design:** can ship in v1 cheaply once `lessons_period` is available in coordinator (delphiki proves this in ~120 LOC).
- **Event entity vs bus events conflict in spirit (don't fire both for same payload):** pick one source of truth. Recommendation: **bus events for v1** (matches delphiki's contract, easier for users to grep tutorials), **add event entities in v1.x as opt-in**.

---

## MVP Definition

### Launch With (v1) — Strict MVP

Minimum viable product. Ruthlessly aligned with PROJECT.md "Core Value": fiable et exploitable dès qu'un cours est annulé ou modifié pour J ou J+1.

- [ ] **Config Flow** (URL + identifiants + parent/eleve, no ENT) — required, no UI = no install
- [ ] **Multi-child** (one ConfigEntry per child; parent flow steps through children) — French families table-stake
- [ ] **DataUpdateCoordinator** with adaptive polling (default 30 min, 15 min during 17h-20h window) — Core Value
- [ ] **Sensor: Emploi du temps** per child — state = nombre de cours du jour (or "next lesson" timestamp), attributes = J + J+1 (matière, prof, salle, heure début/fin, statut). Attribute payload < 16 KiB.
- [ ] **Sensor: Notes** per child — state = moyenne générale (numeric, comma fixed, `state_class=measurement`), attributes = N dernières notes (matière, note, sur, coef, date) — ApexCharts-ready schema documented
- [ ] **Sensor: Notifications/Informations** per child — state = nb non lues, attributes = N dernières (titre, expéditeur, date, extrait)
- [ ] **Schedule-change detection** comparing previous poll for J and J+1 → `pronote_schedule_changed` bus event with diff payload — Core Value
- [ ] **`pronote_new_grade` and `pronote_new_information` bus events** — supports automation table-stakes
- [ ] **Reauth flow** (`async_step_reauth`) — avoids the delphiki #133 trap; HA Silver
- [ ] **Numeric overall_average** — fixes delphiki #135 from day 1
- [ ] **Stable `unique_id` strategy** documented + tested — `f"pronote_{child_id}_{sensor_key}"`, never includes nickname
- [ ] **Device per child** with `DeviceInfo` (manufacturer "Pronote", model = child class/level)
- [ ] **`has_entity_name = True` + `_attr_translation_key`** — HA modern naming
- [ ] **Options Flow** (polling interval, J+1 watch window times, optional nickname)
- [ ] **strings.json + translations/fr.json** — UI in French
- [ ] **HACS custom repo structure** (manifest.json + hacs.json + info.md + iot_class=cloud_polling)
- [ ] **CI: lint + tests + HACS validation** — required for trust

### Add After Validation (v1.x)

Features to add once core is working and we have user feedback.

- [ ] **Calendar entity** (`CalendarEntity`) — high value, low cost (~120 LOC); deferred only to keep MVP scope tight. Trigger: first user request OR week-2 of v1
- [ ] **Diagnostics support** (`async_get_config_entry_diagnostics`) — trigger: first non-trivial bug report we can't reproduce
- [ ] **Repair Issues** for IP ban + auth failure — trigger: first IP ban report from a user
- [ ] **Per-subject average sensors** (`sensor.pronote_alice_average_math`, etc.) — trigger: feature request (very likely; delphiki #134)
- [ ] **Reconfigure flow** (`async_step_reconfigure`) — trigger: first user with URL/ENT migration need
- [ ] **Event entities** (HA Event component) — trigger: HA 2026.x stabilizes this and dashboard cards show them well
- [ ] **Schema migration scaffolding** (`async_migrate_entry`) — trigger: first breaking schema change between v1.x versions
- [ ] **Brand logo PR** to `home-assistant/brands` — trigger: v1.x stable; not blocking
- [ ] **Logbook integration** for schedule-change events — trigger: power user request
- [ ] **`RestoreEntity` mixin** to keep state across HA restart — trigger: user complains about "unknown" sensors after reboot
- [ ] **Service `pronote.get_period_data(period_id)`** — trigger: users want historical period drill-down without entity explosion

### Future Consideration (v2+)

Per PROJECT.md decisions, explicitly deferred:

- [ ] **Devoirs (homework) sensor + events** — deferred per PROJECT.md decision; out of MVP scope
- [ ] **ENT support** (Educonnect, ATEN, generic) — deferred per PROJECT.md decision; needs broader testing surface
- [ ] **Submission to HACS default repository** — deferred per PROJECT.md decision; v2+ once mature
- [ ] **Absences/retards/punishments sensors** — deferred per PROJECT.md decision; minor for parent monitoring
- [ ] **QR-code authentication path** (delphiki has it) — adds setup-time complexity; only valuable for users who can't reuse password (e.g. ENT-only). Reconsider if v2 brings ENT support.
- [ ] **Menus de cantine sensor** — niche, defer

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Config Flow + auth (Pronote direct, parent + eleve) | HIGH | MEDIUM | P1 |
| DataUpdateCoordinator (polling skeleton) | HIGH | LOW | P1 |
| Multi-child (one ConfigEntry per child) | HIGH | MEDIUM | P1 |
| Sensor: Emploi du temps (J + J+1) | HIGH | MEDIUM | P1 |
| Schedule-change detection + `pronote_schedule_changed` event | HIGH | MEDIUM | P1 |
| Adaptive polling (17h-20h window) | HIGH | LOW | P1 |
| Sensor: Notes with numeric average | HIGH | LOW | P1 |
| Sensor: Notifications/Informations | MEDIUM | LOW | P1 |
| Reauth flow | HIGH | MEDIUM | P1 |
| Stable unique_id + DeviceInfo per child | HIGH | LOW | P1 |
| Options flow (polling interval, nickname) | MEDIUM | LOW | P1 |
| HACS custom repo + CI + tests | HIGH | MEDIUM | P1 |
| French translations | MEDIUM | LOW | P1 |
| Numeric average (comma → dot, state_class) | MEDIUM | LOW | P1 |
| Attribute size guard (<16 KiB) | MEDIUM | LOW | P1 |
| Documented ApexCharts attribute schema | MEDIUM | LOW | P1 |
| Calendar entity | MEDIUM | MEDIUM | P2 |
| Diagnostics support | MEDIUM | LOW | P2 |
| Repair issues (IP ban, auth fail) | MEDIUM | MEDIUM | P2 |
| Per-subject average sensors | MEDIUM | LOW | P2 |
| Reconfigure flow | LOW | MEDIUM | P2 |
| Event entities | LOW | MEDIUM | P3 |
| Schema migration scaffolding | LOW | LOW | P2 |
| Brand logo PR | LOW | LOW | P3 |
| Logbook integration | LOW | LOW | P3 |
| Devoirs sensor | HIGH | MEDIUM | P3 (v2 per PROJECT.md) |
| ENT support | MEDIUM | HIGH | P3 (v2 per PROJECT.md) |
| QR-code auth path | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1 launch
- P2: Should add in v1.x post-validation
- P3: Future consideration

---

## Competitor Feature Analysis

| Feature | delphiki/hass-pronote | vingerha/pronote2mqtt (deprecated) | Our Approach |
|---------|----------------------|-----------------------------------|--------------|
| Auth methods | username/password OR QR code, parent/eleve, ENT optional | username/password, parent/eleve, ENT | username/password parent/eleve, **no ENT, no QR in v1** (PROJECT.md scope) |
| Timetable sensors | 4 separate sensors (today / tomorrow / next_day / period_15d) + iCal URL + next_alarm | Lessons in DB + MQTT | **1 sensor (state=cours du jour) with J + J+1 in attributes**, calendar entity in v1.x |
| Calendar entity | Yes (`CalendarEntity` over period_lessons) | No (MQTT-only) | **Yes in v1.x**, after MVP validation |
| Schedule-change detection | Yes — fires `pronote_event` `type=new_lesson` on diff | No (snapshots only) | **Yes — `pronote_schedule_changed` with rich diff payload** (change_type, before, after) |
| Average as numeric sensor | NO — string with comma (issue #135) | Numeric | **Yes — numeric, dot, state_class=measurement** |
| Per-subject averages as sensors | No — only attribute on `averages` sensor | Per-subject sensors | Single sensor in v1, **per-subject sensors in v1.x** |
| Per-period sensors | YES — `grades_trimestre_1`, `..._2`, ... → entity explosion | One row per period in DB | **NO — current period only, service for historical** |
| Devoirs (homework) | Yes (homework + period_homework sensors) | Yes (DB rows) | **Deferred to v2** (PROJECT.md) |
| Notifications/Informations | `information_and_surveys` sensor | No | **Yes — `notifications` sensor with non-read count + attributes** |
| Multi-child | Yes (one entry per child) | Yes (1 or 2 children) | **Yes — one ConfigEntry per child, device per child** |
| Bus events | Yes — `pronote_event` `{type, data, child_*}` (8 types: new_grade, new_homework, new_lesson, ...) | MQTT topic per event | **Yes — bus events but with separate event types** (`pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_information`) for cleaner automation triggers |
| Reauth flow | Partial — issue #133 reports unrecoverable broken entries | N/A | **Full reauth + reconfigure flow** (P1 differentiator) |
| Options flow | Yes (refresh_interval, alarm_offset, lunch_break_time, nickname) | param.py file | **Yes — refresh_interval, J+1 window, nickname** |
| Diagnostics support | NO | NO | **Yes in v1.x** (Quality Scale Silver) |
| Repair issues | NO | NO | **Yes in v1.x** (IP ban + auth fail) |
| Polling interval | Fixed 15 min default (configurable) | Cron-based | **Adaptive: 30 min default, 15 min during 17h-20h** |
| Attribute size discipline | NO — issue #136 (`period_s_timetable` exceeds 16 KiB) | N/A | **Yes — CI test asserts < 16 KiB at realistic data scale** |
| HACS distribution | Default HACS repo | Docker image | **Custom HACS repo in v1, default in v2** (PROJECT.md) |
| Companion Lovelace cards | Yes (`delphiki/lovelace-pronote`) | Markdown card example | **No bundled card** — README documents ApexCharts/markdown YAML examples (PROJECT.md scope) |
| Activity (Mar 2026) | 94⭐, 77 open issues, active | Deprecated Dec 2024 | New entrant — focus on quality not features |

### Where delphiki Falls Short — Our v1 Opportunities

1. **Authentication brittleness** (issues #133, #141, #155): no proper reauth → delete-and-recreate workflow → broken automations. **We solve via reauth + reconfigure flow.**
2. **Numeric data treated as text** (issue #135): comma decimal not normalized. **We normalize at coordinator level.**
3. **Attribute payload size** (issue #136): no discipline → recorder drops history. **We enforce <16 KiB via tests.**
4. **No diagnostics** → users debugging blind. **We ship diagnostics in v1.x (cheap).**
5. **No repair issues** → IP ban (#148) is silent failure. **We surface as actionable repair card.**
6. **Entity explosion via period sensors** (issue #142, #134): user wants direct sensors. **We expose only current period as entities, historical via service.**
7. **Constant 15-min polling regardless of need** → wasted requests, IP-ban risk. **Adaptive polling matches the use case (J+1 publication late afternoon).**
8. **`new_lesson` event lacks change semantics** → automation has to guess "was it cancelled? moved? teacher swap?". **We ship structured `pronote_schedule_changed` with `change_type` field.**

These are not "nice-to-haves" — they're concrete pain points reported in delphiki's open issues. Each one is a reason a parent would switch to our integration after a week of frustration.

---

## Sources

- delphiki/hass-pronote source code: [coordinator.py](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/coordinator.py), [sensor.py](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/sensor.py), [calendar.py](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/calendar.py), [config_flow.py](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/config_flow.py), [const.py](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/const.py), [manifest.json](https://github.com/delphiki/hass-pronote/blob/main/custom_components/pronote/manifest.json) (HIGH confidence — direct source read)
- delphiki/hass-pronote open issues #129, #133, #134, #135, #136, #142, #148, #155 (HIGH confidence — direct issue read)
- delphiki/hass-pronote [README](https://github.com/delphiki/hass-pronote) (HIGH)
- delphiki/lovelace-pronote [README](https://github.com/delphiki/lovelace-pronote) (HIGH — confirms attribute schema is the public contract)
- vingerha/pronote2mqtt [README](https://github.com/vingerha/pronote2mqtt) (HIGH — confirms deprecation, validates "device per student" pattern)
- HA Developer Docs: [Config flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/), [Integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/), [Calendar entity](https://developers.home-assistant.io/docs/core/entity/calendar/), [Fetching data / DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) (HIGH — official)
- HA Quality Scale tiers documentation: [Bronze/Silver/Gold/Platinum rules](https://www.home-assistant.io/docs/quality_scale/) (HIGH)
- HA Core release changelogs (2025.2, 2025.7, 2026.4) confirming quality scale enforcement (MEDIUM)
- ApexCharts-card [data_generator docs + community examples](https://github.com/RomRider/apexcharts-card) (MEDIUM — confirms attribute-based graphing patterns)
- HA community thread on reauth/reconfigure flow distinction (MEDIUM)

---
*Feature research for: Home Assistant Pronote custom_component (HACS)*
*Researched: 2026-05-03*
