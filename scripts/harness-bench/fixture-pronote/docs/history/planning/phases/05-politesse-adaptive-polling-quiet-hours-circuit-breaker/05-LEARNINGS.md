---
phase: 05
phase_name: "Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker"
project: "HA-Pronote — Intégration Home Assistant pour Pronote"
generated: "2026-05-25"
counts:
  decisions: 12
  lessons: 8
  patterns: 11
  surprises: 7
missing_artifacts: []
---

# Phase 5 Learnings: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker

## Decisions

### Atomic event gate at top of `_fire_diff_events` (D-09 prose override)
`should_fire_event(now, options)` is queried **once** at the top of `_fire_diff_events`; all four diff loops downstream then fire atomically per poll or none. `_previous_snapshot` mutation still happens BEFORE this method (CR-03 ordering preserved) so the next non-quiet poll diffs against a fresh baseline.

**Rationale:** PATTERNS.md Specifics memo overrode the D-09 prose interpretation. A per-loop predicate would have produced partial event-firing if quiet-hours boundary fell mid-method.
**Source:** 05-03-SUMMARY.md (decisions)

---

### V-16 threshold lowered from ≥5 to ≥3 distinct cadences
`test_24h_synthetic_clock_tz_matrix_produces_at_least_5_distinct_intervals` originally asserted ≥5 distinct minute-rounded cadences across a 7-timestamp set. `compute_interval` only has 4 branches and the chosen timestamps trigger 3 of them — values collapse to {15, 30, 240}.

**Rationale:** Threshold was mathematically unachievable. Lowered to ≥3 to match runtime behavior; test intent (prove `update_interval` mutates across a 24h walk) preserved.
**Source:** 05-03-SUMMARY.md (Rule 1 auto-fix bug)

---

### V-17 sampling reduced from 84 iters to 28 strategic samples
Plan called for every-2-hour sampling across 168h (84 iterations) but `pytest-timeout=1s` per test (D-28) would blow the timeout (~4s).

**Rationale:** Reduced to 4 strategic times per day (3am/9am/15h/23h × 7 days = 28 iters) covering both quiet and non-quiet windows. Atomic-gate verification intent preserved.
**Source:** 05-03-SUMMARY.md (Rule 1 auto-fix bug)

---

### `_resolve_options` uses `(ValueError, TypeError)` only — never bare `except`
Per `feedback_no_silent_exceptions.md`: typed exceptions propagate raw. The fallback logs a warning + returns default; the warning IS the trace.

**Rationale:** User feedback memory explicitly rejects mapped error handling — let HA's stock 500 + traceback surface.
**Source:** 05-03-SUMMARY.md (decisions) + memory/feedback_no_silent_exceptions.md

---

### `_handle_failure` is ADDITIVE: ticks counter + creates notification BEFORE re-raising
The breaker tick happens before the existing `raise UpdateFailed(...)` / `raise ConfigEntryAuthFailed(...)` propagates.

**Rationale:** Pure additive design preserves the typed-exception contract from Phase 3 D-22 verbatim. The notification is a side-effect; the raise is the source-of-truth.
**Source:** 05-03-SUMMARY.md (tech_stack patterns) + memory/feedback_no_silent_exceptions.md

---

### `holidays==0.97` exact pin (matches `pronotepy==2.14.6` discipline)
Phase 1 D-14 "exact-pin discipline" extended to the new runtime dep.

**Rationale:** Avoid the resolver-thrash class of bugs HA's `manifest.json` requirements list is prone to; PyPI metadata verified 2026-05-25.
**Source:** 05-02-SUMMARY.md (decisions)

---

### `TROUBLESHOOTING_DOC_URL_BASE` with `<placeholder-owner>` literal substring
Const holds the base URL only (no `#` anchor); coordinator's `_format_notification` builds the kind-specific anchor via `f"{BASE}#troubleshooting-{kind.replace('_', '-')}"`.

**Rationale:** Single-source URL composition (BLOCKER-3 fix). Phase 7 DIST-07 fills the placeholder; tests assert on the anchor not the base, so they remain valid post-Phase-7.
**Source:** 05-02-SUMMARY.md, 05-03-SUMMARY.md (decisions)

---

### `holiday_dates.py` as neutral helper sibling module (WR-2)
Sibling to `politesse.py`. Both `coordinator.py` and `__init__.py` import via `from .holiday_dates import compute_holiday_dates_for_year` — never function-local imports.

**Rationale:** Removes function-local-import coupling and gives the AST guard a clean target. Mirrors the `api/_strip.py` module-shape precedent.
**Source:** 05-02-SUMMARY.md (decisions)

---

### `NC_LOCAL_HOLIDAYS_SUPPLEMENT` stays `frozenset()`
The C-03 probe confirmed zero discrepancy between `holidays.France(subdiv='NC', years=2026)` and the RESEARCH.md baseline (12/12 dates including Fête de la Citoyenneté 24/09).

**Rationale:** No supplement override needed; keeps the union with `compute_holiday_dates_for_year` a no-op for 2026. Forward-compatible if NC adds a custom holiday later.
**Source:** 05-02-SUMMARY.md (decisions)

---

### MagicMock (not AsyncMock) for `persistent_notification`
`@callback` synchronous functions; `MagicMock` is the right tool.

**Rationale:** RESEARCH.md verified that `async_create` + `async_dismiss` are `@callback`, not coroutines. Using AsyncMock would silently coerce results to coroutines and break the call-args inspection in V-21.
**Source:** 05-03-SUMMARY.md (tech_stack patterns)

---

### Module-level autouse `_frozen_school_day` fixture (NOT conftest-level)
Pinning at the test module level narrows blast radius. Pure-Python `test_politesse_tz_matrix.py` / `test_holiday_dates.py` / `test_no_ha_imports.py` keep their synthetic-`now` contracts intact (D-20).

**Rationale:** A conftest-level autouse pin would silently corrupt the pure-pytest modules that assert against real `holidays.France(subdiv='NC')` calendar lookups.
**Source:** 05-04-SUMMARY.md (key-decisions)

---

### Pin date chosen for 4 simultaneous properties
Thu 2026-05-07 14:00 Pacific/Noumea satisfies: weekday=3 (Thursday), NOT in `NC_VACATION_RANGES_2026`, NOT in `holidays.France(subdiv='NC')`, NOT in afternoon window [17:00, 20:00), NOT in quiet hours [22:00, 06:00).

**Rationale:** Net result: `should_poll == True`, `is_afternoon_window == False`, `is_quiet_hours == False`. Coordinator falls through both `_async_update_data` short-circuits and reaches `fetch_all` — exactly the assumption baked into Phase 3/4-era tests.
**Source:** 05-04-SUMMARY.md (Pin date and 4 verified properties)

---

## Lessons

### Real `dt_util.now()` in tests can collide with politesse short-circuit on férié days
14 Phase 3/4-era tests passed for weeks, then broke the day Phase 5 shipped — because today (2026-05-25) is Pentecôte, a NC férié, and Plan 05-03's `should_poll` short-circuit returns True (poll suspended) → tests never reach the executor branch they're asserting on.

**Context:** Production code was correct; the failure was a test-vs-real-clock collision. The fix was pure test infrastructure (freezegun pin), not a production bug.
**Source:** 05-04-PLAN.md (objective), 05-04-SUMMARY.md (Accomplishments)

---

### 24h-stride synthetic-clock loops can land on OTHER fériés
V-08 (`test_3_consecutive_auth_failures_set_backoff_4h_and_notification`) used `t0 = Tue 2026-05-12 14:00 NC` + 24h stride. The 3rd strike lands on **Ascension Day 2026-05-14** — also a NC férié. "DID NOT RAISE" was hidden behind a 2nd short-circuit at a different stride position.

**Context:** Discovered via the captured pytest log showing the exception NOT raised at the `2026-05-14 14:00:00` freezer tick — Hypothesis 0 diagnostic. Resolved by re-anchoring t0 to Mon 2026-05-18 (post-Ascension, pre-Pentecôte, outside vacation).
**Source:** 05-04-SUMMARY.md (Issues Encountered + Decisions Made)

---

### Worktree cwd-drift bug recurred in the same phase (Plans 05-02 AND 05-04)
Both Plan 05-02's executor and Plan 05-04's executor wrote initial Edit/Write calls to the parent project path instead of the worktree path. Plan 05-04 was hit even after the orchestrator pre-spawn warning called it out from 05-02.

**Context:** The cwd-drift sentinel from `worktree-path-safety.md` was not set up before the first Bash call; the `[ -f .git ]` worktree guard was bypassed because the main repo's `.git` is a directory, not a file.
**Source:** 05-03-SUMMARY.md (Worktree path-write error), 05-04-SUMMARY.md (Auto-fixed Issue 1)

---

### `requirements_test.txt` vs PHACC version pin is mutually unsatisfiable
`requirements_test.txt` pins `homeassistant==2026.4.4`, but `pytest-homeassistant-custom-component==0.13.326` declares `Requires-Dist: homeassistant==2026.5.0b0`. Locally surfaces when `uv pip install` tries to satisfy both pins simultaneously; CI's `uv pip install --system` resolves transitively and dodges it.

**Context:** Hit in Plan 05-01 (worktree venv bootstrap) and Plan 05-04 (worktree venv missing `holidays`). Pre-existing requirements-pinning bug unrelated to Phase 5; logged for a future infra plan.
**Source:** 05-01-SUMMARY.md (Issues Encountered), 05-04-SUMMARY.md (Auto-fixed Issue 2)

---

### Plan-recommended `yield freezer` triggered ruff PT022
PT022 ("No teardown in fixture") flagged `yield freezer` since pytest-freezer auto-teardowns. The plan's recommended pattern was wrong against the project's ruff config.

**Context:** Switched to `return freezer` — behavior identical, matches existing `auto_enable_custom_integrations` autouse pattern in `tests/conftest.py:20-27`.
**Source:** 05-04-SUMMARY.md (Decisions Made)

---

### V-16 math: 4 branches × 7-timestamp set = only 3 distinct minute-rounded cadences
The Plan's `>=5 distinct` assertion would have required at least 5 of `compute_interval`'s 4 branches to fire — impossible.

**Context:** Caught during Plan 05-03 Task 3 (writing V-16). Plan-time arithmetic missed the branch count vs distinct-output mapping. Lesson for future plan assertions: count the range, not the domain.
**Source:** 05-03-SUMMARY.md (Rule 1 auto-fix bug)

---

### TC003 flags eager `date` import when `from __future__ import annotations` is active
Ruff's TC003 demands `from datetime import date` live inside `if TYPE_CHECKING:` when `date` only appears in an annotation under `from __future__ import annotations`.

**Context:** Hit in `holiday_dates.py`; resolved by adding `from typing import TYPE_CHECKING` and guarding the `date` import. Annotation still resolves at runtime via the `__future__` stringification.
**Source:** 05-02-SUMMARY.md (Auto-fixed Issue 2)

---

### Worktree venv bypass via main repo's already-bootstrapped `.venv`
When the worktree's `.venv` is missing a package (`holidays`) and `uv pip install` fails on a transitive pin conflict (PHACC homeassistant pin), invoking `/data/projets/perso/pronote/.venv/bin/python -m pytest ...` directly from the main repo's venv runs tests against the worktree's source files without needing to fix the worktree venv.

**Context:** Workflow recovery for Plan 05-04; the main venv has the full PHACC-transitive dep set.
**Source:** 05-04-SUMMARY.md (Auto-fixed Issue 2)

---

## Patterns

### Pure HA-free predicate module (D-16)
`@dataclass(frozen=True)` options snapshot + free functions taking `now` + options, no module state, no I/O, no `try/except`. Imports stdlib only — no `homeassistant.*`, no `holidays` (those defaults flow through `PolitesseOptions`).

**When to use:** Any algorithmic/decision-making code you want to test under pure pytest without the HA harness, and want to keep portable to other runtimes (e.g. a future async fork).
**Source:** 05-01-SUMMARY.md (patterns-established)

---

### Injectable RNG (D-19)
`rng: random.Random | random = random` keyword-only param duck-types `.uniform`. Tests pass `rng=random.Random(seed=42)` for reproducibility.

**When to use:** Anywhere stochastic behavior (jitter, retry backoff, sampling) needs deterministic testing without freezing or monkey-patching the global `random`.
**Source:** 05-01-SUMMARY.md (patterns-established)

---

### File-name-driven `pytest -k` selector
Test file name carries a substring (e.g. `tz_matrix`) so a single `pytest -k "tz_matrix"` invocation resolves every collected case in the module.

**When to use:** When VALIDATION.md needs a single selector that resolves a group of related TZ-matrixed or scenario-specific tests across multiple files.
**Source:** 05-01-SUMMARY.md (patterns-established; precedent: tests/test_diff/test_lessons_tz_matrix.py)

---

### AST guard tripwire as plan-ordering forcing function
Extending `GUARDED_PATHS` with files that another (parallel-wave) plan must ship makes `test_guarded_paths_are_not_empty` a forcing function for wave-merge ordering.

**When to use:** Parallel-wave plans where Plan A guards a file that Plan B creates. The test fails until Plan B lands — intended behavior, surfaces ordering bugs early.
**Source:** 05-01-SUMMARY.md (patterns-established)

---

### Module-level autouse freezegun pin
`@pytest.fixture(autouse=True)\ndef _frozen_school_day(freezer): freezer.move_to(...); return freezer`. Tests with their own clock requirements override via `freezer.move_to(...)` at body top.

**When to use:** Any test module driving date-sensitive coordinator paths where the real clock could collide with politesse short-circuits. NOT at conftest level — pure-Python politesse/holiday tests rely on real calendar lookups.
**Source:** 05-04-SUMMARY.md (patterns-established)

---

### Jitter envelope assertion
`abs(actual.total_seconds() - expected_seconds) <= JITTER_SECONDS + 5`. The `+5` absorbs minute-rounding artifacts; `JITTER_SECONDS` is the central source-of-truth.

**When to use:** Anywhere you assert on a `compute_interval` result that includes jitter without disabling jitter; preserves the Plan 05-01 contract while keeping the test deterministic.
**Source:** 05-04-SUMMARY.md (patterns-established)

---

### Clean-week anchor for synthetic-stride tests
Mon 2026-05-18 → Thu 2026-05-21 — post-Ascension (2026-05-14), pre-Pentecôte (2026-05-25), outside NC school vacation. Document the dodge in the test docstring so future edits don't break the assumption.

**When to use:** 24h-stride or week-stride synthetic-clock tests that iterate across multiple weekdays. Check the stride positions against `holidays.France(subdiv='NC', years=YEAR)` before committing.
**Source:** 05-04-SUMMARY.md (patterns-established)

---

### Atomic event gate (PATTERNS.md Specifics override of D-09 prose)
Query the gating predicate ONCE at the top of the dispatching method; all downstream loops fire atomically per call or none. Mutate prior-state baseline BEFORE the gate so the next non-gated call diffs against fresh state.

**When to use:** Any per-poll event-firing method where partial firing (some events through, some suppressed) would corrupt downstream consumer state.
**Source:** 05-03-SUMMARY.md (decisions)

---

### MagicMock dual-patch (source module + import-site binding)
For `@callback` (synchronous) HA helpers like `persistent_notification.async_create`, patch BOTH the source module path AND the import-site binding inside the SUT.

**When to use:** When the SUT imports a callable via `from x import y` (binding-time) — patching only `x.y` won't catch the call; the SUT's local binding holds the unpatched reference.
**Source:** 05-03-SUMMARY.md (tech_stack patterns)

---

### Probe + auto-approve-under-AUTO_MODE checkpoint
One-off script that prints public data + asserts a fail-fast invariant; output captured into a fixture with HUMAN-UAT sign-off. Under AUTO_MODE the contract (exit code 0 + specific dates present) auto-approves; the sign-off section documents the auto-approval origin for downstream transparency.

**When to use:** Probe-style human-verify checkpoints where the verification contract is mechanical (assertion-based) — auto-approval is safe AND the audit trail still records the AUTO_MODE origin.
**Source:** 05-02-SUMMARY.md (AUTO_MODE checkpoint behavior + Decisions Made)

---

### Neutral helper sibling module (WR-2)
When two modules need to call into shared logic, ship the shared logic as a sibling module rather than have one module import from the other (or worse, use function-local imports). Both call sites then import via `from .helper import func`.

**When to use:** When a function-local import would otherwise hide a coupling, or when two equal-level modules need the same logic. Mirrors `api/_strip.py` shape from Phase 2.
**Source:** 05-02-SUMMARY.md (decisions), 05-03-SUMMARY.md (key links)

---

## Surprises

### Plan 05-03's correct production code was hidden behind 14 test failures because today happened to be Pentecôte
The day Plan 05-03 shipped, the project's CI/local clock advanced into 2026-05-25 (Pentecôte). Plan 05-03's `should_poll` short-circuit kicked in for tests that previously assumed the executor branch always runs. 14 previously-green tests went red even though the production code was correct per D-10/D-13/D-15.

**Impact:** Required a full new gap-closure plan (05-04) to fix test infrastructure without touching production. Re-enabled V-08/V-15/V-16/V-17/V-20/V-21 from the test harness.
**Source:** 05-04-PLAN.md (objective), 05-VERIFICATION.md (test gate)

---

### V-08's "DID NOT RAISE" was hidden behind Ascension Day, not the freezegun fix
After Plan 05-04 Task 1's autouse fixture, V-08 STILL failed. The 24h-stride synthetic clock landed the 3rd strike on Ascension Day 2026-05-14 — yet another NC férié, hit by the same `should_poll` short-circuit but at a different stride position.

**Impact:** Required Task 2 (Hypothesis 0 contingency arm) to re-anchor V-08's t0 from Tue 2026-05-12 to Mon 2026-05-18. Production code stayed untouched; Hypotheses 1-5 (`_handle_failure` / `_recover_from_auth_error` / `_format_notification`) not invoked.
**Source:** 05-04-SUMMARY.md (Issues Encountered, Decisions Made)

---

### V-16 threshold was mathematically unachievable
The Plan's `>=5 distinct minute-rounded cadences` assertion required at least 5 of `compute_interval`'s 4 branches to fire from a 7-timestamp set. Even with all 4 branches hit, the minute-rounded outputs collapse to 4 values; the chosen 7 timestamps only triggered 3 branches.

**Impact:** Plan 05-03 Rule 1 auto-fix bug lowered threshold to `>=3`. Future plan reviews should count the range, not the domain.
**Source:** 05-03-SUMMARY.md (Rule 1 auto-fix bug)

---

### Worktree cwd-drift bug hit twice in the same phase
Plan 05-02's executor and Plan 05-04's executor BOTH wrote initial Edit/Write calls to the parent project path. Plan 05-04 hit it despite the orchestrator's pre-spawn warning carrying the lesson from 05-02.

**Impact:** Both required recovery commits (cherry-pick onto worktree + revert on main per #2924 — no protected-ref rewind). Audit trail of the drift is preserved in main's git log; the production diff lands cleanly via the worktree branch merge.
**Source:** 05-03-SUMMARY.md (Worktree path-write error), 05-04-SUMMARY.md (Auto-fixed Issue 1)

---

### Plan 05-04 itself was discovered AFTER Plan 05-03 shipped
The gap surfaced only when the test suite ran post-merge on real-clock Pentecôte. There was no plan-time signal that today's date would collide with the short-circuit; the bug had to manifest in real time before it could be planned.

**Impact:** Phase 5 grew from 3 plans (initial scope) to 4 plans (gap closure added Wave 3 mid-phase). The gap-closure plan was modeled as a separate plan with `gap_closure: true` frontmatter so it could be re-executed via `--gaps-only`.
**Source:** 05-04-PLAN.md (objective: "This is NOT a production bug in Plan 05-03's runtime")

---

### Plan-recommended `yield freezer` was wrong against project ruff config
The plan's verbatim fixture body used `yield freezer`, but ruff PT022 ("No teardown in fixture") fires because pytest-freezer auto-teardowns and there's nothing to clean up. The plan was written without checking the project's ruff rule set.

**Impact:** Switched to `return freezer` — behavior identical. Lesson: plan-time test scaffolds should be linted before being committed verbatim.
**Source:** 05-04-SUMMARY.md (Decisions Made)

---

### PHACC's transitive `homeassistant` pin doesn't match the project's `requirements_test.txt`
`requirements_test.txt` pins `homeassistant==2026.4.4`. `pytest-homeassistant-custom-component==0.13.326` declares `Requires-Dist: homeassistant==2026.5.0b0`. uv refuses to resolve both pins simultaneously; CI's transitive resolver dodges it.

**Impact:** Both Plan 05-01 and Plan 05-04 had to bootstrap their worktree venv around this. Logged for a future infra plan (out of scope for Phase 5).
**Source:** 05-01-SUMMARY.md (Issues Encountered), 05-04-SUMMARY.md (Auto-fixed Issue 2)
