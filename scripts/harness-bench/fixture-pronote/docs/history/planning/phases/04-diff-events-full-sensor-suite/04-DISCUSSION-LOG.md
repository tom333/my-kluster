# Phase 4: Diff, Events & Full Sensor Suite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 4-Diff, Events & Full Sensor Suite
**Areas discussed:** Sensor state + attribute shape, Calendar cancelled-distinction, Bus event payload wrapping, Heavy-class fixture + probe discipline

---

## Sensor state + attribute shape

### Q1 — EDT sensor state value (TIME-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep count (Phase 3 baseline) | native_value = len(lessons_today). Numeric, state_class=MEASUREMENT, graphs cleanly. | ✓ |
| Next-lesson timestamp | device_class=TIMESTAMP; goes 'unavailable' nights/weekends; loses 'busy today' signal | |
| Both — two sensors | lessons_today (count) + next_lesson (timestamp); cheap to add | |

**User's choice:** Keep count (Phase 3 baseline).
**Notes:** Confirms the Phase 3 contract — TIME-02 is a deliberate add, not a refactor.

### Q2 — EDT attribute payload per lesson (TIME-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Full Lesson.to_dict() | All 8 fields, ~150 bytes/lesson, well under 16 KiB cap | ✓ |
| Lean (time + subject + room + status) | ~80 bytes/lesson; drops teacher and end time | |
| Full + cancelled-aware top-level counts | Adds today_canceled_count / tomorrow_canceled_count; redundant with bus events | |

**User's choice:** Full Lesson.to_dict() with separate lessons_today / lessons_tomorrow keys.
**Notes:** Confirmed via the preview — two keys, full schema.

### Q3 — Grades overall_average source (GRADE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Pronote's Period.overall_average | Read and normalise comma→dot; matches what user sees on phone | ✓ |
| Locally computed weighted mean | Independent of Pronote rounding; may differ from app | |
| Pronote field with computed fallback | Most robust; most code; adds 'average_source' attribute | |

**User's choice:** Pronote field directly.
**Notes:** Probe STEP 6 will lock the exact attribute name before sensor lands.

### Q4 — Attribute window N for grades + notifications (GRADE-02 + NOTIF-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Grades: all current-period; Notifications: 20 most recent | Period boundary natural; 20 covers a week of school comms | ✓ |
| Fixed N=20 for both | Uniform contract; caps memory; cuts ApexCharts history short | |
| Configurable via const, OPT in Phase 6 | Lock defaults, promote later | |

**User's choice:** All-current-period grades + 20 most-recent informations.

### Q5 — Per-grade attribute schema (GRADE-02)

| Option | Description | Selected |
|--------|-------------|----------|
| FEATURES baseline 5 fields | date, subject, grade, out_of, coefficient | |
| + class context (avg/min/max) | Above + class_average, class_min, class_max | |
| + context + comment string | Above + comment (capped 200 chars); richest schema | ✓ |

**User's choice:** Richest schema with comment field capped at 200 chars.
**Notes:** Probe STEP 6 will verify pronotepy 2.14.6 exposes the class context + comment fields; planner downgrades the schema explicitly if any field is absent (no silent absence).

---

## Calendar cancelled-distinction

### Q6 — Cancelled lesson visual marker (CAL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Emoji prefix in summary | summary = '❌ Subject'; renders on mobile widget + cards | ✓ |
| Text marker '[ANNULÉ]' | Max compatible; takes 10 chars of summary | |
| Skip cancelled lessons entirely | Cleanest calendar UI; loses 'what was supposed to happen' visibility | |
| Description-only marker | summary identical to live lesson; worst for glance UX | |

**User's choice:** Emoji prefix '❌' in summary.

### Q7 — Calendar event source method (CAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| async_get_events from coordinator.data | HA cards call this for week/month views; out-of-window returns [] | ✓ |
| Hybrid get_events + event property | Both for small + large card support | |
| event property only | Simpler; cuts week/grid card data | |

**User's choice:** async_get_events filtering coordinator.data.lessons by date range.

### Q8 — Calendar event fields (CAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| location=classroom, description=teacher+status | Concise; location shows as pin in some cards | ✓ |
| Description-only block | location empty; everything in description | |
| All fields populated + stable uid | + uid hash of (date, start, subject) for dedup | |

**User's choice:** location=classroom; description holds teacher + (status line only when canceled).
**Notes:** Final CONTEXT.md D-09 adds the stable uid recipe on top — dedup is non-negotiable for HA calendar card behaviour.

### Q9 — Calendar unique_id kind

| Option | Description | Selected |
|--------|-------------|----------|
| kind='calendar' — single entity per child | Matches HACS naming convention | ✓ |
| kind='timetable' | More descriptive but breaks convention | |
| kind='lessons' | Risks confusion with sensor.pronote_<slug>_lessons_today | |

**User's choice:** kind='calendar'; PLATFORMS adds Platform.CALENDAR.

---

## Bus event payload wrapping

### Q10 — Event payload wrapper fields (EVENT-01..03)

| Option | Description | Selected |
|--------|-------------|----------|
| Full: child_id + child_name + entry_id | Three identification keys; matches REQUIREMENTS wording + research suggestion | ✓ |
| Minimal: child_id only | Cleanest payload; harder template work in automations | |
| All three but rename keys | Internal naming consistency; breaks REQUIREMENTS contract | |

**User's choice:** Full set — child_id (slug, frozen), child_name (display), config_entry_id (technical).

### Q11 — Event firing site

| Option | Description | Selected |
|--------|-------------|----------|
| After snapshot stash, before return; raise raw | Surfaces diff bugs in HA logs; respects 'no silent exceptions' | ✓ |
| Same site, wrapped in best-effort guard | Contradicts the feedback memory — would lose diff bug visibility | |
| Separate async listener fed by coordinator | More moving parts; useful for Phase 5 quiet hours only | |

**User's choice:** After snapshot stash, before return, propagates raw.

### Q12 — Event type name constants

| Option | Description | Selected |
|--------|-------------|----------|
| const.py module-level constants, exact REQUIREMENTS names | EVENT_SCHEDULE_CHANGED / EVENT_NEW_GRADE / EVENT_NEW_INFORMATION | ✓ |
| Same constants, shorter strings | e.g. 'ha_pronote_schedule_changed' (domain-prefixed); breaks REQUIREMENTS | |
| Inline strings in coordinator | Cheap but drift risk between code + tests | |

**User's choice:** const.py constants matching REQUIREMENTS verbatim.

### Q13 — Diff identity keys for grades / notifications

| Option | Description | Selected |
|--------|-------------|----------|
| Strict per Phase 2 D-02 — set-difference on identity tuples | Mirror diff_lessons style; EVENT-04 preserved | ✓ |
| + 'edited grade' detection | New event type not in REQUIREMENTS — scope creep | |
| Information id only (drop date) | Probably correct but date guard is cheap insurance | |

**User's choice:** Strict identity keys: grades=(subject,date,value), informations=(info_id,date), set-difference, EVENT-04 first-poll skip preserved.

---

## Heavy-class fixture + probe discipline

### Q14 — Heavy-class fixture source (TIME-03 / GRADE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic Python generator | Committed _gen + heavy_class.json; account-independent | ✓ |
| Captured from author's real class via probe | Realistic; doesn't hit worst case | |
| Both: synthetic + small captured real | Twice maintenance; marginal coverage gain | |

**User's choice:** Synthetic generator (committed alongside the JSON output).

### Q15 — Heavy-class CI assertion scope

| Option | Description | Selected |
|--------|-------------|----------|
| Every sensor + calendar attrs, hard CI fail | Parametrised test; matches SC#3 verbatim | ✓ |
| Sensors only (skip calendar) | Calendar has no 16 KiB cap; skips regression on async_get_events | |
| Sensors hard-fail, calendar warning-only | Adds complexity; not recommended for v1 | |

**User's choice:** Hard CI fail on every sensor + a separate calendar size/length test.

### Q16 — Probe-first plan discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Probe + capture per sensor plan | Pre-flight checklist; addresses 8-alpha-release pain directly | ✓ |
| Probe once at phase start, freeze findings | Lighter ceremony; could drift if pronotepy upgrades | |
| Probe is optional / informational | Same risk profile as Phase 3 | |

**User's choice:** Per-plan probe with HUMAN-UAT sign-off on captured shape before release.

### Q17 — DeviceInfo.model source

| Option | Description | Selected |
|--------|-------------|----------|
| Probe-first; pick verified field, log fallback | model=None if missing; HA hides the row | ✓ |
| Required field; raise if missing | Strictest contract; risky if pronotepy doesn't guarantee field | |
| Store on entry.data at config-flow time | Requires Phase 3 migration | |

**User's choice:** Probe-first; getattr(client.info, CLASS_LEVEL_ATTR, None) with one-time log if absent.

---

## Claude's Discretion

- **C-01:** Plan-wave decomposition (4 plans across 3 waves: diff bodies + heavy fixture parallel, then sensors + calendar parallel, then coordinator event firing).
- **C-02:** Probe notes location (`tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md`).
- **C-03:** `NewInformation.date` typed as `date` for bus payload; full datetime stays in sensor attribute.
- **C-04:** Sensor naming — kinds `grades` and `notifications`; matches unique_id family pattern.
- **C-05:** Drop `tests/test_diff/test_stubs.py` and replace with positive tests once bodies land.
- **C-06:** Mock strategy — MagicMock for new pronotepy surfaces (matches Phase 3); requests-mock stays in tests/test_api/ only.

## Deferred Ideas

- `pronote_grade_edited` event (out of REQUIREMENTS scope, possible v2)
- Next-lesson timestamp as a separate sensor (Phase 6 if requested)
- Top-level today_canceled_count / tomorrow_canceled_count on EDT sensor (overlaps with bus events)
- Calendar `event` property (only async_get_events in v1)
- Calendar fetcher window growth beyond J−7→J+14 (Phase 6 if requested)
- D-04 typed-error → form-error mapping reintroduction (permanently OFF until user reverses 'no silent exceptions' preference)
- D-12 child_identifier collision suffix using ClientInfo.id (Phase 6 config_flow patch)
- ENT / Keycloak SSO for Pronote NC (Phase 6 reopened)
- Per-period grade sensor or service (Phase 6 via pronote.get_period_grades)
- pronotepy upgrade beyond 2.14.6 (only on real-bug pressure)
- OptionsFlow knobs for NOTIFICATIONS_WINDOW / GRADE_COMMENT_MAX_LEN (Phase 6)
- DIAG-01 redaction extension for new attributes (Phase 7)
- README ApexCharts + automation YAML examples (Phase 7)
