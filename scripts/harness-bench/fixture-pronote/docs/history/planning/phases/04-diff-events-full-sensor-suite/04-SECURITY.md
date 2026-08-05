---
phase: 4
slug: diff-events-full-sensor-suite
status: secured
threats_open: 0
threats_closed: 22
asvs_level: 1
created: 2026-05-25
---

# SECURITY.md — Phase 4 Security Audit

**Phase:** 04 — Diff, Events & Full Sensor Suite
**Audit date:** 2026-05-25
**ASVS Level:** 1
**Auditor:** gsd-secure-phase (automated)
**Verdict:** SECURED — all declared mitigations present in code

---

## Threat Verification

### Cross-cutting threats (Plan 04-07 threat register)

| Threat ID | STRIDE | Disposition | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| T-04-1 | Denial of Service | mitigate | CLOSED | `sensor.py:31-46` — `_to_float()` wraps `float(raw.replace(",","."))` in `try/except ValueError: return None`. Also applied at `sensor.py:144` via `_to_float(normalised)` in `PronoteGradesSensor.native_value`. Typed conversion guard only (ValueError on string→float), not a swallowing catch — compliant with "no silent exceptions" memory. |
| T-04-2 | Information Disclosure / DoS | mitigate | CLOSED | `sensor.py:171` — `(g.comment or "")[:GRADE_COMMENT_MAX_LEN]` in `PronoteGradesSensor.extra_state_attributes`. `GRADE_COMMENT_MAX_LEN = 200` in `const.py:42`. Truncation at sensor serialisation, NOT in fetcher layer (api/ stays faithful). |
| T-04-3 | Information Disclosure | mitigate | CLOSED | `calendar.py:42-124` inherits `CalendarEntity` base. Verified at runtime: `CalendarEntity._entity_component_unrecorded_attributes = frozenset({"description"})` (confirmed via import — `description in frozenset({"description"})` is True). Teacher names in `description` field are excluded from recorder storage. The inheritance is passive — no override of the base class frozenset. |
| T-04-4 | Information Disclosure | mitigate | CLOSED | `coordinator.py:263-267` — `child_context` dict contains exactly `child_id`, `child_name`, `config_entry_id`. AST-verified: `_fire_diff_events` has 0 try blocks. Payload fields sourced from `to_payload()` methods in `diff/events.py` — `LessonChange.to_payload()` (line 52-59), `NewGrade.to_payload()` (line 76-83), `NewInformation.to_payload()` (line 99-107). None contain `password`, `token`, `username`, `session`, or URL fields. grep confirms: no credential-adjacent fields in any `to_payload` or `async_fire` call site. |

### Per-plan scoped threats

| Threat ID | STRIDE | Disposition | Status | Evidence |
|-----------|--------|-------------|--------|----------|
| T-04-01a | Tampering | accept | CLOSED | Identity key `(subject, date, value)` in `diff/grades.py` uses normalized strings from fetcher. No injection surface. Documented in Plan 04-01 threat_model. |
| T-04-01b | Denial of Service | accept | CLOSED | `Information.date.date()` call in `diff/notifications.py` — `Information.date` guaranteed tz-aware datetime from `_info_from_raw`. Documented accept. |
| T-04-02a | Tampering | mitigate | CLOSED | Truncation at sensor render (`sensor.py:171`). Verified: `api/` layer (`fetcher.py:_grade_from_raw`) receives and stores raw `comment` without truncation — faithful. |
| T-04-02b | Denial of Service | mitigate | CLOSED | `fetcher.py:89-90` — `overall_average` captured via `getattr(client.current_period, "overall_average", "")` inside the executor-bound `fetch_all` function. Never called from `PronoteGradesSensor.native_value` — sensor reads `coordinator.data.overall_average` (a plain string field, no HTTP). |
| T-04-02c | Tampering | accept | CLOSED | `str()` cast on all fetched values in `fetcher.py:_grade_from_raw` (lines 177-180). `None → "" via `or ""`. Documented accept. |
| T-04-03a | Tampering | accept | CLOSED | `tests/fixtures/synthetic/_gen_heavy_class.py` committed. Generator produces deterministic output from committed source; drift detectable by re-run. Documented accept per plan threat_model. |
| T-04-03b | Information Disclosure | mitigate | CLOSED | `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` exists and contains only field shapes and sample non-secret values. grep for `password`, `token`, `session`, `uuid`, `credential` in probe notes returns empty. Credentials loaded from `.env` (not committed) per Phase 2 `.env.example` pattern. |
| T-04-04a | Information Disclosure | accept | CLOSED | DeviceInfo.model exposes class level (public school data, not a credential). Documented accept. |
| T-04-04b | Tampering | mitigate | CLOSED | `const.py:30-32` — all three event constants are `Final` with exact string values: `"pronote_schedule_changed"`, `"pronote_new_grade"`, `"pronote_new_information"`. Tests in `tests/test_init.py:test_phase4_const_values` assert exact values. |
| T-04-04c | Denial of Service | accept | CLOSED | `Platform.CALENDAR` imported from `homeassistant.const` (present in HA Core). hassfest validates at CI. Documented accept. |
| T-04-05a | Denial of Service | mitigate | CLOSED | Same as T-04-1: `_to_float()` at `sensor.py:31-46` applied in `PronoteGradesSensor.native_value` at line 144. |
| T-04-05b | Information Disclosure | mitigate | CLOSED | Same as T-04-2: `(g.comment or "")[:GRADE_COMMENT_MAX_LEN]` at `sensor.py:171`. |
| T-04-05c | Denial of Service | mitigate | CLOSED | `tests/test_attribute_size.py` — CI gate asserts `attrs_bytes <= 16384` on heavy_class fixture for all 3 sensors. GRADES_WINDOW=50 cap added at `const.py:49` and applied at `sensor.py:158` to bound the grades list. |
| T-04-06a | Information Disclosure | accept | CLOSED | CalendarEntity base class excludes `description` from recorder (T-04-3 verified). Documented accept — this is the inherited mechanism. |
| T-04-06b | Denial of Service | mitigate | CLOSED | `calendar.py:113-116` — uid formula `pronote_{child_id}_{date}_{start.isoformat()}_{slugify(subject)}` is deterministic; same lesson inputs produce same uid. `tests/test_calendar.py:test_lesson_to_event_uid_stability` verifies. |
| T-04-06c | Denial of Service | mitigate | CLOSED | `calendar.py:111` — `end = lesson.end if lesson.end > lesson.start else lesson.start + timedelta(hours=1)`. Guard is present at the exact location in `_lesson_to_event`. |
| T-04-04 (T-04-04d per threat register) | accept | accept | CLOSED | `entity.py:84` — `getattr(info_obj, CLASS_LEVEL_ATTR, None) or None`. The explicit `or None` converts `""` to `None`. Present at the expected call site. |
| T-04-07a | Information Disclosure | accept | CLOSED | Bus event payloads contain only public school-context fields. No credentials appear in `child_context` or any `to_payload()` result. Documented accept. |
| T-04-07b | Denial of Service | accept | CLOSED | `_fire_diff_events` crash propagates to fail the poll (D-12 intent). Coordinator retries on next cycle. Documented accept. |
| T-04-07c | Tampering | accept | CLOSED | All `to_payload()` methods call `.isoformat()` on date fields; `child_context` values are all `str`. JSON-serializable. Documented accept. |

---

## ASVS L1 Coverage

| ASVS Category | Applicable | Verified |
|---------------|------------|---------|
| V2 Authentication | No — no auth surface touched in Phase 4 | N/A |
| V3 Session Management | No — session persistence unchanged from Phase 3 | N/A |
| V4 Access Control | No — no new access control surface | N/A |
| V5 Input Validation | Yes — comma-normalisation (_to_float) + comment truncation | CLOSED via T-04-1 + T-04-2 |
| V6 Cryptography | No — no crypto surface touched | N/A |
| V7 Error Handling | Yes — no swallowing try/except in _fire_diff_events | CLOSED: 0 try blocks in _fire_diff_events (AST verified) |

---

## Unregistered Flags

From SUMMARY.md `## Threat Flags` sections:

- 04-02-SUMMARY: "No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries" — maps to T-04-02a/b/c (registered). No unregistered surface.
- 04-03-SUMMARY: No threat flags section.
- 04-04-SUMMARY: No threat flags section.
- 04-05-SUMMARY: "No new network endpoints, auth paths, or file access patterns introduced. The sensor layer is read-only from coordinator data." — maps to T-04-05a/b/c (registered). No unregistered surface.
- 04-06-SUMMARY: "None — no new network endpoints, auth paths, or file access patterns beyond what the plan's threat_model already covers (T-04-06a, T-04-06b, T-04-06c all mitigated in implementation)." — all registered.
- 04-07-SUMMARY: "No new network endpoints, auth paths, or trust-boundary surfaces introduced. Bus event payloads contain only public school-context data" — maps to T-04-07a (registered, accept). No unregistered surface.

**Unregistered flags: none.**

---

## Accepted Risks Log

| Risk ID | Description | Accepted by | Rationale |
|---------|-------------|-------------|-----------|
| T-04-01a | diff_grades identity key uses Pronote-normalized strings — no injection surface | Plan 04-01 threat_model | Fields are pre-normalized strings; no user-controlled injection path into the diff key |
| T-04-01b | `.date()` on tz-aware datetime cannot raise | Plan 04-01 threat_model | `Information.date` guaranteed tz-aware by `_info_from_raw` |
| T-04-02c | `str()` cast normalizes unexpected pronotepy types | Plan 04-02 threat_model | Explicit visible default; str() on any Python object cannot raise |
| T-04-03a | heavy_class.json fixture drift | Plan 04-03 threat_model | Generator is committed; re-run detects drift deterministically |
| T-04-04a | DeviceInfo.model exposes class level string | Plan 04-04 threat_model | Public school information visible in Pronote UI; not a credential |
| T-04-04c | Platform.CALENDAR availability | Plan 04-04 threat_model | Validated by hassfest CI gate |
| T-04-06a | CalendarEvent.description with teacher name | Plan 04-06 threat_model | HA base class excludes description from recorder (T-04-3 verified) |
| T-04-07a | Bus event payloads contain child_name + lesson/grade details | Plan 04-07 threat_model | Public school-context data; Phase 7 diagnostics redactor covers extension if needed |
| T-04-07b | _fire_diff_events crash fails the poll | Plan 04-07 threat_model | Intentional per D-12 / "no silent exceptions" memory; coordinator retries |
| T-04-07c | Bus event date fields JSON-serializable | Plan 04-07 threat_model | All to_payload() methods call .isoformat(); child_context values are str |

---

## UAT Evidence (Live Validation)

Per 04-UAT.md (8/8 pass):

- **Test 7B:** Real `pronote_schedule_changed` event observed in HA Developer Tools with full payload including `child_id`, `child_name`, `config_entry_id`, `change_type`, `day`, `lesson_date`, `subject`, `before`, `after` — confirms T-04-4 wrapper operational and no credential leakage in practice.
- **Test 8:** Zero "Detected blocking call" and zero "State attributes exceed maximum size" warnings over a real 30-minute poll cycle — confirms T-04-1 (blocking HTTP stays in executor) and T-04-2 (size discipline holds on real account data).
- **Test 7A:** EVENT-04 first-poll skip confirmed on live HA restart — no events fired when `previous_snapshot=None`.
