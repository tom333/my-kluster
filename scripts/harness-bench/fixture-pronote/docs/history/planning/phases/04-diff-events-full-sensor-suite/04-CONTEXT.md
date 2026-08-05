# Phase 4: Diff, Events & Full Sensor Suite - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

The integration starts paying off: every poll diff produces typed bus events
(`pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_information`),
the full sensor suite ships (EDT + J/J+1 attrs, Grades + ApexCharts attrs,
Notifications + recent items), a Calendar entity exposes J−7 → J+14 with
cancelled lessons visually distinct, and a CI heavy-class fixture proves
the 16 KiB attribute discipline holds.

**Phase 4 ships:**

1. **Bus event firing in `coordinator._async_update_data`** — after each
   successful snapshot, walk the (previous, new) diff for the three event
   families, wrap each payload with `child_id` / `child_name` /
   `config_entry_id`, fire via `hass.bus.async_fire(EVENT_*, payload)`.
   First-poll skip (`previous is None`) already in `diff_lessons`; the
   `diff_grades` / `diff_notifications` stubs (Phase 2 NotImplementedError)
   get their bodies filled with the strict identity-key contract Phase 2
   pre-locked.
2. **TIME-02 J/J+1 attribute payload on `PronoteLessonsTodaySensor`** —
   `extra_state_attributes = {"lessons_today": [Lesson.to_dict(), …],
   "lessons_tomorrow": [Lesson.to_dict(), …]}` with full Lesson schema
   (date, start, end, subject, teacher, classroom, canceled, status). State
   stays count (Phase 3 D-14 preserved).
3. **`PronoteGradesSensor`** — state = `float(Period.overall_average)` with
   comma→dot normalisation, `state_class=MEASUREMENT`. Attributes:
   `period_name` + `grades: [{date, subject, grade, out_of, coefficient,
   class_average, class_min, class_max, comment(≤200 chars)}, …]` covering
   all current-period grades.
4. **`PronoteNotificationsSensor`** — state = `unread_count` (count of
   `info.read == False` in `Snapshot.information`). Attributes:
   `informations: [{info_id, title, sender, date, excerpt, read}, …]`
   capped at 20 most-recent by date desc.
5. **`PronoteCalendar` (new platform)** — `CalendarEntity` per child via
   `async_get_events(start, end)` filtering `coordinator.data.lessons` by
   date range. `summary = "❌ {subject}"` for canceled lessons, plain
   `subject` otherwise. `location = classroom`. `description =
   "Professeur: {teacher}\nStatut: {status}"` (Statut line only when
   canceled). `PLATFORMS = (Platform.SENSOR, Platform.CALENDAR)`.
6. **`DeviceInfo.model = <class level>`** added to `PronoteEntity` —
   sourced from a probe-verified `pronotepy.ClientInfo` attribute (likely
   `class_name`; locked at probe time). Missing-field fallback = `None`
   (HA hides the row). One-time `_LOGGER.info` if missing.
7. **`const.py` event-type constants** — `EVENT_SCHEDULE_CHANGED`,
   `EVENT_NEW_GRADE`, `EVENT_NEW_INFORMATION` (exact REQUIREMENTS strings)
   importable by coordinator + tests.
8. **Heavy-class CI gate** — `tests/fixtures/synthetic/heavy_class.json`
   built by a committed Python generator (`_gen_heavy_class.py`),
   `tests/test_attribute_size.py` parametrises over every sensor + asserts
   `len(state) ≤ 255` AND `len(json.dumps(extra_state_attributes)) ≤ 16384`
   AND `state not in (None, 'unknown')`.
9. **Probe-first plan discipline** — every Phase 4 plan that calls a new
   pronotepy method (`client.lessons`, `current_period.grades`,
   `information_and_surveys`, `client.info`) has a pre-flight checklist:
   (a) run `scripts/probe_config_flow.py` against author's instance,
   (b) capture the printed shape into a fixture sibling notes file,
   (c) verify mocks match the captured shape, (d) HUMAN-UAT sign-off on
   the captured shape before the release.

**In scope (Phase 4 only):**

- `custom_components/ha_pronote/coordinator.py` — EXTEND `_async_update_data`
  with `_fire_diff_events(previous, new)`; no other change.
- `custom_components/ha_pronote/sensor.py` — EXTEND with
  `PronoteGradesSensor`, `PronoteNotificationsSensor`; ADD TIME-02 attrs to
  `PronoteLessonsTodaySensor`.
- `custom_components/ha_pronote/calendar.py` — NEW (`PronoteCalendar`
  subclass of `PronoteEntity` + `CalendarEntity`).
- `custom_components/ha_pronote/entity.py` — EXTEND `DeviceInfo` with
  `model=<class level>` (probe-verified field).
- `custom_components/ha_pronote/diff/grades.py` — FILL body
  (NotImplementedError → strict identity diff).
- `custom_components/ha_pronote/diff/notifications.py` — FILL body
  (NotImplementedError → strict identity diff).
- `custom_components/ha_pronote/const.py` — APPEND `EVENT_SCHEDULE_CHANGED`,
  `EVENT_NEW_GRADE`, `EVENT_NEW_INFORMATION`, `PLATFORMS += (CALENDAR,)`,
  optionally `CLASS_LEVEL_ATTR` (probe-locked name), `NOTIFICATIONS_WINDOW = 20`,
  `GRADE_COMMENT_MAX_LEN = 200`.
- `custom_components/ha_pronote/strings.json` — APPEND translation keys for
  `grades`, `notifications`, `calendar` entity names.
- `custom_components/ha_pronote/__init__.py` — EXTEND `PLATFORMS` constant
  (sourced from `const.py`) so `async_forward_entry_setups` includes CALENDAR.
- `tests/fixtures/synthetic/_gen_heavy_class.py` — NEW (generator script,
  committed).
- `tests/fixtures/synthetic/heavy_class.json` — NEW (committed output).
- `tests/test_diff/test_grades.py` — NEW (test_stubs.py shrinks).
- `tests/test_diff/test_notifications.py` — NEW.
- `tests/test_coordinator.py` — EXTEND with `test_fires_*_events_on_diff`,
  `test_fires_no_events_on_first_poll` (EVENT-04 regression).
- `tests/test_sensor.py` — EXTEND with grades + notifs + TIME-02 attrs tests.
- `tests/test_calendar.py` — NEW.
- `tests/test_attribute_size.py` — NEW (the 16 KiB / 255-char CI gate).

**Out of scope (deferred to later phases):**

- Adaptive 17h–20h polling, weekend / vacation suspension, quiet hours,
  jitter, IP-ban circuit breaker — Phase 5 (COORD-04..09, DIST-06).
- Reauth / reconfigure / Options Flow / multi-child reconfigure UX —
  Phase 6 (AUTH-03/05/06, OPT-01..04).
- Reintroduce D-12 child_identifier collision suffix using `ClientInfo.id`
  — Phase 6 (config_flow patch).
- Reintroduce D-04 typed-error → form-error mapping in config_flow —
  permanently OFF until the user reverses the "no silent exceptions"
  preference. NOT a Phase 4 item.
- ENT / Keycloak SSO support for Pronote NC users — Phase 6 (reopened
  per Phase 3 live UAT finding #6).
- Diagnostics + repair issues (DIAG-01..03) + translations beyond
  strings.json — Phase 7.
- Daily cron CI against pronotepy@main — Phase 7 (DIST-04).
- README install / configuration docs incl. example automations — Phase 7
  (DIST-07). Phase 4 freezes the event payload schema the README will
  document, but the README itself is Phase 7.
- `pronote_grade_edited` event for "edited grade detection" — explicitly
  rejected (out of REQUIREMENTS scope).

</domain>

<decisions>
## Implementation Decisions

### Sensor state + attribute shape (Area 1)

- **D-01:** EDT sensor state stays `count` (Phase 3 D-14 preserved).
  `PronoteLessonsTodaySensor.native_value = len(coordinator.data.lessons_today)`.
  No second `next_lesson` sensor in Phase 4 — TIME-01 explicitly allows
  either count or timestamp; count graphs cleanly in long-term statistics
  and matches the existing Phase 3 contract.
- **D-02:** EDT TIME-02 attribute layout = two separate keys
  `lessons_today` + `lessons_tomorrow`, each a list of `Lesson.to_dict()`
  output (`models.Lesson` already ships this method — zero new serialisation
  code). Per-lesson fields: `date, start, end, subject, teacher, classroom,
  canceled, status` (all 8). ~150 bytes/lesson × 50 lessons ≈ 7.5 KB on the
  heavy-class fixture — comfortably under the 16 KiB cap (D-10).
- **D-03:** Grades sensor state = `float(Period.overall_average)` after
  comma→dot normalisation (`str.replace(",", ".")`). `state_class =
  SensorStateClass.MEASUREMENT`. No `device_class`. No
  `native_unit_of_measurement` (no good fit; HA shows the raw float).
  Probe STEP 6 will lock the exact pronotepy attribute name — `current_period.overall_average`
  is the documented pronotepy 2.14.6 surface but the field could be `.average`
  on certain Pronote builds; planner pins after probe verification.
- **D-04:** Grades sensor `extra_state_attributes`:
  - `period_name: str` — current Period's display name (e.g. "Trimestre 2")
  - `grades: list[dict]` — **all grades for the current period**, each:
    - `date: str` (ISO date)
    - `subject: str`
    - `grade: float` (comma→dot normalised; raw `Grade.value` retained in
      `diff/events.py:NewGrade` for the bus payload)
    - `out_of: float`
    - `coefficient: float`
    - `class_average: float | None`
    - `class_min: float | None`
    - `class_max: float | None`
    - `comment: str` (capped at 200 chars; longer comments truncated with
      `…` suffix)
  - Probe STEP 6 will confirm pronotepy 2.14.6 actually exposes
    `class_average / class_min / class_max / comment` on Grade objects
    — if any field is missing in practice, planner downgrades the schema
    and logs the change (no silent absence).
- **D-05:** Notifications sensor state = `unread_count` =
  `sum(1 for i in snapshot.information if not i.read)`. Attributes:
  - `unread_count: int` (mirrors state for template-card convenience)
  - `informations: list[dict]` — **20 most recent** by date desc, each:
    - `info_id: str`, `title: str`, `sender: str`, `date: str` (ISO),
      `excerpt: str` (already capped at 500 chars in `_info_from_raw`),
      `read: bool`
- **D-06:** `Snapshot.lessons_today` / `.lessons_tomorrow` slice properties
  already filter by date — sensor reads them directly. Sorting: lessons by
  `start` ascending (assumed pronotepy default; assert in test). Grades by
  `date` descending (newest first). Informations by `date` descending.

### Calendar entity (Area 2)

- **D-07:** `PronoteCalendar(PronoteEntity, CalendarEntity)` — new file
  `custom_components/ha_pronote/calendar.py`. One calendar per child,
  `unique_id = f"pronote_{child_identifier}_calendar"` (D-13 family extension).
  `translation_key = "calendar"` — strings.json gets a new entry.
- **D-08:** `async_get_events(hass, start, end)` overrides the
  CalendarEntity contract; returns list of `CalendarEvent` filtered from
  `self.coordinator.data.lessons` by `start.date() ≤ lesson.date ≤ end.date()`.
  No `event` property override in v1 — full week/month card use cases are
  the priority. If HA asks for a range outside J−7→J+14 the result is just
  `[]` (the fetcher window is hardcoded; Phase 6 could grow it).
- **D-09:** `CalendarEvent` fields per lesson:
  - `summary = f"❌ {subject}"` if `lesson.canceled`, else `subject` plain
  - `start = lesson.start`, `end = lesson.end` (tz-aware already per
    Phase 2 D-23)
  - `location = lesson.classroom`
  - `description = "Professeur: {teacher}\nStatut: annulé"` when canceled;
    `"Professeur: {teacher}"` otherwise. The `status` raw string is NOT
    surfaced (it's free-form drift noise per `diff/lessons.py` docstring).
  - `uid = f"pronote_{child_identifier}_{lesson.date}_{lesson.start.isoformat()}_{slugify(subject)}"` —
    stable across polls so HA cards that dedup by uid don't double-render.
- **D-10:** `PLATFORMS = (Platform.SENSOR, Platform.CALENDAR)` in `const.py`.
  `__init__.py:async_setup_entry` already iterates the const via
  `async_forward_entry_setups(entry, PLATFORMS)` — no edit needed there
  beyond updating the const.

### Bus event payload wrapping (Area 3)

- **D-11:** Coordinator wraps every event payload with three top-level
  identification keys:
  - `child_id: str` — the frozen slug (`entry.runtime_data.child_identifier`).
    Matches REQUIREMENTS EVENT-01 wording verbatim.
  - `child_name: str` — display name from `entry.data["child_name"]`. May
    change if Pronote-side name is edited; automations that template
    notification bodies use this.
  - `config_entry_id: str` — `self.config_entry.entry_id`. Multi-child
    installs filter on this in automation YAML.
  These three are PREPENDED to the per-change `to_payload()` dict before
  `hass.bus.async_fire`. Existing `LessonChange.to_payload()` /
  `NewGrade.to_payload()` / `NewInformation.to_payload()` shapes are
  preserved verbatim (no rename, no field drop).
- **D-12:** Event firing site = `_async_update_data`, ordering:
  ```python
  snapshot = await fetch  # existing
  previous = self._previous_snapshot  # NEW: capture BEFORE overwrite
  self._previous_snapshot = snapshot  # existing
  try:
      await self._capture_session()  # existing, best-effort
  except Exception:
      _LOGGER.warning(...)
  self._fire_diff_events(previous, snapshot)  # NEW — propagates RAW
  return snapshot
  ```
  `_fire_diff_events` does NOT have a typed try/except (per the "no silent
  exceptions" feedback memory — diff bugs surface in HA logs immediately).
  A genuine `hass.bus.async_fire` crash (extremely rare) would fail the
  poll; HA's coordinator retries on the next cycle.
- **D-13:** Event-type constants in `const.py`:
  ```python
  EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"
  EVENT_NEW_GRADE: Final = "pronote_new_grade"
  EVENT_NEW_INFORMATION: Final = "pronote_new_information"
  ```
  Verbatim REQUIREMENTS EVENT-01..03 strings. Imported by `coordinator.py`
  and by tests; never inlined.
- **D-14:** `diff_grades` / `diff_notifications` body recipe (Phase 2 D-02
  contract activation):
  - `diff_grades(previous, new)`:
    ```python
    if previous is None: return []
    prev_keys = {(g.subject, g.date, g.value) for g in previous.grades}
    return [
        NewGrade(subject=g.subject, value=g.value, out_of=g.out_of,
                 coefficient=g.coefficient, date=g.date)
        for g in new.grades
        if (g.subject, g.date, g.value) not in prev_keys
    ]
    ```
  - `diff_notifications(previous, new)`:
    ```python
    if previous is None: return []
    prev_keys = {(i.info_id, i.date) for i in previous.information}
    return [
        NewInformation(info_id=i.info_id, title=i.title, sender=i.sender,
                       date=i.date, excerpt=i.excerpt)
        for i in new.information
        if (i.info_id, i.date) not in prev_keys
    ]
    ```
  `NewGrade.date` and `NewInformation.date` are `date` objects in the
  diff/events.py dataclass; the dataclass's `to_payload()` already calls
  `.isoformat()`. Note: `Information.date` in `api/models.py` is a
  `datetime` (tz-aware); `NewInformation.date` in `diff/events.py` is a
  `date` — planner needs to confirm the type contract; either widen
  `NewInformation.date` to `datetime` OR call `.date()` at construction.
- **D-15:** EVENT-04 (no events on first poll after restart) is enforced
  structurally in two places: (a) every diff function returns `[]` when
  `previous is None`, (b) `_fire_diff_events(None, snapshot)` is therefore
  a no-op. Phase 3's coordinator already sets `_previous_snapshot = None`
  in `__init__`; after the first successful poll it equals the just-fetched
  snapshot, so the second poll has a non-None previous. Test covers both:
  first call to `_fire_diff_events` with `(None, snapshot)` fires zero
  events; second call with `(snapshot1, snapshot2)` fires the diff.

### Heavy-class fixture + probe discipline (Area 4)

- **D-16:** Heavy-class fixture source = **synthetic Python generator**.
  `tests/fixtures/synthetic/_gen_heavy_class.py` is committed; it builds
  `tests/fixtures/synthetic/heavy_class.json` (also committed for CI
  reproducibility — no runtime generation in test). Generator parameters:
  ~50 lessons/week × 3 weeks (covers J−7→J+14) with realistic French
  subject names (Mathématiques, Histoire-Géographie, EPS, …), accented
  teacher names, classroom codes (B204, S102, GYM); 100 grades distributed
  across 4–6 subjects; ~30 information entries with multi-paragraph
  excerpts to stress the 500-char truncation.
- **D-17:** CI assertion shape — `tests/test_attribute_size.py`
  parametrises over `[PronoteLessonsTodaySensor, PronoteGradesSensor,
  PronoteNotificationsSensor]`, instantiates each against a coordinator
  whose data = `Snapshot.from_dict(heavy_class_json)`, asserts:
  ```python
  assert len(str(sensor.native_value)) <= 255
  assert len(json.dumps(sensor.extra_state_attributes, default=str)) <= 16384
  assert sensor.state not in (None, "unknown", "unavailable")
  ```
  Calendar entity covered by a separate test that asserts
  `len(await calendar.async_get_events(hass, ...))` ≥ heavy-load lesson
  count AND no `CalendarEvent.summary > 255` AND each `description ≤ 1024`.
  HARD CI fail on any breach.
- **D-18:** Probe-first plan discipline — every Phase 4 plan that uses a
  new pronotepy surface (steps below) carries a pre-flight checklist in
  its task list, blocking code-review until checked:
  1. Run `uv run --no-project --python 3.13 --with pronotepy --with python-slugify --with requests-mock --with autoslot python scripts/probe_config_flow.py`
     against author's instance.
  2. Capture relevant STEP output into a fixture sibling notes file
     (suggested: `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md`,
     appended with sections per STEP and per pronotepy version).
  3. Verify all mocks in the plan reflect the captured shape (no invented
     attrs — Phase 3's `ClientInfo.identifier` ghost taught us).
  4. HUMAN-UAT sign-off on the captured shape before release.
  pronotepy methods covered: `client.lessons(date_from, date_to)` (STEP 5),
  `client.current_period.grades` + `current_period.overall_average` (STEP 6),
  `client.information_and_surveys()` (STEP 7), `client.info` shape (STEP 11),
  `client.periods` for multi-period awareness (STEP 9 — informational only
  in Phase 4; Phase 6 may add a per-period sensor service).
- **D-19:** DeviceInfo.model source — probe STEP 11 prints
  `pronotepy.ClientInfo` attribute distribution. The exact attribute
  carrying class level (`class_name`, `classe`, `niveau`, …) gets pinned
  in `const.py:CLASS_LEVEL_ATTR` after the probe runs. `entity.py`
  modification:
  ```python
  class_label = getattr(client.info, CLASS_LEVEL_ATTR, None)
  return DeviceInfo(
      identifiers={(DOMAIN, child_identifier)},
      name=entry.data["child_name"],
      manufacturer="Pronote",
      model=class_label or None,  # None hides the row in HA UI
  )
  ```
  If `CLASS_LEVEL_ATTR` lookup misses on a given install, log once at
  setup (`_LOGGER.info` not warning — class level missing is benign) and
  proceed with `model=None`. Per the "no silent exceptions" preference,
  this `getattr(..., None)` is a deliberate, visible default — NOT a
  swallowing catch.

### Claude's Discretion

The planner has flexibility on these; recommended defaults noted, deviate
only with a stronger argument:

- **C-01:** Plan-wave decomposition — RECOMMEND 4 plans across 3 waves:
  - **Wave 1 (parallel):**
    - Plan 04-01 — `diff/grades.py` + `diff/notifications.py` bodies +
      `tests/test_diff/test_grades.py` + `tests/test_diff/test_notifications.py`
      + `tests/test_diff/test_stubs.py` shrinks. HA-free, fastest to land.
    - Plan 04-02 — synthetic heavy-class fixture generator +
      `tests/fixtures/synthetic/heavy_class.json` commit + first probe run
      capturing pronotepy shape into `PHASE-4-PROBE-NOTES.md`. Unblocks
      everything else.
  - **Wave 2 (parallel, blocked on Wave 1):**
    - Plan 04-03 — `entity.py` DeviceInfo.model + `sensor.py` (extend
      lessons sensor TIME-02 attrs, add Grades + Notifications) +
      `tests/test_sensor.py` extensions + `tests/test_attribute_size.py`.
    - Plan 04-04 — `calendar.py` + `tests/test_calendar.py` +
      `const.py` PLATFORMS += CALENDAR + `strings.json` calendar key.
  - **Wave 3 (blocked on Wave 1 + 2):**
    - Plan 04-05 — Bus event firing in coordinator
      (`_fire_diff_events`, const event constants, payload wrappers) +
      `tests/test_coordinator.py` extensions for fire-on-diff + EVENT-04
      regression + multi-event-per-poll ordering.
  Planner may collapse 04-03 / 04-04 / 04-05 if dependency analysis allows;
  bus events conceptually depend on the sensors existing for the
  integration test snapshot, but technically the coordinator can fire
  events into the void.
- **C-02:** Where the probe notes live — RECOMMEND
  `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` (sibling to Phase 2's
  `SPIKE-FINDINGS-bain3-311.md`). One section per probe STEP, one section
  per pronotepy version. Append-only; never overwritten.
- **C-03:** `NewInformation.date` type — pick `date` (call `.date()` on
  construction) for the bus payload because EVENT-03 spec says "date" not
  "datetime" and ApexCharts grade evolution wants `date` granularity. The
  full datetime stays available in the sensor attribute (`info.date` is
  `datetime` in `api/models.py:Information`).
- **C-04:** Sensor naming in HA (entity_id derived from `translation_key`)
  — `grades` and `notifications` are the recommended kinds.
  `unique_id = f"pronote_{child_identifier}_grades"` and
  `_notifications`. Phase 6's OPT-03 nickname leaves these untouched.
- **C-05:** Whether to drop `tests/test_diff/test_stubs.py` (which asserts
  the Phase 2 NotImplementedError stubs) on Phase 4 — RECOMMEND yes, replace
  with positive tests in `test_grades.py` / `test_notifications.py`. Phase 2
  shipped that file as a contract anchor; once the bodies land, asserting
  NotImplementedError is anti-test.
- **C-06:** Mock strategy for the new sensor + calendar HA-side tests —
  RECOMMEND `MagicMock` for `pronotepy.Client.current_period`,
  `client.information_and_surveys`, `client.info` (same approach as
  Phase 3's `mock_pronote_client` fixture). Real `requests-mock` stays
  reserved for `tests/test_api/` only. New PHACC fixtures probably
  needed: `heavy_class_snapshot` (the Snapshot built from
  `heavy_class.json`) and `mock_pronote_client_with_grades` (matching
  the probe-captured shape).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Core Value (alerte EDT J/J+1 fiable),
  ApexCharts attribute discipline, polling politesse, 16 KiB recorder
  cap rationale, "From scratch / not fork" stance, "Pronote direct only
  in v1 (no ENT)" — every Phase 4 sensor decision rests on these.
- `.planning/REQUIREMENTS.md` — Phase 4 owns 14 requirements: TIME-02,
  TIME-03, GRADE-01, GRADE-02, GRADE-03, NOTIF-01, NOTIF-02, CAL-01,
  CAL-02, EVENT-01, EVENT-02, EVENT-03, EVENT-04, ENT-01. Cross-cutting
  trackers: TIME-01 / TIME-04 (Phase 3 / Phase 2 ownership; Phase 4
  must respect the state-as-count contract and the tz-aware datetime
  invariant); EVENT-05 (Phase 2 identity-vs-content key — Phase 4's
  diff_grades / diff_notifications mirror the recipe).
- `.planning/ROADMAP.md` §"Phase 4: Diff, Events & Full Sensor Suite" —
  Goal statement, 4 success criteria (SC#1 typed event with payload,
  SC#2 Device + model + calendar with cancelled distinct, SC#3 heavy-class
  ≤255/≤16 KiB invariant, SC#4 new_grade + new_information events +
  comma-decimal normalisation), `requirements` field, depends-on Phase 3.
- `CLAUDE.md` — Tech stack (Python 3.14.2, HA 2026.4+, pronotepy 2.14.6
  EXACT pin), "What NOT to Use" table (banned APIs still apply:
  no async_timeout, no pytz, no direct requests, no pronotepy.ent.*,
  no monkey-patching, no hardcoded URL — every one applies in Phase 4).
- `.planning/phases/03-coordinator-first-sensor/03-HUMAN-UAT.md` —
  "Live UAT findings (carried forward to Phase 4 / scope notes)" section
  is mandatory reading. Documents pronotepy.set_child accepting Child
  or str (not int), ClientInfo has `.id` not `.identifier`, token_login
  needs `**session` only, ENT Keycloak for Pronote NC. Lessons #1–#4
  apply directly to Phase 4 probe captures.
- `/home/moi/.claude/projects/-data-projets-perso-pronote/memory/feedback_no_silent_exceptions.md` —
  Project-level feedback: NO typed catches that swallow + remap to user-friendly
  labels. Applies to `_fire_diff_events`, `diff_grades`/`diff_notifications`
  bodies, DeviceInfo.model fallback, attribute-size truncation. Default to
  raising / explicit None, never silently absorbing.

### Prior phase context
- `.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md` — Phase 2
  decisions still binding:
  - **D-02:** diff_grades / diff_notifications type contracts frozen;
    bodies land in Phase 4 (this phase activates the contract).
  - **D-06..D-09:** diff_lessons identity-vs-content key contract,
    change_type taxonomy frozen (canceled / modified / teacher / room),
    first-poll skip invariant — Phase 4 mirrors the recipe for grades
    and notifications.
  - **D-15..D-18:** `api/fetcher.fetch_all` signature LOCKED; Phase 4
    coordinator doesn't change it. `today` and `school_tz` injected.
  - **D-19, D-20:** Zero `homeassistant.*` imports in `api/` or `diff/` —
    `tests/test_no_ha_imports.py` enforces. Phase 4 keeps the AST guard
    green (new diff bodies are HA-free; new sensor/calendar/entity code
    is HA-side).
  - **D-21:** `child_index_or_identifier` parameter contract — Phase 4
    coordinator doesn't touch.
  - **D-22:** Typed error hierarchy in `api/errors.py` — diff bodies do
    NOT raise typed errors (pure data manipulation, KeyError / TypeError
    propagate raw if pronotepy ships a regression).
  - **D-23, D-24:** All datetimes tz-aware; back-refs already stripped —
    Phase 4 sensors / calendar consume `Snapshot` directly.
- `.planning/phases/03-coordinator-first-sensor/03-CONTEXT.md` — Phase 3
  decisions still binding:
  - **D-06, D-07, D-09:** session token persistence — Phase 4 doesn't
    touch the token flow; coordinator additions go after `_capture_session`.
  - **D-13:** `unique_id` format frozen as `f"pronote_{child_identifier}_{kind}"`
    — Phase 4 adds three new `kind` values: `grades`, `notifications`,
    `calendar`.
  - **D-14:** Lessons sensor state stays count; Phase 4 ADDS attrs.
    Phase 3 said this is a deliberate add, not a refactor.
  - **D-15:** PronoteEntity base — Phase 4's GradesSensor / NotificationsSensor /
    PronoteCalendar subclass it.
  - **D-17:** DeviceInfo shape — Phase 4 ADDS `model=<class level>` to
    the existing identifiers + name + manufacturer keys. ROADMAP SC#2
    explicitly defers `model` to Phase 4.
  - **D-19, D-20:** Coordinator subclass + `coordinator.data: Snapshot`
    direct — Phase 4 reads `coordinator._previous_snapshot` and
    `coordinator.data` directly for the diff comparison.
  - **C-03:** `self._previous_snapshot` already captured by Phase 3
    (`coordinator.py:147`) — Phase 4 just reads it.
  - **D-25:** `PLATFORMS = (Platform.SENSOR,)` — Phase 4 extends to
    `(Platform.SENSOR, Platform.CALENDAR)`.
- `.planning/phases/03-coordinator-first-sensor/03-VERIFICATION.md` and
  `03-HUMAN-UAT.md` — UAT findings carried forward; especially the eight
  alpha-release lesson that drove probe-first discipline.

### Research already done
- `.planning/research/FEATURES.md` —
  - Line 56–57: Numeric average + ≤16 KiB attribute discipline (the v1
    P0/P1 contract Phase 4 directly satisfies).
  - Line 72–78: Direct numeric sensor for moyenne générale (Pronote
    field is the source); Calendar entity in v1; Attribute size guard
    unit test (Phase 4 ships); Documented ApexCharts attribute schema
    (Phase 4 freezes).
  - Line 73: Per-grade schema documented `{date, subject, grade, out_of,
    coefficient}` — Phase 4 EXTENDS this with class context + comment.
  - Line 92, 94, 95, 97, 102: Explicitly OUT — OCR/PDF parsing,
    homework sensor, push from integration, raw HTML attributes,
    iCal subscription URL. Reject if any creep into the plan.
  - Line 144: Decimal-comma normalisation prerequisite for grade
    sensor.
- `.planning/research/ARCHITECTURE.md` —
  - §"Pattern 3: Diff-as-pure-function, fired from coordinator"
    (lines 220–278): Phase 4's `_fire_diff_events` lifts Pattern 3
    verbatim, with the wrapping fields (`child_slug` etc.) renamed per
    D-11.
  - §"Pattern 2: One coordinator per account" (lines 206–218): Phase 4
    keeps the one-coordinator-per-entry invariant; all 3 new sensors +
    calendar share `entry.runtime_data.coordinator`.
  - Lines 240–256: The `_fire_event` helper shape and the
    `pronote_schedule_changed` example payload — Phase 4's coordinator
    code mirrors this layout.
- `.planning/research/PITFALLS.md` —
  - Line 192: 16 KiB attribute size cap and recorder warning — Phase 4's
    CI gate (D-17) is the structural fix.
  - Line 217: DB recorder growing too fast — controlled by sensor
    state-change frequency. Phase 4's state choices (count, unread_count,
    overall_average rounded float) are intentionally low-cardinality
    to keep recorder cost flat.
  - Line 419: "State attributes >16KB → recorder warning" mitigation —
    same as the CI gate plus the optional comment truncation.
- `.planning/research/STACK.md` — `pronotepy 2.14.6` exact pin remains
  binding (no upgrade for Phase 4 unless a real bug forces it);
  `TimestampDataUpdateCoordinator.last_update_success_time` available
  for any "EDT changed since last poll" predicate.
- `.planning/research/SUMMARY.md` — High-level synthesis, read once for
  orientation only.

### Phase 1 / 2 / 3 shipped code (relevant Phase 4 reads)
- `custom_components/ha_pronote/diff/events.py` — `LessonChange`,
  `NewGrade`, `NewInformation` dataclasses with `.to_payload()`. Phase 4
  imports and instantiates; type contracts are FROZEN.
- `custom_components/ha_pronote/diff/lessons.py` — `diff_lessons`
  reference implementation. Phase 4's `diff_grades` / `diff_notifications`
  mirror the docstring style + first-poll-skip + identity-key pattern.
- `custom_components/ha_pronote/diff/grades.py`,
  `custom_components/ha_pronote/diff/notifications.py` —
  NotImplementedError stubs; Phase 4 FILLS bodies per D-14.
- `custom_components/ha_pronote/coordinator.py` — Phase 4 EXTENDS only
  with `_fire_diff_events(previous, snapshot)` call + helper method.
  Do not touch `_recover_from_auth_error`, `_capture_session`, error
  mapping (Phase 3 contract).
- `custom_components/ha_pronote/sensor.py` — Phase 4 EXTENDS the
  existing module with `PronoteGradesSensor`, `PronoteNotificationsSensor`,
  and TIME-02 attrs on `PronoteLessonsTodaySensor`. The
  `async_setup_entry` already wires entities — Phase 4 adds entries
  to the `async_add_entities([...])` list.
- `custom_components/ha_pronote/entity.py` — Phase 4 EXTENDS
  `DeviceInfo` with `model=<class level>` per D-19. No other change.
- `custom_components/ha_pronote/api/models.py` —
  `Lesson.to_dict()` / `Grade.to_dict()` / `Information.to_dict()` /
  `Snapshot.lessons_today` / `.lessons_tomorrow` already shipped. Phase 4
  uses them directly. NO Phase 4 change to `api/`.
- `custom_components/ha_pronote/api/fetcher.py` — Phase 4 does NOT modify.
  The J−7→J+14 window + grades/info already returned in Snapshot.
- `custom_components/ha_pronote/const.py` — Phase 4 APPENDS event
  constants + extends `PLATFORMS` + adds `CLASS_LEVEL_ATTR` (probe-locked)
  + `NOTIFICATIONS_WINDOW = 20` + `GRADE_COMMENT_MAX_LEN = 200`.
- `custom_components/ha_pronote/strings.json` — Phase 4 APPENDS
  `entity.sensor.grades.name`, `entity.sensor.notifications.name`,
  `entity.calendar.calendar.name`.
- `custom_components/ha_pronote/__init__.py` — Phase 4 does NOT modify
  (PLATFORMS sourced from const).
- `scripts/probe_config_flow.py` — Probe script with STEPS 5–11 covering
  every pronotepy method Phase 4 calls. Run BEFORE each plan that
  touches a new method (D-18).
- `tests/fixtures/real/{cancellation,room_change,teacher_swap}_T0/T1.json`
  — 6 anonymized real fixture pairs from Phase 2 spike. Phase 4's
  bus-event-firing coordinator tests can replay these.
- `tests/fixtures/synthetic/*.json` — 9 synthetic fixtures from Phase 2.
  Phase 4 ADDS `heavy_class.json` + `_gen_heavy_class.py`.
- `tests/conftest.py` — PHACC autouse + Phase 3's `mock_pronote_client`
  fixture. Phase 4 ADDS `heavy_class_snapshot` and
  `mock_pronote_client_with_grades`.

### External references (URL — no local copy)
- HA Developer Docs §"CalendarEntity" —
  `https://developers.home-assistant.io/docs/core/entity/calendar/` —
  `async_get_events(hass, start, end)` contract, `CalendarEvent` dataclass
  shape (`summary`, `description`, `start`, `end`, `location`, `uid`,
  `recurrence_id`).
- HA Developer Docs §"Event bus" —
  `https://developers.home-assistant.io/docs/dev_101_events/` —
  `hass.bus.async_fire(event_type, payload)`; payload must be JSON
  serialisable (informs the date/datetime contracts in `to_payload()`).
- HA Developer Docs §"State machine — attributes ≤16 KiB" —
  the 16 KiB recorder budget originates from HA Core's `RecorderRunner`
  pruning logic; Phase 4 enforces structurally with D-17.
- `bain3/pronotepy/clients.py` § `current_period`, `Period.grades`,
  `Period.overall_average`, `Period.average` (verify which exists in
  2.14.6 via probe STEP 6).
- `bain3/pronotepy/clients.py` § `client.lessons(date_from, date_to)`,
  `Lesson.canceled`, `Lesson.status` — already locked in `diff/lessons.py`
  docstring (SPIKE-FINDINGS S-04 derived).
- `bain3/pronotepy/clients.py` § `client.information_and_surveys()`,
  `Information.id`, `Information.title`, `Information.author`,
  `Information.content`, `Information.read` — Phase 2 already wraps in
  `api/fetcher.py:_info_from_raw`.
- `bain3/pronotepy/clients.py` § `ClientInfo` attrs — exact attribute
  for class level is probe-verified (D-19).
- `delphiki/HomeAssistant-Pronote/sensor.py` — reference implementation
  of Grades + Notifications sensors. Phase 4 reuses the IDEA, not the
  literal code (delphiki ships before runtime_data + uses string state
  for averages — issue #135 Phase 4 explicitly fixes per FEATURES.md
  line 278).
- `delphiki/HomeAssistant-Pronote/calendar.py` — reference implementation
  of `PronoteCalendar.async_get_events`. Phase 4 reuses the IDEA only.

### SPEC.md
None — `/gsd-spec-phase` was not run for Phase 4. Requirements live in
REQUIREMENTS.md (14 reqs listed above) + ROADMAP.md success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Diff layer (Phase 2 shipped):**
  - `diff/events.py` ships `LessonChange`, `NewGrade`, `NewInformation`
    dataclasses + `.to_payload()` methods + the `ChangeType` /
    `DayLabel` Literals. Phase 4 imports without modification.
  - `diff/lessons.py` ships `diff_lessons(previous, new, day)` fully
    implemented with first-poll-skip + identity-vs-content key. Phase 4
    calls it twice per poll (day="today", day="tomorrow") in
    `_fire_diff_events`.
  - `diff/grades.py` and `diff/notifications.py` ship signature-locked
    NotImplementedError stubs. Phase 4 fills bodies per D-14.
- **API layer (Phase 2 shipped):**
  - `api/models.py:Snapshot` exposes `lessons_today`, `lessons_tomorrow`,
    `grades`, `information` slices. Sensors read directly.
  - `api/models.py:{Lesson, Grade, Information}.to_dict()` shipped and
    used in Phase 2 fixture tests. Phase 4 reuses for sensor attributes.
  - `api/fetcher.py:fetch_all(...)` already returns the full
    J−7→J+14 snapshot. NO change in Phase 4.
- **Coordinator (Phase 3 shipped):**
  - `coordinator.py:_previous_snapshot` field captured per poll
    (`coordinator.py:147`). Phase 4 reads it for the diff comparison.
  - `coordinator.py._async_update_data` ordering is locked; Phase 4
    inserts `_fire_diff_events(previous, snapshot)` AFTER
    `_capture_session` and BEFORE `return snapshot`.
  - `coordinator.py:_LOGGER` available for any Phase 4 logging.
- **Entity base (Phase 3 shipped):**
  - `entity.py:PronoteEntity(CoordinatorEntity)` with `has_entity_name = True`,
    `device_info` property reading from `runtime_data` + `entry.data["child_name"]`,
    no override of `available`. Phase 4 subclasses for GradesSensor,
    NotificationsSensor, PronoteCalendar.
  - Phase 4 EXTENDS `device_info` to add `model=<class level>` per D-19 —
    the only change to `entity.py`.
- **Sensor scaffolding (Phase 3 shipped):**
  - `sensor.py:async_setup_entry` already wires entities. Phase 4 ADDS
    entries to the `async_add_entities([...])` list.
  - `sensor.py:PronoteLessonsTodaySensor` ships with state-only
    `native_value`. Phase 4 ADDS TIME-02 `extra_state_attributes`
    property.
- **Const + manifest (Phase 1+3 shipped):**
  - `const.py:DOMAIN`, `DEFAULT_SCHOOL_TZ`, `DEFAULT_LOOKBACK_DAYS`,
    `DEFAULT_LOOKAHEAD_DAYS`, `DEFAULT_REFRESH_INTERVAL`, `PLATFORMS`.
  - `manifest.json` already declares `pronotepy==2.14.6` exact pin
    + `python-slugify==8.0.4`. No new dep in Phase 4.

### Established Patterns
- **From Phase 1 / 2 / 3:**
  - Exact-pin `pronotepy==2.14.6` (Phase 1 D-14) — Phase 4 does NOT bump.
  - All planner-level reads of CLAUDE.md "What NOT to Use" before any
    tooling call.
  - Frozen `@dataclass(frozen=True)` for value types (Phase 2
    `api/models.py`, `diff/events.py`); Phase 4's `NewGrade` /
    `NewInformation` already frozen (Phase 2 D-02 lock).
  - tz-aware datetime everywhere via `zoneinfo.ZoneInfo` (Phase 2 D-23) —
    Phase 4's `CalendarEvent.start` / `.end` inherit `Lesson.start` /
    `.end` which are already tz-aware.
  - "No silent exceptions" feedback memory — Phase 4 default is `raise`
    over `except`; the few `getattr(..., None)` defaults (D-19 model
    fallback) are explicit, visible patterns, not swallowing catches.
  - Probe-first discipline (D-18) — codifies the lesson learned from
    Phase 3's 8 alpha releases.
- **External patterns to mirror (idea, not code):**
  - `delphiki/HomeAssistant-Pronote/coordinator.py` — diff + fire pattern;
    Phase 4 wires the same flow on our runtime_data + typed diff layer.
  - `delphiki/HomeAssistant-Pronote/sensor.py` Grades sensor — reference
    for ApexCharts-shaped attributes; Phase 4 ships the numeric
    overall_average (delphiki shipped string-with-comma per FEATURES.md
    line 278).
  - `delphiki/HomeAssistant-Pronote/calendar.py` —
    `async_get_events(...)` recipe; Phase 4 adds the cancelled-emoji
    distinction.
  - HA Core `homeassistant/components/calendar/__init__.py` —
    `CalendarEntity` interface contract.

### Integration Points
- **Phase 4 → Phase 5 interface:**
  - `_fire_diff_events` is the natural seam for Phase 5's quiet-hours
    suppression: Phase 5 adds a `compute_should_fire(now)` predicate
    that gates the call. Phase 4 does NOT pre-build that guard.
  - `coordinator.last_update_success_time` (Phase 3 D-19's
    TimestampDataUpdateCoordinator gift) — Phase 5 reads to detect
    "no successful poll in the configured backoff window".
  - `RateLimitedError(IP_SUSPENDED)` mapping (Phase 3 D-22) — Phase 5's
    circuit-breaker reads `.reason`. Phase 4's diff calls do NOT introduce
    new error paths.
- **Phase 4 → Phase 6 interface:**
  - `Period.overall_average` source field name (D-03) — Phase 6's
    OptionsFlow could expose a "computed-average" toggle. Out of scope
    for Phase 4.
  - `NOTIFICATIONS_WINDOW = 20`, `GRADE_COMMENT_MAX_LEN = 200` const
    knobs — Phase 6's OptionsFlow could promote them to per-entry
    options. Phase 4 commits the defaults.
  - DeviceInfo.model = `<class level>` (D-19) — when Pronote-side class
    changes year-over-year, Phase 6 reauth flow updates it via DeviceInfo
    refresh on next setup. Phase 4 just sources the current value.
- **Phase 4 → Phase 7 interface:**
  - Bus event payload schema (D-11..D-15) — Phase 7's README documents
    these for users' automation YAML. Phase 4 freezes the schema; Phase 7
    doesn't change it.
  - Heavy-class CI gate (D-17) — Phase 7's daily cron job against
    `pronotepy@main` runs the same test, so a pronotepy regression that
    blows attribute sizes opens an issue automatically.
  - DIAG-01 redaction list — Phase 7 adds `child_name` and Pronote-side
    establishment-derivable fields. Phase 4 doesn't pre-redact.

</code_context>

<specifics>
## Specific Ideas

- **Heavy-class generator parameters** — to make the fixture realistic
  enough to catch the 16 KiB boundary without being a worst-case stress
  test: 6 teaching days × 7 lessons/day = 42 lessons/week × 3 weeks (J−7
  to J+14) ≈ 126 lessons; 100 grades distributed across 4–6 subjects
  with realistic French names (Mathématiques, Histoire-Géographie, EPS,
  Physique-Chimie, Anglais, …); 30 informations with paragraph excerpts
  hitting the 500-char `excerpt` cap.

- **Cancelled-distinct emoji** — `❌` chosen because it renders on
  mobile widgets, terminal HA cards, and the iOS/Android HA app without
  needing special font support. `⚠️` is the fallback if `❌` proves
  problematic in any HA card.

- **Probe captures vs production behaviour** — the probe runs against the
  author's `katiramona.ac-noumea.nc` instance (Province Sud / college
  Jean Fayard). Pronote NC ships behind a Keycloak ENT for the
  `?identifiant=` URL but the `?login=true` URL reaches direct Pronote
  (Phase 3 UAT finding #6). The probe uses the `?login=true` URL — Phase 4
  sensor mocks must match what the direct-Pronote login returns, NOT
  what an ENT-wrapped install returns (Phase 6's reopened ENT work will
  surface those differences).

- **Multi-period awareness** — Pronote exposes `client.periods` (probe
  STEP 9) and `client.current_period`. Phase 4 sensors target
  `current_period` only. Phase 6 may add a
  `pronote.get_period_grades(period_id)` service (per REQUIREMENTS Out
  of Scope table — "service en v1.x si demandé"). NOT a Phase 4 item.

- **delphiki Lovelace YAML compatibility** — Phase 4's attribute schemas
  intentionally diverge from delphiki's (`grades` numeric vs string per
  FEATURES.md line 278; lessons split into today/tomorrow rather than
  one big list). README in Phase 7 will document the differences.

- **Calendar entity dedup** — HA's calendar UI may double-render lessons
  if `CalendarEvent.uid` is unstable. D-09 locks the uid recipe so
  re-polls produce identical uids for the same logical lesson.

- **Period.overall_average comma-string** — pronotepy 2.14.6 surfaces it
  as a string ("14,50"). Probe STEP 6 verifies. The grade sensor normalises
  with `float(value.replace(",", "."))`. If pronotepy ships `14,5` (no
  trailing zero) or `14` (integer), the normalisation handles both.
  Edge case to test: `""` empty string when no grades published yet →
  state = `None` (HA shows "unknown" — acceptable for "trimester just
  started" state).

</specifics>

<deferred>
## Deferred Ideas

These came up during discussion but belong in later phases or post-v1:

- **`pronote_grade_edited` event** for edited-grade detection — explicitly
  rejected (out of REQUIREMENTS scope; would be EVENT-V2-*).
- **Next-lesson timestamp sensor** alongside the count sensor — rejected
  for Phase 4 to keep the entity surface minimal. Phase 6 could add it if
  user feedback requests it.
- **Lessons sensor top-level `today_canceled_count` / `tomorrow_canceled_count`
  derived attrs** — overlap with bus events; not needed in v1.
- **Class context fields on Grade attribute** (class_average, class_min,
  class_max, comment) — INCLUDED in Phase 4 per D-04. If pronotepy 2.14.6
  proves to not expose them, planner downgrades to the FEATURES.md baseline
  schema and notes the downgrade in the plan (no silent absence).
- **Calendar entity `event` property** (current/next lesson) — rejected;
  full async_get_events covers the use cases for v1.
- **Calendar fetcher window growth beyond J−7→J+14** — locked by Phase 2
  fetcher; Phase 6 could grow if user asks. CalendarEntity.async_get_events
  returning `[]` outside the window is the documented behaviour.
- **Reintroduce D-04 typed-error → form-error mapping in config_flow** —
  permanently OFF per the "no silent exceptions" feedback memory. NOT a
  Phase 4 item; user reverses the preference before this is reconsidered.
- **Reintroduce D-12 collision suffix using ClientInfo.id** — Phase 6 item
  (config_flow patch). Phase 4 doesn't touch config_flow.
- **ENT / Keycloak SSO for Pronote NC** — Phase 6 (reopened per
  Phase 3 UAT). Out of scope for Phase 4 even though it's the same
  Pronote instance.
- **Per-period grade sensor or service** — Phase 6 (`pronote.get_period_grades`
  service per REQUIREMENTS Out-of-Scope notes).
- **pronotepy upgrade beyond 2.14.6** — only when a real bug forces it
  (Phase 2 anchor). Phase 4 commits to 2.14.6 as the spike+probe-validated
  version.
- **OptionsFlow knob for `NOTIFICATIONS_WINDOW` / `GRADE_COMMENT_MAX_LEN`**
  — Phase 6 (OPT-* family). Phase 4 commits the const defaults.
- **DIAG-01 redaction list update for new attributes** (child_name,
  teacher names, classroom codes) — Phase 7 (diagnostics platform).
- **README ApexCharts YAML example + automation YAML for
  pronote_schedule_changed / pronote_new_grade / pronote_new_information**
  — Phase 7 (DIST-07). Phase 4 freezes the payload schema; Phase 7
  documents.

</deferred>

---

*Phase: 4-Diff, Events & Full Sensor Suite*
*Context gathered: 2026-05-24*
