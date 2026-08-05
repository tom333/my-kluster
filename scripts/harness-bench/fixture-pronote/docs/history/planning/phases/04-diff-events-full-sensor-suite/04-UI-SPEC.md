---
phase: 4
slug: diff-events-full-sensor-suite
status: approved
reviewed_at: 2026-05-24T00:00:00Z
shadcn_initialized: false
preset: none
created: 2026-05-24
---

# Phase 4 — UI Design Contract

> Visual and interaction contract for Phase 4: Diff, Events & Full Sensor Suite.
>
> **IMPORTANT — non-standard phase:** This is a Home Assistant custom integration (Python
> backend). There is NO custom Lovelace card, no React/Next.js/Vite stack, and no shadcn
> applicability. The "UI surfaces" are:
>
> 1. **Sensor entity dialog** — HA's stock Entity dialog renders state value + key/value
>    attributes (consumed by user-side ApexCharts / Mushroom YAML cards).
> 2. **Calendar card** — HA's stock Calendar card renders `CalendarEvent` objects produced
>    by the `PronoteCalendar` entity.
> 3. **Device row** — HA Settings > Devices & Services renders `DeviceInfo` fields
>    (`manufacturer`, `model`, `name`).
> 4. **Developer Tools > Events** — Bus event payloads are visible here.
>
> The design contract below formalises the entity-rendering decisions that affect dashboards
> and automation YAML. Standard web design system sections (spacing scale, typography,
> color palette) are adapted to the HA entity contract rather than CSS tokens.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none — HA native rendering only |
| Preset | not applicable |
| Component library | none (HA stock cards: Entity, Calendar, Device) |
| Icon library | MDI (Material Design Icons) — via HA `mdi:` prefix |
| Font | HA host theme default — not controlled by the integration |

**shadcn gate:** Not applicable. Stack is Python / Home Assistant, not React/Next.js/Vite.

---

## Spacing Scale

Not applicable — HA renders entity dialogs and calendar cards using its own internal
CSS. The integration does not ship Lovelace CSS.

**Attribute payload compactness rule (replaces spacing contract):**

| Level | Constraint | Enforcement |
|-------|------------|-------------|
| Sensor state | `len(str(native_value)) <= 255` chars | CI: `test_attribute_size.py` (D-17) |
| Sensor attributes | `len(json.dumps(extra_state_attributes, default=str)) <= 16384` bytes | CI: `test_attribute_size.py` (D-17) |
| Grade comment | Capped at 200 chars (truncated with `…` suffix) | `const.py: GRADE_COMMENT_MAX_LEN = 200` |
| Information excerpt | Capped at 500 chars | `api/fetcher.py: _info_from_raw` (pre-existing) |
| CalendarEvent description | Not stored by recorder (`_entity_component_unrecorded_attributes`) | HA base class guarantee |
| Notifications window | 20 most-recent informations (date desc) | `const.py: NOTIFICATIONS_WINDOW = 20` |

Source: CONTEXT.md D-17, RESEARCH.md §HA Recorder 16 KiB Attribute Cap.

---

## Typography

Not applicable — HA host theme controls all text rendering.

**String rendering decisions (replaces typography contract):**

| Surface | Format | Example |
|---------|--------|---------|
| Cancelled lesson summary in Calendar | `"❌ {subject}"` | `"❌ Mathématiques"` |
| Active lesson summary in Calendar | `"{subject}"` plain | `"Mathématiques"` |
| Calendar event description (cancelled) | `"Professeur: {teacher}\nStatut: annulé"` | `"Professeur: M. Dupont\nStatut: annulé"` |
| Calendar event description (active) | `"Professeur: {teacher}"` | `"Professeur: M. Dupont"` |
| Grades sensor state | Numeric float with `.` decimal separator | `14.5` (not `"14,5"`) |
| Grades sensor — no grades yet | `None` → HA shows `unknown` | Acceptable for "trimester not started" |
| Notifications sensor state | Integer unread count | `3` |
| EDT sensor state | Integer lesson count for today | `6` |
| DeviceInfo.model | Class level string from `ClientInfo.class_name` | `"3ème A"` or `None` (hidden row) |
| Period name attribute | `period_name: str` | `"Trimestre 2"` |

Source: CONTEXT.md D-01 through D-09, RESEARCH.md §pronotepy 2.14.6 Runtime Surface.

---

## Color

Not applicable — HA host theme controls all color rendering.

**Visual distinction rules (replaces color contract):**

| Visual Signal | Mechanism | Reserved For |
|---------------|-----------|--------------|
| Cancelled lesson distinction | `❌` emoji prefix in `CalendarEvent.summary` | Cancelled lessons in Calendar card (CAL-02) |
| Sensor icon — EDT | `mdi:school` | `PronoteLessonsTodaySensor` |
| Sensor icon — Grades | `mdi:school` | `PronoteGradesSensor` |
| Sensor icon — Notifications | `mdi:bell` | `PronoteNotificationsSensor` |
| Calendar entity icon | HA default calendar icon | `PronoteCalendar` (inherits from `CalendarEntity`) |

**`❌` vs `⚠️` decision:** `❌` chosen (CONTEXT.md specifics) because it renders on
mobile widgets, terminal HA cards, and the iOS/Android HA app without special font
support. `⚠️` is the fallback only if `❌` proves problematic in a specific HA card
(user-side decision, not integration decision).

Source: CONTEXT.md D-09, RESEARCH.md §State of the Art.

---

## Copywriting Contract

All translation keys below are added to `custom_components/ha_pronote/strings.json`
and must appear in both `translations/fr.json` and `translations/en.json` (Phase 7
deliverable; Phase 4 ships the `strings.json` keys only).

### Entity Names (strings.json keys)

| Translation Key | English Display | French Display |
|-----------------|----------------|----------------|
| `entity.sensor.lessons_today.name` | "Today's Schedule" | "Emploi du temps" |
| `entity.sensor.grades.name` | "Grades" | "Notes" |
| `entity.sensor.notifications.name` | "Notifications" | "Informations" |
| `entity.calendar.calendar.name` | "Timetable" | "Calendrier scolaire" |

### Bus Event Schemas (Developer Tools > Events copy)

These payloads appear verbatim in HA Developer Tools > Events. The field names are
user-visible in automation YAML trigger conditions.

**`pronote_schedule_changed`**

```yaml
child_id: "alice_martin"          # frozen slug, never changes
child_name: "Alice Martin"        # Pronote display name
config_entry_id: "abc123def456"   # unique per ConfigEntry
change_type: "canceled"           # canceled | modified | teacher | room
day: "today"                      # today | tomorrow
lesson_before: {…}                # Lesson.to_dict() snapshot before change
lesson_after: {…}                 # Lesson.to_dict() snapshot after change (or null)
```

**`pronote_new_grade`**

```yaml
child_id: "alice_martin"
child_name: "Alice Martin"
config_entry_id: "abc123def456"
subject: "Mathématiques"
grade: 14.5                       # float, comma-normalised
out_of: 20.0
coefficient: 2.0
date: "2026-05-23"               # ISO date string
```

**`pronote_new_information`**

```yaml
child_id: "alice_martin"
child_name: "Alice Martin"
config_entry_id: "abc123def456"
info_id: "info-abc-123"
title: "Réunion parents-professeurs"
sender: "Direction"
date: "2026-05-23"               # ISO date string (date, not datetime)
excerpt: "La réunion aura lieu…" # ≤500 chars
```

Source: CONTEXT.md D-11 through D-13, REQUIREMENTS.md EVENT-01..03.

### Sensor Attribute Schemas (Entity dialog copy)

**`PronoteLessonsTodaySensor.extra_state_attributes`**

```yaml
lessons_today:
  - date: "2026-05-26"
    start: "2026-05-26T07:30:00+11:00"
    end: "2026-05-26T08:25:00+11:00"
    subject: "Mathématiques"
    teacher: "M. Dupont"
    classroom: "B204"
    canceled: false
    status: null
lessons_tomorrow:
  - {…}
```

**`PronoteGradesSensor.extra_state_attributes`**

```yaml
period_name: "Trimestre 2"
grades:
  - date: "2026-05-23"
    subject: "Mathématiques"
    grade: 14.5
    out_of: 20.0
    coefficient: 2.0
    class_average: 12.3
    class_min: 6.0
    class_max: 18.5
    comment: ""        # ≤200 chars; empty string when no comment
```

**`PronoteNotificationsSensor.extra_state_attributes`**

```yaml
unread_count: 2
informations:
  - info_id: "info-abc-123"
    title: "Réunion parents-professeurs"
    sender: "Direction"
    date: "2026-05-23T08:00:00+11:00"
    excerpt: "La réunion aura lieu…"   # ≤500 chars
    read: false
```

Source: CONTEXT.md D-02, D-04, D-05.

### Empty States

| Surface | Empty State Behaviour |
|---------|----------------------|
| EDT sensor — no lessons today | `native_value = 0` → HA shows `0` (not `unknown`) |
| Grades sensor — no grades yet | `native_value = None` → HA shows `unknown` (acceptable; means trimester not started) |
| Notifications sensor — no informations | `native_value = 0`; `unread_count = 0`; `informations = []` |
| Calendar — no lessons in range | `async_get_events` returns `[]`; HA calendar card shows empty |
| Calendar `event` property — no future lesson | Returns `None` → HA shows `STATE_OFF` (calendar is "off" / no current event) |
| DeviceInfo.model — class level unavailable | `model = None` → HA hides the "Model" row in device panel |

Source: CONTEXT.md D-01, D-03, D-07..D-09, D-19; RESEARCH.md Pitfall 5.

### Error States

| Error Condition | Mechanism | User-Visible Effect |
|----------------|-----------|---------------------|
| `Period.overall_average` returns `"-1"` (no grades sentinel) | `native_value = None` | HA shows `unknown` for grades sensor |
| `Period.overall_average` is empty string | `native_value = None` | HA shows `unknown` for grades sensor |
| `overall_average` string not parseable as float | `try/except ValueError → None` | HA shows `unknown`; no HA log error |
| Coordinator fetch fails | HA coordinator marks all entities `unavailable` | Existing Phase 3 behaviour; no Phase 4 change |
| `CalendarEvent` with `start == end` (degenerate Pronote data) | Guard: `end = start + timedelta(hours=1)` | Event still appears in calendar with 1h duration |

Source: RESEARCH.md Pitfall 5, Pitfall 6, CONTEXT.md D-03.

### Destructive Actions

None in Phase 4. The integration is read-only (CLAUDE.md constraint: "Lecture seule").
No confirmation dialogs, no delete flows.

---

## Device Info Contract (ENT-01)

The HA Device row in Settings > Devices & Services renders these fields:

| DeviceInfo Field | Value | Source |
|-----------------|-------|--------|
| `identifiers` | `{(DOMAIN, child_identifier)}` | Phase 3 D-13 |
| `name` | `entry.data["child_name"]` | Phase 3 D-17 |
| `manufacturer` | `"Pronote"` | REQUIREMENTS ENT-01 (locked) |
| `model` | `getattr(client.info, "class_name", None) or None` | CONTEXT.md D-19 |

`model` fallback: if `ClientInfo.class_name` returns `""` (empty string, pronotepy 2.14.6
behaviour when field is absent), `or None` converts it to `None` and HA hides the row.
This is an explicit, visible default — not a silencing catch (per "no silent exceptions"
project feedback memory).

Source: CONTEXT.md D-19, RESEARCH.md §ClientInfo.

---

## Unique ID Contract (ENT-02 extension)

Phase 4 adds three new entity kinds to the frozen `unique_id` format
`f"pronote_{child_identifier}_{kind}"`:

| Kind | unique_id Example | Platform |
|------|-------------------|----------|
| `lessons_today` | `pronote_alice_martin_lessons_today` | SENSOR (Phase 3) |
| `grades` | `pronote_alice_martin_grades` | SENSOR (Phase 4) |
| `notifications` | `pronote_alice_martin_notifications` | SENSOR (Phase 4) |
| `calendar` | `pronote_alice_martin_calendar` | CALENDAR (Phase 4) |

The `child_identifier` is the frozen slug from Phase 3 config flow. Never altered by
nickname (Phase 6 OPT-03 deferred).

Source: CONTEXT.md D-07, C-04, Phase 3 D-13.

---

## Calendar Event UID Contract (CAL-02 stability)

`CalendarEvent.uid` must be stable across polls so HA calendar cards that dedup by uid
do not double-render the same lesson.

Formula: `f"pronote_{child_identifier}_{lesson.date}_{lesson.start.isoformat()}_{slugify(subject)}"`

| Component | Stability Guarantee |
|-----------|---------------------|
| `child_identifier` | Frozen slug, never changes |
| `lesson.date` | ISO date string `YYYY-MM-DD` |
| `lesson.start.isoformat()` | tz-aware datetime, deterministic for same lesson |
| `slugify(subject)` | `homeassistant.util.slugify.slugify` is deterministic for same input string |

`slugify` import: use `homeassistant.util.slugify.slugify` (not `python_slugify` directly)
for entity-id consistency within HA.

Source: CONTEXT.md D-09, RESEARCH.md Pitfall 7, Assumption A5.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable — no shadcn in this project |
| third-party | none | not applicable |

No frontend component registries. No third-party blocks. Not applicable.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

## Pre-Population Sources

| Source | Decisions Used |
|--------|---------------|
| CONTEXT.md | 19 (D-01 through D-19, C-04) |
| RESEARCH.md | 7 (pronotepy Grade/Period/ClientInfo surface, CalendarEntity API, Recorder cap, bus constraints, pitfalls) |
| REQUIREMENTS.md | 14 (TIME-02, TIME-03, GRADE-01..03, NOTIF-01..02, CAL-01..02, EVENT-01..04, ENT-01) |
| components.json | no (not applicable — Python project) |
| User input | 0 (--auto mode; no questions asked) |
