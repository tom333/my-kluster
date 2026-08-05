# Plan 04-03 Summary — Heavy-Class Fixture + Probe Capture

**Completed:** 2026-05-24
**Wave:** 1
**Requirements:** TIME-03, GRADE-03
**Status:** complete

## What shipped

### Task 1 — Heavy-class fixture (auto)
- **`tests/fixtures/synthetic/_gen_heavy_class.py`** — deterministic generator (D-16). Uses Phase 4-extended `Snapshot`/`Grade` dataclasses so JSON shape stays in sync with the model. Run from repo root: `python tests/fixtures/synthetic/_gen_heavy_class.py`.
- **`tests/fixtures/synthetic/heavy_class.json`** — committed output:
  - **128 lessons** (16 weekdays × 8 slots over J−7..J+14)
  - **100 grades** distributed across 6 subjects, with `class_average / class_min / class_max / comment` populated
  - **30 informations** with 500-char excerpts (stresses Phase 2's excerpt cap)
  - `overall_average="14,50"`, `period_name="Trimestre 2"`
- **Round-trip verified**: `Snapshot.from_dict(heavy_class.json)` passes with 128/100/30 counts.
- Commits: `e93bf3e` (generator + JSON + probe template) and `659a730` (filled probe notes).

### Task 2 — Probe-first capture (human-action, resolved)
- **Probe run**: `scripts/probe_config_flow.py` executed against author's live NC Pronote instance (parent account, child `GUYADER Sacha`, class `504`).
- **Output**: `/tmp/phase4-probe.log` (439 lines) — STEPS 1–11 all returned cleanly.
- **`tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md`** — filled with verified field shapes and sign-off.

## Probe-derived findings (route to downstream plans)

### Verified clean
- **Lesson surface (STEP 5)**: 79 lessons returned; `canceled` is `bool` (7 True / 72 False), `status` is `str | None` (`None` is the common case — 67/79), `teacher_name` is `str`, `classroom` is `str`. Phase 2's `_lesson_from_raw` mappings are correct.
- **canceled vs status divergence**: 7 lessons canceled, only 4 with `status="Cours annulé"`. **Validates diff_lessons priority chain** (`canceled > room > teacher > modified`) — using `status` as a content signal would have produced false-positive "modified" events.
- **Information surface (STEP 7)**: 8 items returned; `id`, `author`, `read` (bool), `start_date` / `creation_date` (datetime) all present. `title` can be `None`. Phase 2's `_info_from_raw` is correct.
- **Period.name (STEP 6)**: `"Trimestre 2"` — matches CONTEXT.md assumption.

### Not live-verified (acceptable per Phase 2 precedent)
- **`Period.grades` and `Period.overall_average`** both raise `KeyError('listeDevoirs')` / `KeyError('listeServices')` on this NC instance for both T1 and T2 (no published grades — the author's child has 44 evaluations recorded but no calculated averages yet). **Phase 4's `fetcher.fetch_all` already handles this** via the `except (KeyError, AttributeError)` block: `raw_grades=[]`, `overall_avg=""`, `period_name=""`. Grades sensor state will become `None` (HA "unknown") on this account until grades are published — documented in CONTEXT.md `<specifics>`.
- **`Grade.average / .max / .min / .comment`** field names verified from pronotepy 2.14.6 source (`pronotepy/dataClasses.py` line 675), NOT from live probe (grades raised KeyError). Plan 04-02's `_grade_from_raw` uses `getattr(raw, "average", None) or ""` defensively — correct pattern even if the live shape can't exercise it on this instance.

### ⚠ Plan 04-04 revision needed (ENT-01)
- **`client.info.class_name = ""`** on the NC **parent** account (the parent has no class).
- **`client.children[0].class_name = "504"`** ← the child's class lives here.
- `set_child(client.children[0])` does NOT swap `client.info` to the child.
- **Plan 04-04 entity.py implementation must be ParentClient-aware**:
  ```python
  if isinstance(client, pronotepy.ParentClient):
      class_label = getattr(client.children[child_index], CLASS_LEVEL_ATTR, None)
  else:
      class_label = getattr(client.info, CLASS_LEVEL_ATTR, None)
  ```
- This will be surfaced as an explicit constraint when the 04-04 executor is spawned. The plan text itself is preserved (audit trail).

### Latent bug to track for follow-up (not blocking)
- In `fetcher.fetch_all`'s grades-fetch try block, if `.grades` succeeds but `.overall_average` raises independently (different Pronote build), the `except (KeyError, AttributeError)` block resets `raw_grades=[]`, losing the fetched grades. On the NC instance this is hypothetical — both raise on the same call so we hit the except cleanly. Worth fixing in Phase 5 or a Phase 4 follow-up via per-attribute try/except.

## Files modified

- `tests/fixtures/synthetic/_gen_heavy_class.py` (new)
- `tests/fixtures/synthetic/heavy_class.json` (new, 77 KB)
- `tests/fixtures/synthetic/PHASE-4-PROBE-NOTES.md` (new, 148 lines)

## Self-Check

- [x] Generator committed and runnable from repo root
- [x] heavy_class.json round-trips via `Snapshot.from_dict` (128 lessons, 100 grades, 30 infos)
- [x] heavy_class.json contains `overall_average: "14,50"` and `period_name: "Trimestre 2"`
- [x] PHASE-4-PROBE-NOTES.md has STEP 5, 6, 7, 9, 11 sections filled
- [x] Sign-off section completed (one item flagged with revision for Plan 04-04)
- [x] No modifications to STATE.md, ROADMAP.md, or production code

**Done.**
