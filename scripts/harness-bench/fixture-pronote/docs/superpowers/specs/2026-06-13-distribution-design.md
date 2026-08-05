# Distribution Sub-Spec — Design

**Date:** 2026-06-13
**Phase 7 items:** DIST-04 (daily upstream canary), DIST-07 (README rewrite), DIST-09 (release verification)
**Goal:** Make v0.1.0 cleanly HACS-installable with accurate docs and early warning on `pronotepy` upstream drift.

## Context

Survey of existing state (2026-06-13):

- **DIST-09 (release workflow) — already implemented.** `.github/workflows/release.yml` triggers on `release: published`, injects the tag into `manifest.json` (`yq`, strips leading `v`), zips `custom_components/ha_pronote/` → `ha_pronote.zip`, uploads to the release. `hacs.json` declares `zip_release: true` + `filename: ha_pronote.zip`. Alpha tags `v0.1.0-alpha.5..9` already shipping. → Verification pass only.
- **DIST-04 (anti-regression CI) — missing.** No scheduled/cron workflow exists. New work.
- **DIST-07 (README) — stale + buggy.** Current `README.md` claims "installs but does not yet create entities" (false), "account configuration via the UI ships in a future release" (false), links the archived `.planning/ROADMAP.md` (broken), and uses the wrong repo URL `tom333/ha-pronote` (hyphen) vs manifest `tom333/ha_pronote` (underscore). Full rewrite.

**Decisions locked during brainstorming:**
- Scope = DIST-04 + DIST-07; DIST-09 = verification only.
- DIST-04 cadence = daily; on failure open a **deduplicated** issue (label `pronotepy-upstream`).
- DIST-04 runs the **full** test suite against `pronotepy@<default-branch>`.
- README = **comprehensive** (BACKLOG criterion #5) and **French** (consistent with the French-only decision).

**Technical insight (shapes DIST-04 value):** most tests mock pronotepy at the `build_or_resume_client` seam (MagicMock), so they will NOT catch pronotepy API-shape drift. Only `tests/test_api/` (requests-mock against the real lib) + import-time / client-construction breakage are caught. The full suite still earns its keep (imports + construction + api-layer parsing); the canary is an early-warning signal, not exhaustive upstream coverage.

## Unit 1 — DIST-04: daily upstream canary

**File:** `.github/workflows/upstream-canary.yml` (new)

**Trigger:**
```yaml
on:
  schedule:
    - cron: "0 6 * * *"   # 06:00 UTC daily
  workflow_dispatch: {}    # manual run button
```

**Permissions:** `contents: read`, `issues: write` (minimum needed to open/comment issues).

**Job `canary` (ubuntu-latest, Python 3.14, uv):**
1. `actions/checkout` (SHA-pinned).
2. `actions/setup-python` 3.14 (SHA-pinned).
3. `astral-sh/setup-uv` (SHA-pinned), cache on `requirements*.txt`.
4. `uv pip install --system -r requirements_test.txt`.
5. **Override the pin:** `uv pip install --system "pronotepy @ git+https://github.com/bain3/pronotepy"` — resolves the upstream default branch HEAD (avoids guessing `main` vs `master`).
6. Print the resolved pronotepy version/commit for the log (`uv pip show pronotepy`).
7. `pytest -q` — full suite. Single TZ `Europe/Paris` (no TZ matrix — the canary targets upstream drift, not the TZ blind-spot already covered by `test.yml`).

**On failure → deduplicated issue.** A final step with `if: failure()` using `actions/github-script` (SHA-pinned):
- Search open issues with label `pronotepy-upstream`.
- If none: create issue. Title: `pronotepy upstream regression`. Body: link to the failed run (`${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`), date, and a one-line "the canary suite failed against pronotepy upstream HEAD; the `==2.14.6` pin still protects production." Apply label `pronotepy-upstream` (created on first use via `addLabels`, which auto-creates).
- If an open one exists: post a comment with the new run link + date (no duplicate issue).

**Why this shape:** the production pin (`pronotepy==2.14.6`) is unaffected — the canary only warns. Dedup keeps a single rolling issue while upstream stays broken.

## Unit 2 — DIST-07: README rewrite (French, comprehensive)

**File:** `README.md` (full replace)

Section order:
1. **Titre + pitch + badges.** One sentence on the core value (notification fiable dès qu'un cours est annulé/modifié pour aujourd'hui ou demain). CI + HACS badges.
2. **Fonctionnalités.** Sensors (cours du jour, notes, notifications), calendar (emploi du temps), 3 événements bus, polling adaptatif, lecture seule.
3. **Installation HACS** (custom repository). Correct URL `https://github.com/tom333/ha_pronote`, category Integration, restart.
4. **Configuration via l'UI.** Flow élève (URL + type + identifiants); flow parent → sélection enfant; pour ajouter un 2e enfant relancer l'ajout; mention reauth (mot de passe) + reconfigure (URL/type, `unique_id` figé).
5. **Entités exposées + tables d'attributs.**
   - `sensor.<enfant>_cours_du_jour` — état = nb cours aujourd'hui; attributs `lessons_today` / `lessons_tomorrow` (listes de leçons, schéma `Lesson.to_dict`).
   - `sensor.<enfant>_notes` — état = moyenne période; attributs `period_name`, `grades[]` (9 champs: date, subject, grade, out_of, coefficient, class_average, class_min, class_max, comment).
   - `sensor.<enfant>_notifications` — état = `unread_count`; attribut `informations[]` (info_id, title, sender, date, excerpt, read).
   - `calendar.<enfant>_emploi_du_temps`.
   - Note: ces attributs alimentent ApexCharts/Mushroom.
6. **Événements bus + automation.** `pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_notification` (payload = contexte enfant + delta). Exemple YAML copy-paste : automation `notify.mobile_app_*` sur `pronote_schedule_changed`.
7. **Exemple carte dashboard.** Snippet Mushroom ou ApexCharts lisant les attributs.
8. **Politesse / anti-ban.** Intervalles (15/30/60), fenêtre renforcée 17h–20h, heures calmes, cadence suspension; lecture seule = aucune écriture vers Pronote.
9. **Dépannage.** Repair Issues (IP suspendue / auth échec → bouton reauth), téléchargement du diagnostics dump (sans secrets).
10. **Licence.**

Removals: broken `.planning/ROADMAP.md` link; false "no entities" / "UI config future" status.

## Unit 3 — DIST-09: release verification pass

No new code unless a gap is found. Checklist:
- `release.yml` flow end-to-end: tag → GitHub release published → `ha_pronote.zip` attached → HACS consumes via `hacs.json filename`.
- Zip contents from `custom_components/ha_pronote/` include `translations/`, `diagnostics.py`, `repairs.py`, `manifest.json`, all `.py` — and no stray cruft (`__pycache__`, the zip itself).
- `manifest.json version: 0.0.1` stays as-is (injected at release time by `release.yml`).
- Record findings in the plan's SUMMARY; fix only if a real gap surfaces.

## Testing Strategy

- **Workflows are not unit-testable.** Validate YAML syntax; run `actionlint` if available locally. Verify DIST-04 via one manual `workflow_dispatch` after merge (and confirm the failure path by temporarily breaking on a throwaway branch, optional).
- **README guard (optional, recommended):** a tiny test asserting `README.md` contains no `.planning/` references and uses the `tom333/ha_pronote` (underscore) URL — locks the two bugs we just fixed.
- **No production code changes** in this sub-spec → existing 483-test suite must stay green (regression guard).

## Out of Scope

- Python 3.14+ banner, Renovate/Dependabot (deferred optional items).
- First real (non-alpha) HACS push / `v0.1.0` tag — a release action, not part of building these artifacts.
- Changing the release trigger (stays `release: published`, not tag-push).
