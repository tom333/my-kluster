# Phase 5: Politesse — Adaptive Polling, Quiet Hours, Circuit Breaker — Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 10 (2 NEW, 1 EXTENDED+ADDED-helpers, 6 APPEND)
**Analogs found:** 10 / 10 (all in-tree, exact role match)

---

## File Classification

| File (NEW / EXTEND / APPEND) | Role | Data Flow | Closest Analog | Match Quality |
|------------------------------|------|-----------|----------------|---------------|
| `custom_components/ha_pronote/politesse.py` (NEW) | utility / pure module | transform (pure function) | `custom_components/ha_pronote/api/_strip.py` + `custom_components/ha_pronote/diff/lessons.py` | exact (HA-free purity) |
| `tests/test_politesse.py` (NEW) | test (pure unit) | request-response (fn-in, value-out) | `tests/test_diff/test_lessons.py` + `tests/test_diff/test_lessons_tz_matrix.py` | exact (pure pytest + tz matrix) |
| `custom_components/ha_pronote/coordinator.py` (EXTEND) | controller / orchestrator | request-response + event-driven | `custom_components/ha_pronote/coordinator.py` (itself, Phase 3+4 baseline) | exact (own file — "EXTEND don't refactor") |
| `custom_components/ha_pronote/const.py` (APPEND) | config | n/a | `custom_components/ha_pronote/const.py` (itself) | exact (own file — append-only) |
| `custom_components/ha_pronote/data.py` (EXTEND) | model / runtime payload | n/a | `custom_components/ha_pronote/data.py` (itself) | exact (own file — add field) |
| `custom_components/ha_pronote/__init__.py` (EXTEND) | setup orchestrator | request-response | `custom_components/ha_pronote/__init__.py` (itself) | exact (own file — extend `async_setup_entry`) |
| `custom_components/ha_pronote/manifest.json` (APPEND) | config | n/a | `custom_components/ha_pronote/manifest.json` (itself) | exact (own file — array append) |
| `custom_components/ha_pronote/strings.json` + `translations/{fr,en}.json` (APPEND) | i18n | n/a | `custom_components/ha_pronote/strings.json` + `translations/en.json` (themselves) | exact (own files — nested-key append) |
| `tests/conftest.py` (EXTEND) | test fixture | n/a | `tests/conftest.py` (itself — `mock_pronote_client` fixture) | exact (own file — new fixture in same module) |
| `tests/test_coordinator.py` (EXTEND) | test (HA integration) | request-response | `tests/test_coordinator.py` (itself — existing `_setup_coordinator` helper + `side_effect` pattern) | exact (own file — extend) |
| `tests/test_no_ha_imports.py` (APPEND) | test (AST guard) | n/a | `tests/test_no_ha_imports.py` (itself — `GUARDED_PATHS` list) | exact (own file — list append) |

---

## Pattern Assignments

### 1. `custom_components/ha_pronote/politesse.py` (NEW, pure module)

**Analog A:** `custom_components/ha_pronote/api/_strip.py` (lines 1-40)
**Analog B:** `custom_components/ha_pronote/diff/lessons.py` (lines 64-98)

**Module docstring + import discipline pattern** (from `_strip.py:1-10` + `diff/lessons.py:1-74`):

```python
"""Public — adaptive polling cadence + circuit-breaker support (D-04, D-05, D-09, D-11).

D-XX cross-refs (see 05-CONTEXT.md):
- D-04: compute_interval branches (quiet > suspended > afternoon > base) + jitter
- D-05: should_poll = False on weekend / vacation / férié (unless primer window)
- D-08: is_quiet_hours cross-midnight default 22h-6h NC
- D-11: BACKOFF_SCHEDULE = (1h, 2h, 4h, 12h, 24h) per PITFALLS §2.1

HA-free per D-16 / D-19 / D-20. Imports limited to stdlib + holidays.
tests/test_no_ha_imports.py asserts zero `homeassistant.*` imports.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from zoneinfo import ZoneInfo
```

Why this matters: `api/_strip.py:1` says *"Private — imported only by api/fetcher.py."* — that "audience comment" pattern + the explicit D-XX cross-refs in `diff/lessons.py` are the project's documentation conventions. Phase 5's module should open with the same shape.

**Function docstring + Args/Returns pattern** (from `_strip.py:12-31`):

```python
def strip_client_refs(obj: Any) -> Any:
    """Null out pronotepy back-references on a fetched object (D-24, C-05).

    Pronotepy attaches large ``client`` / ``_session`` / ``_client`` /
    ``_pronote`` back-pointers on each ``Lesson`` / ``Grade`` / ``Information``
    object. ...

    Args:
        obj: Any pronotepy data object (or a plain dataclass — no-op then).

    Returns:
        The same object, with the four back-ref attributes set to ``None``
        wherever they exist.
    """
```

**Pure-function input gate pattern** (from `diff/lessons.py:100-119`):

```python
def diff_lessons(
    previous: Snapshot | None,
    new: Snapshot,
    day: DayLabel,
) -> list[LessonChange]:
    """Return ``LessonChange`` events between two snapshots for the requested day.

    Args:
        previous: Previous ``Snapshot``, or ``None`` on first poll after restart.
        new: Current ``Snapshot``.
        day: ``"today"`` or ``"tomorrow"`` -- selects the lesson slice to compare.

    Returns:
        List of ``LessonChange`` events. ...
    """
    if previous is None:
        return []
```

Phase 5 mirrors this for `should_poll(now, options) -> bool`, `compute_interval(now, options, *, rng=random) -> timedelta`, etc. Note the keyword-only `*, rng=random` for the injection point (D-19, C-08).

**Key invariants (MUST preserve):**
- **Zero `homeassistant.*` imports** (D-19, enforced by `tests/test_no_ha_imports.py` AST guard — Phase 5 extends the guard to include this file).
- **Imports limited to stdlib + `holidays`** (D-16). `random`, `datetime`, `zoneinfo` only beyond `holidays`. No `pronotepy` import either.
- **No module-level state.** Every function takes `now`, `options`, etc. as arguments (D-16).
- **tz-aware datetime in, tz-aware datetime out.** Phase 2 D-23 invariant. Predicates that take `now: datetime` MUST assert tz-awareness early (`raise ValueError("now must be tz-aware")`) per RESEARCH.md §"zoneinfo + dt_util Time-of-Day Patterns".
- **`should_fire_event(now, options) -> bool` returns `not is_quiet_hours(now)`** (D-09) — the predicate is pure; the coordinator owns the side-effect.
- **`compute_interval` clamps to `timedelta(minutes=1)` minimum** (D-04) so freak negative jitter on a short interval never goes sub-minute.

**Anti-patterns to avoid:**
- **Don't catch `RateLimitedError` / `AuthError` here.** Politesse is HA-free; the typed errors live in `api/errors.py` and `_handle_failure` (coordinator) catches them. Importing `api.errors` here would couple politesse to the API layer; politesse only knows about `time`, `date`, and `holidays`.
- **Don't use `freezegun` in pure tests.** Functions take `now` as arg; tests pass synthetic tz-aware datetimes directly (D-20).
- **Don't reach for `homeassistant.util.dt`.** That's HA-only — the coordinator passes `dt_util.now(self._school_tz)` into politesse; politesse never imports it.
- **Don't add `try/except` to swallow malformed options.** That's the coordinator's `_resolve_options(entry)` adapter's job (D-17). Politesse takes a typed `PolitesseOptions` dataclass; bad data fails fast at the boundary.
- **Don't use `random.SystemRandom`.** Stdlib `random` is correct for non-cryptographic jitter (C-08). Tests inject `random.Random(seed=42)` for determinism (D-19).

---

### 2. `tests/test_politesse.py` (NEW, pure unit tests)

**Analog A:** `tests/test_diff/test_lessons.py` (lines 36-110)
**Analog B:** `tests/test_diff/test_lessons_tz_matrix.py` (lines 1-77)

**Module docstring + intent comment** (from `test_lessons.py:1-13`):

```python
"""Diff lessons tests -- covers ROADMAP success criteria #3 and #4.

NOTE: Plan 02-04 wraps these in a tz-matrix parametrize (D-25). For now they
run on whatever the test runner's local TZ is -- the assertions use
fixture-local school_tz, so they pass regardless. ...
"""
```

Phase 5's version states: *"Pure politesse tests — no `hass` fixture, no `freezer`. TZ matrix on Europe/Paris and Pacific/Noumea per DIST-06 (D-20)."*

**TZ-matrix parametrize pattern** (from `test_lessons_tz_matrix.py:26-29`):

```python
pytestmark = pytest.mark.parametrize(
    "school_tz",
    ["Europe/Paris", "Pacific/Noumea"],
)
```

Phase 5 uses the same module-level `pytestmark`. Every test in `test_politesse.py` is automatically parametrized over both timezones. The `school_tz` parameter is consumed by passing `ZoneInfo(school_tz)` into the function under test as `now=datetime(..., tzinfo=ZoneInfo(school_tz))`.

**TestClass grouping pattern** (from `test_lessons.py:37-49`):

```python
class TestFirstPollInvariant:
    def test_previous_none_with_empty_new_returns_empty(self, load_fixture):
        new = load_fixture("synthetic/empty_to_empty_T1.json")
        assert diff_lessons(None, new, "today") == []

    def test_previous_none_with_full_new_returns_empty(self, load_fixture):
        """D-08, ROADMAP success criterion #4: zero events on first poll."""
        new = load_fixture("synthetic/first_poll_after_restart.json")
        assert len(new.lessons) > 0
        assert diff_lessons(None, new, "today") == []
        assert diff_lessons(None, new, "tomorrow") == []
```

Phase 5 groups: `TestComputeInterval`, `TestShouldPoll`, `TestShouldFireEvent`, `TestNextBackoff`, `TestIsSchoolDay`, `TestPrimerWindow` — each holding the scenarios from RESEARCH.md §"Test matrix scenarios" (Mon-Thu 10h, Mon-Thu 18h with Tue=school-day, Sun 19h primer, Sat 10h suspended, Tue 23h quiet, Tue 5h quiet, Sat 23h weekend-wins, etc.).

**Jitter-bound assertion pattern** (RESEARCH.md §"Test recipe", aligns with Phase 5 "Specifics"):

```python
def test_jitter_is_within_bounds(school_tz):
    rng = random.Random(seed=42)
    options = make_default_options(tz=school_tz)
    now = datetime(2026, 5, 12, 18, 30, tzinfo=ZoneInfo(school_tz))  # weekday afternoon
    base = timedelta(minutes=15)                                     # afternoon branch
    for _ in range(100):
        interval = compute_interval(now, options, rng=rng)
        delta = abs((interval - base).total_seconds())
        assert delta <= 30, f"jitter {delta}s exceeds 30s for tz={school_tz}"
```

Use **bounds assertion** (`abs(delta) <= 30`) rather than exact-equality so a future seed change does not break tests for arithmetic that lands at boundary (Phase 5 "Specifics" — Jitter test reproducibility).

**Key invariants (MUST preserve):**
- **No `hass` fixture, no `freezer` fixture, no `load_fixture` fixture** (D-20). Pure pytest; functions get raw datetimes built inline.
- **No `pytest.mark.asyncio` / `async def`** — politesse functions are sync.
- **Conftest-free** — `test_diff/conftest.py` exists for fixtures; `test_politesse.py` does NOT need a sibling conftest. The root `tests/conftest.py` autouse `enable_custom_integrations` is harmless (it short-circuits when no `hass` fixture is requested).
- **TZ matrix mandatory** (DIST-06). Every test parametrized on both timezones.
- **One test = one branch.** RESEARCH.md lists 10+ scenarios — each gets its own named test for grep-ability.

**Anti-patterns to avoid:**
- **Don't import from `tests/conftest.py`** — the `mock_pronote_client` / `mock_config_entry` fixtures pull HA. Politesse tests use NONE of them.
- **Don't use `freezegun`** — politesse takes `now` as arg. Mocking time is for the coordinator-side tests (`test_coordinator.py`), not for the pure module (D-20, C-04).
- **Don't assert on exact jitter floats.** Use bounds (`abs(...) <= JITTER_SECONDS`). A seed change must not break tests.
- **Don't skip naive-datetime cases.** Politesse predicates MUST raise `ValueError` on naive `now`; add a `test_naive_datetime_raises_value_error` per predicate.

---

### 3. `custom_components/ha_pronote/coordinator.py` (EXTEND `_async_update_data` + `_fire_diff_events`; ADD `_handle_failure` + `_reset_breaker_on_success` + state fields)

**Analog:** `custom_components/ha_pronote/coordinator.py` (itself — Phase 3+4 established the patterns; Phase 5 extends in-place).

**Module docstring "WR-XX / D-XX comment anchor" pattern** (from `coordinator.py:1-23`):

```python
"""HA cloud-polling coordinator. Wraps api/fetcher.fetch_all in executor (D-19, COORD-01).

D-19: TimestampDataUpdateCoordinator subclass — gives last_update_success_time
      for free (Phase 4's diff layer reads it).
D-20: coordinator.data: Snapshot directly (no extra wrapper).
D-22: AuthError -> ConfigEntryAuthFailed; RateLimitedError(IP_SUSPENDED) -> UpdateFailed;
      CommunicationError / other -> UpdateFailed.
D-23: school_tz from PronoteData; today via dt_util.now(school_tz).
D-24: update_interval = const.DEFAULT_REFRESH_INTERVAL (30 min hardcoded; Phase 5 adapts).
...
"""
```

Phase 5 APPENDS to this docstring:

```python
# Phase 5 additions:
# D-04: update_interval mutated at end of _async_update_data via compute_interval(now, options).
# D-09: _fire_diff_events gated by should_fire_event(now, options); quiet-hours events dropped (debug log, no queue).
# D-10: _async_update_data short-circuits on backoff_until (skip fetch, return self.data) and
#       on not should_poll (skip fetch, return self.data) — but only when self.data is not None.
# D-12: in-memory circuit breaker — _consecutive_failures, _backoff_until on the instance.
# D-13: _handle_failure(err) ticks the counter on AuthError(surviving recovery) and RateLimitedError(IP_SUSPENDED).
# D-14: _reset_breaker_on_success() called on every successful poll; dismisses both notifications idempotently.
# D-15: persistent_notification.async_create deduped by notification_id = f"{DOMAIN}_{entry_id}_{kind}".
```

**`_handle_*` helper / nested-method pattern** (from `coordinator.py:174-228` — `_recover_from_auth_error`):

```python
async def _recover_from_auth_error(
    self,
    original_err: AuthError,
    today: date,
) -> Snapshot:
    """D-09: single fresh re-login + retry; on second failure raise ConfigEntryAuthFailed."""
    entry = self.config_entry
    if entry is None:
        raise ConfigEntryAuthFailed(str(original_err)) from original_err
    # ... typed-error try/except mirroring D-22 ...
    except AuthError as err:
        raise ConfigEntryAuthFailed(f"[{err.reason}] {redact(err.message)}") from err
    except RateLimitedError as err:
        raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err
    except (CommunicationError, PronoteIntegrationError) as err:
        raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err
    return snapshot
```

Phase 5's `_handle_failure(err: PronoteIntegrationError) -> None` follows the same shape: docstring with D-XX cross-ref, isinstance-on-typed-error branching, calls into `persistent_notification.async_create`, does NOT swallow the exception (the caller re-raises per D-22).

**WR-04 cooldown precedent — in-method state check** (from `coordinator.py:127-141`):

```python
now = dt_util.utcnow()
if self._last_recovery_at is not None and now - self._last_recovery_at < _SILENT_RECOVERY_COOLDOWN:
    raise UpdateFailed(
        f"[{err.reason}] auth recovery rate-limited; skipping this poll: {redact(err.message)}"
    ) from err
self._last_recovery_at = now
snapshot = await self._recover_from_auth_error(err, today)
# WR-09: a successful recovery PROVES the AuthError was real auth ...
self._last_recovery_at = None
```

Phase 5's backoff short-circuit (D-10) mirrors this shape — early-return when `_backoff_until is not None and now < _backoff_until`, mutate the timer field on success path:

```python
# Phase 5 — D-10 backoff short-circuit (gated on self.data is not None so first poll fetches)
now = dt_util.now(self._school_tz)
options = _resolve_options(self.config_entry)
if self._backoff_until is not None and now < self._backoff_until and self.data is not None:
    self.update_interval = (self._backoff_until - now) + _jitter_delta()  # one-shot
    return self.data  # keep sensors populated, skip fetch + diff + events
if not should_poll(now, options) and self.data is not None:
    self.update_interval = compute_interval(now, options)  # ~6h suspended cadence
    return self.data
```

**Side-effect ordering invariant — CR-03** (from `coordinator.py:148-170`):

```python
# CR-03: state updates BEFORE side-effects that may fail.
# D-12: capture previous BEFORE overwriting — _fire_diff_events reads it.
previous = self._previous_snapshot
self._previous_snapshot = snapshot

# CR-03 / CR-05: token capture is best-effort.
try:
    await self._capture_session()
except Exception:  # noqa: BLE001 — defensive: any failure is non-fatal.
    _LOGGER.warning("Failed to persist session token; will retry next poll", exc_info=True)

# Phase 4: fire typed bus events for each diff since previous snapshot.
self._fire_diff_events(previous, snapshot)
```

Phase 5's success-path addition slots in immediately before `_fire_diff_events`:

```python
# Phase 5 — D-14: clear breaker state + dismiss notifications BEFORE firing events
self._reset_breaker_on_success()
self._fire_diff_events(previous, snapshot)  # now gated internally by should_fire_event

# Phase 5 — D-04: mutate update_interval at end (Pattern 4)
self.update_interval = compute_interval(now, options)
return snapshot
```

**`_fire_diff_events` gating pattern** (extends `coordinator.py:248-283`):

The existing method iterates four loops (`diff_lessons today / tomorrow / grades / notifications`). Phase 5 wraps with a single top-of-method gate per "Specifics" memo (ordering — gate ONCE, not per-event):

```python
def _fire_diff_events(self, previous, new):
    """Fire typed bus events for each diff since previous snapshot.

    Phase 5 (D-09): single top-of-method gate on should_fire_event(now, options).
    Per Phase 5 "Specifics" memo: gate ONCE, not per-event, so a poll either fires
    all its events or none — never half-suppressed.
    """
    now = dt_util.now(self._school_tz)
    options = _resolve_options(self.config_entry)
    if not should_fire_event(now, options):
        _LOGGER.debug(
            "Events suppressed during quiet hours for %s (entry %s)",
            self._child_identifier, self.config_entry.entry_id,
        )
        # Diff loops below would be a no-op visit — drop them too for clarity.
        return
    # ... existing Phase 4 loops unchanged ...
```

**NOTE on the diff-loop running order:** CONTEXT.md D-09 says *"Coordinator's `_fire_diff_events` runs the diff loop normally (so `_previous_snapshot` mutation stays correct) but before each `hass.bus.async_fire` it queries `should_fire_event`"* — that implies per-event gating. The "Specifics" memo overrides with single top-of-method gating because `_previous_snapshot` is updated BEFORE `_fire_diff_events` is called (see `coordinator.py:155-156` and CR-03 ordering). Diff functions are pure; their result is discarded when the gate fails. The single-gate approach is the right one — planner should follow the "Specifics" memo over the D-09 prose.

**Persistent notification call site pattern** (NEW — analog is RESEARCH.md §"HA persistent_notification API"):

```python
from homeassistant.components import persistent_notification

# In _handle_failure:
persistent_notification.async_create(
    self.hass,
    message=_format_ip_suspended_message(err, strike_count, retry_at, school_tz, language),
    title=_format_ip_suspended_title(language),
    notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}",
)

# In _reset_breaker_on_success:
persistent_notification.async_dismiss(
    self.hass,
    f"{DOMAIN}_{self.config_entry.entry_id}_{IP_SUSPENDED_NOTIFICATION_ID_SUFFIX}",
)
persistent_notification.async_dismiss(
    self.hass,
    f"{DOMAIN}_{self.config_entry.entry_id}_{AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX}",
)
```

Both calls are `@callback` (sync, no `await`) per RESEARCH.md §"HA persistent_notification API" verification. They run on the event loop because `_handle_failure` / `_reset_breaker_on_success` are called from `_async_update_data`'s except / success branches.

**Key invariants (MUST preserve):**
- **Phase 3 D-22 typed-error mapping stays verbatim.** `AuthError -> ConfigEntryAuthFailed`, `RateLimitedError -> UpdateFailed`, `CommunicationError/other -> UpdateFailed`. The `_handle_failure` tick is **additive** — it runs INSIDE the except block, before `raise`. The user feedback file (`feedback_no_silent_exceptions.md`) and CONTEXT.md D-13 both lock this.
- **WR-04 cooldown gate stays intact** (`coordinator.py:127-141`). The breaker counter ticks ONLY on `AuthError`s that survive `_recover_from_auth_error` — the aliased-CryptoError loop that WR-04 absorbs MUST NOT increment `_consecutive_failures`.
- **CR-03 side-effect ordering preserved.** `_previous_snapshot` update happens BEFORE `_capture_session` and BEFORE `_fire_diff_events`. Phase 5's `_reset_breaker_on_success` slots between `_capture_session` and `_fire_diff_events` — counter reset is a synchronous state mutation, follows the same "state first, side-effects after" rule.
- **`self.update_interval` (NO underscore prefix) is the public setter.** Per RESEARCH.md Pitfall 1 + verified at `update_coordinator.py:247-251`. Direct mutation of `self._update_interval` skips the cache update.
- **First-poll fetch invariant.** `self.data is not None` gate on both early-returns (D-10) — without this, a weekend install leaves sensors `unavailable` forever.
- **`_previous_snapshot` NOT updated on skip.** Phase 4's diff at the next real poll compares against the snapshot from the previous *real* poll.
- **No `UpdateFailed(retry_after=...)`.** Phase 5 owns `_backoff_until`; HA's `_retry_after` is single-tick and would double-apply. Keep existing `UpdateFailed(f"[{err.reason}] {redact(err.message)}")` shape verbatim.
- **`redact(err.message)` MUST be used on every notification body** (CLAUDE.md "jamais en clair dans les logs"; `api/errors.py:redact` strips password/token/session/Authorization).

**Anti-patterns to avoid:**
- **Don't catch `Exception` in `_handle_failure`.** Match on typed errors (`isinstance(err, RateLimitedError) and err.reason == ErrorReason.IP_SUSPENDED`) — the feedback file forbids silent typed-catch-then-remap; the breaker is ADDITIVE, not a remap.
- **Don't wrap `persistent_notification.async_create` in `async_add_executor_job`.** It's `@callback`; calling from executor raises "Cannot call from outside event loop" (RESEARCH.md Pitfall 3).
- **Don't omit `notification_id`.** Each strike would create a new notification with auto-generated random ID (RESEARCH.md Pitfall 2). The dedupe contract requires the stable `f"{DOMAIN}_{entry_id}_{kind}"`.
- **Don't import `politesse` at module top if it would force `holidays` import at coordinator import time.** `holidays` is fine to import eagerly per RESEARCH.md §"holidays Library Import + Instantiation Overhead" — zero I/O, microseconds. Eager import is OK.
- **Don't refactor `_recover_from_auth_error`.** Phase 3 + 4 baseline established the pattern; Phase 5 only ADDS the breaker tick on the surviving `AuthError` arm. Do NOT touch the WR-04 cooldown logic, the typed-error try/except, or the `set_active_child` re-application.
- **Don't tick the counter on `RateLimitedError(reason != IP_SUSPENDED)` or on `CommunicationError`** (D-13 — transient blip ≠ ban signal).

---

### 4. `custom_components/ha_pronote/const.py` (APPEND)

**Analog:** `custom_components/ha_pronote/const.py` (itself, lines 1-49).

**`Final`-typed append pattern with phase comment anchor** (from `const.py:19-32`):

```python
# Phase 3 additions (D-24, D-25) — HA-side runtime defaults consumed by the
# coordinator (update_interval) and __init__.py (platform forwarding).
DEFAULT_REFRESH_INTERVAL: Final = timedelta(minutes=30)  # D-24 — Phase 5 makes adaptive
# D-10 — Phase 4 extends to include CALENDAR.
PLATFORMS: Final = (Platform.SENSOR, Platform.CALENDAR)

# Phase 4 additions — event-type constants (D-13, EVENT-01..03),
# class level attribute (D-19, ENT-01), attribute caps (D-05, D-04),
# platform extension (D-10).

EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"   # D-13, EVENT-01
EVENT_NEW_GRADE: Final = "pronote_new_grade"                 # D-13, EVENT-02
EVENT_NEW_INFORMATION: Final = "pronote_new_information"     # D-13, EVENT-03
```

Phase 5 APPENDS (D-18 verbatim):

```python
# Phase 5 additions — adaptive polling cadence, quiet hours, circuit breaker.
# D-04: compute_interval branch defaults. D-08: quiet hours default 22h-6h NC.
# D-11: backoff curve per PITFALLS §2.1. D-18: const wording locked in CONTEXT.md.

from datetime import date, time  # add to existing `from datetime import timedelta`

BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
    timedelta(hours=1), timedelta(hours=2), timedelta(hours=4),
    timedelta(hours=12), timedelta(hours=24),
)
JITTER_SECONDS: Final = 30
DEFAULT_AFTERNOON_INTERVAL: Final = timedelta(minutes=15)
DEFAULT_AFTERNOON_WINDOW: Final = (time(17, 0), time(20, 0))
DEFAULT_QUIET_HOURS: Final = (time(22, 0), time(6, 0))
DEFAULT_SUSPENDED_CADENCE: Final = timedelta(hours=6)
DEFAULT_QUIET_CADENCE: Final = timedelta(hours=4)
NC_VACATION_RANGES_2026: Final[tuple[tuple[date, date], ...]] = (
    (date(2026, 4, 4), date(2026, 4, 19)),
    (date(2026, 6, 6), date(2026, 6, 21)),
    (date(2026, 8, 8), date(2026, 8, 23)),
    (date(2026, 10, 10), date(2026, 10, 25)),
    (date(2026, 12, 19), date(2027, 2, 14)),
)
NC_LOCAL_HOLIDAYS_SUPPLEMENT: Final[frozenset[date]] = frozenset()
IP_SUSPENDED_NOTIFICATION_ID_SUFFIX: Final = "ip_suspended"
AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX: Final = "auth_circuit"
```

**Key invariants (MUST preserve):**
- **Append-only.** Existing `DEFAULT_REFRESH_INTERVAL`, `PLATFORMS`, `EVENT_*`, `CLASS_LEVEL_ATTR`, `NOTIFICATIONS_WINDOW`, `GRADE_COMMENT_MAX_LEN`, `GRADES_WINDOW` stay untouched.
- **`Final` annotation on every constant** (matches `const.py:10, 15, 16, 17, 21, 24, 30-32, 39, 41, 42, 49`).
- **Phase comment anchor** (`# Phase 5 additions —`) keeps the file scannable.
- **`date` + `time` import additions** — extend the existing `from datetime import timedelta` line to `from datetime import date, time, timedelta` (alphabetical inside one import statement, project style).

**Anti-patterns to avoid:**
- **Don't move existing constants.** Phase 5 modifies nothing it didn't add.
- **Don't add an `OPTIONS_KEYS` dict.** Phase 6 owns the OptionsFlow schema; `entry.options.get(KEY, DEFAULT_FROM_CONST)` reads happen in the coordinator's `_resolve_options` adapter (D-17). The KEY strings live as module-level `Final` strings in const.py if shared, else as local string literals.

---

### 5. `custom_components/ha_pronote/data.py` (EXTEND — add `holiday_dates` field)

**Analog:** `custom_components/ha_pronote/data.py` (itself, lines 1-38).

**Field-add pattern preserving "NOT frozen" comment + TYPE_CHECKING discipline** (from `data.py:1-35`):

```python
"""Typed runtime_data payload for HA-Pronote ConfigEntries (D-21).
...
NOT frozen: ``client`` is reassigned by the coordinator on D-09 silent-recovery
when a mid-poll AuthError triggers a single fresh re-login.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo
    import pronotepy
    from homeassistant.config_entries import ConfigEntry
    from .coordinator import PronoteDataUpdateCoordinator


@dataclass
class PronoteData:
    """Runtime payload — owned by the ConfigEntry, lives until unload (D-21)."""

    coordinator: PronoteDataUpdateCoordinator
    client: pronotepy.Client | pronotepy.ParentClient
    child_identifier: str
    child_index: int | None
    school_tz: ZoneInfo
```

Phase 5 EXTENDS by appending fields and adding `date` to TYPE_CHECKING:

```python
"""...
NOT frozen: ``client`` is reassigned by the coordinator on D-09 silent-recovery
when a mid-poll AuthError triggers a single fresh re-login. Phase 5: ``holiday_dates``
+ ``holiday_dates_year`` may also be reassigned by the coordinator on year rollover
(see Phase 5 "Specifics" memo).
"""

if TYPE_CHECKING:
    from datetime import date            # NEW for Phase 5
    from zoneinfo import ZoneInfo
    # ...

@dataclass
class PronoteData:
    """Runtime payload — owned by the ConfigEntry, lives until unload (D-21)."""

    coordinator: PronoteDataUpdateCoordinator
    client: pronotepy.Client | pronotepy.ParentClient
    child_identifier: str
    child_index: int | None
    school_tz: ZoneInfo
    # Phase 5 (C-07, D-02): NC fériés precomputed at async_setup_entry; reassigned on year rollover.
    holiday_dates: frozenset[date]
    holiday_dates_year: int
```

**Key invariants (MUST preserve):**
- **NOT frozen.** Phase 5 mutates `holiday_dates` / `holiday_dates_year` on year rollover (per Phase 5 "Specifics" memo). Keep the `@dataclass` decorator without `frozen=True`.
- **`TYPE_CHECKING` import discipline.** `date` only imported under `TYPE_CHECKING` so importing `data.py` doesn't pull `datetime` eagerly (already the rule for `ZoneInfo`).
- **Field order — append, don't reorder.** Existing positional consumers (`__init__.py:110-116` builds `PronoteData(coordinator=..., client=..., ...)` with all kwargs) won't break, but kwargs discipline still demands stability.
- **`PronoteConfigEntry = ConfigEntry[PronoteData]` type alias preserved** (`data.py:38`).

**Anti-patterns to avoid:**
- **Don't store the `holidays.France(subdiv='NC')` instance directly.** It's a stateful `HolidayBase` subclass; serializing it makes no sense and ages poorly across `holidays` lib upgrades. Only the `frozenset[date]` extracted at setup-time gets stored. The extraction is `frozenset(holidays.France(subdiv='NC', years=year).keys())`.
- **Don't make `holiday_dates` a `set` (mutable).** `frozenset` matches the "value-type" discipline elsewhere (Phase 2 frozen dataclasses); the coordinator REASSIGNS the whole field on rollover, never mutates it in place.

---

### 6. `custom_components/ha_pronote/__init__.py` (EXTEND `async_setup_entry`)

**Analog:** `custom_components/ha_pronote/__init__.py` (itself, lines 51-119).

**Executor-wrap idiom + runtime_data assignment pattern** (from `__init__.py:62-119`):

```python
school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)  # Phase 6 OPT-04 reads entry.options.
device_name = f"home-assistant-{entry.entry_id[:8]}"

try:
    client = await hass.async_add_executor_job(
        partial(
            build_or_resume_client,
            entry.data["url"],
            entry.data["account_type"],
            entry.data["username"],
            entry.data["password"],
            entry.data.get("session"),
            device_name,
        )
    )
except AuthError as err:
    raise ConfigEntryAuthFailed(str(err)) from err
except PronoteIntegrationError as err:
    raise ConfigEntryNotReady(str(err)) from err
# ...
coordinator = PronoteDataUpdateCoordinator(hass, entry, client=client, ...)
await coordinator.async_config_entry_first_refresh()

entry.runtime_data = PronoteData(
    coordinator=coordinator,
    client=client,
    child_identifier=entry.data["child_identifier"],
    child_index=child_index,
    school_tz=school_tz,
)
```

Phase 5 EXTENDS by adding a one-shot executor call BEFORE `coordinator = PronoteDataUpdateCoordinator(...)` and stashing on `runtime_data`:

```python
# Phase 5 (C-07, D-02): precompute NC fériés for current school year. Executor-wrapped per
# CLAUDE.md "executor for any blocking work" discipline (defensive — verified no I/O in
# holidays==0.97, but the rule keeps the policy uniform). Year-rollover check lives on
# the coordinator (per Phase 5 "Specifics" memo: cache `(year, frozenset[date])`).
now_year = dt_util.now(school_tz).year
holiday_dates = await hass.async_add_executor_job(_compute_holiday_dates_for_year, now_year)

coordinator = PronoteDataUpdateCoordinator(hass, entry, client=client, ...)
await coordinator.async_config_entry_first_refresh()

entry.runtime_data = PronoteData(
    coordinator=coordinator,
    client=client,
    child_identifier=entry.data["child_identifier"],
    child_index=child_index,
    school_tz=school_tz,
    holiday_dates=holiday_dates,           # Phase 5 — C-07
    holiday_dates_year=now_year,           # Phase 5 — year rollover sentinel
)
```

Module-level helper (HA-free, lives in `__init__.py` not `politesse.py` because it imports `holidays` and uses `NC_LOCAL_HOLIDAYS_SUPPLEMENT`):

```python
def _compute_holiday_dates_for_year(year: int) -> frozenset[date]:
    """C-07 — extract NC fériés for `year` from holidays==0.97; union with hardcoded supplement."""
    import holidays  # imported inside fn so module import stays fast for tests that don't load entry
    return frozenset(holidays.France(subdiv="NC", years=year).keys()) | NC_LOCAL_HOLIDAYS_SUPPLEMENT
```

**Key invariants (MUST preserve):**
- **WR-02 guard at top of `async_setup_entry` stays first.** `missing = [k for k in _REQUIRED_ENTRY_DATA_KEYS if k not in entry.data]` (`__init__.py:58-60`) — Phase 5 does NOT add to `_REQUIRED_ENTRY_DATA_KEYS` (no new entry.data keys per CONTEXT.md).
- **`async_add_executor_job` for the `holidays` call** even though `holidays==0.97` does no I/O (RESEARCH.md verified). The discipline is uniform; planner should add a code comment explaining why.
- **`PronoteData(...)` kwargs order matches the `data.py` field order.** Adding `holiday_dates=` and `holiday_dates_year=` at the END.
- **WR-07 unload contract.** `async_unload_entry` calls `coordinator.async_shutdown()` (`__init__.py:130-131`). Phase 5 does NOT add unload-side cleanup for `holiday_dates` — it's a `frozenset`, GC'd with the entry.

**Anti-patterns to avoid:**
- **Don't compute `holiday_dates` inside `PronoteDataUpdateCoordinator.__init__`** — that runs sync on the event loop. The `__init__.py:async_setup_entry` is the only place that can await the executor.
- **Don't make `_compute_holiday_dates_for_year` an `async def`.** It does sync `holidays` instantiation; awaiting `async_add_executor_job` on a sync fn is the project pattern (see `__init__.py:69` + `coordinator.py:109`).
- **Don't add a year-rollover listener** (`async_track_time_change(hour=0, minute=0, second=0)`). RESEARCH.md §"Don't Hand-Roll" + Phase 5 "Specifics" memo: per-tick year check in `_async_update_data` is simpler and avoids the extra HA primitive. The check is `if runtime_data.holiday_dates_year != now.year: runtime_data.holiday_dates = await ...; runtime_data.holiday_dates_year = now.year`.
- **Don't fail setup if `holidays` instantiation raises.** Wrap in `try/except` returning an empty `frozenset` + `_LOGGER.warning` — fériés gate is non-essential (politesse falls through to the next branch). But: do NOT swallow silently per the feedback file; the warning IS the trace.

---

### 7. `custom_components/ha_pronote/manifest.json` (APPEND `holidays==0.97`)

**Analog:** `custom_components/ha_pronote/manifest.json` (itself, line 11).

**Array-append shape — exact-pin discipline** (from `manifest.json:11`):

```json
"requirements": ["pronotepy==2.14.6", "python-slugify==8.0.4"],
```

Phase 5 APPENDS:

```json
"requirements": ["pronotepy==2.14.6", "python-slugify==8.0.4", "holidays==0.97"],
```

**Key invariants (MUST preserve):**
- **Exact `==X.Y.Z` pin** (Phase 1 D-14). No `>=`, no `~=`, no caret. RESEARCH.md verified `0.97` is the latest stable as of 2026-05-25.
- **Insertion at END of array.** No alphabetical sort — preserves the chronological insertion order matching the project's evolution (pronotepy = Phase 1, python-slugify = Phase 3, holidays = Phase 5).
- **No other manifest.json key changes.** `iot_class: cloud_polling` (line 8), `quality_scale: bronze` (line 10), `config_flow: true` (line 5), `integration_type: hub` (line 7), `version: 0.0.1` (line 12) — all stay untouched per CONTEXT.md.

**Anti-patterns to avoid:**
- **Don't add `dependencies: ["persistent_notification"]`.** `persistent_notification` is a HA Core built-in; `dependencies` lists OTHER custom_components our component requires loaded. The hassfest validator will warn if added unnecessarily.
- **Don't bump `version: 0.0.1`.** Phase 7's release workflow injects the tag-derived version; v1 doesn't bump per-phase.
- **Don't add `loggers: ["holidays"]`.** The `holidays` lib uses Python's standard logging; no special declaration needed.

---

### 8. `custom_components/ha_pronote/strings.json` + `translations/{fr,en}.json` (APPEND notification keys)

**Analog:** `custom_components/ha_pronote/strings.json` + `translations/en.json` (themselves, lines 1-53 — identical content).

**Nested-key shape with `entity.sensor.*` precedent** (from `strings.json:35-52` / `translations/en.json:35-52`):

```json
{
  "config": { ... },
  "entity": {
    "sensor": {
      "lessons_today": { "name": "Lessons today" },
      "grades": { "name": "Notes" },
      "notifications": { "name": "Notifications" }
    },
    "calendar": {
      "calendar": { "name": "Emploi du temps" }
    }
  }
}
```

Phase 5 APPENDS a new top-level `notification` block (D-15 — UI hint text only; the f-strung body lives as Python constants in `coordinator.py`):

```json
{
  "config": { ... },
  "entity": { ... },
  "notification": {
    "ip_suspended": {
      "title": "[HA-Pronote] IP suspendue par Pronote",
      "message": "L'IP de votre instance Home Assistant a été suspendue par le serveur Pronote. Voir les détails dans la notification."
    },
    "auth_circuit": {
      "title": "[HA-Pronote] Identifiants Pronote rejetés à plusieurs reprises",
      "message": "Trois tentatives d'authentification consécutives ont échoué. Voir les détails dans la notification."
    }
  }
}
```

(English `translations/en.json` uses the same keys with English strings.)

**CRITICAL CAVEAT — read CONTEXT.md D-15 carefully:** *"The `strings.json` entries added in Phase 5 are FOR THE NOTIFICATION UI HINT TEXT ONLY (the buttons "Dismiss" etc.), not the f-strung body."* The body the user sees in the persistent_notification carousel is built in Python in `coordinator.py` (C-05 — pick `fr` vs `en` from `hass.config.language`). The `strings.json` entries here are STATIC fallback/hint strings, not the dynamic strike-count-bearing message.

**Translation file scope discrepancy detected:** Only `translations/en.json` exists in the current tree; the prompt mentions `translations/{fr,en}.json`. Phase 5 must CREATE `translations/fr.json` if it does not yet exist, mirroring the structure of `translations/en.json` and adding the French notification block. Planner: confirm fr.json existence at probe time; if missing, create it as part of Plan 05-03.

**Key invariants (MUST preserve):**
- **`strings.json` and every `translations/{lang}.json` stay structurally identical** — same key tree, only string values change per language. The `config` and `entity` blocks already exhibit this — adding `notification` follows the same rule.
- **No string contains `<token>`, `<password>`, or a URL.** Per CLAUDE.md "jamais en clair dans les logs" — the f-strung body in Python uses `redact(err.message)`; static strings here are credentials-free by construction.
- **Top-level key alphabetical order is NOT a project convention** (existing order is `config, entity` — both insertion-order). `notification` appended at end of `entity`-following position is fine.

**Anti-patterns to avoid:**
- **Don't move the dynamic strike-count-bearing message into `strings.json`** with placeholder interpolation (`{strike_count}`). HA's `strings.json` does not natively support runtime interpolation for `persistent_notification`; that's why D-15 keeps the body as Python constants.
- **Don't add untranslated keys to fr.json.** The Phase 7 i18n polish wires the full surface; Phase 5 ships the minimum (D-18 lists exactly 4 keys × 2 langs).

---

### 9. `tests/conftest.py` (EXTEND — add `mock_persistent_notification` fixture)

**Analog:** `tests/conftest.py` (itself — existing `mock_pronote_client` at lines 51-67 + `mock_config_entry` at lines 90-112).

**`@pytest.fixture` + `MagicMock` idiom** (from `conftest.py:51-67`):

```python
@pytest.fixture
def mock_pronote_client():
    """A MagicMock standing in for pronotepy.Client (eleve account).

    info.name, children=[], lessons(), current_period.grades, information_and_surveys(),
    export_credentials() — the surface fetch_all + build_or_resume_client touch.
    """
    client = MagicMock()
    client.info.name = "Jean Dupont"
    client.info.class_name = "3ème A"
    # ...
    return client
```

**`monkeypatch.setattr` for HA Core surfaces** (analog: the `setup_ha_calendar_http_dependency` autouse fixture at `conftest.py:30-43` uses `async_setup_component`; for patching a callable, the project uses `unittest.mock.patch` as context manager in the test bodies — see `test_coordinator.py:90-110`. The new `mock_persistent_notification` fixture follows the C-06 / RESEARCH.md recommendation):

Phase 5 ADDS:

```python
# Phase 5 (C-06) — patch homeassistant.components.persistent_notification surface so
# coordinator tests can assert on create/dismiss call args without actually wiring HA's
# notifications component. `persistent_notification.async_create` and `async_dismiss` are
# @callback (synchronous) per RESEARCH.md §"HA persistent_notification API" — MagicMock
# (NOT AsyncMock) is the correct stand-in.


@pytest.fixture
def mock_persistent_notification(monkeypatch):
    """Patch persistent_notification.async_create + async_dismiss with MagicMocks.

    Returns a SimpleNamespace with `.create` and `.dismiss` MagicMocks so tests can
    assert on call args: `mock_persistent_notification.create.assert_called_once_with(
        hass, message=..., title=..., notification_id="ha_pronote_<entry_id>_ip_suspended"
    )`.
    """
    from types import SimpleNamespace

    create_mock = MagicMock()
    dismiss_mock = MagicMock()
    monkeypatch.setattr(
        "homeassistant.components.persistent_notification.async_create", create_mock
    )
    monkeypatch.setattr(
        "homeassistant.components.persistent_notification.async_dismiss", dismiss_mock
    )
    # Also patch the import site used by the coordinator if it does
    # `from homeassistant.components import persistent_notification` then `persistent_notification.async_create(...)`:
    monkeypatch.setattr(
        "custom_components.ha_pronote.coordinator.persistent_notification.async_create", create_mock
    )
    monkeypatch.setattr(
        "custom_components.ha_pronote.coordinator.persistent_notification.async_dismiss", dismiss_mock
    )
    return SimpleNamespace(create=create_mock, dismiss=dismiss_mock)
```

**Key invariants (MUST preserve):**
- **`autouse=True` fixtures stay intact.** `auto_enable_custom_integrations` (line 20-27) and `setup_ha_calendar_http_dependency` (line 30-43) MUST NOT be modified — Phase 4 wired them and any change cascades into all HA-side tests.
- **`MockConfigEntry` D-08 keys preserved** (`conftest.py:98-112`). Phase 5 adds no new entry.data keys; the existing 8-key payload stays.
- **`MagicMock` (not `AsyncMock`) for `persistent_notification`.** Verified at RESEARCH.md §"HA persistent_notification API" — both `async_create` and `async_dismiss` are `@callback` (synchronous). `AsyncMock` would await and the test would silently pass on a non-awaited call.
- **Patch BOTH the source module AND the import site.** If `coordinator.py` does `from homeassistant.components import persistent_notification` and calls `persistent_notification.async_create(...)`, the test must patch both `homeassistant.components.persistent_notification.async_create` AND `custom_components.ha_pronote.coordinator.persistent_notification.async_create`. The dual-patch is defensive — pick the one matching the actual import in `coordinator.py` at implementation time.

**Anti-patterns to avoid:**
- **Don't make the fixture `autouse=True`.** Phase 5 tests opt in by adding `mock_persistent_notification` to the test signature; non-Phase-5 tests stay untouched.
- **Don't use `AsyncMock`.** See above.
- **Don't patch at the test-module level via `@patch(...)`.** The fixture pattern is the project convention (see `mock_pronote_client`); aligns with C-06.

---

### 10. `tests/test_coordinator.py` (EXTEND with breaker + suspension + event-gate scenarios)

**Analog:** `tests/test_coordinator.py` (itself).

**`hass`-fixture-based test + `MockConfigEntry` + `_setup_coordinator` helper** (from `test_coordinator.py:256-271`):

```python
async def _setup_coordinator(hass, mock_config_entry, mock_pronote_client, snapshot, today):
    """Boot the integration with a happy first refresh; return the coordinator."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ha_pronote.build_or_resume_client",
            return_value=mock_pronote_client,
        ),
        patch(
            "custom_components.ha_pronote.coordinator.fetch_all",
            return_value=snapshot,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry.runtime_data.coordinator
```

Phase 5 REUSES this helper verbatim — every new test starts by booting with a happy first refresh, then mutates `fetch_all`'s `side_effect` to drive failure scenarios.

**`side_effect=[...]` sequential-failure pattern** (from `test_coordinator.py:288-304`):

```python
fresh_client = MagicMock()
fresh_client.set_child = MagicMock()
fresh_client.export_credentials = MagicMock(return_value={"token": "x"})

with (
    patch(
        "custom_components.ha_pronote.coordinator.fetch_all",
        side_effect=[
            AuthError("session expired"),                   # tick 1 — first fetch
            RateLimitedError("Your IP address is suspended"),  # tick 2 — recovery retry
        ],
    ),
    patch(
        "custom_components.ha_pronote.coordinator.build_or_resume_client",
        return_value=fresh_client,
    ),
    pytest.raises(UpdateFailed),
):
    await coordinator._async_update_data()  # noqa: SLF001
```

Phase 5's 3-strike-auth test follows the same shape — three consecutive `await coordinator._async_update_data()` blocks each with `side_effect=AuthError(...)` (or use `side_effect=[AuthError(...), AuthError(...)]` per call for the recovery path).

**WR-04 cooldown-style state assertion** (from `test_coordinator.py:519-521`):

```python
# WR-09: the success path MUST clear the cooldown timestamp.
assert coordinator._last_recovery_at is None, (  # noqa: SLF001
    "WR-09: successful recovery must clear _last_recovery_at"
)
```

Phase 5 mirrors with breaker assertions:

```python
assert coordinator._consecutive_failures == 3
assert coordinator._backoff_until is not None
assert coordinator._backoff_until > dt_util.now(coordinator._school_tz)
```

**`freezer` fixture pattern (NEW for Phase 5, transitive via PHACC)** — see RESEARCH.md §"freezegun / pytest-freezer in PHACC Tests":

```python
async def test_3_strike_auth_sets_backoff_4h(
    hass, mock_config_entry, mock_pronote_client, mock_persistent_notification, freezer
):
    t0 = datetime(2026, 5, 12, 14, 0, tzinfo=ZoneInfo("Pacific/Noumea"))
    freezer.move_to(t0)
    # ... setup ...
    # First strike → 1h backoff
    # freezer.move_to(t0 + timedelta(hours=2))
    # Second strike → 2h backoff
    # ...
```

The `freezer` fixture is auto-discovered by `pytest-freezer` (already transitive per RESEARCH.md). No explicit import needed.

**Test scenarios to cover** (per CONTEXT.md D-20 + RESEARCH.md):
1. Suspension short-circuit: `should_poll=False`, snapshot stays cached, no executor call, no events fired
2. Backoff short-circuit: `_backoff_until > now`, same behavior
3. 3-strike auth → `ConfigEntryAuthFailed` + `persistent_notification.async_create` called + `_backoff_until` set
4. `IP_SUSPENDED` → `UpdateFailed` + `persistent_notification.async_create` called + `_backoff_until` set
5. Successful poll after strike → counters reset + both notifications dismissed
6. Quiet-hours event suppression → diff still runs (the function is called) BUT `hass.bus.async_fire` is not invoked; `_LOGGER.debug` emits suppression line
7. First poll on weekend (`should_poll=False`, `self.data is None`) → MUST fetch (the D-10 gate)
8. `RateLimitedError(reason != IP_SUSPENDED)` → `UpdateFailed`, **no** breaker tick
9. `CommunicationError` → `UpdateFailed`, **no** breaker tick
10. WR-04 cooldown interaction with breaker: an aliased `AuthError` short-circuiting to `UpdateFailed` via the cooldown MUST NOT tick the counter (CONTEXT.md D-13 explicit)

**Key invariants (MUST preserve):**
- **`mock_pronote_client` + `mock_config_entry` + `snapshot_with_n_lessons_today` fixture trio** is the canonical boot path. All new tests use it.
- **`patch("custom_components.ha_pronote.coordinator.fetch_all", ...)`** is the seam — NOT `patch("custom_components.ha_pronote.api.fetcher.fetch_all", ...)`. The coordinator imports `fetch_all` from `.api`, so the patch target is the imported binding (`coordinator.fetch_all`), not the source module. Verified at `coordinator.py:41-42`.
- **`# noqa: SLF001` on private-attribute access.** `coordinator._async_update_data()`, `coordinator._backoff_until`, `coordinator._consecutive_failures` — all leading-single-underscore attrs need this comment.
- **The first refresh in `_setup_coordinator` populates `coordinator.data`.** This is critical for the D-10 gate tests (the suspension short-circuit only kicks in when `self.data is not None`).

**Anti-patterns to avoid:**
- **Don't write a test against `coordinator._update_interval_seconds` directly.** Test `coordinator.update_interval` (the public property) per RESEARCH.md Pitfall 1.
- **Don't assert on exact `_backoff_until` to the second.** Use `assert _backoff_until > now and _backoff_until < now + timedelta(hours=1, seconds=JITTER_SECONDS)`. The first-strike backoff is `1h` ± jitter.
- **Don't patch `persistent_notification` per-test with `@patch(...)`.** Use the `mock_persistent_notification` fixture from conftest.py for consistency.
- **Don't test HA's `_schedule_refresh` integration.** Per RESEARCH.md last line of "freezegun / pytest-freezer" section: *"Phase 5's backoff tests primarily test the state (`_backoff_until`, `_consecutive_failures`, notification calls) and skip the scheduler integration (HA's `_schedule_refresh` is the framework's concern, not ours)."*

---

### 11. `tests/test_no_ha_imports.py` (APPEND `politesse.py` to AST-guarded list)

**Analog:** `tests/test_no_ha_imports.py` (itself, lines 1-80).

**Path-list extension pattern** (from `test_no_ha_imports.py:27-33`):

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_PATHS = [
    REPO_ROOT / "custom_components" / "ha_pronote" / "api",
    REPO_ROOT / "custom_components" / "ha_pronote" / "diff",
    REPO_ROOT / "tests" / "test_api",
    REPO_ROOT / "tests" / "test_diff",
]
```

Phase 5 APPENDS `politesse.py` (file, not directory) and `tests/test_politesse.py`. Two options:

**Option A — extend `GUARDED_PATHS` with file paths:**

```python
GUARDED_PATHS = [
    REPO_ROOT / "custom_components" / "ha_pronote" / "api",
    REPO_ROOT / "custom_components" / "ha_pronote" / "diff",
    REPO_ROOT / "custom_components" / "ha_pronote" / "politesse.py",   # Phase 5 — D-16
    REPO_ROOT / "tests" / "test_api",
    REPO_ROOT / "tests" / "test_diff",
    REPO_ROOT / "tests" / "test_politesse.py",                          # Phase 5 — D-20
]
```

The existing `_python_files(root)` helper at `test_no_ha_imports.py:48-50` uses `if root.is_dir() else []` — so a file path returns `[]`. Phase 5 must either generalize `_python_files` to handle files (recommended) OR introduce a separate `GUARDED_FILES` list and merge both.

**Option B — generalize `_python_files`:**

```python
def _python_files(root: Path) -> list[Path]:
    """Return every ``.py`` file under ``root`` (or [root] if it's a file)."""
    if root.is_file() and root.suffix == ".py":
        return [root]
    return list(root.rglob("*.py")) if root.is_dir() else []
```

Option B is the cleaner extension — preserves the existing parametrize collection at line 53-56 with no further changes.

**AST visitor invocation (unchanged) — for reference** (from `test_no_ha_imports.py:60-73`):

```python
tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith("homeassistant"), (
                f"{py_file.relative_to(REPO_ROOT)} imports {alias.name} — "
                f"D-19 violated. Move to coordinator.py (Phase 3+)."
            )
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        assert not module.startswith("homeassistant"), (
            f"{py_file.relative_to(REPO_ROOT)} imports from {module} — "
            f"D-19 violated. Move to coordinator.py (Phase 3+)."
        )
```

The walker is generic — it just checks every `.py` file in `GUARDED_PATHS`. Phase 5 needs no AST logic changes.

**Key invariants (MUST preserve):**
- **`auto_enable_custom_integrations` override** (`test_no_ha_imports.py:36-45`) — this gate is HA-free; the override prevents the root autouse from forcing HA test harness load.
- **`test_guarded_paths_are_not_empty` sanity check** (`test_no_ha_imports.py:76-80`) — Phase 5's new file paths MUST satisfy this. The check uses `_python_files(path)` so Option B above is required for the file-path case.
- **Error message wording stays unchanged.** *"D-19 violated. Move to coordinator.py (Phase 3+)."* — this is the same Phase 2 D-19 invariant Phase 5 extends to `politesse.py`.

**Anti-patterns to avoid:**
- **Don't add `politesse.py`'s parent directory (`custom_components/ha_pronote`).** That would protect ALL Python files in the integration, including `coordinator.py` which legitimately imports `homeassistant.*`. Only the specific file gets the AST guard.
- **Don't skip the test_politesse.py guard.** Phase 5 "Specifics" memo and D-20: pure tests should not need `homeassistant.*`. If they do, the test design is wrong (should use the `mock_persistent_notification` fixture or `mock_config_entry`, which live in HA-aware tests under `test_coordinator.py`).

---

## Shared Patterns

### Shared Pattern A: Typed-exception "no silent catch" discipline

**Source:** `/home/moi/.claude/projects/-data-projets-perso-pronote/memory/feedback_no_silent_exceptions.md` + `coordinator.py:118-146`

**Apply to:** `_handle_failure` (coordinator), `_resolve_options` (coordinator), every politesse predicate

**Concrete excerpt** (`coordinator.py:142-146`):

```python
except RateLimitedError as err:
    # D-22 — IP_SUSPENDED -> UpdateFailed; Phase 5 reads .reason for backoff.
    raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err  # WR-05
except (CommunicationError, PronoteIntegrationError) as err:
    raise UpdateFailed(f"[{err.reason}] {redact(err.message)}") from err  # WR-05
```

The pattern: typed-exception catch → REMAP to HA-typed exception → re-raise with `from err` to preserve chain → `redact()` on the message. Phase 5's `_handle_failure` ADDS a side-effect (counter tick + notification) but DOES NOT change the remap behaviour. The exception still propagates raw.

`_resolve_options(entry)` follows a related rule (D-17): on parse error, log warning + fall back to default — never swallow silently. The warning IS the trace.

### Shared Pattern B: `redact()` on every credentials-bearing error string

**Source:** `api/errors.py:27-38` + `coordinator.py:130, 144, 146, 220, 223, 226`

**Apply to:** `_handle_failure` notification body, every `UpdateFailed` / `ConfigEntryAuthFailed` raised in Phase 5 coordinator extensions

**Concrete excerpt** (`api/errors.py:27-38`):

```python
def redact(message: str) -> str:
    """Return ``message`` with known credential-bearing fragments replaced.

    WR-05: pronotepy exception messages are not strictly redacted; a future
    pronotepy version (or a 500 with the request URL echoed back) could put
    the user's URL, username, or partial token in ``str(err)``. ...
    """
    for pattern in _REDACT_PATTERNS:
        message = pattern.sub("<redacted>", message)
    return message
```

Patterns matched: `password=`, `pwd=`, `token=`, `session=`, `authorization:`. Phase 5's f-strung notification body MUST pass `err.message` through `redact()` per D-15 + CLAUDE.md "jamais en clair dans les logs".

### Shared Pattern C: `Final`-typed constants with Phase-anchor comments

**Source:** `const.py` (every section line starts with `# Phase X additions —`)

**Apply to:** `const.py` Phase 5 append (D-18)

**Concrete excerpt** (`const.py:12-32`):

```python
# Phase 2 additions (D-15, D-18) — defaults consumed by Phase 3 coordinator.
DEFAULT_SCHOOL_TZ: Final = "Pacific/Noumea"
DEFAULT_LOOKBACK_DAYS: Final = 7  # J-7
DEFAULT_LOOKAHEAD_DAYS: Final = 14  # J+14

# Phase 3 additions (D-24, D-25) — HA-side runtime defaults consumed by the
# coordinator (update_interval) and __init__.py (platform forwarding).
DEFAULT_REFRESH_INTERVAL: Final = timedelta(minutes=30)  # D-24 — Phase 5 makes adaptive

# Phase 4 additions — event-type constants (D-13, EVENT-01..03), ...
EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"   # D-13, EVENT-01
```

Phase 5 follows the same: `# Phase 5 additions — adaptive polling cadence, quiet hours, circuit breaker.` followed by `Final`-typed constants with inline `# D-XX` cross-refs.

### Shared Pattern D: TZ matrix on every datetime-sensitive test

**Source:** `tests/test_diff/test_lessons_tz_matrix.py:26-29`

**Apply to:** EVERY test in `tests/test_politesse.py`; relevant subset in `tests/test_coordinator.py` extensions

**Concrete excerpt:**

```python
pytestmark = pytest.mark.parametrize(
    "school_tz",
    ["Europe/Paris", "Pacific/Noumea"],
)
```

Phase 2 D-25 (the NC-author blind-spot guard) becomes DIST-06 in Phase 5. Module-level `pytestmark` is the project's preferred shape — every test in the module gets parametrized.

### Shared Pattern E: `async_add_executor_job(partial(fn, args...))` for blocking calls

**Source:** `__init__.py:69-79` + `coordinator.py:109-117, 184-211`

**Apply to:** `_compute_holiday_dates_for_year` call in `__init__.py:async_setup_entry`

**Concrete excerpt** (`__init__.py:69-79`):

```python
client = await hass.async_add_executor_job(
    partial(
        build_or_resume_client,
        entry.data["url"],
        entry.data["account_type"],
        entry.data["username"],
        entry.data["password"],
        entry.data.get("session"),
        device_name,
    )
)
```

The `partial(...)` wrap is mandatory when the callable takes positional args (executor takes a single callable + variadic). For zero-arg or single-arg callables, `hass.async_add_executor_job(fn)` or `hass.async_add_executor_job(fn, arg)` is fine. Phase 5's `_compute_holiday_dates_for_year(year: int)` takes one arg, so:

```python
holiday_dates = await hass.async_add_executor_job(_compute_holiday_dates_for_year, now_year)
```

No `partial` needed.

---

## No Analog Found

Every Phase 5 file has an in-tree analog (the integration is mature enough that the prompt's pre-mapped analogs cover every case). Listed below for explicit "no surprise" confirmation:

| File | Reason |
|------|--------|
| (none) | All 10 files have direct analogs documented above. |

The single net-new file (`politesse.py`) DOES have analogs (`_strip.py` + `diff/lessons.py`) — they share the "HA-free pure Python module" role even though their domains differ. The same is true for `test_politesse.py` (analogs: `test_diff/test_lessons.py` + `test_diff/test_lessons_tz_matrix.py`).

---

## Metadata

**Analog search scope:** `custom_components/ha_pronote/{api,diff}/*`, `custom_components/ha_pronote/*.{py,json}`, `custom_components/ha_pronote/translations/*.json`, `tests/conftest.py`, `tests/test_coordinator.py`, `tests/test_no_ha_imports.py`, `tests/test_diff/test_lessons.py`, `tests/test_diff/test_lessons_tz_matrix.py`, `custom_components/ha_pronote/api/__init__.py`, `custom_components/ha_pronote/api/errors.py`
**Files scanned:** 14 source files + 4 phase planning artifacts (CONTEXT.md, RESEARCH.md, DISCUSSION-LOG.md surface only, VALIDATION.md surface only)
**Pattern extraction date:** 2026-05-25
**Phase boundary read:** CONTEXT.md `<domain>` section (lines 6-115) for the explicit file list; CONTEXT.md `<decisions>` section (D-01..D-20) for invariants; CONTEXT.md `<canonical_refs>` for cross-phase invariant inheritance; RESEARCH.md "Stack Verification" for the API surface verifications (`persistent_notification` is `@callback`, `update_interval` setter contract, `holidays==0.97` no I/O).

---

## Quick-Reference Index for the Planner

When writing each plan's action section, copy the analog file path + line range below and paste-then-tailor:

| Plan | New/Modified File | Copy patterns from |
|------|-------------------|---------------------|
| 05-01 | `politesse.py` | `api/_strip.py:1-40` (module docstring + pure-fn shape) + `diff/lessons.py:64-119` (Args/Returns docstring + first-arg-None guard) |
| 05-01 | `tests/test_politesse.py` | `tests/test_diff/test_lessons.py:36-110` (TestClass grouping) + `tests/test_diff/test_lessons_tz_matrix.py:26-29` (module-level pytestmark) |
| 05-01 | `tests/test_no_ha_imports.py` | `tests/test_no_ha_imports.py:27-33` (GUARDED_PATHS list — generalize `_python_files` per Option B) |
| 05-02 | `const.py` | `const.py:19-32` (Phase-anchor comment + `Final`-typed constants) |
| 05-02 | `manifest.json` | `manifest.json:11` (`"requirements": [..., "X==Y.Z"]` — exact-pin discipline) |
| 05-02 | `scripts/probe_nc_holidays.py` (C-03) | RESEARCH.md "Stack Verification" §"holidays PyPI Library" — verify subdiv=NC + 24 Sept |
| 05-03 | `coordinator.py` | `coordinator.py:118-146` (typed-exception remap) + `coordinator.py:127-141` (WR-04 in-method state check) + `coordinator.py:174-228` (`_handle_*` helper shape) + `coordinator.py:248-283` (`_fire_diff_events` loop — extend with top-of-method gate) |
| 05-03 | `data.py` | `data.py:27-35` (dataclass field-add — TYPE_CHECKING discipline + NOT-frozen invariant) |
| 05-03 | `__init__.py` | `__init__.py:62-79` (`async_add_executor_job(partial(...))` idiom) + `__init__.py:110-116` (`runtime_data = PronoteData(...)` kwargs) |
| 05-03 | `strings.json` + `translations/{fr,en}.json` | `strings.json:35-52` (`entity.sensor.*` nested-key shape) |
| 05-03 | `tests/conftest.py` | `tests/conftest.py:51-67` (`@pytest.fixture` + `MagicMock` idiom) |
| 05-03 | `tests/test_coordinator.py` | `tests/test_coordinator.py:256-271` (`_setup_coordinator` helper) + `tests/test_coordinator.py:288-304` (`side_effect=[...]` sequential pattern) + `tests/test_coordinator.py:519-521` (post-state assertion) + RESEARCH.md "freezegun / pytest-freezer in PHACC Tests" (freezer recipe — NEW idiom for the project) |
