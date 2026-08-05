# Phase 5 Probe Notes — `holidays.France(subdiv='NC')` 2026

**Captured:** 2026-05-25
**Source:** Local execution of `scripts/probe_nc_holidays.py` against `holidays==0.97`
**Command:** `uv run --with holidays==0.97 python scripts/probe_nc_holidays.py`
**Exit code:** 0
**Library version:** holidays==0.97 (PyPI, released 2026-05-18)

Locks the NC férié set surfaced by the Phase 5 runtime dep (`holidays==0.97`) for
the 2026 school year. Future `holidays` upgrades or PyPI yanks are detected when
this notes file's content drifts from a fresh probe re-run. Plan 05-02 (D-02 /
C-03) ships this fixture as the project-locked validation point — the
RESEARCH.md source-level verification already happened at planning time, but
this is the verbatim runtime evidence.

---

## STEP A — Verbatim probe stdout

The output below is the unmodified stdout of `python scripts/probe_nc_holidays.py`
(exit code 0). Sorted by date ascending.

```
# holidays.France(subdiv='NC', years=2026) — 12 dates

2026-01-01  Jour de l'an
2026-04-06  Lundi de Pâques
2026-05-01  Fête du Travail
2026-05-08  Fête de la Victoire
2026-05-14  Ascension
2026-05-25  Lundi de Pentecôte
2026-07-14  Fête nationale
2026-08-15  Assomption
2026-09-24  Fête de la Citoyenneté
2026-11-01  Toussaint
2026-11-11  Armistice
2026-12-25  Noël

Total dates: 12
```

---

## STEP B — Baseline expectation from RESEARCH.md §"NC Fériés 2026"

RESEARCH.md table (verified source-level against `holidays/countries/france.py`
dev master 2026-05-25 — see `france.py` lines 70 + 287-298) predicts exactly 12
dates for `holidays.France(subdiv='NC', years=2026)`:

| Date | Name | Source line in `france.py` |
|------|------|----------------------------|
| 01/01/2026 | Jour de l'an | line 117-118 (`year >= 1811`) |
| 06/04/2026 | Lundi de Pâques | line 122-123 (movable, computed) |
| 01/05/2026 | Fête du Travail | line 137-138 |
| 08/05/2026 | Fête de la Victoire | line 152-154 (`year >= 1982`) |
| 14/05/2026 | Ascension | line 156-157 (movable) |
| 25/05/2026 | Lundi de Pentecôte | line 126-128 (movable, except 2005-2007) |
| 14/07/2026 | Fête nationale | line 160-162 (`year >= 1880`) |
| 15/08/2026 | Assomption | line 164-165 |
| **24/09/2026** | **Fête de la Citoyenneté** (NC-specific) | line 287-298 |
| 01/11/2026 | Toussaint | line 167-168 |
| 11/11/2026 | Armistice | line 170-173 (`year >= 1922`) |
| 25/12/2026 | Noël | line 175-176 |

---

## STEP C — Diff vs baseline

| Aspect | Expected (RESEARCH.md) | Observed (probe stdout) | Verdict |
|--------|------------------------|-------------------------|---------|
| Total date count | 12 | 12 | MATCH |
| Set membership | 11 metropolitan + 1 NC-specific (24/09) | Same | MATCH |
| Fête de la Citoyenneté 24/09 present | YES | YES | MATCH |
| Saint Vincent de Paul 06/12 present | NO (not a NC civil férié) | NO | MATCH (correct absence) |
| Probe exit code | 0 | 0 | MATCH |

**Result: zero discrepancies.** `NC_LOCAL_HOLIDAYS_SUPPLEMENT = frozenset()` per
const.py is confirmed correct — no supplement dates needed.

If a future probe re-run surfaces a missing date, the documented escape hatch
is to populate `custom_components/ha_pronote/const.py:NC_LOCAL_HOLIDAYS_SUPPLEMENT`
with the missing `date(...)` literal. The
`custom_components/ha_pronote/holiday_dates.py` helper already unions the
library output with the supplement (`return frozenset(holidays.France(...).keys())
| NC_LOCAL_HOLIDAYS_SUPPLEMENT`), so the supplement override is the
forward-compatible repair path — NO override of the library output is needed.

---

## STEP D — HUMAN-UAT Sign-off

**Per AUTO_MODE active, Plan 05-02 Task 3 auto-approves on probe exit==0 + zero
diff vs baseline. The orchestrator will respawn the executor with
`user_response = "approved"` after this checkpoint is acknowledged.**

| Field | Value |
|-------|-------|
| Date | 2026-05-25 |
| Decision | LGTM — 12 dates match RESEARCH.md baseline exactly |
| Notes | Auto-approved under AUTO_MODE (see Plan 05-02 frontmatter `autonomous: false` but executor was launched with `--auto`). `NC_LOCAL_HOLIDAYS_SUPPLEMENT` stays `frozenset()` empty. Fixture re-runs annually (Dec/Jan) when `NC_VACATION_RANGES_2026` is hand-updated to `NC_VACATION_RANGES_<year>`. |
| Reviewer | (auto-approved — orchestrator) |
