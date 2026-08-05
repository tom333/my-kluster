"""Neutral helper for NC fériés precomputation.

HA-free per WR-2 architectural improvement (revised plan). Lives as a sibling
module to politesse.py so coordinator.py imports from `.holiday_dates` instead
of doing a function-local import from `.` (which coupled coordinator.py to
__init__.py internals and risked a circular import).

Imports: `holidays` (the new Phase 5 runtime dep) + stdlib only. The AST guard
at tests/test_no_ha_imports.py (Plan 05-01 Task 3 extension) asserts zero
homeassistant.* imports — same invariant as politesse.py.

The function `compute_holiday_dates_for_year` is called by:
- `custom_components/ha_pronote/__init__.py:async_setup_entry` once at setup
  (via `hass.async_add_executor_job(compute_holiday_dates_for_year, year)`)
- `custom_components/ha_pronote/coordinator.py:_async_update_data` on year
  rollover (Dec 31 → Jan 1) via the same executor wrapper.

The implementation does no I/O (verified at RESEARCH §"holidays Library Import
+ Instantiation Overhead": microseconds, zero file/socket access). Executor
wrapping is policy-uniformity per CLAUDE.md "executor for any blocking work".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import holidays

from .const import NC_LOCAL_HOLIDAYS_SUPPLEMENT

if TYPE_CHECKING:
    from datetime import date


def compute_holiday_dates_for_year(year: int) -> frozenset[date]:
    """C-07 / WR-2 — extract NC fériés for `year` from holidays==0.97; union with hardcoded supplement.

    Args:
        year: Calendar year to enumerate fériés for (e.g. 2026).

    Returns:
        Frozen set of date objects covering NC fériés that year. Includes
        metropolitan + NC-local dates (Fête de la Citoyenneté 24/9) per the
        `holidays.France(subdiv='NC')` enumeration plus any hardcoded
        supplement from `const.NC_LOCAL_HOLIDAYS_SUPPLEMENT` (empty by default
        after the Plan 05-02 Task 3 HUMAN-UAT probe sign-off).

    Raises:
        ImportError: if `holidays` is not installed. Propagates raw per
            feedback_no_silent_exceptions.md (no try/except in this module).
    """
    return frozenset(holidays.France(subdiv="NC", years=year).keys()) | NC_LOCAL_HOLIDAYS_SUPPLEMENT
