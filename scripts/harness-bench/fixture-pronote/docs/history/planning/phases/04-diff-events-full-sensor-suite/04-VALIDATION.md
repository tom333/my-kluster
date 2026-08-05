---
phase: 4
slug: diff-events-full-sensor-suite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Sourced from `04-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-homeassistant-custom-component 0.13.326 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/test_diff/ -x -q` (diff tasks) — or `uv run pytest tests/test_sensor.py tests/test_calendar.py -x -q` (sensor/calendar tasks) |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 s (diff-only quick), ~20 s (sensor/calendar quick), ~45 s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run quick run command for the touched layer (diff / sensor / calendar / coordinator).
- **After every plan wave:** Run `uv run pytest tests/ -x` (full suite).
- **Before `/gsd-verify-work`:** Full suite must be green AND `tests/test_attribute_size.py` must pass (heavy-class CI gate).
- **Max feedback latency:** ~5 s on a single diff/sensor test run; ~45 s for the full suite.

---

## Per-Task Verification Map

Per Phase 4 requirement IDs (from ROADMAP / REQUIREMENTS).

| Req ID | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| TIME-02 | `lessons_today` + `lessons_tomorrow` attrs on EDT sensor | — | N/A | unit | `pytest tests/test_sensor.py -k test_lessons_today_attrs -x` | ❌ W0 | ⬜ pending |
| TIME-03 | EDT state ≤255, attrs ≤16384 on heavy fixture | — | N/A | unit (CI gate) | `pytest tests/test_attribute_size.py -k lessons -x` | ❌ W0 | ⬜ pending |
| GRADE-01 | Numeric float state from `Period.overall_average` (comma→dot) | T-04-1 | `try float() except ValueError → None` | unit | `pytest tests/test_sensor.py -k test_grades_sensor_state -x` | ❌ W0 | ⬜ pending |
| GRADE-02 | ApexCharts attrs dict (all current-period grades; class context + comment) | T-04-2 | `str[:200]` comment truncation | unit | `pytest tests/test_sensor.py -k test_grades_attrs -x` | ❌ W0 | ⬜ pending |
| GRADE-03 | Grades state ≤255, attrs ≤16384 on heavy fixture | — | N/A | unit (CI gate) | `pytest tests/test_attribute_size.py -k grades -x` | ❌ W0 | ⬜ pending |
| NOTIF-01 | `unread_count` state | — | N/A | unit | `pytest tests/test_sensor.py -k test_notifications_sensor_state -x` | ❌ W0 | ⬜ pending |
| NOTIF-02 | 20 most-recent informations in attrs (date desc) | — | N/A | unit | `pytest tests/test_sensor.py -k test_notifications_attrs -x` | ❌ W0 | ⬜ pending |
| CAL-01 | `async_get_events` returns CalendarEvent list for J−7→J+14 range | T-04-3 | `description` in `_entity_component_unrecorded_attributes` (recorder skips) | unit | `pytest tests/test_calendar.py -k test_get_events_range -x` | ❌ W0 | ⬜ pending |
| CAL-02 | Cancelled lesson has ❌ prefix in summary | — | UTF-8 safe in recorder | unit | `pytest tests/test_calendar.py -k test_cancelled_lesson_summary -x` | ❌ W0 | ⬜ pending |
| EVENT-01 | `pronote_schedule_changed` fires on lesson change | T-04-4 | child_name in payload is non-secret public data | unit | `pytest tests/test_coordinator.py -k test_fires_schedule_changed -x` | ❌ W0 | ⬜ pending |
| EVENT-02 | `pronote_new_grade` fires on new grade | T-04-4 | non-secret | unit | `pytest tests/test_coordinator.py -k test_fires_new_grade -x` | ❌ W0 | ⬜ pending |
| EVENT-03 | `pronote_new_information` fires on new info | T-04-4 | excerpt already capped at 500 chars | unit | `pytest tests/test_coordinator.py -k test_fires_new_information -x` | ❌ W0 | ⬜ pending |
| EVENT-04 | No events on first poll (`previous is None`) | — | N/A | unit | `pytest tests/test_coordinator.py -k test_no_events_first_poll -x` | ❌ W0 | ⬜ pending |
| ENT-01 | DeviceInfo.model = `ClientInfo.class_name` (or None on empty) | — | N/A | unit | `pytest tests/test_sensor.py -k test_device_info_model -x` | ❌ W0 | ⬜ pending |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Threat refs map to `04-RESEARCH.md` §Security Domain "Known Threat Patterns for Phase 4".*

---

## Wave 0 Requirements

The following files must be created (or extended) BEFORE or AS PART OF the implementing plan that depends on them:

- [ ] `tests/test_diff/test_grades.py` — `diff_grades` identity-key set diff, first-poll skip, new grade detection
- [ ] `tests/test_diff/test_notifications.py` — `diff_notifications` identity-key set diff, first-poll skip
- [ ] `tests/test_sensor.py` (extend) — grades sensor + notifications sensor + TIME-02 attrs + ENT-01 model
- [ ] `tests/test_calendar.py` — CalendarEvent shape, uid stability, cancelled prefix, `event` property, range filtering
- [ ] `tests/test_coordinator.py` (extend) — `_fire_diff_events` happy path + EVENT-04 no-events-first-poll regression
- [ ] `tests/test_attribute_size.py` — heavy-class fixture CI gate (255 chars + 16384 bytes + state never None/unknown)
- [ ] `tests/conftest.py` (extend) — `heavy_class_snapshot` fixture, `mock_pronote_client_with_grades` fixture
- [ ] `tests/fixtures/synthetic/heavy_class.json` + `_gen_heavy_class.py` (committed generator + output)
- [ ] `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` — captured probe STEP 5–11 output (per-plan probe-first discipline, CONTEXT.md D-18)

*Existing test infra used as-is: `tests/conftest.py` (PHACC autouse), `tests/test_diff/test_lessons.py` (Phase 2 reference), `tests/test_diff/test_stubs.py` (shrinks to positive tests in Phase 4 per CONTEXT.md C-05).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Modify a lesson in Pronote → see `pronote_schedule_changed` in HA Developer Tools → Events | EVENT-01 (SC#1) | Requires live Pronote write + live HA instance; cannot run in CI | (1) Open Pronote app, modify a lesson (cancel / move / change room). (2) Wait one polling cycle (≤30 min). (3) Open HA Developer Tools → Events → listen to `pronote_schedule_changed`. (4) Assert payload contains `child_id`, `child_name`, `config_entry_id`, `change_type`, `day`, `lesson_date`, `subject`, `before`, `after`. |
| Each child Device shows `manufacturer="Pronote"` + `model=<class level>` in HA UI | ENT-01 (SC#2) | Visual / DeviceInfo render check | HA Settings → Devices & Services → HA-Pronote → click child Device. Header should show Pronote manufacturer + class level (e.g. "5e1"). If class missing on this Pronote build, model row is hidden (acceptable). |
| Calendar entity shows cancelled lessons with ❌ prefix in week view | CAL-02 (SC#2) | Visual render check across cards (Mushroom, Atomic, Calendar) | Add `calendar.pronote_<slug>` to a dashboard with the default Calendar card. Locate a cancelled lesson day. Verify the lesson title renders with ❌ prefix. |
| Zero "State attributes for X exceed maximum size" warnings in HA logs over a 24h window | TIME-03 / GRADE-03 (SC#3) | Recorder warning emission requires live HA over time | After 24h of polling against author's instance, `grep "State attributes.*exceed maximum" home-assistant.log` returns no lines. |
| Probe captures align with mocks (mock-drift mitigation) | CONTEXT.md D-18 | Requires author's live creds + `scripts/probe_config_flow.py` execution before each pronotepy-touching plan ships | For each plan that calls a new pronotepy method: (1) Run probe per CONTEXT.md D-18 command. (2) Paste STEP output into `PHASE-4-PROBE-NOTES.md`. (3) Verify all mocks in the plan match the captured shape. (4) Sign off in plan HUMAN-UAT. |

---

## Validation Sign-Off

- [ ] All 14 phase requirements have `<automated>` verify commands or Wave 0 dependencies declared
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (planner enforces during plan writing)
- [ ] Wave 0 covers all MISSING test files listed above
- [ ] No watch-mode flags (PHACC tests run once per command)
- [ ] Feedback latency < 45 s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter once plans satisfy all rows in the Per-Task Verification Map

**Approval:** pending
