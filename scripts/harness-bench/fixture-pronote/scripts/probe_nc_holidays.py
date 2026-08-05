#!/usr/bin/env python3
"""C-03 — Probe holidays.France(subdiv='NC') 2026 dates.

Usage:
    uv run --with holidays==0.97 python scripts/probe_nc_holidays.py

Captures the 12 expected 2026 NC fériés (11 metropolitan + 1 NC-specific
Fête de la Citoyenneté 24/09). Output is captured into
tests/fixtures/synthetic/PHASE-5-PROBE-NOTES.md as Task 3 of Plan 05-02.

If Fête de la Citoyenneté (24/09/2026) is absent from the output, the
holidays library regressed NC support — populate
custom_components/ha_pronote/const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT with
frozenset({date(2026, 9, 24)}) and document in PHASE-5-PROBE-NOTES.md.
The helper module `custom_components/ha_pronote/holiday_dates.py` already
unions the library output with NC_LOCAL_HOLIDAYS_SUPPLEMENT at runtime, so
the supplement override is the documented escape hatch.

Exits 0 on success, 1 if the NC-specific date is missing.
"""

from __future__ import annotations

from datetime import date
import sys

import holidays


def main() -> int:
    """Probe and print. Return non-zero on missing NC-specific date."""
    nc_holidays = holidays.France(subdiv="NC", years=2026)
    rows = sorted(nc_holidays.items())  # type: ignore[arg-type]

    print(f"# holidays.France(subdiv='NC', years=2026) — {len(rows)} dates")
    print()
    for d, name in rows:
        print(f"{d.isoformat()}  {name}")
    print()
    print(f"Total dates: {len(rows)}")

    # Critical assertion: Fête de la Citoyenneté (NC-specific, 24/09)
    if date(2026, 9, 24) not in nc_holidays:
        print(
            "\nERROR: 24/09/2026 (Fête de la Citoyenneté) NOT in holidays output. "
            "Populate const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
