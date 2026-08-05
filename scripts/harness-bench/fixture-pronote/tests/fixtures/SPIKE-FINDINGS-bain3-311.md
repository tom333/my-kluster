# Spike findings — pronotepy 2.14.6 cancel/room/teacher semantics

**Captured:** Plan 02-02, 2026-05-06
**Source instance:** `katiramona.ac-noumea.nc` (parent account, NC vice-rectorat)
**pronotepy version:** 2.14.6
**Reference issue:** https://github.com/bain3/pronotepy/issues/311

This document is the empirical ground truth Plan 02-03 (`diff/lessons.py`)
must respect when distinguishing **cancellation**, **room change**, and
**teacher swap** events between two consecutive polls.

## Spike scope

Six fixture pairs were captured against the author's live Pronote instance:
`{cancellation, room_change, teacher_swap} × {T0, T1}`. Files live in
`tests/fixtures/real/`. The raw outputs (`_raw_*.json`) are gitignored;
only the anonymized `<scenario>_<phase>.json` pairs are committed
(security threats T-02-02-01 + T-02-02-02).

**Window:** J-7 → J+14 from capture date. 58 lessons in each snapshot.

## Findings

### S-01 — `current_period.grades` raises `KeyError('listeDevoirs')`

**Symptom.** On a parent-side account, `client.current_period.grades` may
raise `KeyError('listeDevoirs')` deep inside pronotepy's response parser
even when `client.current_period` is truthy (a period object exists).
This happens when Pronote does not expose the grades section for the
current period (e.g. before grades publication or when the parent is not
authorised to see them).

**pronotepy origin.** `pronotepy/dataClasses.py:526` does
`response["dataSec"]["data"]["listeDevoirs"]["V"]` without the listing key
guard.

**Mitigation in this codebase.** `api/fetcher.py` wraps the
`current_period.grades` access in `try/except (KeyError, AttributeError)`
and downgrades to `grades=[]`. Lessons + information are the Core Value
path — the snapshot must still produce. Regression locked by
`tests/test_api/test_fetcher.py::test_keyerror_on_current_period_grades_returns_empty_grades`
and `test_attributeerror_on_current_period_grades_returns_empty_grades`.

**Plan 02-03 implication.** Snapshots from real parent accounts may carry
`grades=[]`. The grades-diff stub (Phase 4) must accept empty lists as a
normal state, not a degraded one.

### S-02 — `PRONOTE_URL` requires `?login=true` query parameter

**Symptom.** `pronotepy.Client(url, ...)` raises
`pronotepy.PronoteAPIError: Page html is different than expected. Be sure
that pronote_url is the direct url to your pronote page.` on URLs of the
form `https://<host>/pronote/parent.html` (or `eleve.html`) without query
parameters.

**Cause.** Many real Pronote instances (including `ac-noumea.nc`) redirect
the bare `parent.html`/`eleve.html` URL to an ENT/portal/JavaScript
landing page that pronotepy's `_parse_html` cannot parse. Adding
`?login=true` forces the direct login form.

**Mitigation.** `.env.example` documents the `?login=true` requirement.
No code change — pronotepy already raises a clear error message.

**Plan 02-03 implication.** None. `.env`/Config Flow concern only.
Carries forward to Phase 3's Config Flow validator: the form must accept
URLs with `?login=true` and not strip query parameters.

### S-03 — `Client.information_and_surveys` is a method, not a property

**Symptom.** `list(client.information_and_surveys)` raises
`TypeError: 'method' object is not iterable`.

**Cause.** pronotepy 2.14.6 declares `information_and_surveys` as a
function on `Client` and `ParentClient` (verified via
`inspect.getmembers(pronotepy.Client)`). Plan 02-01 wrote it as an
attribute access, mirrored by the `_FakeClient` test fake — both wrong,
both consistent with each other, missed by the synthetic test suite.

**Mitigation.** `api/fetcher.py` now calls
`client.information_and_surveys()`. `_FakeClient` and the regression
tests now expose it as a method. Regression locked by
`tests/test_api/test_fetcher.py::test_information_and_surveys_is_called_as_method_not_iterated_as_attribute`.

**Plan 02-03 implication.** None. Same shape on the snapshot side.

### S-04 — No empirical lessons-diff was captured

**Symptom.** All three T0→T1 pairs produced **byte-identical lessons
arrays** (58 lessons each, no field changes, no additions, no removals).
Only the `information` array differed (school messages added/removed
between captures).

**Cause.** The captures were taken on the author's parent account without
teacher-side ability to manipulate the Pronote schedule. The plan's
fallback ("naturally-occurring schedule change in the next school week")
did not materialize in the capture window.

**Consequence.** This spike does **not** ground the cancel/room/teacher
semantics empirically. Plan 02-03 (`diff/lessons.py`) must build against:

1. **pronotepy 2.14.6's documented `Lesson` model** —
   `Lesson.canceled: bool`, `Lesson.status: str`, `Lesson.classroom: str`,
   `Lesson.teacher_name: str`. Source: `pronotepy/dataClasses.py:300+`.
2. **The bain3#311 thread's reported behavior** — the issue documents
   that pronotepy maps Pronote's `couleurFond`/`indicateurAbsence` to
   `canceled`/`status`. Read:
   https://github.com/bain3/pronotepy/issues/311
3. **Synthetic fixtures** under `tests/fixtures/synthetic/` (created by
   Plan 02-03) — `cancellation_T0/T1`, `room_change_T0/T1`,
   `teacher_swap_T0/T1` constructed by hand from the documented model.

**Plan 02-03 design rule (locked here).** The diff layer treats
identity-vs-content as:

- **Identity key** (stable across normal life of a lesson):
  `(date, start, end, subject)`.
- **Content keys** (compared between T0 and T1 for the same identity):
  - `canceled` (bool) → if `False → True` ⇒ emit `change_type=canceled`
  - `classroom` (str) → if value differs ⇒ emit `change_type=room`
  - `teacher` (str) → if value differs ⇒ emit `change_type=teacher`
- **Lesson disappeared** (identity in T0 not in T1) **without prior
  `canceled=True`** ⇒ emit `change_type=removed`. *Cannot be empirically
  distinguished from a Pronote bug or a polling race* — this is a known
  ambiguity carried forward to Phase 4 verification.
- **Lesson appeared** (identity in T1 not in T0) ⇒ emit
  `change_type=added`. Same caveat.

**Plan 02-03 must include in its SUMMARY** an explicit note that the
empirical cancel/room/teacher behavior was not observed, and that
Phase 4's verification gate is the first place this code path will be
validated against real Pronote in motion.

**Phase 4 follow-up.** The first user-observed real cancellation /
room change / teacher swap on the author's instance MUST be re-captured
as a `tests/fixtures/real/<scenario>_<phase>.json` pair (using
`scripts/snapshot.py`) and the `diff/lessons.py` algorithm re-validated
against it. If the algorithm misclassifies any of the three scenarios,
the diff layer is amended and Plan 02-03's tests are extended.

## Summary table

| Finding | Severity | Code change | Doc change | Carries to |
|---------|----------|-------------|------------|------------|
| S-01 | High (blocks fetch_all on parent accounts) | `fetcher.py` defensive wrap | — | Phase 4 grades stub |
| S-02 | Low (operator-side; clear error) | — | `.env.example` | Phase 3 Config Flow URL validator |
| S-03 | High (would have crashed every real fetch) | `fetcher.py:71` + `_FakeClient` | — | — |
| S-04 | Medium (assumption risk) | — | This file | Phase 4 verification, Plan 02-03 must-haves |

## Source data

- `tests/fixtures/real/cancellation_T0.json` + `_T1.json`
- `tests/fixtures/real/room_change_T0.json` + `_T1.json`
- `tests/fixtures/real/teacher_swap_T0.json` + `_T1.json`

Each fixture is anonymized via `scripts/snapshot.py` against
`.replacements.json` (gitignored). Round-trip safety locked by
`tests/test_fixtures.py` (Plan 02-04).
