# Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HA-Pronote cleanly HACS-installable: green test CI, a daily upstream-`pronotepy` canary that opens a deduplicated issue on regression, and an accurate French README — without changing production code.

**Architecture:** Five tasks. Task 1 is a prerequisite that fixes the never-green test CI (incompatible PHACC pin + missing runtime deps) — DIST-04 depends on a working test install. Task 2 adds the canary workflow. Tasks 3–4 rewrite the README and lock its two prior bugs with a guard test. Task 5 is a verification-only pass over the already-implemented release workflow (DIST-09).

**Tech Stack:** GitHub Actions (SHA-pinned), `uv`, `pytest`, `pytest-homeassistant-custom-component`, `actions/github-script`. No HA/integration runtime code changes.

**Spec:** `docs/superpowers/specs/2026-06-13-distribution-design.md`

**Key facts gathered (do not re-investigate):**
- `requirements_test.txt` pins `pytest-homeassistant-custom-component==0.13.326`, which requires `homeassistant==2026.5.0b0`, but the file also pins `homeassistant==2026.4.4` → unsatisfiable → CI install fails on every run (verified: 15/15 recent `test.yml` runs `failure`, same error since 2026-05-24).
- `uv` resolves `homeassistant==2026.4.4` together with `pytest-homeassistant-custom-component==0.13.325` (verified via dry-run).
- `manifest.json` runtime requirements: `pronotepy==2.14.6`, `python-slugify==8.0.4`, `holidays==0.97`. None are in `requirements_test.txt`; HA core does not pull them transitively. `tests/conftest.py` line 11 does `import pronotepy` at collection time, so they must be installed for pytest to even collect.
- pronotepy upstream repo: `https://github.com/bain3/pronotepy` (from installed package `Home-page` metadata).
- Bus event constants (`custom_components/ha_pronote/const.py`): `EVENT_SCHEDULE_CHANGED = "pronote_schedule_changed"`, `EVENT_NEW_GRADE = "pronote_new_grade"`, `EVENT_NEW_INFORMATION = "pronote_new_information"`.
- `schedule_changed` event payload = child context `{child_id, child_name, config_entry_id}` merged with `LessonChange.to_payload()` = `{change_type, day, lesson_date, subject, before, after}`.
- Entity IDs (French object_ids): `sensor.<child>_cours_du_jour`, `sensor.<child>_notes`, `sensor.<child>_notifications`, `calendar.<child>_emploi_du_temps`.
- Sensor attributes: cours-du-jour → `lessons_today` / `lessons_tomorrow` (lists of `Lesson.to_dict()`). notes → `period_name`, `grades[]` (9 fields: `date, subject, grade, out_of, coefficient, class_average, class_min, class_max, comment`). notifications → `unread_count`, `informations[]` (`info_id, title, sender, date, excerpt, read`).
- Existing workflows pin actions by SHA. Reuse the exact SHAs already in `.github/workflows/test.yml`:
  - `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd` (v6.0.2)
  - `actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405` (v6.2.0)
  - `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b` (v8.1.0)
  - `actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea` (v7.0.1) — NEW, verify SHA at use.

---

### Task 1: Fix the test CI dependencies (prerequisite — greens CI, unblocks DIST-04)

**Files:**
- Modify: `requirements_test.txt`

**Why:** `test.yml` has never passed. Two compounding bugs: (a) PHACC pin incompatible with the HA pin; (b) runtime deps (`pronotepy`, `python-slugify`, `holidays`) absent from the test install so pytest cannot import `pronotepy` at collection. Fix both. KISS over DRY: mirror the three manifest pins into `requirements_test.txt` with a comment rather than building a manifest-extraction step.

- [ ] **Step 1: Read the current file**

Run: `cat requirements_test.txt`
Confirm it contains `homeassistant==2026.4.4` and `pytest-homeassistant-custom-component==0.13.326`.

- [ ] **Step 2: Bump PHACC pin to the HA-2026.4.4-compatible release**

Edit `requirements_test.txt`: change `pytest-homeassistant-custom-component==0.13.326` → `pytest-homeassistant-custom-component==0.13.325`.

- [ ] **Step 3: Add the runtime deps (mirror manifest.json)**

Append to `requirements_test.txt` (after the `requests-mock` line):

```
# D-DIST: runtime deps mirrored from custom_components/ha_pronote/manifest.json.
# HA core does not pull these transitively; conftest.py imports pronotepy at
# collection time, so the test job must install them explicitly. Keep in lockstep
# with manifest.json requirements.
pronotepy==2.14.6
python-slugify==8.0.4
holidays==0.97
```

- [ ] **Step 4: Verify a clean resolve + full suite in an isolated venv**

Run:
```bash
uv venv /tmp/ci-verify --python 3.14
VIRTUAL_ENV=/tmp/ci-verify uv pip install -r requirements_test.txt
VIRTUAL_ENV=/tmp/ci-verify uv run --no-project python -c "import pronotepy, slugify, holidays; print('imports OK')"
VIRTUAL_ENV=/tmp/ci-verify uv run --no-project pytest -q
```
Expected: install succeeds (no "unsatisfiable"), `imports OK`, and `483 passed, 7 skipped` (or current count). If the isolated-venv commands are blocked by sandbox permissions, fall back to the project venv: `uv pip install -r requirements_test.txt && uv run pytest -q` and confirm the resolve prints no conflict.

- [ ] **Step 5: Commit**

```bash
git add requirements_test.txt
git commit -m "fix(ci): repair never-green test job — PHACC 0.13.325 + runtime deps

PHACC 0.13.326 requires homeassistant==2026.5.0b0, conflicting with the
pinned homeassistant==2026.4.4 → install was unsatisfiable on every run.
Pin PHACC to 0.13.325 (its HA 2026.4.4 release). Also add pronotepy,
python-slugify, holidays (manifest runtime deps) — conftest imports
pronotepy at collection and HA core does not pull them transitively."
```

---

### Task 2: DIST-04 — daily upstream-pronotepy canary workflow

**Files:**
- Create: `.github/workflows/upstream-canary.yml`

**Depends on:** Task 1 (the canary installs `requirements_test.txt` then overrides pronotepy).

- [ ] **Step 1: Write a YAML-structure test (TDD guard for the workflow)**

Create `tests/test_workflows.py`:

```python
"""Structural guards for GitHub Actions workflows (DIST-04).

These do not run the workflows — they assert the YAML declares the pieces the
design requires, so an accidental edit (wrong trigger, dropped issue step) is
caught by the test suite instead of only at 06:00 UTC.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_CANARY = Path(__file__).parent.parent / ".github" / "workflows" / "upstream-canary.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_canary_workflow_exists() -> None:
    assert _CANARY.is_file(), f"missing {_CANARY}"


def test_canary_runs_daily_and_manually() -> None:
    wf = _load(_CANARY)
    # PyYAML parses the bare `on:` key as the boolean True.
    triggers = wf.get("on") or wf.get(True)
    assert "schedule" in triggers, "canary must be scheduled"
    assert triggers["schedule"][0]["cron"] == "0 6 * * *"
    assert "workflow_dispatch" in triggers, "canary must be manually runnable"


def test_canary_can_open_issues() -> None:
    wf = _load(_CANARY)
    assert wf["permissions"]["issues"] == "write"


def test_canary_overrides_pronotepy_from_git() -> None:
    raw = _CANARY.read_text(encoding="utf-8")
    assert "git+https://github.com/bain3/pronotepy" in raw
    assert "requirements_test.txt" in raw  # installs the pinned base first


def test_canary_opens_deduplicated_issue_on_failure() -> None:
    raw = _CANARY.read_text(encoding="utf-8")
    assert "if: failure()" in raw
    assert "pronotepy-upstream" in raw  # the dedup label
    assert "actions/github-script" in raw
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_workflows.py -q`
Expected: FAIL — `missing .../upstream-canary.yml`.

- [ ] **Step 3: Create the workflow**

Create `.github/workflows/upstream-canary.yml`:

```yaml
name: Upstream canary

# Early warning when pronotepy's upstream HEAD breaks our suite. The production
# pin (pronotepy==2.14.6) is unaffected — this job only warns.
on:
  schedule:
    - cron: "0 6 * * *"   # 06:00 UTC daily
  workflow_dispatch: {}

permissions:
  contents: read
  issues: write

jobs:
  canary:
    name: Tests vs pronotepy@HEAD
    runs-on: ubuntu-latest
    env:
      TZ: Europe/Paris   # single TZ — this job targets upstream drift, not the TZ matrix
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "requirements*.txt"

      - name: Install pinned test deps
        run: uv pip install --system -r requirements_test.txt

      - name: Override pronotepy with upstream HEAD
        run: |
          uv pip install --system "pronotepy @ git+https://github.com/bain3/pronotepy"
          echo "Resolved pronotepy:"
          uv pip show pronotepy | grep -E "^(Name|Version|Location):"

      - name: Run full suite
        run: pytest -q

      - name: Open or update regression issue
        if: failure()
        uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea  # v7.0.1
        with:
          script: |
            const label = "pronotepy-upstream";
            const runUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            const body = [
              "The daily canary suite failed against **pronotepy upstream HEAD**.",
              "",
              `Run: ${runUrl}`,
              "",
              "The production pin (`pronotepy==2.14.6`) still protects installed users —",
              "this is an early warning that upstream has drifted. Investigate before",
              "the next pronotepy bump.",
            ].join("\n");

            const existing = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: "open",
              labels: label,
            });

            if (existing.data.length > 0) {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: existing.data[0].number,
                body: `Canary still failing. ${runUrl}`,
              });
            } else {
              await github.rest.issues.create({
                owner: context.repo.owner,
                repo: context.repo.repo,
                title: "pronotepy upstream regression",
                body,
                labels: [label],
              });
            }
```

- [ ] **Step 4: Run the structural test to verify it passes**

Run: `uv run pytest tests/test_workflows.py -q`
Expected: PASS (5 tests). If `yaml` import fails, it is provided transitively by `pytest-homeassistant-custom-component` (PyYAML) — confirm with `uv run python -c "import yaml"`.

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `uv run pytest -q`
Expected: previous count + 5 new = e.g. `488 passed, 7 skipped`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/upstream-canary.yml tests/test_workflows.py
git commit -m "feat(dist): daily pronotepy upstream canary with dedup issue (DIST-04)"
```

---

### Task 3: DIST-07 — rewrite README (French, comprehensive)

**Files:**
- Modify: `README.md` (full replace)

**Why:** Current README is factually wrong (claims no entities / no UI config), links the archived `.planning/ROADMAP.md`, and uses the wrong repo URL `tom333/ha-pronote` (hyphen) instead of `tom333/ha_pronote` (underscore).

- [ ] **Step 1: Replace the file with the full French content**

Overwrite `README.md` with:

````markdown
# HA-Pronote

Intégration Home Assistant **non officielle** pour [Pronote](https://www.index-education.com/fr/logiciel-gestion-vie-scolaire.php), le logiciel de vie scolaire des établissements français.

> **Valeur principale :** recevoir une notification fiable dès qu'un cours est **annulé ou modifié** pour aujourd'hui ou demain — notes et informations en découlent.

[![Test](https://github.com/tom333/ha_pronote/actions/workflows/test.yml/badge.svg)](https://github.com/tom333/ha_pronote/actions/workflows/test.yml)
[![HACS](https://github.com/tom333/ha_pronote/actions/workflows/validate.yml/badge.svg)](https://github.com/tom333/ha_pronote/actions/workflows/validate.yml)

## Fonctionnalités

- **Capteurs** par enfant : cours du jour, notes, notifications (informations & sondages).
- **Calendrier** : emploi du temps exposé comme entité `calendar`.
- **Événements** sur le bus HA : changement d'emploi du temps, nouvelle note, nouvelle information — pour vos automatisations.
- **Polling poli** : intervalle réglable, surveillance renforcée 17h–20h les soirs d'école, heures calmes la nuit — pour éviter le bannissement IP du serveur de l'école.
- **Lecture seule** : aucune écriture vers Pronote.

## Installation (HACS — dépôt personnalisé)

1. Ouvrez HACS dans Home Assistant.
2. **Intégrations** → menu en haut à droite → **Dépôts personnalisés**.
3. Ajoutez `https://github.com/tom333/ha_pronote` avec la catégorie **Integration**.
4. Installez **HA-Pronote** depuis le catalogue HACS.
5. Redémarrez Home Assistant.

## Configuration (via l'interface)

1. **Paramètres → Appareils et services → Ajouter une intégration → HA-Pronote**.
2. Saisissez :
   - **URL de votre espace Pronote** — l'URL complète, par ex. `https://0123456a.index-education.net/pronote/eleve.html`.
   - **Type de compte** — `eleve` (compte élève) ou `parent` (portail parent).
   - **Identifiant** et **Mot de passe** Pronote.
3. **Compte parent multi-enfants** : un écran de sélection s'affiche. Choisissez l'enfant à ajouter. Pour en suivre un second, relancez l'ajout d'intégration et choisissez l'autre enfant.

Deux opérations de maintenance sont disponibles depuis la fiche de l'intégration :
- **Ré-authentification** — si Pronote rejette vos identifiants (mot de passe changé), un bouton « Reconfigurer » relance la saisie du mot de passe.
- **Reconfiguration** — modifier l'URL ou le type de compte sans perdre l'historique des entités (l'identifiant interne reste figé).

## Entités exposées

Pour un enfant nommé « Jean Dupont », les entités sont préfixées `jean_dupont` :

| Entité | État | Attributs principaux |
|--------|------|----------------------|
| `sensor.jean_dupont_cours_du_jour` | nombre de cours aujourd'hui | `lessons_today`, `lessons_tomorrow` |
| `sensor.jean_dupont_notes` | moyenne générale de la période | `period_name`, `grades` |
| `sensor.jean_dupont_notifications` | nombre d'informations non lues | `unread_count`, `informations` |
| `calendar.jean_dupont_emploi_du_temps` | cours en cours / à venir | (entité calendrier standard) |

### Schéma des attributs (pour ApexCharts / Mushroom)

`lessons_today` / `lessons_tomorrow` — liste de cours :

```json
{
  "date": "2026-06-15",
  "start": "2026-06-15T08:00:00+02:00",
  "end": "2026-06-15T09:00:00+02:00",
  "subject": "Mathématiques",
  "teacher": "Mme A",
  "classroom": "101",
  "canceled": false,
  "status": ""
}
```

`grades` — liste de notes (9 champs) :

```json
{
  "date": "2026-05-10",
  "subject": "Mathématiques",
  "grade": 15.0,
  "out_of": 20.0,
  "coefficient": 2.0,
  "class_average": 13.0,
  "class_min": 8.0,
  "class_max": 18.0,
  "comment": ""
}
```

`informations` — liste d'informations :

```json
{
  "info_id": "abc123",
  "title": "Réunion parents-professeurs",
  "sender": "Direction",
  "date": "2026-05-12T10:00:00+02:00",
  "excerpt": "…",
  "read": false
}
```

## Événements et automatisations

Trois événements sont émis sur le bus Home Assistant. Chacun porte un contexte enfant (`child_id`, `child_name`, `config_entry_id`) plus des champs spécifiques.

| Événement | Émis quand | Champs spécifiques |
|-----------|-----------|--------------------|
| `pronote_schedule_changed` | un cours d'aujourd'hui ou demain est ajouté / annulé / modifié | `change_type`, `day`, `lesson_date`, `subject`, `before`, `after` |
| `pronote_new_grade` | une nouvelle note apparaît | champs de la note (cf. schéma `grades`) |
| `pronote_new_information` | une nouvelle information arrive | champs de l'information (cf. schéma `informations`) |

### Exemple : notification mobile sur changement d'emploi du temps

```yaml
automation:
  - alias: "Pronote — cours modifié"
    trigger:
      - platform: event
        event_type: pronote_schedule_changed
    action:
      - service: notify.mobile_app_mon_telephone
        data:
          title: "Emploi du temps modifié — {{ trigger.event.data.child_name }}"
          message: >
            {{ trigger.event.data.subject }} ({{ trigger.event.data.day }},
            {{ trigger.event.data.lesson_date }}) :
            {{ trigger.event.data.change_type }}.
```

### Exemple : carte dashboard (Mushroom template)

```yaml
type: custom:mushroom-template-card
primary: Cours du jour — {{ state_attr('sensor.jean_dupont_cours_du_jour','friendly_name') }}
secondary: >
  {{ states('sensor.jean_dupont_cours_du_jour') }} cours aujourd'hui
icon: mdi:school
```

## Politesse du polling (anti-bannissement)

Le serveur Pronote de l'école peut bannir une IP qui l'interroge trop souvent. L'intégration limite donc ses requêtes :

- **Intervalle de rafraîchissement** réglable (15 / 30 / 60 min, défaut 30).
- **Surveillance renforcée 17h–20h** les soirs d'école — c'est là qu'arrivent les changements pour le lendemain.
- **Heures calmes** la nuit et **cadence réduite** les week-ends / vacances.

Tous ces réglages sont dans **Options** de l'intégration. L'intégration est en **lecture seule** : elle n'écrit jamais vers Pronote.

## Dépannage

- **« Pronote a suspendu votre adresse IP »** (carte de réparation HA) — augmentez l'intervalle de polling dans les Options, puis patientez.
- **« Pronote a rejeté vos identifiants »** (carte de réparation HA) — cliquez sur **Reconfigurer** pour ressaisir votre mot de passe.
- **Diagnostic** — depuis la fiche de l'intégration, **Télécharger les diagnostics** produit un export sans secret (mot de passe, identifiant, jeton et URL d'établissement sont expurgés).

## Licence

Voir [LICENSE](LICENSE).
````

- [ ] **Step 2: Sanity-check rendering + links**

Run: `grep -n ".planning" README.md || echo "no .planning refs"` → expect `no .planning refs`.
Run: `grep -n "ha-pronote" README.md || echo "no hyphen url"` → expect `no hyphen url` (only `ha_pronote`).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(dist): rewrite README in French — install, entities, events, polling (DIST-07)"
```

---

### Task 4: README guard test

**Files:**
- Create: `tests/test_readme.py`

**Why:** Lock the two bugs we just fixed (broken `.planning/` link, wrong hyphenated URL) so they cannot silently return.

- [ ] **Step 1: Write the failing test**

Create `tests/test_readme.py`:

```python
"""Guards locking the two README bugs fixed in DIST-07."""

from __future__ import annotations

from pathlib import Path

_README = Path(__file__).parent.parent / "README.md"


def test_readme_exists() -> None:
    assert _README.is_file()


def test_readme_has_no_archived_planning_links() -> None:
    text = _README.read_text(encoding="utf-8")
    assert ".planning/" not in text, "README links the archived .planning/ tree"


def test_readme_uses_underscore_repo_url() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "tom333/ha-pronote" not in text, "wrong hyphenated repo URL"
    assert "tom333/ha_pronote" in text, "missing correct repo URL"


def test_readme_documents_schedule_event() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "pronote_schedule_changed" in text
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_readme.py -q`
Expected: PASS (4 tests) — the README was already fixed in Task 3. (If any fail, the README content is wrong; fix `README.md`, not the test.)

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: previous count + 4 = e.g. `492 passed, 7 skipped`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_readme.py
git commit -m "test(dist): guard README against .planning links + hyphen URL regressions"
```

---

### Task 5: DIST-09 — release workflow verification pass (no build unless gap found)

**Files:**
- Read-only: `.github/workflows/release.yml`, `hacs.json`, `custom_components/ha_pronote/manifest.json`
- (Conditional) Modify only if a real gap surfaces.

**Why:** `release.yml` already exists and ships alpha zips. Confirm it produces a HACS-consumable artifact with the new files (`diagnostics.py`, `repairs.py`, `translations/`) and no cruft.

- [ ] **Step 1: Dry-run the zip exactly as the workflow does, into a temp dir**

Run:
```bash
cd custom_components/ha_pronote
zip -r /tmp/ha_pronote_verify.zip ./ -x '*.pyc' -x '*__pycache__*'
cd -
unzip -l /tmp/ha_pronote_verify.zip
```
Note: the real workflow runs `zip ha_pronote.zip -r ./` on a clean CI checkout (no `__pycache__`). The `-x` flags here only protect a local dirty tree.

- [ ] **Step 2: Assert the artifact contains the required files**

Confirm the `unzip -l` listing includes: `manifest.json`, `__init__.py`, `config_flow.py`, `coordinator.py`, `sensor.py`, `calendar.py`, `diagnostics.py`, `repairs.py`, `const.py`, `strings.json`, and `translations/en.json` + `translations/fr.json`. Confirm it does **not** include `__pycache__/`, `*.pyc`, or a nested `ha_pronote.zip`.

- [ ] **Step 3: Confirm the HACS contract**

Run: `cat hacs.json` — confirm `"zip_release": true` and `"filename": "ha_pronote.zip"`.
Run: `grep -n '"version"' custom_components/ha_pronote/manifest.json` — confirm `"0.0.1"` (injected at release time by `release.yml`; left as-is).

- [ ] **Step 4: Record the verification result**

Append a short "DIST-09 verification" note to the plan's execution summary (or `BACKLOG.md`) stating: release.yml verified end-to-end (tag → release published → `ha_pronote.zip` built from `custom_components/ha_pronote/` → uploaded → HACS consumes `filename`); artifact contains the new diagnostics/repairs/translations files; no cruft. **Only if a gap was found** (e.g. cruft in the zip), open a follow-up — do not silently patch `release.yml` without surfacing it.

- [ ] **Step 5: Commit (only if Step 4 changed a tracked file)**

```bash
git add BACKLOG.md
git commit -m "docs(dist): record DIST-09 release-workflow verification"
```

---

## Self-Review

**Spec coverage:**
- DIST-04 (daily canary, dedup issue, full suite, `pronotepy@HEAD`) → Task 2. ✅
- DIST-07 (French comprehensive README) → Task 3. ✅
- DIST-09 (release verification) → Task 5. ✅
- Prerequisite not in spec but discovered during planning (never-green CI) → Task 1. ✅ (DIST-04 cannot pass without it.)
- README guard (spec "optional, recommended") → Task 4. ✅

**Placeholder scan:** No TBD/TODO/"handle errors". Workflow YAML, README, and tests are complete and literal.

**Type/name consistency:** Event names (`pronote_schedule_changed`, `pronote_new_grade`, `pronote_new_information`), entity IDs (`cours_du_jour`, `notes`, `notifications`, `emploi_du_temps`), label `pronotepy-upstream`, PHACC `0.13.325`, and the SHA-pinned actions are used identically across tasks. Test file paths (`tests/test_workflows.py`, `tests/test_readme.py`) are distinct and created once.

**Note on `actions/github-script` SHA:** verify `60a0d83039c74a4aee543508d2ffcb1c3799cdea` (v7.0.1) at implementation time; if stale, pin the current v7 release SHA.
