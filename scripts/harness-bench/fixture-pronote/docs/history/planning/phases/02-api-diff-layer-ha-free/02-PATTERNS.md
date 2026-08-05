# Phase 2: API & Diff Layer (HA-free) - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 33 (28 to create, 5 to modify, 6 generated fixtures listed for completeness)
**Analogs found:** 33 / 33

## Greenfield Notice for `api/`, `diff/`, `scripts/`

Phase 1 shipped a HACS-loadable shell — `manifest.json`, `const.py:DOMAIN`, placeholder `config_flow.py`, `tests/conftest.py`, `pyproject.toml`, `requirements_test.txt`, `.github/workflows/test.yml`. **There is zero Python runtime code in `custom_components/ha_pronote/` beyond `const.py` and the placeholder ConfigFlow.** No `api/`, no `diff/`, no `scripts/`. Every Phase 2 NEW file is greenfield in this repo.

Consequence for the planner: **internal Phase 1 analogs cover only structural/tooling files** (`tests/conftest.py`, `pyproject.toml`, `requirements_test.txt`, `tests/test_manifest.py`, `.github/workflows/test.yml`). Every `api/*.py`, `diff/*.py`, `scripts/snapshot.py`, and most `tests/test_api/` and `tests/test_diff/` files cite **external analogs only**:

- `delphiki/HomeAssistant-Pronote` — `coordinator.py` (the 26-call-site `async_add_executor_job` pattern, `_strip_client_refs` walker, `compare_data` diff shape) and `pronote_helper.py` (sync client builder)
- `bain3/pronotepy` `pronotepy/clients.py` — the `Client.__init__(url, username, password)` and `ParentClient` constructor surfaces Phase 2 wraps
- HA Core `homeassistant/util/dt.py` — *concept-only* (Phase 2's `api/` cannot import it per D-19; we mirror its tz-localization idiom against `zoneinfo.ZoneInfo` directly)
- Python stdlib idioms — `dataclasses.dataclass(frozen=True)` + `from_dict`/`to_dict` classmethods (mirrored after `homeassistant.helpers.entity.DeviceInfo`-style typed dicts), `enum.StrEnum` (PEP 663, stdlib since 3.11), `argparse` for `scripts/snapshot.py`

**Planner directive:** Phase 2 has no RESEARCH.md (orchestrator skipped research-step). External analogs are cited by repo+file path only — the planner reads CONTEXT.md decisions D-01..D-28 + this pattern map + the relevant section of `.planning/research/ARCHITECTURE.md` and `.planning/research/PITFALLS.md`. Do NOT re-fetch external repos; the architectural shape is locked by D-08, D-22, D-23, D-24.

---

## File Classification

### NEW files (28 — every one greenfield in this repo)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|----------------|
| `custom_components/ha_pronote/api/__init__.py` | package marker | declarative re-exports | `custom_components/ha_pronote/__init__.py` (Phase 1, lines 1–11 — same docstring + `__all__` shape) | role-match |
| `custom_components/ha_pronote/api/client.py` | service (sync facade) | request-response (sync HTTP via pronotepy) | `delphiki/hass-pronote/custom_components/pronote/pronote_helper.py:get_pronote_client` + `bain3/pronotepy/pronotepy/clients.py:Client.__init__` | role-match (idea, not code — D-21) |
| `custom_components/ha_pronote/api/fetcher.py` | service (sync orchestrator) | batch (multi-fetch + transform) | `delphiki/hass-pronote/custom_components/pronote/coordinator.py:_async_update_data` (executor-side calls) — strip pronotepy refs into our dataclasses | role-match (idea, not code — D-24) |
| `custom_components/ha_pronote/api/models.py` | model (dataclasses) | declarative | stdlib `@dataclass(frozen=True)` + `classmethod from_dict` + `to_dict` round-trip idiom; HA `DeviceInfo` typed-dict shape | role-match (stdlib idiom) |
| `custom_components/ha_pronote/api/errors.py` | model (typed exception hierarchy) | event-driven (raised) | CLAUDE.md "What NOT to Use" §"PronoteIntegrationError(reason=…)" + Pitfall 2 wrapper recipe; PEP 663 `enum.StrEnum` | role-match (PITFALLS.md recipe) |
| `custom_components/ha_pronote/api/_strip.py` | utility (private walker) | transform | `delphiki/hass-pronote/custom_components/pronote/coordinator.py:_strip_client_refs` — copy the *idea* (D-24, C-05), not the literal code (delphiki's data shape ≠ ours) | role-match |
| `custom_components/ha_pronote/diff/__init__.py` | package marker | declarative re-exports | `custom_components/ha_pronote/__init__.py` (Phase 1, lines 1–11) — same `__all__` shape | role-match |
| `custom_components/ha_pronote/diff/lessons.py` | service (pure function) | transform (CRUD-style set-diff) | `delphiki/hass-pronote/.../coordinator.py:compare_data` — same shape; cleaner identity-vs-content keys per Pitfall 10 + the spike (D-08) | role-match (idea, refined per spike) |
| `custom_components/ha_pronote/diff/events.py` | model (dataclasses) | declarative | ARCHITECTURE.md Pattern 3 lines 260–278 (event payload schema) + stdlib `@dataclass(frozen=True)` + `to_payload() -> dict` method (D-09, C-01) | role-match (ARCHITECTURE.md recipe) |
| `custom_components/ha_pronote/diff/grades.py` | service stub | transform (Phase 4 fills) | Pattern: `raise NotImplementedError` body + types imported from `events.py` (D-02). Closest in-repo: `custom_components/ha_pronote/config_flow.py:async_step_user` (Phase 1 placeholder pattern — return-an-abort/raise-NotImplemented + minimal docstring naming Phase 4) | exact (Phase 1 placeholder shape) |
| `custom_components/ha_pronote/diff/notifications.py` | service stub | transform (Phase 4 fills) | Same as `diff/grades.py` (mirror file) | exact (Phase 1 placeholder shape) |
| `scripts/snapshot.py` | utility (one-shot CLI) | request-response + file-I/O | Stdlib idiom: `argparse.ArgumentParser` + `os.environ.get` + `json.dump`. `python-dotenv` is NOT a runtime dep (D-13) — read `.env` manually OR rely on shell-exported env vars. Recursive walker for anonymizer mirrors `_strip_client_refs` shape (C-03) | role-match (stdlib idiom) |
| `tests/test_api/conftest.py` | test fixture module | declarative (pytest fixtures) | `tests/conftest.py` (Phase 1, lines 1–16) — local override scope (no `enable_custom_integrations` autouse — `api/` is HA-free per D-19) | role-match (Phase 1 conftest minus PHACC autouse) |
| `tests/test_api/test_client.py` | test (unit + mocked HTTP) | unit | `tests/test_manifest.py` (Phase 1, lines 1–24, 32–35) — module-level path resolution + `_load_manifest()` helper. For HTTP mocking: `requests-mock==1.12.1` (D-26) — `requests_mock` fixture from `requirements_test.txt` (transitive via PHACC, made explicit Phase 2) | role-match (parse pattern + new mocking layer) |
| `tests/test_api/test_fetcher.py` | test (unit + tz-aware) | unit | `tests/test_manifest.py` (Phase 1) — assertion-style + `freezegun==1.5.5` (transitive via PHACC) for `today` injection determinism. tz-localization assertions: `assert lesson.start.tzinfo is not None` | role-match |
| `tests/test_api/test_models.py` | test (round-trip) | unit | `tests/test_manifest.py` (Phase 1, lines 21–24 — `_load_manifest()` JSON round-trip pattern). Adapt to: `Snapshot.from_dict(json.load(...)).to_dict() == json.load(...)` | exact (round-trip pattern) |
| `tests/test_api/test_strip.py` | test (walker) | unit | `tests/test_manifest.py` — flat assertion set against a fixture loaded once at module level | role-match |
| `tests/test_api/test_errors.py` | test (enum + subclass init) | unit | `tests/test_manifest.py` — flat assertion set. New surface: `assert AuthError("msg").reason == ErrorReason.AUTH_FAILED` | role-match |
| `tests/test_diff/conftest.py` | test fixture (tz-aware loader) | declarative | `tests/conftest.py` (Phase 1, lines 1–16). Adapt: read fixture's top-level `"school_tz"` field, rebuild `datetime.fromisoformat(...).replace(tzinfo=ZoneInfo(school_tz))` for every datetime in the snapshot | role-match (Phase 1 conftest + tz post-processing) |
| `tests/test_diff/test_lessons.py` | test (parameterized matrix) | unit | `tests/test_manifest.py` flat-assertion shape + new: `@pytest.mark.parametrize("school_tz", ["Europe/Paris", "Pacific/Noumea"])` per D-25. Each case loads a fixture pair from `tests/fixtures/real/` or `tests/fixtures/synthetic/` | role-match (Phase 1 + new tz parametrization) |
| `tests/test_diff/test_lessons_synthetic.py` | test (combinatorics) | unit | Same shape as `test_lessons.py` but loads only from `tests/fixtures/synthetic/` | role-match |
| `tests/test_fixtures.py` | test (schema gate) | unit | `tests/test_manifest.py` (Phase 1, lines 21–35 — JSON load + `set(.keys()) == expected` shape). Adapt to: `pathlib.Path(__file__).resolve().parent / "fixtures"` glob walk | exact (round-trip pattern) |
| `tests/test_no_ha_imports.py` | test (static AST guard) | unit | New surface — no in-repo analog. Stdlib idiom: `ast.parse(source).body` walk + `isinstance(node, ast.Import \| ast.ImportFrom)` checking `node.module.startswith("homeassistant")` | no analog (stdlib `ast` only) |
| `tests/test_scripts/test_snapshot.py` | test (smoke + invariant) | unit | `tests/test_manifest.py` shape; the invariant `assert no_pii(anonymize(fixture)) is True` is bespoke (D-13, `<specifics>` line 213) | role-match |
| `tests/fixtures/real/cancellation_T0.json` | fixture (data) | declarative | Generated by `scripts/snapshot.py` (anonymized output). NOT authored. Listed for completeness. | n/a (generated) |
| `tests/fixtures/real/cancellation_T1.json` | fixture (data) | declarative | Same | n/a (generated) |
| `tests/fixtures/real/room_change_T{0,1}.json` | fixture (data) | declarative | Same | n/a (generated) |
| `tests/fixtures/real/teacher_swap_T{0,1}.json` | fixture (data) | declarative | Same | n/a (generated) |
| `tests/fixtures/synthetic/*.json` (6 files: empty_to_empty, reorder_no_op, multi_change, first_poll_after_restart, lesson_removed, lesson_added) | fixture (hand-crafted) | declarative | The `Snapshot.to_dict()` shape — must round-trip via `tests/test_fixtures.py` (D-11) | role-match (hand-authored to schema) |
| `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` | docs (analysis) | declarative | `.planning/research/PITFALLS.md` §"Pitfall 10" — same shape (problem statement + observed semantics + recipe). Phase 2's spike OUTPUT, not authored ahead | role-match (PITFALLS.md narrative shape) |
| `.env.example` | config (env-var template) | declarative | New surface — no in-repo analog. Standard Twelve-Factor App pattern: `KEY=value` lines, comments via `#`. D-14 lists the four required vars | no analog (community standard) |

### MODIFIED files (5 — Phase 1 already shipped these)

| Existing File | Role | Modification | Internal Analog (the file itself) | Match Quality |
|----------|------|---------|----------------|----------------|
| `custom_components/ha_pronote/const.py` | constants | APPEND `DEFAULT_SCHOOL_TZ`, `DEFAULT_LOOKBACK_DAYS`, `DEFAULT_LOOKAHEAD_DAYS` | Phase 1 lines 1–7 (existing `DOMAIN: Final` declaration) — append in same `Final`-typed style | exact |
| `pyproject.toml` | tooling | APPEND `[tool.pytest.ini_options]` `timeout` marker; APPEND `[tool.coverage.run] omit` for stub modules | Phase 1 lines 34–62 (existing `[tool.pytest.ini_options]` and `[tool.coverage.run]`/`[tool.coverage.report]` blocks) | exact |
| `requirements_test.txt` | tooling | APPEND `requests-mock==1.12.1` | Phase 1 lines 1–16 (existing pinned-deps shape with explanatory comments) | exact |
| `.github/workflows/test.yml` | workflow | AMEND pytest invocation: `--cov=custom_components/ha_pronote/diff --cov-fail-under=90`; add `strategy.matrix` axis for `Europe/Paris` + `Pacific/Noumea` | Phase 1 lines 1–25 (existing `pytest -q` step) | exact |
| `tests/conftest.py` | test fixture | **NO MODIFICATION** (Phase 2 conftest extensions live in subdirectory `tests/test_api/conftest.py` and `tests/test_diff/conftest.py` per `<canonical_refs>` line 160) | n/a — referenced by Phase 2 tests, not modified | n/a |

---

## Pattern Assignments

### `custom_components/ha_pronote/api/__init__.py` (package marker, declarative)

**Internal analog:** `custom_components/ha_pronote/__init__.py` (Phase 1)

**Imports / package marker pattern** (Phase 1 `__init__.py` lines 1–11):
```python
"""HA-Pronote — Home Assistant integration for Pronote.

Phase 1: package skeleton only. The coordinator, sensors, calendar entity, and
real Config Flow ship in subsequent phases (see ROADMAP.md). This file is
intentionally minimal so the integration can be loaded by HA / HACS without
exposing any runtime behavior yet.
"""

from .const import DOMAIN

__all__ = ["DOMAIN"]
```

**Phase 2 adaptation:** docstring → "API subpackage. Pure-sync facade over `pronotepy==2.14.6` per Phase 2 D-19 (zero `homeassistant.*` imports)." `__all__` re-exports `build_client`, `fetch_all`, the error hierarchy. NO `homeassistant.*` import (D-19, `tests/test_no_ha_imports.py` enforces).

---

### `custom_components/ha_pronote/api/client.py` (service, sync facade)

**External analog:** `delphiki/hass-pronote/custom_components/pronote/pronote_helper.py:get_pronote_client` (the canonical sync `pronotepy.Client(url, user, pwd)` builder; idea-only — D-21 forbids the parent-account-with-ENT branches delphiki ships)

**Constructor pattern** (locked by D-21):
```python
"""Sync facade over pronotepy — HA-free per D-19/D-20."""
from __future__ import annotations

from typing import Literal

import pronotepy  # NO pronotepy.ent.* imports (D-33 / Phase 1 anti-pattern)

from .errors import AuthError, CommunicationError, RateLimitedError, ErrorReason

AccountType = Literal["eleve", "parent"]  # C-04 RECOMMENDED


def build_client(
    url: str,
    account_type: AccountType,
    username: str,
    password: str,
) -> pronotepy.Client | pronotepy.ParentClient:
    """Construct a pronotepy client. Sync — caller wraps in async_add_executor_job."""
    cls = pronotepy.ParentClient if account_type == "parent" else pronotepy.Client
    try:
        return cls(url, username=username, password=password)
    except pronotepy.PronoteAPIError as err:
        if "Your IP address is suspended" in str(err):  # D-22, Pitfall 1 literal
            raise RateLimitedError(reason=ErrorReason.IP_SUSPENDED, message=str(err)) from err
        raise CommunicationError(reason=ErrorReason.SERVER_DOWN, message=str(err)) from err
    except pronotepy.exceptions.CryptoError as err:  # Pitfall 2 — looks like wrong password but isn't
        raise AuthError(reason=ErrorReason.AUTH_FAILED, message=str(err)) from err
```

**Banned imports** (Phase 1 `pyproject.toml` lines 139–142 — ruff banned-API enforces):
- NO `requests` direct (D-32 / Phase 1 banned-api)
- NO `pronotepy.ent.*` (D-33)
- NO `homeassistant.*` (D-19)

**Error mapping table** (locked by D-22):
| pronotepy raises | Detection | We raise |
|---|---|---|
| `pronotepy.exceptions.CryptoError("Padding...")` | exception class | `AuthError(AUTH_FAILED)` |
| `PronoteAPIError("Your IP address is suspended")` | substring check | `RateLimitedError(IP_SUSPENDED)` |
| `PronoteAPIError(code=N)` other | exception class | `CommunicationError(PROTOCOL_BROKEN)` |
| network/socket errors | `OSError` | `CommunicationError(SERVER_DOWN)` |

---

### `custom_components/ha_pronote/api/fetcher.py` (service, sync orchestrator)

**External analog:** `delphiki/hass-pronote/custom_components/pronote/coordinator.py:_async_update_data` — the executor-side fetch sequence (lessons, grades, information_and_surveys). Idea, not code — delphiki's coordinator mixes HA logic; Phase 2 ships ONLY the sync core.

**Function signature pattern** (locked by D-15, D-17, D-18, D-23):
```python
"""Snapshot fetch + tz-localization. Sync — caller wraps in executor."""
from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pronotepy

from ._strip import strip_client_refs
from .models import Snapshot, Lesson, Grade, Information


def fetch_all(
    client: pronotepy.Client | pronotepy.ParentClient,
    today: date,                          # D-17: passed in, not computed
    school_tz: ZoneInfo,                  # D-18: passed in, no global default
) -> Snapshot:
    """Fetch J−7 → J+14 window (D-15), tz-localize, strip back-refs (D-24)."""
    start = today - timedelta(days=7)
    end = today + timedelta(days=14)
    raw_lessons = client.lessons(date_from=start, date_to=end)
    raw_grades = client.current_period.grades if client.current_period else []
    raw_info = client.information_and_surveys

    return Snapshot(
        today=today,
        school_tz=str(school_tz),
        lessons=[_lesson_from_raw(L, school_tz) for L in raw_lessons],
        grades=[_grade_from_raw(G, school_tz) for G in raw_grades],
        information=[_info_from_raw(I, school_tz) for I in raw_info],
    )
```

**tz-localization pattern** (locked by D-23, Pitfall 4):
```python
def _localize(naive_dt, school_tz: ZoneInfo):
    """Pronotepy returns naive datetimes in school local time (Pitfall 4)."""
    if naive_dt is None:
        return None
    if naive_dt.tzinfo is not None:
        return naive_dt  # already aware (defensive — pronotepy 2.14.6 returns naive but future-proof)
    return naive_dt.replace(tzinfo=school_tz)
```

**Back-ref stripping** (locked by D-24, C-05 — calls into `api/_strip.py`):
```python
def _lesson_from_raw(raw, school_tz: ZoneInfo) -> Lesson:
    """Copy fields out — never store the pronotepy object itself (Anti-Pattern 5)."""
    return Lesson(
        date=raw.start.date(),
        start=_localize(raw.start, school_tz),
        end=_localize(raw.end, school_tz),
        subject=raw.subject.name if raw.subject else "",
        teacher=raw.teacher_name or "",
        classroom=raw.classroom or "",
        canceled=bool(raw.canceled),
        status=raw.status or "",
        # ... NO `client` reference, NO `_obj`, NO pronotepy back-pointer
    )
```

**Banned in this file:**
- NO `datetime.now()` — `today` is injected (D-17)
- NO `dt_util` (HA helper banned by D-19/D-20)
- NO global `school_tz` — passed in (D-18)
- NO `pytz` — `zoneinfo` only (Phase 1 banned-api)

---

### `custom_components/ha_pronote/api/models.py` (model, dataclasses)

**External analog:** Stdlib `@dataclass(frozen=True)` + `from_dict`/`to_dict` round-trip pattern. Closest in-repo: `tests/test_manifest.py:_load_manifest` (Phase 1 lines 21–24) — JSON-load idiom Phase 2 mirrors at the model layer.

**Dataclass pattern** (locked by D-3, D-23, D-16):
```python
"""Plain dataclasses — JSON-serializable, frozen, tz-aware."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Lesson:
    """One pronotepy lesson, fields copied out (no client back-ref)."""
    date: date
    start: datetime  # tz-aware, localized in fetcher (D-23)
    end: datetime
    subject: str
    teacher: str
    classroom: str
    canceled: bool
    status: str
    # NO `_pronotepy_obj`, NO `client`, NO `_raw` — Anti-Pattern 5

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any], school_tz: ZoneInfo) -> "Lesson":
        return cls(
            date=date.fromisoformat(data["date"]),
            start=datetime.fromisoformat(data["start"]),  # ISO with offset preserves tz
            end=datetime.fromisoformat(data["end"]),
            # ... rest pass-through
        )
```

**`Snapshot` slice properties** (locked by D-16):
```python
@dataclass(frozen=True)
class Snapshot:
    today: date
    school_tz: str
    lessons: list[Lesson]
    grades: list[Grade]
    information: list[Information]

    @property
    def lessons_today(self) -> list[Lesson]:
        return [L for L in self.lessons if L.date == self.today]

    @property
    def lessons_tomorrow(self) -> list[Lesson]:
        from datetime import timedelta
        return [L for L in self.lessons if L.date == self.today + timedelta(days=1)]
```

**Round-trip invariant** (D-11): `Snapshot.from_dict(snap.to_dict()) == snap` for every fixture in `tests/fixtures/{real,synthetic}/`. Enforced by `tests/test_fixtures.py`.

---

### `custom_components/ha_pronote/api/errors.py` (model, typed exception hierarchy)

**External analog:** `CLAUDE.md` "What NOT to Use" + PITFALLS.md §"Pitfall 2" — the `PronoteIntegrationError(reason=...)` recipe. `enum.StrEnum` is stdlib (PEP 663, Python 3.11+).

**Pattern** (locked by D-22):
```python
"""Typed exception hierarchy — Phase 5 reads `.reason` to route circuit-breaker."""
from __future__ import annotations

from enum import StrEnum


class ErrorReason(StrEnum):
    AUTH_FAILED = "auth_failed"
    IP_SUSPENDED = "ip_suspended"
    PROTOCOL_BROKEN = "protocol_broken"
    SERVER_DOWN = "server_down"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    PARSE_ERROR = "parse_error"


class PronoteIntegrationError(Exception):
    """Base — never raised directly; subclass forces the reason."""
    def __init__(self, reason: ErrorReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(f"[{reason}] {message}")


class AuthError(PronoteIntegrationError):
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.AUTH_FAILED) -> None:
        super().__init__(reason, message)


class RateLimitedError(PronoteIntegrationError):
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.IP_SUSPENDED) -> None:
        super().__init__(reason, message)


class CommunicationError(PronoteIntegrationError):
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.SERVER_DOWN) -> None:
        super().__init__(reason, message)


class ParseError(PronoteIntegrationError):
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.PARSE_ERROR) -> None:
        super().__init__(reason, message)
```

**Test contract** (`tests/test_api/test_errors.py`):
- `assert AuthError("x").reason == ErrorReason.AUTH_FAILED`
- `assert RateLimitedError("x").reason == ErrorReason.IP_SUSPENDED`
- `assert isinstance(AuthError("x"), PronoteIntegrationError)`
- `assert ErrorReason.AUTH_FAILED == "auth_failed"` (StrEnum equality with raw strings — PEP 663)

---

### `custom_components/ha_pronote/api/_strip.py` (utility, private walker)

**External analog:** `delphiki/hass-pronote/.../coordinator.py:_strip_client_refs` — the *idea* (recursive walk, drop `client`/`_session` attributes, prevent JSON-serialization-blocking back-refs and memory leaks). NOT the literal code — delphiki walks delphiki-shaped data; we own ours.

**Pattern** (locked by D-24, C-05):
```python
"""Private — imported only by api/fetcher.py."""
from __future__ import annotations

from typing import Any


def strip_client_refs(obj: Any) -> Any:
    """Recursively walk a pronotepy object graph and drop `client`/`_session` back-refs.

    Not strictly needed if fetcher.py copies fields out via _lesson_from_raw etc., but
    kept as defense-in-depth for any field that carries a sub-object we missed.
    """
    if hasattr(obj, "__dict__"):
        for attr in ("client", "_session", "_client", "_pronote"):
            if hasattr(obj, attr):
                try:
                    setattr(obj, attr, None)
                except (AttributeError, TypeError):
                    pass
    return obj
```

**Test contract** (`tests/test_api/test_strip.py`): build a fixture with synthetic back-refs (a class with `client` attribute pointing to a sentinel), pass through `strip_client_refs`, assert the attribute is `None`.

**Privacy:** the leading underscore in the filename + module-level marker comment. Exposed only to `api.fetcher`.

---

### `custom_components/ha_pronote/diff/__init__.py` (package marker, declarative)

**Internal analog:** `custom_components/ha_pronote/__init__.py` (Phase 1 lines 1–11) — same docstring + `__all__` shape.

**Pattern** (locked by C-01 — single import surface for events + diff function):
```python
"""Pure diff functions over Snapshot. HA-free per D-19."""
from __future__ import annotations

from .events import LessonChange, NewGrade, NewInformation
from .lessons import diff_lessons

__all__ = ["LessonChange", "NewGrade", "NewInformation", "diff_lessons"]
```

NO `homeassistant.*` import (`tests/test_no_ha_imports.py` enforces).

---

### `custom_components/ha_pronote/diff/lessons.py` (service, pure function)

**External analog:** `delphiki/hass-pronote/.../coordinator.py:compare_data` (the "old vs new snapshot → list of changes" shape). Phase 2 refines per Pitfall 10 + spike findings (D-08).

**Function signature** (locked by D-08, D-09):
```python
"""Diff lessons: identity-vs-content keys, room-vs-cancellation discrimination."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from .events import LessonChange

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Lesson, Snapshot


def diff_lessons(
    previous: "Snapshot | None",
    new: "Snapshot",
    day: date,
) -> list[LessonChange]:
    """Return zero events on first poll (previous is None) per D-08 invariant."""
    if previous is None:
        return []
    # ... identity key + content key + room-change-vs-cancel discrimination
    # — exact algorithm spike-locked, NOT pre-locked here per D-05/D-06/D-08
```

**Identity key (starting hypothesis, spike-locked per D-08):**
```python
def _identity_key(lesson: "Lesson") -> tuple:
    return (lesson.date, lesson.start.time(), lesson.end.time(), lesson.subject)
    # NB: teacher_initial dropped — substitution is a CONTENT change (D-08)
```

**Content key (starting hypothesis, spike-locked per D-08):**
```python
def _content_key(lesson: "Lesson") -> tuple:
    return (lesson.canceled, lesson.status, lesson.classroom, lesson.teacher)
```

**Change types frozen** (D-09, ROADMAP Phase 4 success criterion #1):
- `"canceled"` — lesson disappeared OR `canceled` flag flipped True
- `"modified"` — content changed but identity matched
- `"teacher"` — teacher field changed (subset of "modified")
- `"room"` — classroom field changed (subset of "modified")

**Pitfall 10 special case (D-08, the bain3#311 bug):** if a lesson appears `canceled=True` AND another lesson at the SAME identity key appears `canceled=False` with a different `classroom`, emit ONE `room` event, not a `canceled` + `added` pair. Final algorithm comes from spike output `tests/fixtures/SPIKE-FINDINGS-bain3-311.md`.

**First-poll-skip invariant** (D-08, Pitfall 10): `assert diff_lessons(None, snapshot_with_50_lessons, day) == []` — tested in `tests/test_diff/test_lessons.py`.

**Reorder no-op invariant** (Pitfall 10): if `previous.lessons_today` and `new.lessons_today` contain the same lessons in different order (same identity + content keys), `diff_lessons(...) == []`.

---

### `custom_components/ha_pronote/diff/events.py` (model, dataclasses)

**External analog:** ARCHITECTURE.md Pattern 3 lines 260–278 (the canonical event payload schema for `pronote_schedule_changed`). Phase 2 ships the dataclasses; Phase 4 routes their `to_payload()` onto `hass.bus.async_fire`.

**Pattern** (locked by D-09, C-01):
```python
"""Event dataclasses — Phase 4 routes these onto hass.bus."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Any, Literal


ChangeType = Literal["canceled", "modified", "teacher", "room"]  # D-09 frozen taxonomy


@dataclass(frozen=True)
class LessonChange:
    change_type: ChangeType
    day: Literal["today", "tomorrow"]
    lesson_date: Date
    subject: str
    # before / after snapshots of the changed lesson — `before` is None for "added"-shaped
    before: dict[str, Any] | None
    after: dict[str, Any] | None

    def to_payload(self) -> dict[str, Any]:
        """ARCHITECTURE.md Pattern 3 lines 260–278 schema."""
        return {
            "change_type": self.change_type,
            "day": self.day,
            "lesson_date": self.lesson_date.isoformat(),
            "subject": self.subject,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class NewGrade:
    """Stub type — diff/grades.py body is Phase 4 (D-02)."""
    subject: str
    value: str
    date: Date
    # Phase 4 fills, Phase 2 just locks the field list

    def to_payload(self) -> dict[str, Any]:
        return {"subject": self.subject, "value": self.value, "date": self.date.isoformat()}


@dataclass(frozen=True)
class NewInformation:
    """Stub type — diff/notifications.py body is Phase 4 (D-02)."""
    info_id: str
    title: str
    date: Date

    def to_payload(self) -> dict[str, Any]:
        return {"info_id": self.info_id, "title": self.title, "date": self.date.isoformat()}
```

**Why a single file (C-01):** `from custom_components.ha_pronote.diff import LessonChange, NewGrade, NewInformation` — one import path for all event types; mirrors "this is what we EMIT" mental model.

---

### `custom_components/ha_pronote/diff/grades.py` (service stub, transform)

**Internal analog:** `custom_components/ha_pronote/config_flow.py` (Phase 1 lines 1–28) — the placeholder pattern (docstring naming the future-phase owner + body returns `async_abort` / raises `NotImplementedError`).

**Pattern** (locked by D-02, C-02):
```python
"""Grade diff — body lands in Phase 4. Type contract locked here.

Phase 2 ships `NewGrade` (in `diff/events.py` per C-01). Phase 4 fills this body
(D-02). The function signature below freezes Phase 4's contract so it cannot drift.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import NewGrade

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Snapshot


def diff_grades(previous: "Snapshot | None", new: "Snapshot") -> list[NewGrade]:
    """Return new grades since previous poll. First-poll returns []. Phase 4 fills."""
    raise NotImplementedError("diff_grades body lands in Phase 4 (D-02)")
```

**Coverage-omit alignment** (C-02): `pyproject.toml [tool.coverage.run] omit = ["*/diff/grades.py", "*/diff/notifications.py"]` keeps the ≥90% gate honest. `coverage exclude_lines` already includes `raise NotImplementedError` (Phase 1 line 59) — belt-and-suspenders.

---

### `custom_components/ha_pronote/diff/notifications.py` (service stub, transform)

**Internal analog:** Same as `diff/grades.py` — mirror file. `custom_components/ha_pronote/config_flow.py` (Phase 1 lines 1–28).

**Pattern** (locked by D-02, C-02):
```python
"""Information diff — body lands in Phase 4. Type contract locked here."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import NewInformation

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Snapshot


def diff_notifications(previous: "Snapshot | None", new: "Snapshot") -> list[NewInformation]:
    """Return new informations since previous poll. First-poll returns []. Phase 4 fills."""
    raise NotImplementedError("diff_notifications body lands in Phase 4 (D-02)")
```

---

### `scripts/snapshot.py` (utility, one-shot CLI)

**External analog:** Stdlib `argparse` + `os.environ` + `json.dump`. The anonymizer is a recursive-walk + dict-replacement pattern (C-03 RECOMMEND), shape-mirrored after `_strip_client_refs`.

**Pattern** (locked by D-12, D-13, D-14, C-03):
```python
"""One-shot real-Pronote spike + anonymizer (D-13). Not a tested code surface.

Reads PRONOTE_URL / PRONOTE_USERNAME / PRONOTE_PASSWORD / PRONOTE_ACCOUNT_TYPE
from .env (D-14). Outputs raw + anonymized JSON to tests/fixtures/real/.
ONLY anonymized output is committed (.gitignore covers the raw output).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

# scripts/ is OUTSIDE custom_components/ — direct sys.path manipulation needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from custom_components.ha_pronote.api.client import build_client
from custom_components.ha_pronote.api.fetcher import fetch_all


def _read_env(path: Path) -> dict[str, str]:
    """Manual .env parser — no python-dotenv runtime dep (D-13 = scripts/ excluded)."""
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def anonymize(snapshot_dict: dict, replacements: dict[str, str]) -> dict:
    """C-03: explicit name-list, recursive walk. NOT regex."""
    return walk_and_replace(snapshot_dict, replacements)


def walk_and_replace(obj, replacements: dict[str, str]):
    if isinstance(obj, str):
        for old, new in replacements.items():
            obj = obj.replace(old, new)
        return obj
    if isinstance(obj, dict):
        return {k: walk_and_replace(v, replacements) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk_and_replace(v, replacements) for v in obj]
    return obj


def no_pii(obj, pii_blocklist: list[str]) -> bool:
    """`<specifics>` line 213 — the smoke-test invariant."""
    serialized = json.dumps(obj)
    return not any(needle in serialized for needle in pii_blocklist)
```

**CLI shape:**
```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["cancellation", "room_change", "teacher_swap"])
    parser.add_argument("--phase", required=True, choices=["T0", "T1"])
    args = parser.parse_args()

    env = _read_env(Path(".env"))
    client = build_client(
        url=env["PRONOTE_URL"],
        account_type=env["PRONOTE_ACCOUNT_TYPE"],
        username=env["PRONOTE_USERNAME"],
        password=env["PRONOTE_PASSWORD"],
    )
    snap = fetch_all(client, today=date.today(), school_tz=ZoneInfo("Pacific/Noumea"))

    raw_path = Path(f"tests/fixtures/real/_raw_{args.scenario}_{args.phase}.json")  # gitignored
    anon_path = Path(f"tests/fixtures/real/{args.scenario}_{args.phase}.json")     # committed

    raw_path.write_text(json.dumps(snap.to_dict(), indent=2, ensure_ascii=False))
    replacements = _build_replacements(env)
    anon_path.write_text(json.dumps(anonymize(snap.to_dict(), replacements), indent=2, ensure_ascii=False))

    assert no_pii(json.loads(anon_path.read_text()), list(replacements.keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Replacements (D-12 spec):**
```python
def _build_replacements(env) -> dict[str, str]:
    return {
        env["PRONOTE_USERNAME"]: "Eleve Test",
        # firstname / lastname / teachers / classroom IDs / school URL / establishment
        # — explicit name list, NOT regex (C-03)
    }
```

**Excluded from quality gates** (D-13): NOT in `[tool.pyright] include`, NOT in `[tool.ruff]` strict checks (could be added to `per-file-ignores`), NOT in `[tool.coverage.run] source`. The ONE test against this surface is `tests/test_scripts/test_snapshot.py:test_anonymize_is_deterministic + test_no_pii`.

**.gitignore addition required:** `tests/fixtures/real/_raw_*.json` (raw output is local-only).

---

### `tests/test_api/conftest.py` (test fixture module, declarative)

**Internal analog:** `tests/conftest.py` (Phase 1 lines 1–16) — local override scope.

**Pattern** (locked by D-19 — pure-Python tests don't need PHACC autouse):
```python
"""Local fixtures for tests/test_api/. NO PHACC autouse — api/ is HA-free per D-19."""
from __future__ import annotations

import pytest
import requests_mock as rm  # D-26 explicit dep


@pytest.fixture
def mocked_pronote_session():
    """requests-mock against pronotepy's underlying requests.Session (D-26)."""
    with rm.Mocker() as mocker:
        yield mocker


@pytest.fixture
def fixture_path():
    """Resolve fixtures relative to repo root."""
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "fixtures"
```

**Why no `enable_custom_integrations` autouse:** Phase 2's `api/` and `diff/` tests do NOT need the `hass` fixture. The root `tests/conftest.py` autouse fixture is fine where it lives (it's only invoked when tests *use* `hass`); these tests don't.

---

### `tests/test_api/test_client.py` (test, unit + mocked HTTP)

**Internal analog:** `tests/test_manifest.py` (Phase 1 lines 1–24, 32–35) — flat module-level path resolution + `_load_*()` helper + per-decision assertion test. Adapted for HTTP mocking via `requests-mock`.

**Pattern** (locked by D-26, D-22):
```python
"""Unit tests for api/client.py — D-26 hermetic via requests-mock."""
from __future__ import annotations

import pytest

from custom_components.ha_pronote.api.client import build_client
from custom_components.ha_pronote.api.errors import (
    AuthError,
    CommunicationError,
    ErrorReason,
    RateLimitedError,
)


def test_ip_suspended_raises_rate_limited(mocked_pronote_session):
    """D-22: literal 'Your IP address is suspended' → RateLimitedError(IP_SUSPENDED)."""
    mocked_pronote_session.post(
        "https://example.com/pronote/eleve.html",
        json={"Erreur": {"G": 0, "Message": "Your IP address is suspended"}},
        status_code=200,
    )
    with pytest.raises(RateLimitedError) as exc:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert exc.value.reason == ErrorReason.IP_SUSPENDED


def test_eleve_account_type_returns_client(mocked_pronote_session):
    """C-04: account_type="eleve" → pronotepy.Client (not ParentClient)."""
    # ... mock successful auth response, assert isinstance


def test_parent_account_type_returns_parent_client(mocked_pronote_session):
    """C-04: account_type="parent" → pronotepy.ParentClient."""
    # ...
```

**Banned in this file** (Phase 1 banned-api): NO `requests` import; the mocker is the public surface.

---

### `tests/test_api/test_fetcher.py` (test, unit + tz-aware)

**Internal analog:** `tests/test_manifest.py` (Phase 1) — flat assertion shape.

**Pattern** (locked by D-15, D-17, D-18, D-23):
```python
"""Unit tests for api/fetcher.py — tz-localization, J−7→J+14 window, back-ref strip."""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from custom_components.ha_pronote.api.fetcher import fetch_all


def test_fetch_all_window_is_j_minus_7_to_j_plus_14(mocked_pronote_session):
    """D-15: fetch covers J−7 → J+14 from day one."""
    today = date(2026, 5, 4)
    # ... mock pronotepy lessons() — assert called with date_from=today-7, date_to=today+14


def test_naive_datetimes_are_localized_to_school_tz(mocked_pronote_session):
    """D-23 / Pitfall 4: pronotepy returns naive dt's; we localize to school_tz."""
    snap = fetch_all(client, today=date(2026, 5, 4), school_tz=ZoneInfo("Pacific/Noumea"))
    for L in snap.lessons:
        assert L.start.tzinfo is not None
        assert L.start.tzinfo.utcoffset(None).total_seconds() == 11 * 3600  # NC = UTC+11


def test_no_pronotepy_back_refs_in_snapshot(mocked_pronote_session):
    """D-24: Anti-Pattern 5 — no pronotepy objects leak into Snapshot."""
    snap = fetch_all(...)
    for L in snap.lessons:
        assert not hasattr(L, "client")
        assert not hasattr(L, "_pronotepy_obj")
```

---

### `tests/test_api/test_models.py` (test, round-trip)

**Internal analog:** `tests/test_manifest.py` (Phase 1 lines 21–24) — JSON round-trip pattern adapted from manifest-loading.

**Pattern** (locked by D-11, D-16):
```python
def test_snapshot_from_dict_to_dict_roundtrip():
    """D-11 invariant: every fixture round-trips cleanly through Snapshot."""
    raw = json.loads(fixture_path / "synthetic" / "empty_to_empty.json").read_text()
    snap = Snapshot.from_dict(raw)
    assert snap.to_dict() == raw


def test_lessons_today_filters_to_today():
    """D-16: convenience slice properties filter the wider window."""
    snap = Snapshot(today=date(2026, 5, 4), school_tz="Pacific/Noumea", lessons=[
        Lesson(date=date(2026, 5, 3), ...),
        Lesson(date=date(2026, 5, 4), ...),
        Lesson(date=date(2026, 5, 5), ...),
    ], grades=[], information=[])
    assert len(snap.lessons_today) == 1
    assert len(snap.lessons_tomorrow) == 1
```

---

### `tests/test_api/test_strip.py` (test, walker)

**Internal analog:** `tests/test_manifest.py` — flat assertion against module-level fixture.

**Pattern** (locked by D-24, C-05):
```python
class _FakePronotepyObj:
    def __init__(self):
        self.client = "should-be-stripped"
        self.subject = "Mathématiques"


def test_strip_drops_client_back_ref():
    obj = _FakePronotepyObj()
    strip_client_refs(obj)
    assert obj.client is None
    assert obj.subject == "Mathématiques"  # unchanged
```

---

### `tests/test_api/test_errors.py` (test, enum + subclass init)

**Pattern** (locked by D-22):
```python
def test_error_reason_str_enum_values():
    assert ErrorReason.AUTH_FAILED == "auth_failed"  # PEP 663 StrEnum equality
    assert ErrorReason.IP_SUSPENDED == "ip_suspended"


def test_auth_error_forces_auth_failed_reason():
    err = AuthError("bad password")
    assert err.reason == ErrorReason.AUTH_FAILED


def test_rate_limited_error_forces_ip_suspended_reason():
    err = RateLimitedError("Your IP address is suspended")
    assert err.reason == ErrorReason.IP_SUSPENDED


def test_subclass_is_pronote_integration_error():
    assert isinstance(AuthError("x"), PronoteIntegrationError)
```

---

### `tests/test_diff/conftest.py` (test fixture, tz-aware loader)

**Internal analog:** `tests/conftest.py` (Phase 1 lines 1–16) — local fixture pattern + post-processing.

**Pattern** (locked by D-25, D-23):
```python
"""Loader rebuilds tz-aware datetimes from fixture's school_tz field (D-25)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture
def load_fixture():
    """Read fixture JSON and rebuild tz-aware datetimes per fixture's school_tz."""
    def _load(name: str) -> dict:
        path = Path(__file__).resolve().parent.parent / "fixtures"
        if (path / "real" / name).exists():
            data = json.loads((path / "real" / name).read_text())
        else:
            data = json.loads((path / "synthetic" / name).read_text())
        # tz-aware ISO datetimes round-trip via fromisoformat;
        # this fixture is the safety net for any pre-tz fixture authoring mistakes
        return data
    return _load
```

---

### `tests/test_diff/test_lessons.py` (test, parameterized matrix)

**Internal analog:** `tests/test_manifest.py` flat-assertion shape + new tz-matrix parametrization.

**Pattern** (locked by D-25, D-08, D-09):
```python
"""Diff lessons — tz matrix Europe/Paris ∪ Pacific/Noumea (D-25)."""
from __future__ import annotations

import pytest
from zoneinfo import ZoneInfo

from custom_components.ha_pronote.diff import diff_lessons
from custom_components.ha_pronote.api.models import Snapshot


@pytest.mark.parametrize("school_tz", ["Europe/Paris", "Pacific/Noumea"])
class TestLessonsDiffTzMatrix:
    """Every diff scenario runs on both timezones (D-25, NC-author blind-spot guard)."""

    def test_first_poll_returns_empty(self, school_tz, load_fixture):
        """D-08: previous is None → []."""
        new = Snapshot.from_dict(load_fixture("synthetic/first_poll_after_restart.json"))
        assert diff_lessons(None, new, day=new.today) == []

    def test_reorder_no_op(self, school_tz, load_fixture):
        """Pitfall 10: same lessons, different order → no events."""
        old = Snapshot.from_dict(load_fixture("synthetic/reorder_no_op_T0.json"))
        new = Snapshot.from_dict(load_fixture("synthetic/reorder_no_op_T1.json"))
        assert diff_lessons(old, new, day=new.today) == []

    def test_real_cancellation_emits_canceled(self, school_tz, load_fixture):
        """D-09: change_type='canceled' on real spike fixture."""
        old = Snapshot.from_dict(load_fixture("real/cancellation_T0.json"))
        new = Snapshot.from_dict(load_fixture("real/cancellation_T1.json"))
        changes = diff_lessons(old, new, day=new.today)
        assert any(c.change_type == "canceled" for c in changes)

    def test_real_room_change_emits_room(self, school_tz, load_fixture):
        """D-09 / Pitfall 10: change_type='room' (NOT 'canceled' + 'added')."""
        # ... fixture pair from real/room_change_T{0,1}.json
        # Spike-locked algorithm — assertion shape stable, exact output TBD by SPIKE-FINDINGS

    def test_real_teacher_swap_emits_teacher(self, school_tz, load_fixture):
        """D-09: change_type='teacher'."""
        # ...
```

---

### `tests/test_diff/test_lessons_synthetic.py` (test, combinatorics)

**Pattern:** same shape as `test_lessons.py` but loads only from `tests/fixtures/synthetic/`. Cases (D-10): empty→empty (vacation), reorder no-op, multi-change, first-poll-after-restart, lesson removed (silent — period rollover noise), lesson added.

---

### `tests/test_fixtures.py` (test, schema gate)

**Internal analog:** `tests/test_manifest.py` (Phase 1 lines 21–35) — JSON-load + key-set assertion shape.

**Pattern** (locked by D-11):
```python
"""Schema gate: every fixture round-trips Snapshot.from_dict → to_dict cleanly."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.ha_pronote.api.models import Snapshot

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize("fixture_path", sorted(FIXTURE_ROOT.rglob("*.json")))
def test_fixture_roundtrips(fixture_path):
    """D-11 invariant: dataclass shape == fixture shape."""
    if "_raw_" in fixture_path.name:
        pytest.skip("raw spike output, not a Snapshot fixture")
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    snap = Snapshot.from_dict(raw)
    assert snap.to_dict() == raw
```

---

### `tests/test_no_ha_imports.py` (test, static AST guard)

**External analog:** Stdlib `ast.parse` walk pattern (no in-repo analog — this is a bespoke static check).

**Pattern** (locked by D-19):
```python
"""Static guard: api/ + diff/ + their tests have ZERO `homeassistant.*` imports."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_PATHS = [
    REPO_ROOT / "custom_components" / "ha_pronote" / "api",
    REPO_ROOT / "custom_components" / "ha_pronote" / "diff",
    REPO_ROOT / "tests" / "test_api",
    REPO_ROOT / "tests" / "test_diff",
]


def _python_files(root: Path):
    return list(root.rglob("*.py")) if root.is_dir() else []


@pytest.mark.parametrize(
    "py_file",
    [f for root in GUARDED_PATHS for f in _python_files(root)],
)
def test_no_homeassistant_import(py_file):
    """D-19: zero homeassistant.* imports in api/ or diff/ or their tests."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("homeassistant"), (
                    f"{py_file} imports {alias.name} — D-19 violated"
                )
        elif isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("homeassistant"), (
                f"{py_file} imports from {node.module} — D-19 violated"
            )
```

---

### `tests/test_scripts/test_snapshot.py` (test, smoke + invariant)

**Internal analog:** `tests/test_manifest.py` shape — flat assertion.

**Pattern** (locked by D-13, `<specifics>` line 213):
```python
"""Smoke: anonymize() is deterministic; no_pii() invariant."""
from __future__ import annotations

import json

# scripts/ is outside custom_components/ — direct import via sys.path is fine in tests
from scripts.snapshot import anonymize, no_pii


def test_anonymize_is_deterministic():
    """Same input + same replacements → same output, byte-for-byte."""
    raw = {"name": "Alice Dupont", "school": "Lycée Katiramona"}
    repls = {"Alice Dupont": "Eleve Test", "Lycée Katiramona": "Établissement Test"}
    out1 = anonymize(raw, repls)
    out2 = anonymize(raw, repls)
    assert out1 == out2
    assert out1 == {"name": "Eleve Test", "school": "Établissement Test"}


def test_no_pii_invariant():
    """`<specifics>` line 213: no_pii returns True iff PII allowlist absent from output."""
    raw = {"name": "Alice Dupont"}
    cleaned = anonymize(raw, {"Alice Dupont": "Eleve Test"})
    assert no_pii(cleaned, ["Alice Dupont"]) is True
    assert no_pii(raw, ["Alice Dupont"]) is False
```

---

### `tests/fixtures/real/{cancellation,room_change,teacher_swap}_T{0,1}.json` (6 fixtures, generated)

**Source:** Generated by `scripts/snapshot.py` against the author's `katiramona.ac-noumea.nc` instance, anonymized per D-12. NOT authored. Conform to `Snapshot.to_dict()` shape (D-11). Listed here for completeness — the actual content is the spike output.

---

### `tests/fixtures/synthetic/*.json` (6 hand-crafted)

**Files (locked by D-10):**
- `empty_to_empty.json` (vacation)
- `reorder_no_op_T0.json` + `reorder_no_op_T1.json` (or single-file two-snapshot wrapper)
- `multi_change.json` (multiple changes in one poll)
- `first_poll_after_restart.json` (`previous is None` cycle)
- `lesson_removed.json` (period rollover noise — silent)
- `lesson_added.json`

**Schema:** identical to real fixtures (D-11) — `Snapshot.to_dict()` shape, including the top-level `"school_tz"` field (D-25 fixture-local school_tz).

**Authoring constraints:**
- All `datetime` strings ISO-8601 with explicit offset (e.g. `"2026-05-04T08:00:00+11:00"`) — this is what `Snapshot.from_dict` expects (no naive datetimes in committed fixtures, D-23)
- Hand-crafted to round-trip via `tests/test_fixtures.py`

---

### `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` (docs, analysis)

**External analog:** `.planning/research/PITFALLS.md` §"Pitfall 10" — same narrative shape. Phase 2's spike output, NOT pre-authored.

**Required sections** (locked by D-06):
1. Observed pronotepy 2.14.6 semantics for: `canceled` field shape, `status` field values, paired-vs-unpaired lessons at same datetime, teacher representation under substitution
2. Whether the D-08 starting-hypothesis identity key `(date, start, end, subject)` and content key `(canceled, status, classroom, teacher)` are confirmed or refined
3. Concrete example payloads from each of the 3 anonymized real fixtures
4. Algorithm decision: how `diff/lessons.py` handles the bain3#311 paired-canceled+room-change case

This document is the source of truth `diff/lessons.py` reads (D-07 dependency: plan 02-01 produces it, plan 02-02 consumes it).

---

### `.env.example` (config, env-var template)

**External analog:** Twelve-Factor App / dotenv community standard. No in-repo analog.

**Pattern** (locked by D-14):
```bash
# scripts/snapshot.py reads these. Do NOT commit a real .env (gitignored).
# See README §"Refreshing fixtures when Pronote breaks".
PRONOTE_URL=https://demo.index-education.net/pronote/eleve.html
PRONOTE_USERNAME=demonstration
PRONOTE_PASSWORD=pronotevs
PRONOTE_ACCOUNT_TYPE=eleve
```

**`.gitignore` addition required:** `.env` (real one is local-only; only `.env.example` is committed).

---

### MODIFIED files

#### `custom_components/ha_pronote/const.py` (APPEND constants)

**Internal analog:** Phase 1 `const.py` lines 1–7 (existing `DOMAIN: Final = "ha_pronote"` declaration).

**Append pattern** (preserve `DOMAIN`):
```python
"""Constants for HA-Pronote."""
from __future__ import annotations
from typing import Final

DOMAIN: Final = "ha_pronote"   # PRESERVED from Phase 1

# Phase 2 additions (D-15, D-18) — defaults consumed by Phase 3 coordinator
DEFAULT_SCHOOL_TZ: Final = "Pacific/Noumea"
DEFAULT_LOOKBACK_DAYS: Final = 7    # J−7
DEFAULT_LOOKAHEAD_DAYS: Final = 14  # J+14
```

**Constraint:** the Phase 2 additions live in `const.py` (single source of truth per `<canonical_refs>` line 157) and are imported into `api/fetcher.py` ONLY at the call-site of fetcher.py's caller (Phase 3 coordinator) — `api/fetcher.py` itself takes them as arguments per D-17/D-18 (no ambient state in `api/`).

---

#### `pyproject.toml` (APPEND `[tool.pytest.ini_options]` timeout + `[tool.coverage.run] omit`)

**Internal analog:** Phase 1 `pyproject.toml` lines 34–62 (existing `[tool.pytest.ini_options]` and `[tool.coverage.run]` blocks).

**Append `timeout` to existing block:**
```toml
[tool.pytest.ini_options]
# ... existing keys preserved ...
timeout = 1   # D-28: per-test 1s timeout (sub-2s gate via pytest-timeout 2.4.0 transitive)
```

**Modify existing `[tool.coverage.run]`** (locked by C-02):
```toml
[tool.coverage.run]
source = ["custom_components/ha_pronote"]
omit = [
    "tests/*",
    "*/diff/grades.py",         # D-04 / C-02 — Phase 4 fills the body
    "*/diff/notifications.py",  # D-04 / C-02 — Phase 4 fills the body
]
```

The existing `[tool.coverage.report] exclude_lines` already covers `raise NotImplementedError` (Phase 1 line 59) — belt-and-suspenders, both mechanisms apply.

---

#### `requirements_test.txt` (APPEND requests-mock)

**Internal analog:** Phase 1 `requirements_test.txt` lines 1–16 (pinned-dep style with explanatory comments).

**Append at end:**
```
# D-26: explicit pin (already transitive via PHACC). Hermetic api/ tests.
requests-mock==1.12.1
```

---

#### `.github/workflows/test.yml` (AMEND pytest invocation + add tz matrix)

**Internal analog:** Phase 1 `.github/workflows/test.yml` lines 1–25 (existing `pytest -q` step).

**Modification** (locked by D-25, D-27):
```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: {}

jobs:
  pytest:
    name: Pytest (${{ matrix.tz }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        tz: ["Europe/Paris", "Pacific/Noumea"]   # D-25 NC-author blind-spot guard
    env:
      TZ: ${{ matrix.tz }}
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "requirements*.txt"
      - run: uv pip install --system -r requirements_test.txt
      - run: pytest -q --cov=custom_components/ha_pronote/diff --cov-fail-under=90  # D-27
```

**Key changes:**
- `strategy.matrix.tz` → 2 jobs (D-25)
- `env.TZ` propagates to runner / pytest (note: pytest tests parametrize `school_tz` independently — this matrix is belt-and-suspenders for any HA-side tz code that lands in Phase 3+)
- pytest invocation: `--cov=custom_components/ha_pronote/diff --cov-fail-under=90` (D-27)
- SHAs preserved verbatim from Phase 1 `01-PATTERNS.md` Shared Patterns section

---

## Shared Patterns

### Pure-Python Boundary (D-19, D-20)

**Source:** D-19 / D-20 / `tests/test_no_ha_imports.py`.
**Apply to:** every file under `custom_components/ha_pronote/api/`, `custom_components/ha_pronote/diff/`, `tests/test_api/`, `tests/test_diff/`.

**Allowed imports:**
- stdlib: `datetime`, `zoneinfo`, `dataclasses`, `typing`, `enum`, `json`, `pathlib`, `ast` (test only)
- `pronotepy` — `api/` only
- `python-slugify` — `api/client.py` only, lazy (C-06)
- `requests-mock` — tests only

**Banned imports (Phase 1 ruff banned-api applies + Phase 2 add):**
- `homeassistant.*` — D-19 (test_no_ha_imports.py enforces)
- `async_timeout` — Phase 1 D-30
- `pytz` — Phase 1 D-31
- `requests` direct — Phase 1 D-32
- `pronotepy.ent.*` — Phase 1 D-33
- `aiohttp` — D-20
- `voluptuous` — D-20

**Ruff banned-api block** (`pyproject.toml` lines 139–142, Phase 1) already enforces 4 of these. Phase 2 may extend the banned-api list to include `homeassistant` for `api/` + `diff/`, but the AST test (`tests/test_no_ha_imports.py`) is the canonical guard because ruff cannot scope by directory.

---

### Sync Surface for Future Executor Wrap (Pitfall 3, ARCHITECTURE Pattern 1)

**Source:** ARCHITECTURE.md Pattern 1 + Pitfall 3.
**Apply to:** every public function in `api/`.

**Rule:** every `api/*.py` public function is fully synchronous and **kwargs-friendly via `functools.partial`** so Phase 3's coordinator can wrap with `await hass.async_add_executor_job(partial(api.fetch_all, client, today=today, school_tz=tz))`.

**No `async def` anywhere in `api/`.** No `await`. No `asyncio` import. No `aiohttp`. The whole point of D-19 is that `api/` is provably testable in plain pytest, no event loop.

---

### Anti-Pattern 5 Avoidance — No pronotepy Refs Escape `api/`

**Source:** ARCHITECTURE.md Anti-Pattern 5 (lines 573–579) + D-24.
**Apply to:** `api/fetcher.py` exclusively.

**Rule:** `Snapshot`, `Lesson`, `Grade`, `Information` dataclasses contain ONLY plain values (str, int, bool, datetime, date, list, dict). NO `pronotepy.Lesson`, `pronotepy.Client`, `pronotepy.Period`, or any object whose `__class__.__module__.startswith("pronotepy")`. The `_strip_client_refs` walker (D-24, C-05) is defense-in-depth; primary defense is `_lesson_from_raw` / `_grade_from_raw` / `_info_from_raw` field-by-field copies.

**Test** (`tests/test_api/test_fetcher.py`): `for L in snap.lessons: assert L.__class__.__module__.startswith("custom_components.ha_pronote.api")`.

---

### tz-Aware Datetimes Everywhere (D-23, Pitfall 4, TIME-04)

**Source:** PITFALLS.md §"Pitfall 4" + D-23.
**Apply to:** every `datetime` field on every `api/models.py` dataclass + every committed fixture.

**Rule:**
- `api/fetcher.py` localizes pronotepy's naive datetimes to `school_tz` (passed in via D-18) at parse time
- `api/models.py` constructors are reach-free — they accept whatever the caller passes (D-23: localization is fetcher's job, not models')
- Every fixture's datetime fields are ISO-8601 strings with explicit offset (e.g. `"+11:00"` for Pacific/Noumea, `"+02:00"` summer / `"+01:00"` winter for Europe/Paris)
- `tests/test_api/test_fetcher.py` asserts `lesson.start.tzinfo is not None` after `fetch_all`

---

### Frozen Dataclasses (Pattern 3 in ARCHITECTURE)

**Source:** ARCHITECTURE.md §Pattern 3 (lines 230–231: "Snapshot must be deep-copied or immutable to avoid mutation aliasing. Use plain dataclasses (frozen=True where possible)").
**Apply to:** `api/models.py` `Lesson`, `Grade`, `Information`, `Snapshot`; `diff/events.py` `LessonChange`, `NewGrade`, `NewInformation`.

**Rule:** every dataclass declares `@dataclass(frozen=True)`. Mutability is opt-in only if a clear reason emerges in the spike (e.g. `Snapshot.lessons` mutation by Phase 3 coordinator before re-storing — but even then, the mutation should be a `dataclasses.replace(snap, lessons=new_list)` rather than in-place).

---

### File Path Resolution Pattern (Phase 1 idiom)

**Source:** `tests/test_manifest.py` (Phase 1 lines 13–18) — `Path(__file__).resolve().parent.parent / ...`.
**Apply to:** every test that loads a fixture or the manifest.

**Rule:** never use relative paths or string concatenation; always `Path(__file__).resolve().parent.parent / "fixtures" / name`. Plays correctly under `pytest -q` invoked from any cwd, the `enable_custom_integrations` fixture, and CI.

---

### Coverage-omit for Stub Modules (D-04, C-02)

**Source:** Phase 2 D-04 / C-02 + Phase 1 `pyproject.toml` lines 52–61 (existing `[tool.coverage.run]` and `[tool.coverage.report]` blocks).
**Apply to:** `pyproject.toml` `[tool.coverage.run]`.

**Rule:** add `*/diff/grades.py` and `*/diff/notifications.py` to the `omit` list. The `[tool.coverage.report] exclude_lines = ["raise NotImplementedError", ...]` from Phase 1 line 59 is the secondary safety net; both mechanisms compose to keep the ≥90% gate honest.

---

### .env / Real-Output Gitignore (D-12, D-13)

**Source:** D-12 ("only the anonymized output is git-committed; raw is gitignored") + D-13 (`.env`).
**Apply to:** `.gitignore`.

**Required additions:**
```gitignore
# Phase 2: real-Pronote spike output (raw + .env)
.env
tests/fixtures/real/_raw_*.json
```

---

## No Analog Found

These files have no in-repo analog and only weak external analogs (community standards or stdlib idioms). The planner should treat them as bespoke:

| File | Role | Reason |
|------|------|--------|
| `tests/test_no_ha_imports.py` | static AST guard | Bespoke check; relies only on stdlib `ast`. No HA / pronotepy / Phase 1 analog. |
| `.env.example` | env-var template | Twelve-Factor convention — no Python file equivalent. Plain key=value lines. |
| `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` | analysis doc | Spike OUTPUT, not pre-authored. Shape mirrors PITFALLS.md §"Pitfall 10" but content is empirical. |
| `scripts/snapshot.py` | one-shot CLI | No in-repo CLI exists yet. Stdlib `argparse`/`os.environ`/`json` only — no Phase 1 reference. |

For `tests/test_no_ha_imports.py` and `scripts/snapshot.py`, the planner should ground the implementation in the locked decisions (D-19 for the AST test; D-12/D-13/D-14/C-03 for the script) rather than search for a closer analog.

---

## Cross-Cutting Pitfall References

These PITFALLS.md sections are NOT shared patterns to copy from — they are **risks the Phase 2 patterns explicitly mitigate**. Cited here so the planner can verify each plan slice closes the loop:

| Pitfall | Phase 2 mitigation pattern |
|---|---|
| **Pitfall 1** (IP suspension) | `api/client.py` literal `"Your IP address is suspended"` detection → `RateLimitedError(IP_SUSPENDED)` (D-22). Phase 5 implements the long-backoff response; Phase 2 raises the typed signal. |
| **Pitfall 2** (pronotepy breakage) | `api/errors.py` `ErrorReason.PROTOCOL_BROKEN` for unrecognized `PronoteAPIError` codes; `CryptoError` mapped to `AuthError` so users don't think their password is wrong. |
| **Pitfall 3** (blocking calls) | `api/` is purely sync; D-19 + sub-2s test gate confirms no event-loop work. Phase 3's coordinator wraps in executor. |
| **Pitfall 4** (NC tz) | D-23 tz-localization in `api/fetcher.py` + D-25 tz matrix in `tests/test_diff/test_lessons.py`. Every datetime field in `api/models.py` is tz-aware. |
| **Pitfall 8** (unique_id stability) | `Lesson`/`Grade`/`Information` carry `child_identifier` field per `<canonical_refs>` line 141 — Phase 3's `unique_id` builds on this. |
| **Pitfall 10** (EDT diff false ±/−) | The CORE Phase 2 pitfall. Mitigated by: D-05 spike, D-06 SPIKE-FINDINGS doc, D-08 identity-vs-content keys, D-10 hand-crafted reorder + multi-change synthetic fixtures, D-25 tz matrix, D-27 ≥90% coverage gate. |

---

## Metadata

**Analog search scope:**
- Internal codebase: `custom_components/ha_pronote/{__init__,const,manifest,config_flow,strings}` + `tests/{conftest,test_init,test_manifest,__init__}.py` + `pyproject.toml` + `requirements_test.txt` + `.github/workflows/{test,lint,validate,release}.yml` + `hacs.json` + `.pre-commit-config.yaml` + `package.json` + `.gitignore` (Phase 1 deliverables, all Read).
- Greenfield directories confirmed empty: `custom_components/ha_pronote/api/` (DNE), `custom_components/ha_pronote/diff/` (DNE), `scripts/` (DNE), `tests/test_api/` (DNE), `tests/test_diff/` (DNE), `tests/fixtures/` (DNE).
- External references: NOT re-fetched. Architectural shapes pulled from `.planning/research/ARCHITECTURE.md` (Pattern 1, 3, 5, 6 + Anti-Pattern 5) and `.planning/research/PITFALLS.md` (Pitfalls 1, 2, 3, 4, 10), both verified by `gsd-phase-researcher` on 2026-05-03.

**Files scanned:** 17 Phase 1 source/config files + 4 planning docs (`02-CONTEXT.md`, `01-CONTEXT.md`, `ARCHITECTURE.md`, `PITFALLS.md`) + targeted reads of `01-PATTERNS.md` for output-format reference.

**Pattern extraction date:** 2026-05-04

**Quick-lookup convention for the planner:** when writing each plan slice's task, cite analogs as `"Phase 1 internal: <file>:<line-range>"` for in-repo files (the actual file content is short — re-read directly), and `"PITFALLS.md §<section>"` or `"ARCHITECTURE.md §<pattern>"` for external/architectural patterns. Decision IDs (`D-NN`, `C-NN`) are the SOURCE OF TRUTH — every pattern in this document is derived from a CONTEXT.md decision, never invented.

## PATTERN MAPPING COMPLETE
