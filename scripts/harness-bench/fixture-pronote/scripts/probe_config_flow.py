"""Live probe of the pronotepy API path our Phase 3 config flow uses.

Calls pronotepy DIRECTLY (bypassing custom_components.ha_pronote.api) so
this script doesn't need Home Assistant installed. Reproduces the exact
sequence of pronotepy calls our code makes:

  1. pronotepy.ParentClient(url, user, pass)        (= build_client)
  2. client.set_child(child_object_or_name)         (= set_active_child)
  3. client.export_credentials()                    (capture session)
  4. ParentClient.token_login(url, **kwargs)        (= build_or_resume_client)

For each step prints the **real** type + attribute shape of returned
objects. Use this to spot mock-drift bugs (ClientInfo vs Child, session
dict keys overlapping token_login kwargs, etc.) BEFORE shipping a release.

Run from repo root:

    uv run --no-project --python 3.13 \\
      --with pronotepy --with python-slugify --with requests-mock --with autoslot \\
      python scripts/probe_config_flow.py

Reads creds from .env (gitignored). Redacts secrets in output.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import uuid as uuid_lib

import pronotepy

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        k, sep, v = s.partition("=")
        if sep:
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _summarise(obj: object, *, max_attrs: int = 40) -> dict[str, object]:
    type_name = f"{type(obj).__module__}.{type(obj).__name__}"
    attrs = sorted(a for a in dir(obj) if not a.startswith("_"))[:max_attrs]
    info: dict[str, object] = {"_type": type_name, "_attrs": attrs}
    for a in attrs:
        try:
            v = getattr(obj, a)
        except Exception as e:  # noqa: BLE001
            info[a] = f"<getattr error: {e!r}>"
            continue
        if callable(v):
            info[a] = "<method>"
        elif isinstance(v, (str, int, float, bool, type(None))):
            s = str(v)
            info[a] = s if len(s) < 80 else s[:77] + "..."
        elif isinstance(v, (list, tuple)):
            info[a] = f"<{type(v).__name__} len={len(v)}>"
        elif isinstance(v, dict):
            info[a] = f"<dict keys={sorted(v.keys())[:10]}>"
        else:
            info[a] = f"<{type(v).__module__}.{type(v).__name__}>"
    return info


def _redact_session(session: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in session.items():
        if "password" in k.lower() or "token" in k.lower() or "secret" in k.lower():
            out[k] = f"<redacted {type(v).__name__} len={len(str(v))}>"
        elif isinstance(v, str) and len(v) > 80:
            out[k] = f"<str len={len(v)} starts={v[:20]!r}>"
        else:
            out[k] = v
    return out


def main() -> int:
    env = _read_env(REPO_ROOT / ".env")
    url = env.get("PRONOTE_URL", "")
    username = env.get("PRONOTE_USERNAME", "")
    password = env.get("PRONOTE_PASSWORD", "")
    account_type = env.get("PRONOTE_ACCOUNT_TYPE", "eleve")
    if not (url and username and password):
        print("ERROR: PRONOTE_URL / PRONOTE_USERNAME / PRONOTE_PASSWORD required in .env", file=sys.stderr)
        return 1

    cls = pronotepy.ParentClient if account_type == "parent" else pronotepy.Client
    print(f"=== Client class: {cls.__name__} ===\n")

    print(f"=== STEP 1: {cls.__name__}({url!r}, username, password, uuid=...) ===")
    client = cls(url, username=username, password=password, uuid=str(uuid_lib.uuid4()))
    print(json.dumps(_summarise(client), indent=2, default=str))
    print()

    if account_type == "parent":
        print(f"=== STEP 1b: client.children[*] introspection ({len(client.children)} children) ===")
        for i, child in enumerate(client.children):
            print(f"--- child[{i}] ---")
            print(json.dumps(_summarise(child), indent=2, default=str))
        print()

        print("=== STEP 2a: client.set_child(client.children[0]) — Child object ===")
        try:
            client.set_child(client.children[0])
            print("OK")
        except Exception as e:  # noqa: BLE001
            import traceback

            print(f"FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()
        print()

        print("=== STEP 2b: client.set_child(0) — int (the bug we already know) ===")
        try:
            client.set_child(0)
            print("OK (unexpected — int actually works)")
        except Exception as e:  # noqa: BLE001
            print(f"EXPECTED FAILURE: {type(e).__name__}: {e}")
        print()

        print("=== STEP 2c: client.set_child(client.children[0].name) — name string ===")
        try:
            client.set_child(client.children[0].name)
            print("OK")
        except Exception as e:  # noqa: BLE001
            print(f"FAILED: {type(e).__name__}: {e}")
        print()
    else:
        print("=== STEP 1b/2 skipped (account_type != parent) ===\n")

    print("=== STEP 3: client.export_credentials() ===")
    session = client.export_credentials()
    print(f"type: {type(session).__name__}")
    if isinstance(session, dict):
        print(f"keys: {sorted(session.keys())}")
        print(json.dumps(_redact_session(session), indent=2, default=str))
    else:
        print(repr(session)[:300])
    print()

    print(f"=== STEP 4a: {cls.__name__}.token_login signature ===")
    sig = inspect.signature(cls.token_login)
    print(f"  {sig}")
    if isinstance(session, dict):
        overlap = [p for p in sig.parameters if p in session and p != "self"]
        print(f"  session keys overlapping token_login params: {overlap}")
        explicit_kwargs = {"username", "device_name"}
        conflicts = [k for k in explicit_kwargs if k in session]
        print(f"  conflicts with our explicit kwargs ({explicit_kwargs}): {conflicts}")
    print()

    print(f"=== STEP 4b: {cls.__name__}.token_login(url, username=..., device_name=..., **session) — repro ===")
    try:
        resumed = cls.token_login(
            url,
            username=username,
            device_name="home-assistant-probe",
            **session if isinstance(session, dict) else {},
        )
        print(f"OK — resumed: {type(resumed).__name__}")
    except TypeError as e:
        print(f"REPRODUCED TypeError: {e}")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"OTHER: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 4c: try without explicit username/device_name (let session win) ===")
    try:
        if isinstance(session, dict):
            resumed = cls.token_login(url, **session)
            print(f"OK — resumed: {type(resumed).__name__}")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 4d: token_login(device_name=..., **session) — the actual fix ===")
    try:
        if isinstance(session, dict):
            resumed = cls.token_login(device_name="home-assistant-probe", **session)
            print(f"OK — resumed: {type(resumed).__name__}, logged_in={getattr(resumed, 'logged_in', '?')}")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    # =====================================================================
    # PHASE 4 PROBES — every pronotepy call the Phase 4 sensors/calendar/
    # events will need. Run these BEFORE writing Phase 4 code to avoid the
    # mock-drift cycle that hit Phase 3 alpha.1..alpha.8.
    # =====================================================================

    from datetime import date, timedelta

    today = date.today()
    j_minus_7 = today - timedelta(days=7)
    j_plus_14 = today + timedelta(days=14)

    # The steps 4b/4c/4d above created multiple token_login clients which
    # invalidate the original client's session ("Page a expiré"). Re-create
    # a fresh client + re-select the child for Phase 4 fetches. This also
    # mirrors what the coordinator does at every poll cycle (#D-21).
    print("=== Phase 4 prep: fresh client + set_child to clear session contamination ===")
    client = cls(url, username=username, password=password, uuid=str(uuid_lib.uuid4()))
    if account_type == "parent":
        client.set_child(client.children[0])
        print(f"OK — fresh ParentClient, set_child to {client.children[0].name}")
    else:
        print("OK — fresh Client")
    print()

    print("=== STEP 5: client.lessons(today-7, today+14) — EDT sensor + Calendar entity (TIME-02, CAL-01/02) ===")
    try:
        lessons = list(client.lessons(date_from=j_minus_7, date_to=j_plus_14))
        print(f"OK — got {len(lessons)} lessons")
        if lessons:
            print("--- first lesson shape ---")
            print(json.dumps(_summarise(lessons[0]), indent=2, default=str))
            print()
            print("--- pronotepy.Lesson attribute distribution (across all returned lessons) ---")
            sample = lessons[0]
            for attr in sorted(a for a in dir(sample) if not a.startswith("_")):
                try:
                    v = getattr(sample, attr)
                except Exception as e:  # noqa: BLE001
                    print(f"  {attr}: <getattr error: {type(e).__name__}>")
                    continue
                if callable(v):
                    continue
                # Sample 5 lessons to see range of values
                values = []
                for ls in lessons[:5]:
                    try:
                        values.append(str(getattr(ls, attr))[:40])
                    except Exception as e:  # noqa: BLE001
                        values.append(f"<err:{type(e).__name__}>")
                print(f"  {attr}: {values}")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 6: client.current_period.grades — Grade sensor (GRADE-01..03) ===")
    try:
        period = client.current_period
        print(f"period type: {type(period).__name__}")
        print(json.dumps(_summarise(period, max_attrs=20), indent=2, default=str))
        print()
        try:
            grades = list(period.grades)
            print(f"OK — got {len(grades)} grades")
            if grades:
                print("--- first grade shape ---")
                print(json.dumps(_summarise(grades[0]), indent=2, default=str))
        except (KeyError, AttributeError) as e:
            # 02-02 spike documented this — pronotepy may raise KeyError 'listeDevoirs'
            # when current_period is truthy but .grades hits a missing key
            print(f"period.grades raised {type(e).__name__}: {e}")
            print("(this matches 02-02 spike finding — handle as 'no grades available')")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 7: client.information_and_surveys() — Notifications sensor (NOTIF-01/02) ===")
    try:
        infos = list(client.information_and_surveys())
        print(f"OK — got {len(infos)} information items")
        if infos:
            print("--- first information shape ---")
            print(json.dumps(_summarise(infos[0]), indent=2, default=str))
            print()
            # Sample read/unread distribution
            unread = sum(1 for i in infos if not getattr(i, "read", True))
            print(f"--- read/unread distribution: {len(infos) - unread} read / {unread} unread ---")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 8: client.menus(today, today+7) — optional Cantine sensor (out of scope v1) ===")
    try:
        menus = list(client.menus(date_from=today, date_to=today + timedelta(days=7)))
        print(f"OK — got {len(menus)} menu entries")
        if menus:
            print("--- first menu shape ---")
            print(json.dumps(_summarise(menus[0]), indent=2, default=str))
    except Exception as e:  # noqa: BLE001
        print(f"INFO: menus probe raised {type(e).__name__}: {e} (out of scope v1)")
    print()

    print("=== STEP 9: client.periods — period list for grades sensor multi-period ===")
    try:
        periods = client.periods
        print(f"OK — got {len(periods)} periods")
        print(f"--- period names: {[getattr(p, 'name', '?') for p in periods]} ---")
        if periods:
            print("--- first period shape ---")
            print(json.dumps(_summarise(periods[0], max_attrs=15), indent=2, default=str))
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 10: cancellation/modification signal — Lesson.canceled / .status / .detention ===")
    # Phase 4 GOAL hinges on detecting "cours annulé" vs "modifié" reliably.
    # Plan 02-02 spike captured fixture pairs but documented byte-identical
    # T0/T1 cases (see tests/test_diff/test_lessons.py SKIPPED entries).
    # Live probe across ~21 days of lessons to see real signal distribution.
    try:
        lessons = list(client.lessons(date_from=j_minus_7, date_to=j_plus_14))
        if lessons:
            sample = lessons[0]
            candidate_signals = [
                a
                for a in dir(sample)
                if a
                in {
                    "canceled",
                    "cancelled",
                    "status",
                    "outing",
                    "exempted",
                    "test",
                    "detention",
                    "memo",
                    "background_color",
                }
            ]
            print(f"candidate signal attrs on Lesson: {candidate_signals}")
            print()
            # Distribution
            for attr in candidate_signals:
                vals = [str(getattr(ls, attr, None))[:30] for ls in lessons]
                from collections import Counter

                dist = Counter(vals).most_common(5)
                print(f"  {attr}: top values {dist}")
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()

    print("=== STEP 11: client.info — needed for AUTH-07 DeviceInfo refinement (Phase 4 device.model) ===")
    try:
        info = client.info
        print(json.dumps(_summarise(info), indent=2, default=str))
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {type(e).__name__}: {e}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
