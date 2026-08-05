---
status: partial
phase: 02-api-diff-layer-ha-free
source: [02-VERIFICATION.md]
started: 2026-05-06T14:30:00Z
updated: 2026-05-06T14:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. GitHub Actions test.yml runs green on push (both TZ matrix axes)
expected: |
  After pushing to a branch, the GitHub Actions test workflow runs and shows
  green for both matrix axes — `tz: Europe/Paris` and `tz: Pacific/Noumea` —
  on Python 3.14. The diff coverage gate (`--cov-fail-under=90`) is enforced
  on both axes. The HACS validation and hassfest jobs from Phase 1 also stay
  green. No quarantined skip count beyond the 7 known S-04 skips
  (4 real-fixture cancel/room/teacher + 1 missing-fixture probe + 2 in
  test_lessons_tz_matrix.py).
result: [pending]

### 2. `.env.example` documentation is sufficient for a new contributor
expected: |
  A new contributor reading `.env.example` understands that
  `?login=true` may be needed on real Pronote instances and is not just a
  cargo-cult artifact. (Note: full operator UX is deferred to the Phase 7
  README — this UAT item is a sanity check that the inline comment in
  `.env.example` is at least readable in isolation.)
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
