# Phase 2: API & Diff Layer (HA-free) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 2-API & Diff Layer (HA-free)
**Areas discussed:** Diff scope, Diff keys & bain3#311 strategy, Fixture sourcing strategy, Snapshot fetch window

---

## Diff Scope (Area 1)

**Question:** Phase 2 ships `diff/lessons.py` (the hard one — identity vs content). What about `diff/grades.py` and `diff/notifications.py` — also Phase 2, or push to Phase 4?

| Option | Description | Selected |
|--------|-------------|----------|
| Full suite in Phase 2 (Recommended) | Ship lessons + grades + notifications diff modules now. Phase 4 then only wires events to the bus — no diff logic written there. Bigger Phase 2, much leaner Phase 4. >90% coverage applies to a complete diff/ subpackage. | |
| Lessons-only in Phase 2 | Ship only `diff/lessons.py`. Defer grades/notifs diff to Phase 4 alongside the sensor work. Phase 2 stays tightly focused on the success criterion. Risk: Phase 4 grows. | |
| Lessons + dataclasses-only stub for grades/notifs | Phase 2 ships `diff/lessons.py` plus the empty `NewGrade` / `NewInformation` dataclasses (just types, no diff function bodies). Phase 4 fills bodies. Locks types so Phase 4 can't drift. | ✓ |

**User's choice:** Lessons + dataclasses-only stub for grades/notifs
**Notes:** Locks the type contract early so Phase 4 cannot drift. Bodies for grades/notifs diff are deferred to Phase 4 alongside the sensor + event-firing work. Coverage gate (>90%) applies to `diff/lessons.py`; the empty stubs are excluded via `[tool.coverage.run] omit` in `pyproject.toml`.

---

## Diff Keys & bain3#311 Strategy (Area 2)

**Question 1:** How do we handle the bain3#311 cancel-vs-room-change semantics in Phase 2?

| Option | Description | Selected |
|--------|-------------|----------|
| Spike against real fixtures FIRST (Recommended) | Before locking diff/lessons.py, capture a real T0/T1 pair from `katiramona.ac-noumea.nc` covering: a real cancellation, a real room change, a real teacher swap. Inspect what pronotepy 2.14.6 actually returns. Then lock keys based on observed reality. Cost: 1 extra plan slice. Benefit: zero "works in tests, breaks in prod" risk. | ✓ |
| Trust Pitfall 10 recipe verbatim | Use identity=(date, start_time, end_time, subject, teacher_initial), content=(canceled, status, classroom, modified) as-is. Validate against synthetic fixtures only. Faster but risky. | |
| Hybrid — lock recipe, mark assumptions, defer real-fixture validation to Phase 4 | Implement the Pitfall 10 keys now with explicit `# ASSUMES bain3#311 semantics per PITFALLS.md` comments. Phase 4 captures real fixtures and tightens. | |

**User's choice:** Spike against real fixtures FIRST
**Notes:** STATE.md had originally flagged bain3#311 as a Phase 4 spike, but Phase 2 success criterion #3 explicitly requires the cancellation-vs-room-change distinction. Moving the spike up. The spike's output (real fixtures + findings doc) is itself a Phase 2 deliverable.

**Question 2 (follow-up):** How should the spike feed into Phase 2? What's the deliverable that locks the diff algorithm?

| Option | Description | Selected |
|--------|-------------|----------|
| Spike plan slice produces SPIKE-FINDINGS.md (Recommended) | First plan in Phase 2 = `scripts/snapshot.py` skeleton + a one-shot spike that captures 3 real T0/T1 pairs. Output: `tests/fixtures/{cancellation,room_change,teacher_swap}_T{0,1}.json`, AND `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` documenting actual pronotepy 2.14.6 behavior. Subsequent diff plan reads that doc. | ✓ |
| Spike inline in diff plan, no separate doc | The diff/lessons.py plan opens with `python scripts/snapshot.py` to capture fixtures, then writes the diff against what was observed. Findings encoded in code + tests, no standalone doc. Loses the "why" trail. | |
| Skip dedicated spike — capture during normal fixture authoring | Capturing real fixtures is just part of test-authoring. No separate spike, no findings doc. Iterative. Risk: less rigorous. | |

**User's choice:** Spike plan slice produces SPIKE-FINDINGS.md
**Notes:** Plan order locked: (1) api/ skeleton + scripts/snapshot.py + spike + SPIKE-FINDINGS-bain3-311.md, (2) diff/lessons.py reading the findings, (3) tests + coverage gate. The findings doc preserves the "why" trail for future maintainers (e.g. when pronotepy 2.15 ships and someone needs to know which assumptions held in 2.14.6).

---

## Fixture Sourcing Strategy (Area 3)

**Question:** Beyond the spike's real fixtures, do we ALSO write synthetic fixtures for diff unit tests — or rely solely on real captures?

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid — real for bain3#311, synthetic for combinatorics (Recommended) | Real captures (3 pairs from spike) live in `tests/fixtures/real/`. Synthetic fixtures live in `tests/fixtures/synthetic/`: edge cases (empty→empty, reorder no-op, multiple changes per poll, vacation, first-poll-after-restart) hand-crafted to cover combinatorics that real-Pronote can't reliably reproduce. Best coverage. | ✓ |
| Real captures only | Every fixture pair = a real Pronote capture, anonymized. To test "reorder produces no events", capture two polls minutes apart and rely on Pronote randomly reordering. Brittle and high anonymization burden. | |
| Synthetic for everything except bain3#311 | Real captures only for the cancellation-vs-room-change discriminator. Everything else synthetic, hand-crafted to match pronotepy 2.14.6's schema. Lower anonymization cost, but new pronotepy quirks could escape. | |

**User's choice:** Hybrid — real for bain3#311, synthetic for combinatorics
**Notes:** Both fixture roots conform to the same JSON schema (the `Snapshot` dataclass's `to_dict()` shape). A `tests/test_fixtures.py` schema-roundtrip test asserts every fixture round-trips cleanly through `Snapshot.from_dict()`, so any future refactor of the dataclass shape forces revalidation in CI. The anonymizer (D-12) lives in `scripts/snapshot.py` and is itself unit-tested via a deterministic `assert no_pii(anonymize(fixture))` invariant.

---

## Snapshot Fetch Window (Area 4)

**Question:** What window does Phase 2's `fetch_all(client, today)` retrieve from Pronote?

| Option | Description | Selected |
|--------|-------------|----------|
| Wide window J−7 → J+14 from day 1 (Recommended) | `fetch_all` returns lessons across J−7 to J+14 in one snapshot. Phase 4 Calendar entity reuses the exact same fetch surface without refactor. Aligns with delphiki/hass-pronote's coordinator pattern. | ✓ |
| Narrow J/J+1 only, widen in Phase 4 | Phase 2 returns only today and tomorrow. Phase 4 widens. `fetch_all`'s signature changes between phases — and so do all the Phase 2 fixtures. | |
| Configurable window param, default J−7 → J+14 | `fetch_all(client, today, *, lookback_days=7, lookahead_days=14)`. Tests can pass narrow windows for fast unit tests. Slightly more API surface. | |

**User's choice:** Wide window J−7 → J+14 from day 1
**Notes:** Snapshot exposes `lessons_today` and `lessons_tomorrow` convenience slice properties for diff/lessons.py to consume; `lessons` (the full window) for Phase 4's Calendar entity. Avoids the Phase 4 refactor risk entirely.

---

## Claude's Discretion

The user delegated these sub-decisions to the planner (see CONTEXT.md `<decisions>` §"Claude's Discretion" for recommended defaults):

- **C-01:** Filename for `LessonChange` / `NewGrade` / `NewInformation` dataclasses (`diff/types.py` vs `diff/events.py`)
- **C-02:** Coverage exclusion mechanic for grades/notifications stubs (`# pragma: no cover` vs `[tool.coverage.run] omit`)
- **C-03:** Anonymization implementation in `scripts/snapshot.py` (replacements dict + recursive walker vs `faker`)
- **C-04:** `account_type` representation (`enum.StrEnum` vs `Literal["eleve", "parent"]`)
- **C-05:** Where the `_strip_client_refs` walker lives (`api/_strip.py` recommended)
- **C-06:** Whether `python-slugify` is actively used in Phase 2 or just declared

## Deferred Ideas

Ideas that came up during discussion but belong in later phases:

- `diff/grades.py` and `diff/notifications.py` function bodies → Phase 4
- Heavy-class fixture for HA size-limit assertions (50 lessons/week × 2 weeks, 100 grades) → Phase 4 (size limit lives on sensors)
- Token persistence via `client.export_credentials()` round-trip into `entry.data` → Phase 3 (AUTH-04)
- Adaptive interval, quiet hours, vacation calendar, jitter → Phase 5 (COORD-04..09, DIST-06)
- NC vice-rectorat school-calendar machine-readable format research → Phase 5
- Calendar entity J−7 → J+14 rendering → Phase 4 (CAL-01); Phase 2 already exposes the wide-window snapshot
- Numeric grade normalization ("14,5" → 14.5) → Phase 4 (GRADE-01)
- `async_migrate_entry` skeleton → Phase 3 (ENT-04)
- Diagnostics redaction → Phase 7 (DIAG-01)
- Daily cron CI against `pronotepy@main` → Phase 7 (DIST-04)
- Brand assets for HACS → v2+
- pronotepy upgrade beyond 2.14.6 → only when spike or real bug forces it

---

*Discussion conducted: 2026-05-03*
