# Phase 1: Foundations & Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 1-Foundations & Skeleton
**Areas discussed:** Domain identifier, Python/HA floor, Release workflow, Repo identity

---

## Domain identifier

Question asked: *Quel `domain` mettre dans manifest.json ?*

| Option | Description | Selected |
|--------|-------------|----------|
| `ha_pronote` (Recommended) | Aligne DIST-09 (zip naming `custom_components/ha_pronote/`), zéro collision avec delphiki/hass-pronote (qui utilise `pronote`), nom du repo cohérent. Inconvénient : entity_ids un peu longs. | ✓ |
| `pronote` | Plus court (`sensor.pronote_alice_lessons`). Mais delphiki/hass-pronote utilise déjà `pronote` — un user qui a tenté delphiki ne peut pas installer le nôtre sans wipe complet de `.storage`. Bloque la migration. | |
| `pronote_nc` | Suffixe NC signale le scope (ac-noumea.nc), zéro collision. Inconvénient : exclut symboliquement les users hors-NC qui voudraient adopter (même si techniquement ça marche partout). | |

**User's choice:** `ha_pronote` (Recommended)
**Notes:** Décision irréversible après première install réelle (entity_ids + .storage). Note importante : `unique_id` (ENT-02) reste `pronote_{child}_{kind}` — indépendant du domain — pour garder les entity_ids courts côté user.

---

## Python/HA floor

Question asked: *Quel plancher Python / HA cibler pour la v1 ?*

| Option | Description | Selected |
|--------|-------------|----------|
| HA 2026.4+ / Py 3.14.2 (Recommended) | Recommandé par CLAUDE.md/STACK.md. Aligne sur HA Core master + blueprint moderne. Ruff `target-version=py314`. Exclut HA 2026.1–2026.2 et 2025.x. | ✓ |
| HA 2026.1+ / Py 3.13.2 | Couvre les users non encore migrés vers 2026.3+. Mais ces versions atteignent EOL mid-2026. Maintenir 3.13 + 3.14 en parallèle ajoute complexité. | |
| HA 2025.12+ / Py 3.12 | Plus large adoption. Mais STACK.md flag explicitement comme anti-pattern : "self-inflicted wound, users on 2026.x will not install you". | |

**User's choice:** HA 2026.4+ / Py 3.14.2 (Recommended)
**Notes:** Implique : `pyproject.toml:requires-python = ">=3.14.2"`, `[tool.ruff] target-version = "py314"`, `hacs.json:homeassistant = "2026.4.0"`, mise à jour de `.python-version` (`3.10` → `3.14`). Tradeoff de coverage utilisateur explicitement accepté.

---

## Release workflow

Question asked: *Quel pattern de release CI utiliser pour automatiser version + zip HACS ?*

| Option | Description | Selected |
|--------|-------------|----------|
| Manuel + zip (delphiki) (Recommended) | Tag GitHub manuel → workflow `release.yml` qui injecte `tag_name` dans `manifest.json:version`, zip `custom_components/ha_pronote/`, attache au GitHub Release. ~30 lignes. Pattern delphiki éprouvé. | ✓ |
| release-please (Google) | Full automation : conventional commits → release-please ouvre PR de release auto avec CHANGELOG. Plus puissant mais courbe d'apprentissage et discipline conventional-commits stricte. | |

**User's choice:** Manuel + zip (delphiki) (Recommended)
**Notes:** Migration vers release-please reste une option v2+ si la cadence de release le justifie. DIST-09 satisfait. Conventional Commits encouragés mais non-obligatoires.

---

## Repo identity

Question asked: *GitHub handle + URL repo (réponse en texte libre)*

**User's response:** `@tom333`, `https://github.com/tom333/ha-pronote`

**Derived values (locked) :**
- `manifest.json:codeowners = ["@tom333"]`
- `manifest.json:documentation = "https://github.com/tom333/ha-pronote"`
- `manifest.json:issue_tracker = "https://github.com/tom333/ha-pronote/issues"`
- Repo name : `ha-pronote` (hyphen) sur GitHub
- Folder/integration domain : `ha_pronote` (underscore) — accepté, HACS gère le mapping

**Notes:** Le real name (`Thomas Guyader`) n'est PAS mis dans `codeowners` (ce champ attend des GitHub handles uniquement). Il vit dans `git config user.name` + `LICENSE`/`README.md` si shipped.

---

## Claude's Discretion

User selected "Laisser le planner décider" pour 3 sous-décisions :

1. **Test scaffolding scope** — recommandation : full `pytest-homeassistant-custom-component` setup dès Phase 1 (pas seulement smoke test) pour zéro friction Phase 2. Décision finale au planner.
2. **Dev container** — recommandation : ship un `.devcontainer/devcontainer.json` minimal du blueprint `jpawlowski` (HA dev container + uv). Coût ~30 lignes, rend success criteria #1 reproductible.
3. **Pre-commit hooks** — recommandation : `.pre-commit-config.yaml` avec `prek` (ruff format → ruff check --fix → pyright → codespell). Mêmes hooks que CI, fail fast en local.

Voir CONTEXT.md `<decisions>` § "Claude's Discretion" (C-01, C-02, C-03) pour les recommandations détaillées.

## Deferred Ideas

Voir CONTEXT.md `<deferred>` pour la liste complète. Highlights :

- Daily cron CI vs `pronotepy@main` (DIST-04) → Phase 7
- Migration vers `release-please` → v2+
- Soumission brand assets à `home-assistant/brands` → v2+
- Soumission HACS default repository → v2+
- HA Quality Scale Silver/Gold → v2
- README full content → Phase 7 (DIST-07)
- Translations → Phase 7 (I18N-01, I18N-02)
- Renovate/Dependabot pour SHA-pinned actions → v2+
- Compat HA 2026.1–2026.2 / Py 3.13 → explicitement hors scope (D-11)
