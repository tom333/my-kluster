# Planning Archive (historical)

This directory is the immutable archive of the `.planning/` tree used during the GSD (Get Shit Done) workflow that drove HA-Pronote through v0.1.0-pre.

## What's here

| Path | What it is |
|------|-----------|
| `ROADMAP.md` | Phase list, success criteria, requirement mapping. Phases 1–6 complete, Phase 7 deferred to root-level `BACKLOG.md`. |
| `REQUIREMENTS.md` | v1 / v2 requirements catalogue + traceability matrix mapping each REQ-ID → phase. |
| `STATE.md` | Project state machine (current focus, last activity, decisions log). Frozen at Phase 6 completion. |
| `PROJECT.md` | Project rationale, core value, constraints, tech stack notes. |
| `config.json` | GSD workflow toggles for this project. |
| `phases/01-*` … `phases/06-*` | Per-phase artifacts: CONTEXT (decisions), RESEARCH (technical investigation), PATTERNS (analog files), PLAN (executable task breakdown), SUMMARY (what shipped), VERIFICATION (goal-backward audit), LEARNINGS (decisions/lessons/patterns/surprises). |

## Why archived

The project migrated from GSD to superpowers conventions on 2026-05-30 after Phase 6 shipped. New work uses lightweight skills (brainstorming → writing-plans → executing-plans → systematic-debugging → verification-before-completion). Active backlog lives at the repo root `BACKLOG.md`.

## What to do with this

- **Read** to understand the "why" behind any shipped decision. Each phase's CONTEXT.md + LEARNINGS.md is the institutional memory.
- **Don't edit.** This archive is the historical record. If a decision needs updating, capture the new decision in the current workflow's artifacts (commits, ADRs, or backlog notes).
- **Reference in commits / PRs** when reverting or revisiting a phase-era choice: `see docs/history/planning/phases/03-coordinator-first-sensor/03-CONTEXT.md D-07` is a valid citation.

## Cross-cutting reference points

- **`unique_id` format** (Phase 3 D-05): `{url_host.lower()}:{username}:{child_identifier}` — frozen forever; entity history depends on it
- **Single auth seam** (Phase 3 C-02): `api/client.py:build_or_resume_client` — fresh + token_login path, four-arm typed exception surface
- **No-silent-exceptions rule** (Phase 3 feedback): runtime/setup paths propagate raw; config-flow form errors are the scoped exception (D-04 mapping via `_map_error`)
- **Phase 6 critical gotchas** locked by permanent CI guards in `tests/test_init.py`:
  - No `entry.add_update_listener` in production (`OptionsFlowWithReload` replaces it)
  - No `vol.Strip` (doesn't exist in voluptuous; use `lambda v: v.strip()`)
  - No `OptionsFlow.__init__(config_entry)` assignment (HA injects `self.config_entry` as read-only property since 2025.12)
