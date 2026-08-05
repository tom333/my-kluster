#!/usr/bin/env python3
"""WR-5 — Recursive key-tree equality between en.json and fr.json.

Walks both translation dicts and asserts identical dotted-path sets. Catches
the case where a Phase 7 i18n change adds a key to one file but forgets the
other. Top-level-only equality (the original acceptance check) does NOT catch
nested drift.

Exits 0 on parity, 1 on mismatch with a sorted diff.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

EN = Path("custom_components/ha_pronote/translations/en.json")
FR = Path("custom_components/ha_pronote/translations/fr.json")


def walk(d: object, prefix: str = "") -> set[str]:
    """Return the set of dotted key paths in `d` (recursive)."""
    out: set[str] = set()
    if isinstance(d, dict):
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            out.add(path)
            out |= walk(v, path)
    return out


def main() -> int:
    en = json.loads(EN.read_text())
    fr = json.loads(FR.read_text())
    ek = walk(en)
    fk = walk(fr)
    missing_in_fr = ek - fk
    missing_in_en = fk - ek
    if missing_in_fr or missing_in_en:
        print("WR-5 recursive key-tree mismatch:", file=sys.stderr)
        print(f"  missing in fr.json: {sorted(missing_in_fr)}", file=sys.stderr)
        print(f"  missing in en.json: {sorted(missing_in_en)}", file=sys.stderr)
        return 1
    print(f"WR-5 OK: en.json and fr.json have identical recursive key trees ({len(ek)} paths each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
