# Deferred Items — Phase 02

Cross-cutting issues found during plan execution that are **not** caused by
the current plan's changes and are therefore out of scope per the executor's
SCOPE BOUNDARY rule.

## Pre-existing ruff lint findings (logged during Plan 02-04)

Discovered while running `ruff check custom_components tests scripts` from inside
Plan 02-04's executor. None of these files were modified by Plan 02-04. They are
left alone per SCOPE BOUNDARY:

- `tests/conftest.py:15` — `PT022 No teardown in fixture, use return instead of yield`
  - Authored by Phase 1 (commit `35a4f9b`).
- `custom_components/ha_pronote/api/fetcher.py` — `ruff format` would reformat
  - Authored by Plan 02-01 / 02-02 (commits `bb359da`, `4b211b1`).
- `scripts/snapshot.py` — `ruff format` would reformat
  - Authored by Plan 02-01 / 02-02 (commits `2ee7527`, `d1ddaa0`).
- `tests/test_api/test_fetcher.py` — `ruff format` would reformat
  - Authored by Plan 02-01 / 02-02.
- `tests/test_manifest.py` — `ruff format` would reformat
  - Authored by Phase 1.

CI (`.github/workflows/lint.yml`, Phase 1) is the appropriate gate for fixing
these. They do not affect Plan 02-04's gates: tests pass, coverage ≥ 90%,
HA-import guard exits 0, fixture round-trip exits 0, tz matrix passes.
