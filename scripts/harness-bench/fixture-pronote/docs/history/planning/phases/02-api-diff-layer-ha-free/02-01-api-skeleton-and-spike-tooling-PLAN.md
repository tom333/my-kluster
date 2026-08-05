---
phase: 02-api-diff-layer-ha-free
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - custom_components/ha_pronote/api/__init__.py
  - custom_components/ha_pronote/api/errors.py
  - custom_components/ha_pronote/api/models.py
  - custom_components/ha_pronote/api/_strip.py
  - custom_components/ha_pronote/api/client.py
  - custom_components/ha_pronote/api/fetcher.py
  - custom_components/ha_pronote/const.py
  - scripts/snapshot.py
  - .env.example
  - .gitignore
  - requirements_test.txt
  - tests/test_api/__init__.py
  - tests/test_api/conftest.py
  - tests/test_api/test_errors.py
  - tests/test_api/test_models.py
  - tests/test_api/test_strip.py
  - tests/test_api/test_client.py
  - tests/test_api/test_fetcher.py
  - tests/test_scripts/__init__.py
  - tests/test_scripts/test_snapshot.py
autonomous: true
requirements: [TIME-04]
must_haves:
  truths:
    - "api/ subpackage imports cleanly with zero homeassistant.* imports"
    - "ErrorReason StrEnum has 7 members AUTH_FAILED|IP_SUSPENDED|PROTOCOL_BROKEN|SERVER_DOWN|SESSION_EXPIRED|RATE_LIMITED|PARSE_ERROR (D-22)"
    - "Snapshot.from_dict(snap.to_dict()) == snap is True for any constructed Snapshot (D-11)"
    - "Every datetime field on Lesson/Grade/Information returned by fetch_all is tz-aware (D-23, TIME-04)"
    - "fetch_all queries lessons over today-7 to today+14 window (D-15, CAL-01 cross-cutting tracker)"
    - "build_client raises RateLimitedError(IP_SUSPENDED) when pronotepy returns the literal 'Your IP address is suspended' (D-22, Pitfall 1)"
    - "scripts/snapshot.py --help exits 0 and prints usage including --scenario and --phase"
    - "anonymize() is deterministic and no_pii() invariant holds against PII allowlist (<specifics> line 213)"
  artifacts:
    - path: "custom_components/ha_pronote/api/__init__.py"
      provides: "api package marker re-exporting build_client, fetch_all, error hierarchy"
      contains: "__all__"
    - path: "custom_components/ha_pronote/api/errors.py"
      provides: "Typed exception hierarchy + ErrorReason StrEnum (D-22)"
      contains: "class ErrorReason(StrEnum)"
    - path: "custom_components/ha_pronote/api/models.py"
      provides: "Lesson, Grade, Information, Snapshot frozen dataclasses with from_dict/to_dict (D-11, D-16)"
      contains: "@dataclass(frozen=True)"
    - path: "custom_components/ha_pronote/api/_strip.py"
      provides: "Private back-ref walker (D-24, C-05)"
      contains: "def strip_client_refs"
    - path: "custom_components/ha_pronote/api/client.py"
      provides: "Sync facade build_client(url, account_type, username, password) -> pronotepy.Client | ParentClient (D-21)"
      contains: "def build_client"
    - path: "custom_components/ha_pronote/api/fetcher.py"
      provides: "fetch_all(client, today, school_tz, child_index_or_identifier=None) -> Snapshot, J-7..J+14, tz-localized; sets child for ParentClient (D-15..D-18, D-21, D-23, D-24, PC-02-03)"
      contains: "def fetch_all"
    - path: "scripts/snapshot.py"
      provides: "One-shot real-Pronote spike + anonymizer CLI (D-12..D-14, C-03)"
      contains: "def anonymize"
    - path: ".env.example"
      provides: "Documented env vars for spike (D-14)"
      contains: "PRONOTE_URL"
    - path: ".gitignore"
      provides: "Gitignore .env and raw spike output"
      contains: ".env"
  key_links:
    - from: "custom_components/ha_pronote/api/fetcher.py"
      to: "custom_components/ha_pronote/api/_strip.py"
      via: "strip_client_refs import"
      pattern: "from \\._strip import strip_client_refs"
    - from: "custom_components/ha_pronote/api/fetcher.py"
      to: "custom_components/ha_pronote/api/models.py"
      via: "Snapshot/Lesson/Grade/Information construction"
      pattern: "from \\.models import"
    - from: "custom_components/ha_pronote/api/client.py"
      to: "custom_components/ha_pronote/api/errors.py"
      via: "Error mapping (D-22 — IP_SUSPENDED literal detection)"
      pattern: "Your IP address is suspended"
    - from: "scripts/snapshot.py"
      to: "custom_components/ha_pronote/api/client.py"
      via: "Imports build_client and fetch_all from api/"
      pattern: "from custom_components.ha_pronote.api"
---

<objective>
Ship the pure-sync `custom_components/ha_pronote/api/` subpackage (errors, models,
_strip, client, fetcher) plus the `scripts/snapshot.py` CLI tooling and `.env.example`
that Plan 02-02 will RUN against the author's real Pronote instance. Every
public function is sync (no `async def`), every datetime is tz-aware, every
pronotepy exception is wrapped in the typed `PronoteIntegrationError` hierarchy,
and zero `homeassistant.*` imports leak in.

Purpose: this plan owns Phase 2 success criterion #2 ("scripts/snapshot.py
authenticates against the author's real Pronote instance and writes a valid
anonymized JSON snapshot") at the **code level** — Plan 02-02 owns the actual
RUN against the live server. It also owns TIME-04 (tz-aware datetimes from day
one) and the Phase 2 → Phase 3 interface surface
(`build_client`, `fetch_all`, `AuthError`, `CommunicationError`, `RateLimitedError`).

Output: 18 new files (api/ × 6, scripts/ × 1, tests/test_api/ × 7,
tests/test_scripts/ × 2, .env.example, .gitignore append) + 2 modified
(`const.py` append, `requirements_test.txt` append).
</objective>

<execution_context>
@/home/moi/projets/perso/pronote/.claude/get-shit-done/workflows/execute-plan.md
@/home/moi/projets/perso/pronote/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/research/ARCHITECTURE.md
@.planning/research/PITFALLS.md
@.planning/research/STACK.md
@.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md
@.planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md
@.planning/phases/01-foundations-skeleton/01-CONTEXT.md
@CLAUDE.md

# Existing files Phase 2 builds on or extends
@custom_components/ha_pronote/__init__.py
@custom_components/ha_pronote/const.py
@custom_components/ha_pronote/manifest.json
@tests/conftest.py
@tests/test_manifest.py
@pyproject.toml
@requirements_test.txt
@.gitignore

<interfaces>
<!-- Contracts this plan PRODUCES — Plans 02-02 and 02-03 (and Phase 3 coordinator)
     consume these. Embed here so executors don't have to re-derive them. -->

# api/errors.py contract (D-22)
```python
from enum import StrEnum

class ErrorReason(StrEnum):
    # AUTH_FAILED, IP_SUSPENDED, PROTOCOL_BROKEN, SERVER_DOWN, PARSE_ERROR are used in Phase 2;
    # SESSION_EXPIRED and RATE_LIMITED are reserved for Phase 5's circuit-breaker (D-22 mandates the 7-member set, PC-02-05).
    AUTH_FAILED = "auth_failed"
    IP_SUSPENDED = "ip_suspended"
    PROTOCOL_BROKEN = "protocol_broken"
    SERVER_DOWN = "server_down"
    SESSION_EXPIRED = "session_expired"      # Reserved for Phase 5 circuit-breaker (PC-02-05)
    RATE_LIMITED = "rate_limited"            # Reserved for Phase 5 circuit-breaker (PC-02-05)
    PARSE_ERROR = "parse_error"

class PronoteIntegrationError(Exception):
    def __init__(self, reason: ErrorReason, message: str) -> None: ...
    reason: ErrorReason
    message: str

class AuthError(PronoteIntegrationError):           # default reason = AUTH_FAILED
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.AUTH_FAILED) -> None: ...

class RateLimitedError(PronoteIntegrationError):    # default reason = IP_SUSPENDED
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.IP_SUSPENDED) -> None: ...

class CommunicationError(PronoteIntegrationError):  # default reason = SERVER_DOWN
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.SERVER_DOWN) -> None: ...

class ParseError(PronoteIntegrationError):          # default reason = PARSE_ERROR
    def __init__(self, message: str, reason: ErrorReason = ErrorReason.PARSE_ERROR) -> None: ...
```

# api/models.py contract (D-11, D-16, D-23)
```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class Lesson:
    date: date
    start: datetime          # tz-aware (D-23)
    end: datetime            # tz-aware (D-23)
    subject: str
    teacher: str
    classroom: str
    canceled: bool
    status: str              # raw pronotepy status string ("", "Cours annulé", "Changement de salle", ...)
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lesson": ...

@dataclass(frozen=True)
class Grade:
    subject: str
    value: str               # raw pronotepy field — Phase 4 normalizes "14,5" -> 14.5 at sensor layer
    out_of: str
    coefficient: str
    date: date               # date-only (no datetime needed for grade)
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Grade": ...

@dataclass(frozen=True)
class Information:
    info_id: str
    title: str
    sender: str
    date: datetime           # tz-aware
    excerpt: str             # truncated body
    read: bool
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Information": ...

@dataclass(frozen=True)
class Snapshot:
    today: date
    school_tz: str           # "Pacific/Noumea" or "Europe/Paris" — fixture-local (D-25)
    lessons: list[Lesson]
    grades: list[Grade]
    information: list[Information]

    @property
    def lessons_today(self) -> list[Lesson]: ...      # D-16: filter by date == self.today
    @property
    def lessons_tomorrow(self) -> list[Lesson]: ...   # D-16: filter by date == self.today + 1day
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot": ...
```

# api/client.py contract (D-21, D-22)
```python
from typing import Literal
import pronotepy

AccountType = Literal["eleve", "parent"]   # C-04

def build_client(
    url: str,
    account_type: AccountType,
    username: str,
    password: str,
) -> pronotepy.Client | pronotepy.ParentClient:
    """Sync. Caller wraps in async_add_executor_job (Phase 3)."""
    # Raises:
    # - AuthError(AUTH_FAILED) on pronotepy.exceptions.CryptoError or auth-shaped errors
    # - RateLimitedError(IP_SUSPENDED) when message contains literal "Your IP address is suspended"
    # - CommunicationError(SERVER_DOWN) on network errors / other PronoteAPIError
```

# api/fetcher.py contract (D-15, D-17, D-18, D-23, D-24)
```python
from datetime import date
from zoneinfo import ZoneInfo

def fetch_all(
    client,
    today: date,
    school_tz: ZoneInfo,
    child_index_or_identifier: int | str | None = None,
) -> Snapshot:
    """Fetch lessons over [today-7, today+14], grades from current_period,
    information_and_surveys. tz-localize naive pronotepy datetimes to school_tz.
    Strip pronotepy back-refs. Sync.

    When `client` is a ParentClient AND `child_index_or_identifier` is not None,
    `client.set_child(child_index_or_identifier)` is called BEFORE any fetch
    (D-21 — the parent-vs-child selection lives in api/fetcher.py). When the
    argument is None and `client` is a ParentClient, pronotepy defaults to the
    first child (no `set_child` call). When `client` is an eleve `Client`,
    the argument is ignored.

    Raises CommunicationError on network / fetch failures.
    """
```

# scripts/snapshot.py contract (D-12..D-14, C-03)
```python
def walk_and_replace(obj, replacements: dict[str, str]): ...   # recursive str-replace walker
def anonymize(snapshot_dict: dict, replacements: dict[str, str]) -> dict: ...  # deterministic
def no_pii(obj, pii_blocklist: list[str]) -> bool: ...         # invariant smoke test

# CLI: --scenario {cancellation|room_change|teacher_swap} --phase {T0|T1}
# Reads .env, calls build_client + fetch_all, writes:
#   - tests/fixtures/real/_raw_<scenario>_<phase>.json (gitignored)
#   - tests/fixtures/real/<scenario>_<phase>.json     (anonymized, committed by Plan 02-02)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Define api/errors.py + api/models.py + api/_strip.py + api/__init__.py + tests</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Error Hierarchy & Cross-cutting Invariants" (D-22, D-23, D-24)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"custom_components/ha_pronote/api/errors.py" + §"models.py" + §"_strip.py" + §"__init__.py"
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Pure-Python Boundary" (D-19, D-20)
    - custom_components/ha_pronote/__init__.py (existing Phase 1 docstring + __all__ shape to mirror)
    - tests/test_manifest.py (existing flat-assertion + Path resolution shape to mirror)
    - .planning/research/ARCHITECTURE.md §"Anti-Pattern 5" (no pronotepy refs in entity layer — _strip is the prevention)
    - .planning/research/PITFALLS.md §"Pitfall 4" (NC tz — datetimes must be tz-aware from parse time)
    - CLAUDE.md "What NOT to Use" table (NO pytz, NO async_timeout, NO direct requests, NO pronotepy.ent.*)
  </read_first>
  <behavior>
    - ErrorReason StrEnum has exactly 7 members with snake_case string values:
      AUTH_FAILED="auth_failed", IP_SUSPENDED="ip_suspended", PROTOCOL_BROKEN="protocol_broken",
      SERVER_DOWN="server_down", SESSION_EXPIRED="session_expired", RATE_LIMITED="rate_limited",
      PARSE_ERROR="parse_error".
    - PronoteIntegrationError(reason, message) sets `.reason` and `.message` and stringifies as f"[{reason}] {message}".
    - AuthError("x") -> .reason == ErrorReason.AUTH_FAILED.
    - RateLimitedError("x") -> .reason == ErrorReason.IP_SUSPENDED.
    - CommunicationError("x") -> .reason == ErrorReason.SERVER_DOWN.
    - ParseError("x") -> .reason == ErrorReason.PARSE_ERROR.
    - All four subclasses are isinstance(..., PronoteIntegrationError).
    - ErrorReason.AUTH_FAILED == "auth_failed" (PEP 663 StrEnum equality with raw string).
    - Lesson(date=d, start=tz_dt, end=tz_dt, subject=s, teacher=t, classroom=c, canceled=False, status="").to_dict() is JSON-serializable (json.dumps round-trips).
    - Lesson.from_dict(Lesson(...).to_dict()) == Lesson(...) (idempotent round-trip, D-11).
    - Snapshot(today=d, school_tz="Pacific/Noumea", lessons=[L1, L2, L3], grades=[], information=[]).lessons_today filters lessons whose date == today. lessons_tomorrow filters lessons whose date == today + 1 day.
    - Snapshot.from_dict(snap.to_dict()) == snap for any Snapshot built in-test.
    - strip_client_refs(obj) sets obj.client / obj._session / obj._client / obj._pronote to None when present, leaves other attrs untouched, returns obj.
    - Every dataclass is `@dataclass(frozen=True)` (Pattern 3 ARCHITECTURE.md).
    - tests/test_api/test_errors.py, tests/test_api/test_models.py, tests/test_api/test_strip.py exist and pass with zero homeassistant.* imports.
  </behavior>
  <action>
    Create the foundation layer of `custom_components/ha_pronote/api/` plus the corresponding tests in `tests/test_api/`. This task is the contract-first slice — Plan 02-03 (diff/) and Plan 02-02 (spike RUN) consume these types directly.

    **1. Create `custom_components/ha_pronote/api/__init__.py`** (mirror Phase 1 `__init__.py` lines 1–11 docstring + `__all__` shape — see PATTERNS.md §"api/__init__.py"):
    ```python
    """API subpackage — pure-sync facade over pronotepy==2.14.6.

    Phase 2 D-19: zero `homeassistant.*` imports anywhere in this package.
    Phase 2 D-20: imports limited to stdlib + pronotepy + python-slugify (lazy).

    Public surface (consumed by Phase 3 coordinator via async_add_executor_job):
    - build_client(url, account_type, username, password)
    - fetch_all(client, today, school_tz, child_index_or_identifier=None)
    - AuthError, CommunicationError, RateLimitedError, ParseError, ErrorReason

    Token persistence (`client.export_credentials()`) is Phase 3's coordinator
    responsibility — NOT exposed here. The coordinator owns `entry.data`
    storage for the token round-trip (AUTH-04, PC-02-04). Adding an
    `export_credentials_dict()` wrapper to api/ would couple the pure-Python
    layer to HA's storage concerns; resist the temptation.
    """
    from .client import build_client
    from .errors import (
        AuthError,
        CommunicationError,
        ErrorReason,
        ParseError,
        PronoteIntegrationError,
        RateLimitedError,
    )
    from .fetcher import fetch_all
    from .models import Grade, Information, Lesson, Snapshot

    __all__ = [
        "AuthError",
        "CommunicationError",
        "ErrorReason",
        "Grade",
        "Information",
        "Lesson",
        "ParseError",
        "PronoteIntegrationError",
        "RateLimitedError",
        "Snapshot",
        "build_client",
        "fetch_all",
    ]
    ```

    **2. Create `custom_components/ha_pronote/api/errors.py`** verbatim per D-22 + PATTERNS.md §"api/errors.py" (lines 297–340 of 02-PATTERNS.md):
    - 7-member `ErrorReason(StrEnum)` (exact members listed in `<behavior>`). Add a comment block above the StrEnum body matching the `<interfaces>` template: `# AUTH_FAILED, IP_SUSPENDED, PROTOCOL_BROKEN, SERVER_DOWN, PARSE_ERROR are used in Phase 2; SESSION_EXPIRED and RATE_LIMITED are reserved for Phase 5's circuit-breaker (D-22 mandates the 7-member set, PC-02-05).` — this prevents a future cleanup pass from deleting "unused" members and breaking the D-22 contract.
    - `PronoteIntegrationError(Exception)` base with `__init__(reason, message)` storing both, `super().__init__(f"[{reason}] {message}")`.
    - 4 subclasses each forcing a default `ErrorReason` while still accepting an override (signature: `def __init__(self, message: str, reason: ErrorReason = <DEFAULT>) -> None: super().__init__(reason, message)`).
    - Module docstring: `"""Typed exception hierarchy. Phase 5 reads `.reason` to route circuit-breaker (Pitfall 1, D-22)."""`.
    - Use `from __future__ import annotations`. NO `homeassistant.*`, NO `pytz`, NO `async_timeout`, NO `requests` imports (D-19, Phase 1 banned-api).

    **3. Create `custom_components/ha_pronote/api/models.py`** per D-11, D-16, D-23 + PATTERNS.md §"api/models.py":
    - All four dataclasses are `@dataclass(frozen=True)`.
    - Field lists exactly as listed in `<interfaces>` block of this plan.
    - `to_dict()` serializes `date` and `datetime` to `.isoformat()` strings; lists preserve order; nested objects are converted via their own `to_dict()`.
    - `from_dict()` reconstructs:
        - `date.fromisoformat(data["date"])` for date-only fields,
        - `datetime.fromisoformat(data["start"])` for datetime fields (ISO with offset preserves tz, D-23 — naive ISO is REJECTED via `if dt.tzinfo is None: raise ParseError("naive datetime in fixture")`),
        - lists via `[Lesson.from_dict(d) for d in data["lessons"]]` etc.
    - `Snapshot.lessons_today`: return `[L for L in self.lessons if L.date == self.today]`.
    - `Snapshot.lessons_tomorrow`: return `[L for L in self.lessons if L.date == self.today + timedelta(days=1)]`.
    - `Snapshot.to_dict()` serializes `today` and `school_tz` at top level alongside the three lists.
    - NO `homeassistant.*` import. Imports limited to: `dataclasses`, `datetime`, `typing`, `zoneinfo` (only if needed for type hints — not for runtime localization, that's fetcher.py per D-23).

    **4. Create `custom_components/ha_pronote/api/_strip.py`** per D-24, C-05 + PATTERNS.md §"api/_strip.py":
    - Module docstring: `"""Private — imported only by api/fetcher.py. Defense-in-depth against pronotepy back-refs (Anti-Pattern 5)."""`.
    - `def strip_client_refs(obj)`: walks `obj.__dict__` (if present), sets `obj.client`, `obj._session`, `obj._client`, `obj._pronote` to None if those attributes exist, returns obj. Wrap each setattr in `try/except (AttributeError, TypeError): pass` because pronotepy uses `autoslot` which may forbid arbitrary mutation.
    - `from __future__ import annotations`. Imports: `typing.Any` only.

    **5. Create test files** in `tests/test_api/` (mirror tests/test_manifest.py shape — flat assertions, top-of-module Path/import resolution):

    - **`tests/test_api/__init__.py`**: empty file (just enables package discovery).

    - **`tests/test_api/conftest.py`** per PATTERNS.md §"tests/test_api/conftest.py":
      - Module docstring: `"""Local fixtures for tests/test_api/. NO PHACC autouse — api/ is HA-free per D-19."""`.
      - `mocked_pronote_session` fixture: `with requests_mock.Mocker() as mocker: yield mocker` (D-26).
      - `fixture_path` fixture: returns `Path(__file__).resolve().parent.parent / "fixtures"`.
      - `from __future__ import annotations`. NO `enable_custom_integrations` autouse (the root tests/conftest.py already provides it but only fires when the `hass` fixture is requested — these tests don't request it).

    - **`tests/test_api/test_errors.py`** (5 tests minimum):
      - `test_error_reason_str_enum_values_match_snake_case` asserts `ErrorReason.AUTH_FAILED == "auth_failed"`, `ErrorReason.IP_SUSPENDED == "ip_suspended"`, all 7 values.
      - `test_error_reason_has_exactly_seven_members` asserts `set(ErrorReason) == {ErrorReason.AUTH_FAILED, ..., ErrorReason.PARSE_ERROR}` (size 7).
      - `test_auth_error_forces_auth_failed_reason` asserts `AuthError("bad password").reason == ErrorReason.AUTH_FAILED`.
      - `test_rate_limited_error_forces_ip_suspended_reason` asserts `RateLimitedError("Your IP address is suspended").reason == ErrorReason.IP_SUSPENDED`.
      - `test_communication_error_forces_server_down_reason` and `test_parse_error_forces_parse_error_reason` similar.
      - `test_subclass_is_pronote_integration_error` asserts each subclass `isinstance(..., PronoteIntegrationError)`.
      - `test_str_repr_includes_reason_in_brackets` asserts `str(AuthError("x")) == "[auth_failed] x"`.

    - **`tests/test_api/test_models.py`** (4 tests minimum, per PATTERNS.md §"test_models.py"):
      - `test_lesson_to_from_dict_roundtrip`: build a `Lesson` with tz-aware start/end (`datetime(2026, 5, 4, 8, 0, tzinfo=ZoneInfo("Pacific/Noumea"))`), assert `Lesson.from_dict(L.to_dict()) == L`.
      - `test_snapshot_to_from_dict_roundtrip`: build a `Snapshot` with one Lesson + one Grade + one Information, assert round-trip equality.
      - `test_snapshot_lessons_today_filters_to_today`: 3 lessons (yesterday, today, tomorrow), assert `len(snap.lessons_today) == 1`.
      - `test_snapshot_lessons_tomorrow_filters_to_tomorrow`: same fixture, assert `len(snap.lessons_tomorrow) == 1`.
      - `test_lesson_dataclass_is_frozen`: `with pytest.raises(dataclasses.FrozenInstanceError): L.subject = "X"`.
      - `test_from_dict_rejects_naive_datetime`: `with pytest.raises(ParseError): Lesson.from_dict({"start": "2026-05-04T08:00:00", ...})` (no offset → naive — D-23 rejects).

    - **`tests/test_api/test_strip.py`** (2 tests minimum):
      - Define a local class `_FakePronotepyObj` with `__init__` setting `self.client = sentinel`, `self._session = sentinel`, `self.subject = "Mathématiques"`.
      - `test_strip_drops_client_back_ref`: pass through `strip_client_refs`, assert `obj.client is None`, `obj._session is None`, `obj.subject == "Mathématiques"` (unchanged).
      - `test_strip_returns_same_object`: assert `strip_client_refs(obj) is obj`.
      - `test_strip_handles_object_without_client_ref`: `strip_client_refs(SimpleNamespace(subject="X"))` must not raise.

    **6. Coding constraints (apply to every new file in this task):**
    - `from __future__ import annotations` at top of every .py file.
    - NO `homeassistant.*` import (D-19; the AST guard in Plan 02-04 will fail CI if violated).
    - NO `pytz` (Phase 1 D-31, ruff banned-api).
    - NO `requests` direct (Phase 1 D-32, ruff banned-api).
    - NO `async_timeout` (Phase 1 D-30, ruff banned-api).
    - Match Phase 1 ruff rules — pydocstyle "google" convention, line-length 120, target py314.
    - Use Google-style docstrings on every public class and function.
    - Type-annotate all public signatures (pyright basic mode is configured in Phase 1).

    **7. Verification commands** (in this order):
    - `ruff format custom_components/ha_pronote/api tests/test_api`
    - `ruff check custom_components/ha_pronote/api tests/test_api`
    - `pytest tests/test_api/test_errors.py tests/test_api/test_models.py tests/test_api/test_strip.py -v` — all pass.
    - `python -c "from custom_components.ha_pronote.api import AuthError, ErrorReason, Snapshot, Lesson, Grade, Information; print('ok')"` exits 0 and prints `ok`.
  </action>
  <verify>
    <automated>ruff check custom_components/ha_pronote/api tests/test_api &amp;&amp; ruff format --check custom_components/ha_pronote/api tests/test_api &amp;&amp; pytest tests/test_api/test_errors.py tests/test_api/test_models.py tests/test_api/test_strip.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `custom_components/ha_pronote/api/__init__.py`, `errors.py`, `models.py`, `_strip.py` all exist.
    - `grep -c "class ErrorReason(StrEnum)" custom_components/ha_pronote/api/errors.py` returns 1.
    - `grep -E "AUTH_FAILED|IP_SUSPENDED|PROTOCOL_BROKEN|SERVER_DOWN|SESSION_EXPIRED|RATE_LIMITED|PARSE_ERROR" custom_components/ha_pronote/api/errors.py | wc -l` returns 7 (one per member declaration).
    - `grep -c "@dataclass(frozen=True)" custom_components/ha_pronote/api/models.py` returns at least 4 (Lesson, Grade, Information, Snapshot).
    - `grep -rE "from homeassistant" custom_components/ha_pronote/api tests/test_api` returns nothing.
    - `pytest tests/test_api/test_errors.py tests/test_api/test_models.py tests/test_api/test_strip.py` exits 0.
    - `ruff check custom_components/ha_pronote/api tests/test_api` exits 0.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement api/client.py + api/fetcher.py + tests with requests-mock</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Snapshot Fetch Window" (D-15..D-18) + §"Error Hierarchy" (D-22) + §"Diff Algorithm" (D-23, D-24)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"api/client.py" + §"api/fetcher.py"
    - .planning/research/PITFALLS.md §"Pitfall 1" (IP suspended) + §"Pitfall 2" (pronotepy breakage) + §"Pitfall 4" (NC tz)
    - .planning/research/ARCHITECTURE.md §"Pattern 1" (sync wrapped via executor) + §"Anti-Pattern 5" (no pronotepy refs leak)
    - custom_components/ha_pronote/api/errors.py (the hierarchy Task 1 created — for the error-mapping table)
    - custom_components/ha_pronote/api/models.py (the dataclasses Task 1 created — for fetcher.py construction)
    - custom_components/ha_pronote/api/_strip.py (Task 1 — for fetcher.py defense-in-depth)
    - custom_components/ha_pronote/manifest.json (confirm pronotepy==2.14.6 pin from Phase 1 D-14)
    - requirements_test.txt (Phase 1 — confirm requests-mock is transitive via PHACC, made explicit by this task)
    - CLAUDE.md "What NOT to Use" (NO pronotepy.ent.*, NO direct requests, NO hardcoded URL)
  </read_first>
  <behavior>
    - `build_client("https://demo.example.com/pronote/eleve.html", "eleve", "u", "p")` returns a `pronotepy.Client` instance (NOT `ParentClient`) when authentication succeeds via mocked pronotepy.
    - `build_client("...", "parent", "u", "p")` returns a `pronotepy.ParentClient` instance.
    - When pronotepy raises `pronotepy.PronoteAPIError("Your IP address is suspended")`, build_client raises `RateLimitedError` with `reason == ErrorReason.IP_SUSPENDED` (D-22, Pitfall 1).
    - When pronotepy raises `pronotepy.exceptions.CryptoError(...)`, build_client raises `AuthError(reason=AUTH_FAILED)` (Pitfall 2).
    - When pronotepy raises any other `pronotepy.PronoteAPIError`, build_client raises `CommunicationError(PROTOCOL_BROKEN)` chained `from` the original (`raise ... from err`).
    - When pronotepy raises `OSError` (network), build_client raises `CommunicationError(SERVER_DOWN)`.
    - `fetch_all(client, today=date(2026, 5, 4), school_tz=ZoneInfo("Pacific/Noumea"))` invokes `client.lessons(date_from=date(2026, 4, 27), date_to=date(2026, 5, 18))` (today-7 → today+14, D-15).
    - Every datetime field on returned Lesson/Grade/Information is tz-aware (`.tzinfo is not None`) (D-23, TIME-04).
    - For `school_tz=ZoneInfo("Pacific/Noumea")`, returned datetime tzinfo offset is +11:00 (NC has no DST).
    - For `school_tz=ZoneInfo("Europe/Paris")` summer date, returned tzinfo offset is +02:00; winter date is +01:00.
    - `fetch_all` does NOT call `datetime.now()` (D-17 — `today` is injected).
    - `fetch_all` does NOT use a global `school_tz` constant (D-18 — passed in).
    - When `client` is a `pronotepy.ParentClient` AND `child_index_or_identifier=0`, `client.set_child(0)` is called exactly once BEFORE any fetch (D-21, PC-02-03).
    - When `client` is a `pronotepy.ParentClient` AND `child_index_or_identifier=None`, `client.set_child` is NOT called (pronotepy defaults to the first child).
    - When `client` is a `pronotepy.Client` (eleve), the `child_index_or_identifier` argument is ignored — `client.set_child` is never accessed (`spec=pronotepy.Client` enforces).
    - Snapshot returned from `fetch_all` has `.school_tz` field set to `str(school_tz)`.
    - No object in `Snapshot.lessons | grades | information` has `.client`, `._session`, `._client`, or `._pronote` attribute pointing to a non-None value (D-24, Anti-Pattern 5).
    - All Lesson/Grade/Information objects in the snapshot have `__class__.__module__.startswith("custom_components.ha_pronote.api")` — no pronotepy classes leak (D-24).
  </behavior>
  <action>
    Implement the sync facade and orchestrator that Plan 02-02 will run against the live Pronote server. Use `requests-mock` for hermetic tests — no demo Pronote instance contact in CI.

    **1. Append `requests-mock==1.12.1` line to `requirements_test.txt`** (D-26):
    Open the existing file and append at the end (preserve all existing pinned-deps and comments):
    ```
    
    # D-26: explicit pin (already transitive via PHACC). Hermetic api/ tests.
    requests-mock==1.12.1
    ```

    **2. Append constants to `custom_components/ha_pronote/const.py`** (D-15, D-18 + PATTERNS.md §"const.py"):
    Preserve the existing `DOMAIN: Final = "ha_pronote"` declaration. Append:
    ```python

    # Phase 2 additions (D-15, D-18) — defaults consumed by Phase 3 coordinator.
    # NOT imported by api/ — fetcher.py takes today / school_tz as arguments (D-17, D-18).
    DEFAULT_SCHOOL_TZ: Final = "Pacific/Noumea"
    DEFAULT_LOOKBACK_DAYS: Final = 7    # J-7
    DEFAULT_LOOKAHEAD_DAYS: Final = 14  # J+14
    ```

    **3. Create `custom_components/ha_pronote/api/client.py`** per D-21, D-22 + PATTERNS.md §"api/client.py":

    ```python
    """Sync facade over pronotepy. HA-free per D-19/D-20.

    Caller (Phase 3 coordinator) wraps in `await hass.async_add_executor_job(partial(...))`.
    """
    from __future__ import annotations

    from typing import Literal

    import pronotepy  # NO pronotepy.ent.* imports (D-21 / Phase 1 D-33)

    from .errors import (
        AuthError,
        CommunicationError,
        ErrorReason,
        RateLimitedError,
    )

    AccountType = Literal["eleve", "parent"]   # C-04

    _IP_SUSPENDED_LITERAL = "Your IP address is suspended"  # D-22, Pitfall 1


    def build_client(
        url: str,
        account_type: AccountType,
        username: str,
        password: str,
    ) -> pronotepy.Client | pronotepy.ParentClient:
        """Construct a pronotepy client.

        Args:
            url: Full Pronote space URL (e.g. ``https://example.com/pronote/eleve.html``).
                Phase 1 D-34: never hardcoded — caller passes from ConfigEntry data.
            account_type: ``"eleve"`` or ``"parent"`` (C-04).
            username: Pronote account username.
            password: Pronote account password.

        Returns:
            `pronotepy.Client` for ``"eleve"``, `pronotepy.ParentClient` for ``"parent"``.

        Raises:
            AuthError: pronotepy CryptoError or auth-shaped failure (Pitfall 2).
            RateLimitedError: pronotepy returned the literal "Your IP address is
                suspended" (Pitfall 1, D-22).
            CommunicationError: any other pronotepy or network failure.
        """
        cls = pronotepy.ParentClient if account_type == "parent" else pronotepy.Client
        try:
            return cls(url, username=username, password=password)
        except pronotepy.exceptions.CryptoError as err:
            raise AuthError(str(err)) from err
        except pronotepy.PronoteAPIError as err:
            if _IP_SUSPENDED_LITERAL in str(err):
                raise RateLimitedError(str(err)) from err
            raise CommunicationError(
                str(err), reason=ErrorReason.PROTOCOL_BROKEN
            ) from err
        except OSError as err:
            raise CommunicationError(str(err)) from err
    ```

    **4. Create `custom_components/ha_pronote/api/fetcher.py`** per D-15, D-17, D-18, D-23, D-24 + PATTERNS.md §"api/fetcher.py":

    ```python
    """Snapshot fetch + tz-localization. Sync — caller wraps in executor.

    D-15: J-7 -> J+14 fetch window (CAL-01 cross-cutting tracker for Phase 4 calendar).
    D-17: `today` injected, NOT computed via datetime.now().
    D-18: `school_tz` injected, NO global default in api/.
    D-23: pronotepy returns naive datetimes in school local time (Pitfall 4) — localize here.
    D-24: strip pronotepy back-refs (Anti-Pattern 5).
    """
    from __future__ import annotations

    from datetime import date, datetime, timedelta
    from typing import Any
    from zoneinfo import ZoneInfo

    import pronotepy

    from ._strip import strip_client_refs
    from .errors import CommunicationError, ErrorReason
    from .models import Grade, Information, Lesson, Snapshot


    def fetch_all(
        client: pronotepy.Client | pronotepy.ParentClient,
        today: date,
        school_tz: ZoneInfo,
        child_index_or_identifier: int | str | None = None,
    ) -> Snapshot:
        """Fetch lessons, grades, informations across the J-7 -> J+14 window.

        Args:
            client: Authenticated pronotepy client (built via build_client).
            today: Reference date for the window (D-17 — pure-deterministic).
            school_tz: Timezone of the Pronote server (D-18 — typically
                Pacific/Noumea for ac-noumea.nc, Europe/Paris elsewhere).
            child_index_or_identifier: For ParentClient only (D-21). When set,
                `client.set_child(child_index_or_identifier)` is called BEFORE
                any fetch so subsequent reads return the selected child's data.
                When None and `client` is a ParentClient, pronotepy defaults to
                the first child (no `set_child` call). Ignored for eleve `Client`.

        Returns:
            Plain-dataclass Snapshot. NO pronotepy objects leak (D-24).

        Raises:
            CommunicationError: any failure during pronotepy fetch.
        """
        # D-21 — child selection for ParentClient lives in api/fetcher.py, not
        # in api/client.py (build_client). Phase 3's coordinator decides which
        # child to fetch and passes the index/identifier on each call.
        if (
            isinstance(client, pronotepy.ParentClient)
            and child_index_or_identifier is not None
        ):
            client.set_child(child_index_or_identifier)

        start = today - timedelta(days=7)
        end = today + timedelta(days=14)

        try:
            raw_lessons = client.lessons(date_from=start, date_to=end)
            raw_grades = (
                list(client.current_period.grades) if client.current_period else []
            )
            raw_info = list(client.information_and_surveys)
        except pronotepy.PronoteAPIError as err:
            raise CommunicationError(
                str(err), reason=ErrorReason.PROTOCOL_BROKEN
            ) from err
        except OSError as err:
            raise CommunicationError(str(err)) from err

        # Strip back-refs defense-in-depth (D-24, C-05) BEFORE field-by-field copy.
        for obj in (*raw_lessons, *raw_grades, *raw_info):
            strip_client_refs(obj)

        return Snapshot(
            today=today,
            school_tz=str(school_tz),
            lessons=[_lesson_from_raw(L, school_tz) for L in raw_lessons],
            grades=[_grade_from_raw(G) for G in raw_grades],
            information=[_info_from_raw(I, school_tz) for I in raw_info],
        )


    def _localize(naive_dt: datetime | None, school_tz: ZoneInfo) -> datetime | None:
        """Pronotepy returns naive datetimes in school local time (Pitfall 4)."""
        if naive_dt is None:
            return None
        if naive_dt.tzinfo is not None:
            # Defensive: pronotepy 2.14.6 returns naive, but a future version might.
            return naive_dt
        return naive_dt.replace(tzinfo=school_tz)


    def _lesson_from_raw(raw: Any, school_tz: ZoneInfo) -> Lesson:
        """Field-by-field copy. NO pronotepy back-pointer (Anti-Pattern 5)."""
        start = _localize(raw.start, school_tz)
        end = _localize(raw.end, school_tz)
        if start is None or end is None:
            raise CommunicationError(
                "Lesson missing start/end datetime",
                reason=ErrorReason.PARSE_ERROR,
            )
        return Lesson(
            date=start.date(),
            start=start,
            end=end,
            subject=raw.subject.name if raw.subject else "",
            teacher=raw.teacher_name or "",
            classroom=raw.classroom or "",
            canceled=bool(raw.canceled),
            status=raw.status or "",
        )


    def _grade_from_raw(raw: Any) -> Grade:
        return Grade(
            subject=raw.subject.name if raw.subject else "",
            value=str(raw.grade) if raw.grade is not None else "",
            out_of=str(raw.out_of) if raw.out_of is not None else "",
            coefficient=str(raw.coefficient) if raw.coefficient is not None else "",
            date=raw.date,
        )


    def _info_from_raw(raw: Any, school_tz: ZoneInfo) -> Information:
        published = _localize(raw.start_date, school_tz) or _localize(
            getattr(raw, "creation_date", None), school_tz
        )
        if published is None:
            raise CommunicationError(
                "Information missing date", reason=ErrorReason.PARSE_ERROR
            )
        return Information(
            info_id=str(raw.id),
            title=raw.title or "",
            sender=getattr(raw, "author", "") or "",
            date=published,
            excerpt=(raw.content or "")[:500],
            read=bool(getattr(raw, "read", False)),
        )
    ```

    Note: the exact pronotepy field accessors (`raw.subject.name`, `raw.teacher_name`, `raw.classroom`, `raw.canceled`, `raw.status`, `raw.grade`, `raw.out_of`, `raw.coefficient`, `raw.start_date`, `raw.id`, `raw.title`, `raw.author`, `raw.content`, `raw.read`) are derived from the pronotepy 2.14.6 surface (PATTERNS.md `<canonical_refs>` line 153 + ARCHITECTURE.md "Pattern 1"). If Plan 02-02's spike reveals a different field name, the executor of Plan 02-02 will update this file — Phase 2's spike-first ordering (D-05/D-07) explicitly allows refinement.

    Note (PC-02-04 — Phase 3 deferral): `export_credentials_dict` is **deferred to Phase 3 (AUTH-04)** — Phase 3's coordinator will call `client.export_credentials()` directly (pronotepy already exposes it as a sync method on `Client`/`ParentClient`). Phase 2's `api/` surface intentionally does NOT wrap `export_credentials()` because token persistence belongs to the coordinator (which owns `entry.data` storage), not to the pure-Python `api/`. Document this boundary in `api/__init__.py`'s module docstring: add a paragraph stating `"Token persistence (export_credentials) is Phase 3's coordinator responsibility — not exposed here."` so a future maintainer doesn't add it to `api/` by accident.

    **5. Create `tests/test_api/test_client.py`** per PATTERNS.md §"test_client.py" + D-22, D-26:
    Include at minimum:
    - `test_eleve_account_type_returns_pronotepy_client`: monkeypatch `pronotepy.Client.__init__` to return None (no real auth), assert `isinstance(build_client(...), pronotepy.Client) and not isinstance(..., pronotepy.ParentClient)`.
    - `test_parent_account_type_returns_parent_client`: same but with `account_type="parent"` and `pronotepy.ParentClient`.
    - `test_ip_suspended_message_raises_rate_limited` (D-22): use `monkeypatch.setattr(pronotepy.Client, "__init__", _raises_pronote_api_error("Your IP address is suspended"))`. Assert `pytest.raises(RateLimitedError)` and `exc.value.reason == ErrorReason.IP_SUSPENDED`.
    - `test_crypto_error_raises_auth_error`: monkeypatch to raise `pronotepy.exceptions.CryptoError("Padding")`. Assert `AuthError` with `reason == AUTH_FAILED`.
    - `test_other_pronote_error_raises_communication_error`: monkeypatch to raise `pronotepy.PronoteAPIError("Some other failure")`. Assert `CommunicationError` with `reason == PROTOCOL_BROKEN`.
    - `test_os_error_raises_communication_error_server_down`: monkeypatch to raise `OSError("network unreachable")`. Assert `CommunicationError` with `reason == SERVER_DOWN`.
    - `test_communication_error_chains_original_via_from`: assert `exc.value.__cause__ is the original error`.

    Use `monkeypatch` (pytest builtin) rather than full requests-mock for client constructor tests — pronotepy's `__init__` triggers many internal HTTP calls; intercepting at the constructor level keeps tests fast and focused on the error-mapping contract. The `mocked_pronote_session` fixture from conftest.py is available for any test that needs to drill into the `requests.Session` layer.

    **6. Create `tests/test_api/test_fetcher.py`** per PATTERNS.md §"test_fetcher.py" + D-15, D-17, D-18, D-23, D-24:

    Define a minimal fake pronotepy Client class at module scope (NOT a fixture — fixture caching can mask issues):
    ```python
    class _FakeLesson:
        def __init__(self, start, end, subject="Maths", teacher_name="M. X",
                     classroom="A1", canceled=False, status=""):
            self.start = start
            self.end = end
            self.subject = type("S", (), {"name": subject})()
            self.teacher_name = teacher_name
            self.classroom = classroom
            self.canceled = canceled
            self.status = status

    class _FakeClient:
        def __init__(self, lessons=None, grades=None, info=None):
            self._lessons = lessons or []
            self._grades = grades or []
            self._info = info or []
            class _Period:
                grades = self._grades
            self.current_period = _Period() if grades is not None else None
            self.information_and_surveys = self._info

        def lessons(self, date_from, date_to):
            self.last_call = (date_from, date_to)
            return self._lessons
    ```

    Tests:
    - `test_fetch_all_window_is_today_minus_7_to_today_plus_14` (D-15): inject `today=date(2026, 5, 4)`, assert `client.last_call == (date(2026, 4, 27), date(2026, 5, 18))`.
    - `test_naive_pronotepy_datetimes_are_localized_to_school_tz` (D-23): naive datetime in fixture → assert returned `lesson.start.tzinfo is not None` and `lesson.start.utcoffset()` matches the school_tz offset (Pacific/Noumea = +11:00 always; Europe/Paris = depends on date).
    - `test_no_pronotepy_objects_leak_into_snapshot` (D-24, Anti-Pattern 5): assert every `lesson.__class__.__module__.startswith("custom_components.ha_pronote.api")`.
    - `test_no_back_refs_on_returned_lessons` (D-24): assert no `lesson` has a `.client` or `._session` attribute pointing to a non-None value (use `getattr(lesson, "client", None) is None`).
    - `test_school_tz_is_stored_as_string`: assert `snap.school_tz == str(ZoneInfo("Pacific/Noumea"))`.
    - `test_fetch_all_uses_injected_today_not_datetime_now`: parametrize over `today=date(2020, 1, 1)` and assert `client.last_call[0] == date(2019, 12, 25)` — proves no `datetime.now()` (D-17).
    - `test_pronote_api_error_during_lessons_raises_communication_error`: `_FakeClient.lessons` raises `pronotepy.PronoteAPIError`, assert `CommunicationError` with reason `PROTOCOL_BROKEN`.
    - `test_paris_summer_offset_is_plus_2`: assert with school_tz=Europe/Paris, lesson on 2026-07-15 has `tzinfo.utcoffset(...).total_seconds() == 7200`. (Defensive against Phase 1 D-31 — proves we use zoneinfo, not pytz.)
    - `test_fetch_all_calls_set_child_for_parent_client_with_index` (D-21, PC-02-03): use `unittest.mock.MagicMock(spec=pronotepy.ParentClient)` whose `lessons`, `current_period.grades`, `information_and_surveys` return empty iterables and whose `set_child` is a `MagicMock`. Pass `child_index_or_identifier=0`. Assert `mock.set_child.assert_called_once_with(0)`. Repeat with `child_index_or_identifier="abc"` and assert `assert_called_once_with("abc")` to cover both int and str variants.
    - `test_fetch_all_skips_set_child_for_eleve_client` (D-21, PC-02-03): use `unittest.mock.MagicMock(spec=pronotepy.Client)` (NOT ParentClient). The `spec=pronotepy.Client` constraint forbids accessing `set_child` (it's not in `pronotepy.Client.__dict__`) — accessing the attribute would raise `AttributeError`. Call `fetch_all(mock, today, school_tz, child_index_or_identifier=0)`; assert it completes without error AND that `set_child` was never accessed (use `assert "set_child" not in dir(mock)` or wrap in try/except `AttributeError` then assert no recorded call).
    - `test_fetch_all_skips_set_child_for_parent_client_when_identifier_none` (D-21, PC-02-03): `MagicMock(spec=pronotepy.ParentClient)`, pass `child_index_or_identifier=None` (default). Assert `mock.set_child.call_count == 0` — pronotepy's default-first-child behavior is preserved.

    **7. Coding constraints:** same as Task 1 (no homeassistant.* import, ruff/pyright clean, frozen dataclasses, etc.).

    **8. Verification commands:**
    - `uv pip install --system requests-mock==1.12.1` (locally — CI installs via requirements_test.txt).
    - `ruff format custom_components/ha_pronote/api tests/test_api`
    - `ruff check custom_components/ha_pronote/api tests/test_api`
    - `pytest tests/test_api/ -v` — all pass, sub-2-second runtime.
    - `python -c "from custom_components.ha_pronote.api import build_client, fetch_all; print('ok')"` exits 0.
  </action>
  <verify>
    <automated>uv pip install --system requests-mock==1.12.1 &amp;&amp; ruff check custom_components/ha_pronote/api tests/test_api &amp;&amp; pytest tests/test_api/ -v</automated>
  </verify>
  <acceptance_criteria>
    - `custom_components/ha_pronote/api/client.py` exists and contains `def build_client` with the four-argument signature `(url, account_type, username, password)`.
    - `custom_components/ha_pronote/api/fetcher.py` exists and contains `def fetch_all(client, today, school_tz, child_index_or_identifier=None)` (PC-02-03 — 4-arg signature, D-21).
    - `grep -c "Your IP address is suspended" custom_components/ha_pronote/api/client.py` returns at least 1.
    - `grep -c "today - timedelta(days=7)" custom_components/ha_pronote/api/fetcher.py` returns 1.
    - `grep -c "today + timedelta(days=14)" custom_components/ha_pronote/api/fetcher.py` returns 1.
    - `grep -c "datetime.now\\|dt_util" custom_components/ha_pronote/api/fetcher.py` returns 0 (D-17, D-19).
    - `grep -rE "from homeassistant" custom_components/ha_pronote/api tests/test_api` returns nothing.
    - `grep -c "requests-mock==1.12.1" requirements_test.txt` returns 1.
    - `grep -c "DEFAULT_SCHOOL_TZ" custom_components/ha_pronote/const.py` returns 1.
    - `pytest tests/test_api/ -v` exits 0 with at least 15 tests collected and passing.
    - `ruff check custom_components/ha_pronote/api tests/test_api` exits 0.
    - `grep -c "child_index_or_identifier" custom_components/ha_pronote/api/fetcher.py` returns ≥ 3 (signature, docstring `Args:` block, set_child call site) — D-21 final 4-arg signature (PC-02-03).
    - `grep -c "client.set_child" custom_components/ha_pronote/api/fetcher.py` returns 1 — set_child is only called from one site, gated on `isinstance(client, pronotepy.ParentClient) and child_index_or_identifier is not None` (D-21).
    - `grep -E "test_fetch_all_calls_set_child_for_parent_client_with_index|test_fetch_all_skips_set_child_for_eleve_client|test_fetch_all_skips_set_child_for_parent_client_when_identifier_none" tests/test_api/test_fetcher.py | wc -l` returns ≥ 3 (the three new tests for D-21 contract — PC-02-03).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: scripts/snapshot.py CLI + .env.example + .gitignore + anonymizer smoke test</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Fixture Sourcing" (D-10..D-14) + §"Claude's Discretion" (C-03)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"scripts/snapshot.py" + §".env.example" + §".env / Real-Output Gitignore"
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md `<specifics>` line 213 (no_pii invariant)
    - custom_components/ha_pronote/api/__init__.py (Task 1) — confirms the public surface scripts/snapshot.py imports
    - custom_components/ha_pronote/api/client.py (Task 2) — confirms build_client signature
    - custom_components/ha_pronote/api/fetcher.py (Task 2) — confirms fetch_all signature
    - .gitignore (existing Phase 1 file — Phase 2 appends two patterns)
    - CLAUDE.md "What NOT to Use" + Phase 1 D-34 (NO hardcoded URL — scripts/snapshot.py reads from .env, not from a const)
  </read_first>
  <behavior>
    - `python scripts/snapshot.py --help` exits 0 and prints usage including `--scenario` and `--phase`.
    - `python scripts/snapshot.py --scenario unknown_scenario --phase T0` exits non-zero with argparse error (choices enforcement).
    - `walk_and_replace("Alice Dupont was here", {"Alice Dupont": "Eleve Test"})` returns `"Eleve Test was here"`.
    - `walk_and_replace({"name": "Alice", "list": ["Alice", "Bob"]}, {"Alice": "Eleve"})` returns `{"name": "Eleve", "list": ["Eleve", "Bob"]}` (recursive str+dict+list).
    - `walk_and_replace(42, {"x": "y"}) == 42` (non-str/dict/list passes through).
    - `anonymize(snap_dict, repls)` is byte-for-byte deterministic across two calls with same input.
    - `no_pii(anonymize(d, {"Alice": "X"}), ["Alice"]) is True`.
    - `no_pii({"name": "Alice"}, ["Alice"]) is False`.
    - `_read_env(Path(".env-does-not-exist"))` returns `{}` (no exception).
    - `_read_env` correctly parses lines with `KEY=value`, skips comments (`#`) and blank lines, strips surrounding quotes from values.
    - `.env` and `tests/fixtures/real/_raw_*.json` patterns appear in `.gitignore`.
    - `.env.example` exists at repo root and contains all four required keys (`PRONOTE_URL`, `PRONOTE_USERNAME`, `PRONOTE_PASSWORD`, `PRONOTE_ACCOUNT_TYPE`) with placeholder values (the public Pronote demo instance).
    - `.env.example` MUST NOT contain real-looking credentials (no `katiramona.ac-noumea.nc`, no actual usernames/passwords from the author's account — security_gate threat #1).
  </behavior>
  <action>
    Build the spike tooling. This task does NOT execute the spike against a live server (that's Plan 02-02). It ships the CLI and the deterministic anonymizer that Plan 02-02 invokes.

    **1. Append to `.gitignore`** (D-12, D-13 + PATTERNS.md §".env / Real-Output Gitignore"):
    Preserve all existing lines. Append:
    ```gitignore

    # Phase 2: real-Pronote spike output (raw + .env)
    .env
    tests/fixtures/real/_raw_*.json
    ```

    **2. Create `.env.example`** at repo root per D-14 + PATTERNS.md §".env.example":
    ```bash
    # scripts/snapshot.py reads these. Do NOT commit a real .env (gitignored).
    # See README §"Refreshing fixtures when Pronote breaks" (Phase 7).
    #
    # Use the public Pronote demo instance for safe local experimentation.
    # The author's real instance lives in a local-only .env (gitignored).
    PRONOTE_URL=https://demo.index-education.net/pronote/eleve.html
    PRONOTE_USERNAME=demonstration
    PRONOTE_PASSWORD=pronotevs
    PRONOTE_ACCOUNT_TYPE=eleve
    ```

    SECURITY: Do NOT include `katiramona.ac-noumea.nc` or any real Pronote URL in `.env.example`. Phase 1 D-34 forbids hardcoded `katiramona.ac-noumea.nc` in code; .env.example is part of the committed surface and must follow the same rule. Plan 02-02's executor will populate the LOCAL `.env` (gitignored) with the author's real credentials before running the spike.

    **3. Create `scripts/snapshot.py`** per D-12, D-13, D-14, C-03 + PATTERNS.md §"scripts/snapshot.py":

    ```python
    """One-shot real-Pronote spike + anonymizer (D-13).

    Not a tested production code surface. Lives outside custom_components/.
    Reads .env (D-14), invokes api.build_client + api.fetch_all, writes:
      - tests/fixtures/real/_raw_<scenario>_<phase>.json   (gitignored)
      - tests/fixtures/real/<scenario>_<phase>.json        (anonymized, committed)

    Anonymization (C-03): explicit name-list, recursive walk, NO regex.
    Smoke test (`tests/test_scripts/test_snapshot.py`) covers the deterministic
    behavior of `walk_and_replace` and the `no_pii` invariant — NOT the network
    round-trip (D-13).
    """
    from __future__ import annotations

    import argparse
    import json
    import sys
    from datetime import date
    from pathlib import Path
    from typing import Any
    from zoneinfo import ZoneInfo

    # scripts/ is OUTSIDE custom_components/ — direct sys.path tweak so the
    # script runs from a fresh checkout without `uv pip install -e .` (D-13).
    REPO_ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(REPO_ROOT))

    from custom_components.ha_pronote.api import build_client, fetch_all  # noqa: E402

    SCENARIOS = ("cancellation", "room_change", "teacher_swap")
    PHASES = ("T0", "T1")


    def _read_env(path: Path) -> dict[str, str]:
        """Manual .env parser — no python-dotenv runtime dep (D-13)."""
        if not path.is_file():
            return {}
        out: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, sep, value = stripped.partition("=")
            if not sep:
                continue
            out[key.strip()] = value.strip().strip('"').strip("'")
        return out


    def walk_and_replace(obj: Any, replacements: dict[str, str]) -> Any:
        """C-03: explicit name-list, recursive walk. NOT regex."""
        if isinstance(obj, str):
            for old, new in replacements.items():
                obj = obj.replace(old, new)
            return obj
        if isinstance(obj, dict):
            return {k: walk_and_replace(v, replacements) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk_and_replace(v, replacements) for v in obj]
        return obj


    def anonymize(snapshot_dict: dict, replacements: dict[str, str]) -> dict:
        """Deterministic — same input + same replacements -> same output."""
        return walk_and_replace(snapshot_dict, replacements)


    def no_pii(obj: Any, pii_blocklist: list[str]) -> bool:
        """`<specifics>` line 213 invariant — no PII string in serialized form."""
        serialized = json.dumps(obj, ensure_ascii=False)
        return not any(needle in serialized for needle in pii_blocklist if needle)


    def _build_replacements(env: dict[str, str]) -> dict[str, str]:
        """D-12: child names, school URL, establishment, teacher names.

        EXTEND this dict with real teacher names and classroom IDs as the spike
        captures them. The `replacements` dict is the source of truth — every
        PII token discovered during the spike MUST be added here BEFORE
        committing the anonymized fixture.
        """
        repls = {}
        if env.get("PRONOTE_USERNAME"):
            repls[env["PRONOTE_USERNAME"]] = "Eleve Test"
        if env.get("PRONOTE_URL"):
            from urllib.parse import urlparse

            host = urlparse(env["PRONOTE_URL"]).netloc
            if host:
                repls[host] = "pronote.example.fr"
        # Plan 02-02's spike executor adds firstname/lastname/teacher names/classroom IDs here.
        return repls


    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            description=(
                "One-shot Pronote snapshot + anonymizer. "
                "Reads .env (D-14). Output goes to tests/fixtures/real/."
            )
        )
        parser.add_argument(
            "--scenario", required=True, choices=SCENARIOS,
            help="Which spike scenario this snapshot represents.",
        )
        parser.add_argument(
            "--phase", required=True, choices=PHASES,
            help="T0 = before the change happened in Pronote; T1 = after.",
        )
        parser.add_argument(
            "--out", type=Path, default=Path("tests/fixtures/real"),
            help="Output directory (default: tests/fixtures/real/).",
        )
        args = parser.parse_args(argv)

        env = _read_env(REPO_ROOT / ".env")
        for required in ("PRONOTE_URL", "PRONOTE_USERNAME", "PRONOTE_PASSWORD",
                         "PRONOTE_ACCOUNT_TYPE"):
            if not env.get(required):
                print(
                    f"error: {required} not set in .env (see .env.example)",
                    file=sys.stderr,
                )
                return 2

        client = build_client(
            url=env["PRONOTE_URL"],
            account_type=env["PRONOTE_ACCOUNT_TYPE"],   # type: ignore[arg-type]
            username=env["PRONOTE_USERNAME"],
            password=env["PRONOTE_PASSWORD"],
        )
        snap = fetch_all(
            client,
            today=date.today(),
            school_tz=ZoneInfo("Pacific/Noumea"),
        )

        args.out.mkdir(parents=True, exist_ok=True)
        raw_path = args.out / f"_raw_{args.scenario}_{args.phase}.json"
        anon_path = args.out / f"{args.scenario}_{args.phase}.json"

        snap_dict = snap.to_dict()
        raw_path.write_text(
            json.dumps(snap_dict, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        replacements = _build_replacements(env)
        anon = anonymize(snap_dict, replacements)
        anon_path.write_text(
            json.dumps(anon, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        if not no_pii(json.loads(anon_path.read_text(encoding="utf-8")),
                      list(replacements.keys())):
            print(
                "error: anonymized output still contains PII tokens — "
                "extend _build_replacements before committing.",
                file=sys.stderr,
            )
            return 3

        print(f"wrote {raw_path} (gitignored) and {anon_path} (committable)")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

    **4. Add ruff per-file-ignore and pyright exclusion for `scripts/`** (D-13). Open `pyproject.toml` and:
    - In `[tool.ruff.lint.per-file-ignores]`, add an entry for `"scripts/*"` excluding strict pydocstyle and import-discipline rules:
      ```toml
      "scripts/*" = [
          "T20",     # print is the script's UX
          "INP001",  # scripts/ is intentionally not a package
          "S603", "S607",  # subprocess (in case Plan 02-02 adds shell helpers)
          "D",       # full docstring set not required for one-shot tools
      ]
      ```
    - In `[tool.pyright]`, append `scripts/` to the `exclude` list (or leave `include` to `["custom_components/ha_pronote", "tests"]` so scripts/ is naturally excluded — VERIFY current state and pick the simpler diff). Currently include is `["custom_components/ha_pronote", "tests"]` which already excludes scripts/, so NO pyright change is needed.

    **5. Add coverage exclusion for scripts/** (D-13) — already covered: existing `[tool.coverage.run] source = ["custom_components/ha_pronote"]` excludes scripts/ by default. NO change needed.

    **6. Create `tests/test_scripts/__init__.py`**: empty file.

    **7. Create `tests/test_scripts/test_snapshot.py`** per D-13, `<specifics>` line 213 + PATTERNS.md §"test_snapshot.py":

    ```python
    """Smoke tests for scripts/snapshot.py — the anonymizer is contract-tested.

    D-13: snapshot.py is NOT a tested code surface. We test ONLY:
      1. anonymize() is deterministic (same input + same replacements -> same output).
      2. no_pii() is the documented invariant (returns True iff PII allowlist absent).
      3. walk_and_replace() handles str/dict/list/passthrough recursively.
      4. _read_env() handles missing files, comments, blank lines, quoted values.
      5. CLI --help works and --scenario/--phase choices are enforced.
    """
    from __future__ import annotations

    import json
    import subprocess
    import sys
    from pathlib import Path

    import pytest

    # scripts/ is outside custom_components/ — direct import via REPO_ROOT.
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(REPO_ROOT))

    from scripts.snapshot import (  # noqa: E402
        _build_replacements,
        _read_env,
        anonymize,
        no_pii,
        walk_and_replace,
    )


    def test_walk_and_replace_replaces_in_string():
        assert walk_and_replace("Alice was here", {"Alice": "Eleve"}) == "Eleve was here"


    def test_walk_and_replace_recurses_into_dict():
        out = walk_and_replace({"name": "Alice", "school": "X"}, {"Alice": "Eleve"})
        assert out == {"name": "Eleve", "school": "X"}


    def test_walk_and_replace_recurses_into_list():
        assert walk_and_replace(["Alice", "Bob"], {"Alice": "Eleve"}) == ["Eleve", "Bob"]


    def test_walk_and_replace_recurses_nested():
        inp = {"k": [{"name": "Alice"}, {"name": "Bob"}]}
        out = walk_and_replace(inp, {"Alice": "Eleve"})
        assert out == {"k": [{"name": "Eleve"}, {"name": "Bob"}]}


    def test_walk_and_replace_passes_through_non_str():
        assert walk_and_replace(42, {"x": "y"}) == 42
        assert walk_and_replace(None, {"x": "y"}) is None
        assert walk_and_replace(True, {"x": "y"}) is True


    def test_anonymize_is_deterministic():
        raw = {"name": "Alice Dupont", "school": "Lycée Katiramona"}
        repls = {"Alice Dupont": "Eleve Test", "Lycée Katiramona": "Établissement Test"}
        out1 = anonymize(raw, repls)
        out2 = anonymize(raw, repls)
        assert out1 == out2
        assert out1 == {"name": "Eleve Test", "school": "Établissement Test"}


    def test_no_pii_returns_true_when_allowlist_absent():
        cleaned = anonymize({"name": "Alice"}, {"Alice": "Eleve"})
        assert no_pii(cleaned, ["Alice"]) is True


    def test_no_pii_returns_false_when_allowlist_present():
        assert no_pii({"name": "Alice"}, ["Alice"]) is False


    def test_no_pii_ignores_empty_strings_in_blocklist():
        # Defensive: empty string would always match — guard against it.
        assert no_pii({"name": "Alice"}, ["", "Alice"]) is False
        assert no_pii({"name": "Eleve"}, ["", "Alice"]) is True


    def test_read_env_returns_empty_for_missing_file(tmp_path):
        assert _read_env(tmp_path / "no.env") == {}


    def test_read_env_parses_key_value_pairs(tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text(
            "# comment\n"
            "PRONOTE_URL=https://example.com/pronote\n"
            "PRONOTE_USERNAME=alice\n"
            "\n"
            'PRONOTE_PASSWORD="quoted-secret"\n'
            "PRONOTE_ACCOUNT_TYPE='eleve'\n",
            encoding="utf-8",
        )
        env = _read_env(env_path)
        assert env["PRONOTE_URL"] == "https://example.com/pronote"
        assert env["PRONOTE_USERNAME"] == "alice"
        assert env["PRONOTE_PASSWORD"] == "quoted-secret"
        assert env["PRONOTE_ACCOUNT_TYPE"] == "eleve"


    def test_build_replacements_includes_username_and_host():
        env = {
            "PRONOTE_URL": "https://demo.example.com/pronote/eleve.html",
            "PRONOTE_USERNAME": "demonstration",
        }
        repls = _build_replacements(env)
        assert repls["demonstration"] == "Eleve Test"
        assert repls["demo.example.com"] == "pronote.example.fr"


    @pytest.mark.timeout(5)
    def test_cli_help_exits_zero():
        # @pytest.mark.timeout(5) overrides the global pyproject.toml `timeout = 1` (D-28,
        # PC-02-02): subprocess CLI startup can spend more than 1s in cold imports.
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "snapshot.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--scenario" in result.stdout
        assert "--phase" in result.stdout


    @pytest.mark.timeout(5)
    def test_cli_rejects_invalid_scenario():
        # @pytest.mark.timeout(5) overrides the global pyproject.toml `timeout = 1`
        # (D-28, PC-02-02): subprocess CLI startup can spend more than 1s in cold imports.
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "snapshot.py"),
                "--scenario", "invalid", "--phase", "T0",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "invalid choice" in result.stderr or "invalid" in result.stderr


    def test_env_example_does_not_contain_real_school_url():
        """SECURITY (security_gate threat #1): .env.example must NOT leak the
        author's real ac-noumea.nc URL. Real URL lives in the gitignored .env.
        """
        env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        assert "ac-noumea.nc" not in env_example
        assert "katiramona" not in env_example
        # Demo or example URLs are fine; real ones are not.
        assert "demo.index-education.net" in env_example or "example" in env_example
    ```

    **8. Verification commands:**
    - `python scripts/snapshot.py --help` exits 0 and prints usage.
    - `python scripts/snapshot.py --scenario invalid --phase T0` exits non-zero.
    - `pytest tests/test_scripts/ -v` — all pass.
    - `ruff check scripts tests/test_scripts` exits 0.
    - `grep -c "^.env$" .gitignore` returns 1.
    - `grep -c "tests/fixtures/real/_raw_" .gitignore` returns 1.
  </action>
  <verify>
    <automated>python scripts/snapshot.py --help &amp;&amp; pytest tests/test_scripts/ -v &amp;&amp; ruff check scripts tests/test_scripts &amp;&amp; grep -q '^.env$' .gitignore &amp;&amp; grep -q 'tests/fixtures/real/_raw_' .gitignore &amp;&amp; ! grep -q 'ac-noumea.nc' .env.example</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/snapshot.py` exists and `python scripts/snapshot.py --help` exits 0.
    - `python scripts/snapshot.py --help 2>&1 | grep -E 'scenario|phase'` returns at least 2 matching lines.
    - `.env.example` exists at repo root with all 4 required keys (PRONOTE_URL, PRONOTE_USERNAME, PRONOTE_PASSWORD, PRONOTE_ACCOUNT_TYPE).
    - `grep -c '^PRONOTE_' .env.example` returns 4.
    - `! grep -q 'ac-noumea.nc' .env.example` succeeds (NO real school URL leaks).
    - `! grep -q 'katiramona' .env.example` succeeds.
    - `.gitignore` contains `.env` and `tests/fixtures/real/_raw_*.json` patterns.
    - `pytest tests/test_scripts/ -v` exits 0 with at least 14 tests collected and passing.
    - `ruff check scripts tests/test_scripts` exits 0.
    - `tests/test_scripts/test_snapshot.py` contains a test asserting `.env.example` does not contain `ac-noumea.nc` (security_gate threat #1).
    - `grep -c "@pytest.mark.timeout(5)" tests/test_scripts/test_snapshot.py` returns ≥ 2 — the two subprocess CLI tests (`test_cli_help_exits_zero`, `test_cli_rejects_invalid_scenario`) override the global `timeout = 1` from Plan 02-04 (PC-02-02). Without these, the subprocess tests would flake under the 1-second global cap because cold-import + interpreter spawn can exceed 1s on slow CI runners.
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `.env` (filesystem) → `scripts/snapshot.py` (process memory) | Real Pronote credentials cross from a local-only file into the running script. Never logged, never written to anything but the gitignored raw JSON. |
| `.env.example` (committed file) | Public surface — must contain ONLY placeholder values. Plan 02-02 must not "edit and commit" the real .env. |
| `pronotepy.PronoteAPIError(...)` (third-party exception) → `api/client.py` (typed error mapping) | Untrusted error message strings cross here. The literal `"Your IP address is suspended"` is a security-relevant signal — must be detected reliably (D-22). |
| Naive `datetime` from pronotepy → `api/fetcher.py` localization (D-23) | School-local time semantics could be misinterpreted as UTC if not localized. Subtle correctness boundary, not a security boundary, but in the same defensive class. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01-01 | Information Disclosure | `.env.example` (committed) | mitigate | `.env.example` ships with the public Pronote demo instance URL only (`demo.index-education.net`). Test `test_env_example_does_not_contain_real_school_url` (Task 3) asserts neither `ac-noumea.nc` nor `katiramona` appear. The `.env` real-credential file is gitignored (Task 3 .gitignore append). **Severity: HIGH** if missed — would leak the author's real Pronote credential surface. |
| T-02-01-02 | Information Disclosure | `scripts/snapshot.py` raw output | mitigate | Raw snapshot JSON contains real child name + teacher names + classroom IDs + establishment URL. The `tests/fixtures/real/_raw_*.json` glob is gitignored (Task 3). Plan 02-02's spike executor MUST verify `git status` shows zero `_raw_*.json` files staged before committing. **Severity: HIGH** if missed — would leak PII of minors. |
| T-02-01-03 | Tampering / Information Disclosure | `api/client.py` error mapping | mitigate | Literal `"Your IP address is suspended"` (D-22, Pitfall 1) detection in `build_client` raises `RateLimitedError(IP_SUSPENDED)`. Tested in `tests/test_api/test_client.py::test_ip_suspended_message_raises_rate_limited`. Phase 5 wires the long-backoff response on this typed signal. **Severity: MEDIUM** for Phase 2 (typed signal is the contract; backoff handling is Phase 5). |
| T-02-01-04 | Spoofing | pronotepy `CryptoError` mistaken for "wrong password" | mitigate | `api/client.py` maps `pronotepy.exceptions.CryptoError` to `AuthError(AUTH_FAILED)` per Pitfall 2 — Phase 6's reauth flow surfaces it as "credentials no longer valid" (the user-correct framing). Tested in `tests/test_api/test_client.py::test_crypto_error_raises_auth_error`. **Severity: LOW** — UX correctness, not a security exposure. |
| T-02-01-05 | Information Disclosure / Memory leak | pronotepy `client` back-references on Lesson/Grade objects | mitigate | `api/_strip.py:strip_client_refs` walker (D-24, C-05) sets `.client`, `._session`, `._client`, `._pronote` to None on every fetched object. Field-by-field copy in `_lesson_from_raw` / `_grade_from_raw` / `_info_from_raw` is the primary defense; strip_client_refs is defense-in-depth. Tested in `tests/test_api/test_strip.py` and `tests/test_api/test_fetcher.py::test_no_pronotepy_objects_leak_into_snapshot`. **Severity: MEDIUM** — won't break v1 but degrades over time (HA restart pressure, JSON serialization failures in diagnostics later). |
| T-02-01-06 | Information Disclosure | Naive datetime mishandling (Pitfall 4) | mitigate | `api/fetcher.py:_localize` (D-23) sets `.tzinfo = school_tz` on every naive pronotepy datetime at parse time. Test `test_naive_pronotepy_datetimes_are_localized_to_school_tz` (Task 2) asserts `.tzinfo is not None` on every Lesson.start/end. Plan 02-04 adds the Paris+Nouméa pytest matrix as a second-line check. **Severity: MEDIUM** — would silently misreport "tomorrow" outside NC, eroding the project's Core Value. |
</threat_model>

<verification>
**Plan-level checks** (all must pass after Tasks 1+2+3 are complete):

1. **Pure-Python boundary holds (D-19, D-20):**
   - `grep -rE "from homeassistant" custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` returns nothing.
   - `grep -rE "import homeassistant" custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` returns nothing.
   - `grep -rE "import pytz|from pytz" custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` returns nothing.
   - `grep -rE "import async_timeout" custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` returns nothing.

2. **No `pronotepy.ent.*` imports (D-21, Phase 1 D-33):**
   - `grep -rE "pronotepy\\.ent" custom_components/ha_pronote/api scripts` returns nothing.

3. **Sync surface (Pitfall 3):**
   - `grep -rE "^async def|await " custom_components/ha_pronote/api` returns nothing (no async/await in api/).

4. **Test suite passes:**
   - `pytest tests/test_api/ tests/test_scripts/ -v` exits 0 with all tests passing.

5. **Lint + format clean:**
   - `ruff check custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` exits 0.
   - `ruff format --check custom_components/ha_pronote/api tests/test_api scripts tests/test_scripts` exits 0.

6. **Pyright basic clean:**
   - `npx pyright custom_components/ha_pronote/api tests/test_api` exits 0 (scripts/ excluded per pyproject.toml).

7. **manifest.json unchanged (Phase 2 does not touch it):**
   - `git diff --stat custom_components/ha_pronote/manifest.json` returns nothing (preserve Phase 1 D-14 contract).

8. **Phase 1 contract preserved:**
   - `pytest tests/test_init.py tests/test_manifest.py -v` exits 0 (existing Phase 1 tests still pass).
</verification>

<success_criteria>
- 18 new files exist under `custom_components/ha_pronote/api/` (6), `scripts/` (1), `tests/test_api/` (8 — `__init__.py` + conftest.py + 5 test files), `tests/test_scripts/` (2 — `__init__.py` + test file), and `.env.example` (1).
- 3 modified files (`custom_components/ha_pronote/const.py`, `requirements_test.txt`, `.gitignore`) preserve their existing content and append the Phase 2 additions only.
- 1 modified file (`pyproject.toml`) appends `scripts/*` to `[tool.ruff.lint.per-file-ignores]` (small surgical change).
- `pytest tests/test_api/ tests/test_scripts/` exits 0 with at least 30 tests passing in well under 2 seconds.
- `ruff check` + `ruff format --check` are green across all new/modified Python files.
- All 6 STRIDE threats above have a corresponding test or grep-verifiable mitigation.
- TIME-04 satisfied: every datetime field on every Lesson/Grade/Information is tz-aware after `fetch_all` runs (proven by `test_naive_pronotepy_datetimes_are_localized_to_school_tz`).
- The Phase 2 → Phase 3 interface (`build_client`, `fetch_all`, error hierarchy) is fully importable from `custom_components.ha_pronote.api`.
</success_criteria>

<output>
After completion, create `.planning/phases/02-api-diff-layer-ha-free/02-01-SUMMARY.md` documenting:
- What was built (api/ subpackage, scripts/snapshot.py, tests).
- Decision IDs implemented (D-11, D-15, D-16, D-17, D-18, D-21, D-22, D-23, D-24, D-26, D-12, D-13, D-14, C-03, C-04, C-05).
- Phase 2 success criterion #2 status: code-side ready; live-server execution belongs to Plan 02-02.
- Any pronotepy-2.14.6-field-name discrepancies discovered (e.g. if `raw.teacher_name` is actually `raw.teacherName` in 2.14.6 — the executor of Plan 02-02 will reconcile during the spike).
- Phase 1 contract verification: existing tests still green; manifest.json untouched.
</output>
</content>
</invoke>