---
phase: 02-api-diff-layer-ha-free
plan: 02
subsystem: spike
tags: [pronotepy, real-pronote, anonymization, fixtures, security, bain3-311]

# Dependency graph
requires:
  - phase: 02-api-diff-layer-ha-free / 02-01
    provides: |
      api.build_client + api.fetch_all sync facade + scripts/snapshot.py
      one-shot CLI + .env.example + .gitignore for raw spike output
provides:
  - "Six anonymized real-Pronote fixture pairs at tests/fixtures/real/"
  - "tests/fixtures/SPIKE-FINDINGS-bain3-311.md — empirical findings memo (S-01..S-04)"
  - ".replacements.json contract (gitignored) — per-developer PII stand-in map"
  - "scripts/snapshot.py --anonymize-only mode — re-anonymize without re-fetch"
  - "Three production bug fixes triggered by the spike (api/fetcher.py defensive grades fallback + information_and_surveys() method-call + .env.example ?login=true documentation)"
affects:
  - 02-03-diff-lessons
  - 04-sensors-events
  - 07-quality-distribution-diagnostics

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Externalised PII map: secrets-class data lives in a per-developer gitignored JSON (mirrors .env), never in committed source"
    - "Spike-driven defensive coding: each runtime failure gets a fix + dedicated regression test before continuing the spike"

key-files:
  created:
    - "tests/fixtures/real/cancellation_T0.json"
    - "tests/fixtures/real/cancellation_T1.json"
    - "tests/fixtures/real/room_change_T0.json"
    - "tests/fixtures/real/room_change_T1.json"
    - "tests/fixtures/real/teacher_swap_T0.json"
    - "tests/fixtures/real/teacher_swap_T1.json"
    - "tests/fixtures/SPIKE-FINDINGS-bain3-311.md"
  modified:
    - "scripts/snapshot.py — _build_replacements(env, extra=None) + _load_replacements_file() + --anonymize-only mode"
    - "tests/test_scripts/test_snapshot.py — 7 new tests for the loader contract"
    - "tests/test_api/test_fetcher.py — 3 new regression tests (KeyError grades, AttributeError grades, information_and_surveys is a method)"
    - "custom_components/ha_pronote/api/fetcher.py — defensive grades wrap + information_and_surveys() call site"
    - ".gitignore — added .replacements.json"
    - ".env.example — documented ?login=true requirement"

key-decisions:
  - "PII replacement map externalised to .replacements.json (gitignored) — committing teacher names in source code is the same threat class as committing secrets, even when they don't reach the anonymized output."
  - "Accept S-04 (no empirical lessons-diff captured) and proceed to Plan 02-03 against pronotepy's documented Lesson model + synthetic fixtures. Empirical re-validation is deferred to Phase 4."
  - "Lock the identity-vs-content split here: identity = (date, start, end, subject); content = (canceled, classroom, teacher). Plan 02-03 must respect this contract."

patterns-established:
  - "Spike-driven test-first: every runtime failure surfaced by the spike against real Pronote becomes a regression test in the synthetic suite, so future plan agents cannot reintroduce the bug."
  - "Anonymizer correctness gate: scripts/snapshot.py exits non-zero when the anonymized output still contains a token from the replacement map's keys — fail-loud, not silent leak."

requirements-completed: [EVENT-05]

# Metrics
duration: ~90min (interactive, spread across multiple snapshot iterations + 3 source fixes)
completed: 2026-05-06
---

# Plan 02-02: Real-Pronote Spike Summary

**Empirical pronotepy 2.14.6 ground-truth captured against the author's live Pronote instance — three production bugs found and fixed before the diff layer is even written.**

## Performance

- **Duration:** ~90 minutes (interactive — user-side .env setup + 6 captures + 3 production fixes round-trips)
- **Started:** 2026-05-06 (orchestrator handoff)
- **Completed:** 2026-05-06
- **Tasks:** 3 spike outputs (6 fixtures + findings memo + summary) + 3 source fixes
- **Files modified:** 8 (3 production code, 2 tests, 3 docs/config)

## Accomplishments

- **6 anonymized real-Pronote fixtures committed.** PII-clean (114 audit checks pass), round-trippable through `Snapshot.from_dict`, stable identity keys for the diff layer to consume.
- **3 production-code bugs surfaced and fixed BEFORE Plan 02-03 starts coding.** Without the spike, the diff layer would have been built on a fetcher that crashed on every real Pronote call.
- **PII-safe anonymizer architecture.** Replacement map lives outside the committed tree; `--anonymize-only` mode means future fixture refreshes don't require re-triggering teacher-side changes.

## Task Commits

This plan was not executed by an automated agent — it ran as an interactive
checkpoint between the orchestrator and the user. Commits are therefore
broken down by deliverable rather than by literal plan task:

1. **Defensive grades fallback (S-01)** — `174413c` (fix)
2. **`information_and_surveys()` method call + `?login=true` doc (S-02 + S-03)** — `4b211b1` (fix)
3. **Anonymizer refactor: replacements externalised to `.replacements.json`** — `d1ddaa0` (refactor)
4. **6 anonymized fixtures + SPIKE-FINDINGS memo** — current head before this commit (feat)

**Plan metadata:** this file (docs).

## Files Created/Modified

**Committed:**

- `tests/fixtures/real/{cancellation,room_change,teacher_swap}_{T0,T1}.json` — 6 anonymized snapshots
- `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` — empirical findings memo (canonical source for Plan 02-03)
- `scripts/snapshot.py` — `_load_replacements_file()`, `_build_replacements(env, extra=None)`, `--anonymize-only` mode
- `tests/test_scripts/test_snapshot.py` — 7 new tests for the loader + gitignore contract
- `tests/test_api/test_fetcher.py` — 3 new regression tests
- `custom_components/ha_pronote/api/fetcher.py` — defensive grades wrap + method-call fix
- `.gitignore` — `.replacements.json` added to Phase 2 spike-output block
- `.env.example` — `?login=true` requirement documented

**Gitignored (local-only):**

- `.env` — author's real credentials
- `.replacements.json` — author's PII replacement map (18 teacher names + 1 principal surname)
- `tests/fixtures/real/_raw_*.json` — 6 raw, unanonymized captures

## Decisions Made

- **PII replacements live outside source.** The first spike attempt put teacher names in `_build_replacements()` directly; this would have shipped 18 real names in `git log` forever. Refactored to a gitignored JSON file. Same threat class as `.env` — same mitigation.
- **`--anonymize-only` is a first-class mode, not a debug flag.** Users will extend `.replacements.json` after a spike and need to re-anonymize without re-triggering Pronote teacher-side changes (which are expensive, rate-limited, or simply unavailable). Keeping the script idempotent on local raw files removes the operational pain.
- **Accept S-04 and move on.** The author's account is parent-side without teacher manipulation rights. Re-running the spike with teacher access would delay Phase 2 by days/weeks. Plan 02-03 builds the diff layer against the documented model + synthetic fixtures; Phase 4's first user-observed real schedule change is the empirical re-validation gate.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 — Bugs)

**1. `api/fetcher.py:61` — KeyError on parent accounts (S-01)**
- Found during: first `scripts/snapshot.py --scenario cancellation --phase T0` against the author's instance.
- Issue: `client.current_period.grades` raises `KeyError('listeDevoirs')` when Pronote omits the grades section. The previous `if client.current_period` guard only filtered the `None` case.
- Fix: nested `try/except (KeyError, AttributeError)` around the single line, downgrades to `grades=[]`. Lessons + information are the Core Value path — the snapshot must still produce.
- Committed in: `174413c`. Two regression tests in `tests/test_api/test_fetcher.py`.

**2. `api/fetcher.py:71` — `information_and_surveys` is a method (S-03)**
- Found during: second snapshot attempt after fixing S-01.
- Issue: `list(client.information_and_surveys)` raises `TypeError: 'method' object is not iterable`. Plan 02-01 wrote the access as a property; pronotepy 2.14.6 declares it as a method. The synthetic `_FakeClient` mirrored the bug, so the test suite passed.
- Fix: call with parens. `_FakeClient` updated to expose it as a method. MagicMock-based tests switched from `mock.x = []` to `mock.x.return_value = []`.
- Committed in: `4b211b1`. One regression test that locks the call site.

### Auto-fixed Issues (Rule 3 — Plan path issues)

**3. `.env.example` was silent on the `?login=true` requirement (S-02)**
- Found during: first snapshot attempt with the bare `parent.html` URL → `Page html is different than expected`.
- Issue: The plan agent inherited a `.env.example` with the demo URL (which doesn't need `?login=true`) but did not document that real instances often do. Operator-side problem, but a 30-minute time sink for any new contributor.
- Fix: 4-line comment block in `.env.example`.
- Committed in: `4b211b1`.

### Acknowledged Gaps

**4. No empirical lessons-diff captured (S-04)**
- Found during: post-anonymization audit comparing the 6 fixtures pairwise.
- Issue: All three T0/T1 pairs are byte-identical at the `lessons` level. The author has no teacher-side access and no naturally-occurring schedule change happened in the capture window.
- Mitigation: documented in `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` (S-04). Plan 02-03 builds against pronotepy's documented `Lesson` model + synthetic fixtures. Phase 4 verification is the empirical gate.
- **Not fixed in this phase.** Carried forward to Phase 4.

---

**Total deviations:** 3 fixed (2 production-code bugs, 1 doc gap), 1 acknowledged gap.

## What This Unblocks

Plan 02-03 (`diff/lessons.py`) can now start. Inputs to that plan:

- **Identity-vs-content key contract** locked by S-04 (this memo).
- **6 real fixtures** to round-trip through `Snapshot.from_dict` (Plan 02-04 schema gate test asserts this).
- **Documented pronotepy `Lesson` field set**: `canceled: bool`, `status: str`, `classroom: str`, `teacher_name: str`, `subject.name: str`, `start/end: datetime` (naive, school-local — localized in the fetcher).
- **bain3#311 reference** for any later question about pronotepy's mapping of Pronote's wire-format flags to `canceled/status`.

## Open Questions for Phase 4

- When the first real cancellation/room/teacher event happens on the author's instance, does `diff/lessons.py` correctly classify it? If it misclassifies, the diff layer is amended and a new T0/T1 pair is added to `tests/fixtures/real/`.
- For "lesson disappeared in T1 without prior `canceled=True`": is this ever a true cancellation, or always a Pronote-side data race? Phase 4 verification logs every such event for 1 month before deciding.

## Self-Check: PASSED

- 6 anonymized fixtures committed, 0 PII tokens detected (114-check audit pass).
- 6 raw `_raw_*.json` captures gitignored.
- `.replacements.json` gitignored.
- 74 tests pass, including 10 new regressions (S-01 × 2, S-03 × 1, .replacements.json loader × 7).
- SPIKE-FINDINGS-bain3-311.md committed at `tests/fixtures/SPIKE-FINDINGS-bain3-311.md`.
- Plan 02-03 has the full input it needs (identity/content keys, 6 fixtures, documented model, bain3#311 reference).
