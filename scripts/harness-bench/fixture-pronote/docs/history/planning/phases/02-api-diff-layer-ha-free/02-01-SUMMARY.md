---
phase: 02-api-diff-layer-ha-free
plan: 01
subsystem: api
tags: [pronotepy, dataclass, frozen-dataclass, zoneinfo, requests-mock, ruff, pytest, error-hierarchy, sync-facade, executor-boundary, tz-aware, anonymizer]

# Dependency graph
requires:
  - phase: 01-foundations-skeleton
    provides: |
      pronotepy==2.14.6 manifest pin (D-14), pyproject ruff target-version=py314 +
      banned-api (pytz/async_timeout/requests), root tests/conftest.py PHACC autouse,
      requirements_test.txt (homeassistant + PHACC), .gitignore Phase 1 entries
provides:
  - "custom_components/ha_pronote/api/ pure-Python sync facade (zero homeassistant.* imports)"
  - "ErrorReason 7-member StrEnum + 4 typed exception subclasses (D-22)"
  - "Lesson/Grade/Information/Snapshot frozen dataclasses with to_dict/from_dict and tz-aware datetimes (D-11, D-16, D-23)"
  - "build_client(url, account_type, username, password) — pronotepy facade with full error mapping"
  - "fetch_all(client, today, school_tz, child_index_or_identifier=None) — J-7..J+14 window orchestrator (D-15, D-21)"
  - "_strip_client_refs back-ref walker (D-24, C-05)"
  - "scripts/snapshot.py CLI + deterministic anonymizer (C-03, D-12, D-13)"
  - ".env.example public-demo-only (security_gate threat #1 mitigation)"
  - "requirements_test.txt explicit requests-mock==1.12.1 pin (D-26)"
  - "const.py DEFAULT_SCHOOL_TZ + lookback/lookahead defaults (Phase 3 input)"
affects:
  - 02-02-spike-run
  - 02-03-diff-lessons
  - 03-coordinator
  - 04-sensors-events
  - 05-politesse-circuit-breaker
  - 07-quality-distribution-diagnostics

# Tech tracking
tech-stack:
  added:
    - "requests-mock==1.12.1 (explicit pin in requirements_test.txt; was transitive via PHACC)"
  patterns:
    - "Sync-facade pattern (api/) with strict pure-Python boundary; coordinator wraps in async_add_executor_job (Phase 3)"
    - "Typed error hierarchy with ErrorReason StrEnum — Phase 5 keys circuit-breaker on `.reason`"
    - "Frozen-dataclass DTOs with idempotent to_dict/from_dict and naive-datetime rejection at parse time"
    - "Pronotepy back-ref strip walker (defense-in-depth) + field-by-field copy (primary defense)"
    - "Local pytest conftest override of root autouse — keeps HA-free test trees free of PHACC"
    - "scripts/* per-file ruff ignore (T20/INP001/S603/S607/D) — one-shot dev tooling"

key-files:
  created:
    - "custom_components/ha_pronote/api/__init__.py"
    - "custom_components/ha_pronote/api/errors.py"
    - "custom_components/ha_pronote/api/models.py"
    - "custom_components/ha_pronote/api/_strip.py"
    - "custom_components/ha_pronote/api/client.py"
    - "custom_components/ha_pronote/api/fetcher.py"
    - "scripts/snapshot.py"
    - ".env.example"
    - "tests/test_api/__init__.py"
    - "tests/test_api/conftest.py"
    - "tests/test_api/test_errors.py"
    - "tests/test_api/test_models.py"
    - "tests/test_api/test_strip.py"
    - "tests/test_api/test_client.py"
    - "tests/test_api/test_fetcher.py"
    - "tests/test_scripts/__init__.py"
    - "tests/test_scripts/conftest.py"
    - "tests/test_scripts/test_snapshot.py"
  modified:
    - "custom_components/ha_pronote/const.py — appended DEFAULT_SCHOOL_TZ + lookback/lookahead defaults"
    - "requirements_test.txt — explicit requests-mock==1.12.1 pin"
    - ".gitignore — added .env + tests/fixtures/real/_raw_*.json"
    - "pyproject.toml — scripts/* per-file ruff ignore"

key-decisions:
  - "ErrorReason ships all 7 members in Phase 2 even though SESSION_EXPIRED and RATE_LIMITED are reserved for Phase 5 — D-22 mandates the full set so Phase 5 doesn't have to backfill (PC-02-05)"
  - "Naive datetime rejection lives in models.from_dict (raises ParseError), not silently coerced — fixtures with naive datetimes cannot round-trip, forcing tz-awareness at fixture authoring time (D-23, TIME-04)"
  - "_strip_client_refs uses hasattr+try/except (AttributeError, TypeError) to tolerate autoslot-based pronotepy objects — slot-only mutation can fail silently"
  - "Local override of root tests/conftest.py autouse for HA-free trees — preserves Phase 1's PHACC autouse for HA tests while letting api/ + scripts/ tests run without the HA harness (D-19)"
  - "scripts/* ruff per-file-ignore added inline so the script is held to a sensible subset of rules without downgrading the repo-wide ruleset"
  - "ZoneInfo runtime import moved into TYPE_CHECKING in fetcher.py — only used as a type annotation, the actual tz value is passed through `naive_dt.replace(tzinfo=school_tz)` and doesn't need an isinstance check"

patterns-established:
  - "Sync-facade pattern: every Phase 2 API entry point is plain `def`, callable in any thread; coordinator threads will wrap in async_add_executor_job"
  - "Error contract pattern: every typed exception ships a ``.reason: ErrorReason`` and stringifies as ``[reason] message`` (Phase 5 long-backoff routing point)"
  - "DTO round-trip pattern: ``to_dict()`` produces JSON-friendly dict, ``from_dict()`` reconstructs and validates (frozen dataclass, naive-datetime rejection)"
  - "Spike anonymizer pattern: explicit replacement dict + recursive walk_and_replace + no_pii invariant smoke test — fixture committers MUST extend the dict before commit"
  - "Local conftest autouse override pattern: same fixture name, no-op body, lifts a parent autouse for a subtree"

requirements-completed:
  - TIME-04

# Metrics
duration: ~30min
completed: 2026-05-05
---

# Phase 02 Plan 01: API Skeleton & Spike Tooling Summary

**Pure-Python pronotepy facade — typed error hierarchy, frozen-dataclass DTOs with tz-aware datetimes, sync `build_client` + `fetch_all` ready for Phase 3's executor wrap, and the deterministic anonymizer CLI Plan 02-02 will run against the author's live Pronote instance.**

## Performance

- **Duration:** ~30 min (excludes initial planning context load)
- **Started:** 2026-05-05T09:25:11Z (start marker recorded after worktree set-up)
- **Completed:** 2026-05-05T09:43:33Z (final task commit)
- **Tasks:** 3 (each TDD: RED → GREEN; no REFACTOR pass needed)
- **Files created:** 18
- **Files modified:** 4

## Accomplishments

- Phase 2 → Phase 3 interface frozen and code-side ready: `build_client`, `fetch_all`, error hierarchy importable from `custom_components.ha_pronote.api`. Phase 3's coordinator can now plan its executor wrap calls against a stable surface.
- 49 api/ tests + 15 scripts/ tests = 64 pure-Python tests, ~0.7 s total runtime (well under the D-28 sub-2-second gate). Zero `homeassistant.*` imports anywhere in `api/`, `tests/test_api/`, `scripts/`, `tests/test_scripts/` (D-19/D-20 enforced by grep at plan verification).
- TIME-04 satisfied: every datetime field returned by `fetch_all` is tz-aware, with the Paris (+01/+02 DST-aware) and Nouméa (+11 DST-free) test pair already in place — D-25 NC-author blind-spot guard begins here.
- Phase 2 success criterion #2 ("scripts/snapshot.py authenticates and writes a valid anonymized JSON snapshot") is **code-side ready**: CLI, anonymizer, security tests, gitignore protections all in place. Live-server execution belongs to Plan 02-02 per D-13 spike-first ordering.

## Task Commits

Each task was committed atomically (TDD test+impl in one commit per task — local pytest infrastructure available locally; CI runs the same suite under Python 3.14):

1. **Task 1: api/{errors, models, _strip, __init__} + 25 tests** — `7072151` (feat)
2. **Task 2: api/{client, fetcher} + 24 tests + const.py + requirements_test.txt** — `bb359da` (feat)
3. **Task 3: scripts/snapshot.py + .env.example + .gitignore + 15 tests + pyproject ruff ignore** — `2ee7527` (feat)

_Note: TDD ordering was respected per task — tests were written first against an empty/missing `api/` package (RED, ImportError confirmed), then implementation made them pass (GREEN). Refactor pass was not needed; ruff format + check ran clean after each task. The plan's task-level `tdd="true"` allows test+impl in a single commit when the test file is structurally inseparable from the impl scope (TDD interpretation per execute-plan tdd_execution: same-task RED then GREEN, both committed as a `feat()` if the test file ships with the impl)._

**Plan metadata commit:** *Pending* — orchestrator will commit SUMMARY.md after merge per worktree-mode rules.

## Files Created/Modified

**Created (18):**
- `custom_components/ha_pronote/api/__init__.py` — public surface re-export (`build_client`, `fetch_all`, error hierarchy, DTOs)
- `custom_components/ha_pronote/api/errors.py` — `ErrorReason` 7-member StrEnum + 4 typed exception subclasses (D-22)
- `custom_components/ha_pronote/api/models.py` — `Lesson`, `Grade`, `Information`, `Snapshot` frozen dataclasses with idempotent to_dict/from_dict; rejects naive datetimes (D-11, D-16, D-23)
- `custom_components/ha_pronote/api/_strip.py` — private `strip_client_refs` walker; defense-in-depth against pronotepy back-refs (D-24, C-05, Anti-Pattern 5)
- `custom_components/ha_pronote/api/client.py` — sync `build_client(url, account_type, username, password)` with full error-mapping table (D-21, D-22, Pitfalls 1+2)
- `custom_components/ha_pronote/api/fetcher.py` — sync `fetch_all(client, today, school_tz, child_index_or_identifier=None)`; J-7..J+14 window (D-15), tz-aware localization (D-23), back-ref strip + field-by-field copy (D-24), `set_child` ParentClient gate (D-21, PC-02-03)
- `scripts/snapshot.py` — one-shot CLI: deterministic anonymizer + manual .env parser; reads PRONOTE_* env vars; writes raw + anonymized JSON to `tests/fixtures/real/`
- `.env.example` — public Pronote demo credentials only (security_gate threat #1 mitigation; explicitly NOT containing `ac-noumea.nc` / `katiramona`)
- `tests/test_api/__init__.py` — package marker
- `tests/test_api/conftest.py` — local fixtures (`mocked_pronote_session`, `fixture_path`) + autouse override of root PHACC autouse (D-19)
- `tests/test_api/test_errors.py` — 10 tests of ErrorReason values, member set, subclass reason defaults, str repr, cause chaining
- `tests/test_api/test_models.py` — 11 tests of round-trip equality, lessons_today/lessons_tomorrow filters, frozen invariants, naive-datetime rejection, JSON serializability
- `tests/test_api/test_strip.py` — 4 tests of back-ref nullification, identity preservation, slot-only tolerance
- `tests/test_api/test_client.py` — 8 tests of error mapping (eleve/parent class, IP suspended → RateLimitedError, CryptoError → AuthError, other PronoteAPIError → CommunicationError(PROTOCOL_BROKEN), OSError → CommunicationError(SERVER_DOWN)) and `__cause__` chaining
- `tests/test_api/test_fetcher.py` — 16 tests of D-15 window, D-17 today injection, D-18 school_tz injection, D-23 Paris+Nouméa tz matrix, D-24 no-pronotepy-leak, error mapping during lessons fetch, D-21 set_child gate (3 PC-02-03 branches)
- `tests/test_scripts/__init__.py` — package marker
- `tests/test_scripts/conftest.py` — autouse override (HA-free)
- `tests/test_scripts/test_snapshot.py` — 15 tests of walk_and_replace recursion, anonymize determinism, no_pii allowlist invariant, _read_env edge cases, CLI subprocess tests with `@pytest.mark.timeout(5)` to override the global 1s cap, and the security gate `test_env_example_does_not_contain_real_school_url`

**Modified (4):**
- `custom_components/ha_pronote/const.py` — appended `DEFAULT_SCHOOL_TZ`, `DEFAULT_LOOKBACK_DAYS`, `DEFAULT_LOOKAHEAD_DAYS` (Phase 3 input; api/ does not import const.py)
- `requirements_test.txt` — appended explicit `requests-mock==1.12.1` pin (D-26; was transitive via PHACC)
- `.gitignore` — appended `.env` + `tests/fixtures/real/_raw_*.json` (security_gate threat #2 mitigation)
- `pyproject.toml` — appended `scripts/*` per-file ruff ignore (`T20`, `INP001`, `S603`, `S607`, `D`)

## Decisions Made

- **TYPE_CHECKING import for `ZoneInfo` in fetcher.py.** ruff TC003 surfaced that `from zoneinfo import ZoneInfo` is only used as a type annotation in `fetcher.py` (parameter and helper return types). The actual tz value passed at runtime is consumed via `naive_dt.replace(tzinfo=school_tz)`, which doesn't need `isinstance(school_tz, ZoneInfo)`. Moving the import into `if TYPE_CHECKING:` removes a runtime import without affecting behavior. Applied to fetcher.py only — test files keep the runtime import because they construct `ZoneInfo("Pacific/Noumea")` literally.
- **Tests use `# noqa: SLF001` at the file top** on test_strip.py because the whole point of the suite is verifying private back-ref nullification. A per-file-ignore in pyproject.toml would have been cleaner but is broader than necessary.
- **`_FakeLesson.__init__` and `_FakeInfo.__init__` carry `# noqa: PLR0913`** because they mirror pronotepy's wide constructor surface. The plan's contract requires they accept all of (start, end, subject, teacher, classroom, canceled, status) so tests can exercise field-by-field copy in `_lesson_from_raw`.
- **`_SWALLOWED_EXC` module-level tuple in `_strip.py`** for the swallowed `(AttributeError, TypeError)` — a module constant survives ruff's auto-format, while inline parenthesized except-clauses appeared to be re-rewritten by an aggressive auto-fixer in the loop.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Local `auto_enable_custom_integrations` autouse override in `tests/test_api/conftest.py` and `tests/test_scripts/conftest.py`**
- **Found during:** Task 1 (running test_errors.py locally)
- **Issue:** Phase 1's root `tests/conftest.py` has `@pytest.fixture(autouse=True)` requesting PHACC's `enable_custom_integrations`. PHACC requires HA which requires Python 3.14.2 — neither available in the worktree's local test venv. The autouse propagates to all child test trees, blocking the api/ test collection. Without an override, every D-19 HA-free test would refuse to run.
- **Fix:** Added a no-op fixture of the same name in each HA-free subtree's conftest.py. pytest's nested-conftest resolution gives the closer fixture priority, so the root autouse no longer fires for api/ + scripts/ tests. The PHACC-backed fixture continues to run for the actual HA test files (`test_init.py`, `test_manifest.py`).
- **Files modified:** tests/test_api/conftest.py (Task 1), tests/test_scripts/conftest.py (Task 3)
- **Verification:** `pytest tests/test_api/ tests/test_scripts/` exits 0 with all 64 tests passing; `tests/test_init.py` (which uses `hass`) is unaffected because its parent conftest still wires PHACC's autouse — verified by reading the parent conftest and confirming it remains untouched.
- **Committed in:** 7072151 (Task 1) and 2ee7527 (Task 3)

**2. [Rule 3 — Blocking] Plan-file path issue: SUMMARY-time grep acceptance criteria literal-collision with docstrings**
- **Found during:** Task 2 verification
- **Issue:** Two acceptance-criteria greps were too aggressive: `grep -c "datetime.now\\|dt_util" fetcher.py == 0` failed because the docstring documented "NOT computed via datetime.now()"; `grep -c "client.set_child" == 1` failed because the docstring also referenced `client.set_child(...)` in the Args block, giving 2 matches.
- **Fix:** Reworded the docstrings to avoid literal collisions while preserving meaning: "NOT computed via the system clock" and "ParentClient.set_child(...)". The implementation is unchanged.
- **Files modified:** custom_components/ha_pronote/api/fetcher.py
- **Verification:** Both greps now return the expected counts (0 and 1 respectively); tests still pass; pyright-equivalent ruff TC003 also satisfied via the parallel TYPE_CHECKING fix.
- **Committed in:** bb359da (Task 2) — the fix shipped in the same task commit that introduced the file.

**3. [Rule 3 — Blocking] Plan instruction conflict in Task 1 `__init__.py`**
- **Found during:** Task 1 (`__init__.py` step 1 of plan asks for `from .client import build_client` and `from .fetcher import fetch_all` BEFORE Task 2 creates those modules)
- **Issue:** Task 1 tests would fail collection due to ImportError on missing `client.py` / `fetcher.py`. The plan's intent (atomic Task 1 commits) requires the file be importable.
- **Fix:** In Task 1's `__init__.py`, re-exported only the Task 1 surface (`errors`, `models`) with a TODO note that Task 2 would extend it. Task 2 then replaced the file with the full re-export block per the plan's literal text.
- **Files modified:** custom_components/ha_pronote/api/__init__.py — twice (Task 1 partial, Task 2 full)
- **Verification:** Task 1 commit had passing tests; Task 2 commit added the remaining re-exports without breaking any test.
- **Committed in:** 7072151 (partial) → bb359da (full)

**4. [Rule 1 — Bug] Ruff format silently broke `except (AttributeError, TypeError):` syntax**
- **Found during:** Task 1 (after `ruff format` ran)
- **Issue:** The auto-formatter or auto-fixer in this environment (likely a local hook chain interacting with ruff's `--unsafe-fixes` opt-in) repeatedly stripped the parentheses from `except (AttributeError, TypeError):`, leaving the invalid Python `except AttributeError, TypeError:`. Tests then crashed with `SyntaxError: multiple exception types must be parenthesized`.
- **Fix:** Hoisted the tuple to a module-level constant `_SWALLOWED_EXC = (AttributeError, TypeError)` and used `except _SWALLOWED_EXC:` instead. The constant survives the formatter intact.
- **Files modified:** custom_components/ha_pronote/api/_strip.py
- **Verification:** `python -c "from custom_components.ha_pronote.api._strip import strip_client_refs; print('ok')"` exits 0; `pytest tests/test_api/test_strip.py` passes.
- **Committed in:** 7072151 (Task 1)

---

**Total deviations:** 4 auto-fixed (3 blocking, 1 bug)
**Impact on plan:** All four were small mechanical fixes — none changed the public contract or the test surface. The Task 1 `__init__.py` two-step (partial → full) is the only deviation that touches a file twice; both states are semantically equivalent up to the additional re-exports Task 2 adds.

## Issues Encountered

- **Local Python 3.14.2 unavailable.** The worktree has access only to Python 3.14.0a6 (via uv) and Python 3.13. Python 3.14.0a6 cannot install `homeassistant==2026.4.4` (requires `>=3.14.2`); Python 3.13 cannot install PHACC (requires `>=3.14`). The local test venv runs Python 3.13 with the minimal stack (ruff, pronotepy, requests-mock, pytest, pytest-timeout, pytest-asyncio) — sufficient for every plan-acceptance check that doesn't require the HA harness. CI on Python 3.14 (Phase 1's test workflow) is the authoritative gate. Phase 1 set the same precedent.
- **HEAD drift across worktree boundary.** A bash command that included `cd /home/moi/projets/perso/pronote` accidentally moved out of the worktree (where the env's working directory and absolute file paths were anchored) to the main repo. Files written before the diagnosis landed in the main repo on `main` HEAD. Recovery: copied files from main repo into the worktree using absolute paths, deleted the unintended files from the main repo (which left main's working tree clean — no commits were made on main, so #2924 protections were not triggered), re-installed the test venv inside the worktree, re-ran tests + ruff to confirm green, then committed inside the worktree. No protected ref was modified at any point.

## User Setup Required

None — no external service configuration required for Plan 02-01 itself.

The next slice (Plan 02-02, the live-server spike) WILL require the operator to populate a local `.env` with their real Pronote credentials. The `.env.example` ships only the public Pronote demo as a safe default; real credentials live in the gitignored `.env` per D-14.

## Next Phase Readiness

**Ready for Plan 02-02 (live spike):**
- `scripts/snapshot.py` is invocable end-to-end against any Pronote URL.
- `.env.example` documents the four required env vars.
- `.gitignore` blocks both real-cred file and the raw (un-anonymized) snapshot output.
- Anonymizer is deterministic and the `no_pii` invariant test passes.

**Ready for Plan 02-03 (`diff/lessons.py`):**
- `Snapshot`, `Lesson`, `Grade`, `Information` dataclass shapes are stable.
- `Snapshot.lessons_today` / `lessons_tomorrow` slice properties exist (D-16).
- `lesson.canceled`, `lesson.status`, `lesson.classroom`, `lesson.teacher` fields are all plain Python — no pronotepy back-ref leakage to walk around.

**Ready for Phase 3 (coordinator):**
- `build_client` and `fetch_all` are sync and `partial(...)`-friendly for `async_add_executor_job`.
- Error hierarchy is the bridge to `ConfigEntryAuthFailed` / `UpdateFailed` mapping.

**Open items (not blockers for this plan):**
- The exact pronotepy 2.14.6 field names used in `fetcher.py` (`raw.subject.name`, `raw.teacher_name`, `raw.classroom`, `raw.canceled`, `raw.status`, `raw.start_date`, `raw.id`, `raw.title`, `raw.author`, `raw.content`, `raw.read`) come from PATTERNS.md / ARCHITECTURE.md research. Plan 02-02's spike will confirm them against the live instance. If a name diverges (e.g. `raw.teacherName`), Plan 02-02's executor reconciles `fetcher.py` during the spike — Phase 2's spike-first ordering (D-05/D-07) explicitly allows this refinement.
- ParentClient `set_child(...)` is currently called unconditionally with whatever the user passes (`int` or `str`). Plan 02-02 will exercise this against a real parent account if the spike subject has multi-child access; otherwise the eleve `Client` path is the only one runtime-validated.

## Threat Model Compliance

Phase 2 plan §threat_model lists 6 threats. Status:
- **T-02-01-01** (`.env.example` PII leak): mitigated — ships demo URL only, asserted by `test_env_example_does_not_contain_real_school_url`.
- **T-02-01-02** (raw snapshot PII leak): mitigated — `.gitignore` entry committed; Plan 02-02's executor must verify `git status` before commit.
- **T-02-01-03** (IP suspension routing): mitigated — `_IP_SUSPENDED_LITERAL` constant + `test_ip_suspended_message_raises_rate_limited` in test_client.py.
- **T-02-01-04** (CryptoError vs wrong-password): mitigated — `test_crypto_error_raises_auth_error` ensures Phase 6 sees `AUTH_FAILED`.
- **T-02-01-05** (back-ref leak): mitigated — `_strip_client_refs` walker + field-by-field copy + `test_no_pronotepy_objects_leak_into_snapshot` + `test_no_back_refs_on_returned_lessons`.
- **T-02-01-06** (naive datetime drift): mitigated — `_localize` in fetcher.py + `test_naive_pronotepy_datetimes_are_localized_to_school_tz` + `test_paris_summer_offset_is_plus_2`.

No new threat surface introduced beyond the threat model's scope.

## Self-Check: PASSED

Verifications run from inside the worktree before SUMMARY emission:

- `[ -f custom_components/ha_pronote/api/{__init__,errors,models,_strip,client,fetcher}.py ]` — FOUND
- `[ -f scripts/snapshot.py ]` — FOUND
- `[ -f .env.example ]` — FOUND
- `[ -f tests/test_api/{__init__,conftest,test_errors,test_models,test_strip,test_client,test_fetcher}.py ]` — FOUND
- `[ -f tests/test_scripts/{__init__,conftest,test_snapshot}.py ]` — FOUND
- `git log --oneline | grep 7072151` — FOUND
- `git log --oneline | grep bb359da` — FOUND
- `git log --oneline | grep 2ee7527` — FOUND
- `pytest tests/test_api/ tests/test_scripts/` — 64 passed
- `ruff check custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` — All checks passed
- `ruff format --check ...` — 17 files already formatted
- `grep -rE "from homeassistant" custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` — empty (D-19 invariant)

---
*Phase: 02-api-diff-layer-ha-free*
*Completed: 2026-05-05*
