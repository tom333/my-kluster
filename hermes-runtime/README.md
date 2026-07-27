# hermes-runtime — artefacts Hermes versionnés (PVC, pas GitOps)

Hermes charge ces fichiers depuis son **PVC** (`hermes-agent-data` / `hermes-agent-files`),
pas depuis Git : ArgoCD ne les applique donc pas. Ils sont versionnés ici pour survivre
à un wipe de PVC et garder l'historique, et **`hermes-state` fait la réconciliation**
dans les deux sens.

| Fichier ici | Destination dans le pod |
|---|---|
| `SOUL.md` | `/opt/data/SOUL.md` — **TOUJOURS chargé** (indépendant du cwd et de git) → c'est ICI que vivent les garde-fous d'exécution. `HERMES.md` seul ne suffit PAS : il « remonte jusqu'à la racine git » et `/workspace` n'est pas un dépôt git, donc il n'était jamais injecté. |
| `HERMES.md` | `/workspace/HERMES.md` **et** `/workspace/AGENTS.md` — *context file* injecté dans le system prompt à chaque session (priorité `.hermes.md`/`HERMES.md` > `AGENTS.md` > `CLAUDE.md`). |
| `skills/eval-modeles.SKILL.md` | `/opt/data/skills/eval-modeles/SKILL.md` |
| `skills/decouvertes.SKILL.md` | `/opt/data/skills/decouvertes/SKILL.md` |
| `skills/web-fetch.SKILL.md` | `/opt/data/skills/web-fetch/SKILL.md` |
| `skills/veille-digest/` | `/opt/data/skills/veille-digest/` (répertoire : `SKILL.md` + `references/`) |
| **`state/jobs.json`** | `/opt/data/cron/jobs.json` — **GÉNÉRÉ, ne pas éditer** (voir plus bas) |

## Réappliquer après un rebuild

```bash
cd scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py diff          # voir l'écart
uv run --quiet --with pyyaml python hermes_state.py apply --yes   # écrire dans le pod
```

L'outil gère pour toi le `chown 10000:10000` (⚠️ `kubectl exec` tourne en **root**, l'agent
en **uid 10000** : un fichier non chowné est invisible pour l'agent, **sans aucune erreur**),
les doubles destinations (`HERMES.md` + `AGENTS.md`), l'écriture atomique et la relecture de
vérification. Il **refuse** d'écrire les artefacts que Hermes possède.

Détails : `scripts/hermes-state/README.md`.

## `state/` est GÉNÉRÉ — sens de lecture inversé

`state/jobs.json` porte les **8 tâches planifiées** (~12 900 caractères de consignes). Ce
fichier va du **pod vers Git**, jamais l'inverse :

- **Pour modifier un cron** → passe par le dashboard Hermes. Un cron d'export le capture
  chaque nuit à 03:25 et commit uniquement si la définition a changé.
- **Ne l'édite pas à la main** : le prochain `export` écrasera tes changements.
- `apply` **refuse** cet artefact (`owner: hermes` dans le manifeste). C'est volontaire :
  une commande mal tapée ne peut pas détruire un cron édité au dashboard.

Ce fichier ne contient que la **définition** : les champs de statut (`last_run_at`,
`next_run_at`, `repeat.completed`…) sont écartés à la capture, sinon un commit
apparaîtrait chaque nuit sans changement réel.

⚠️ Le `chat_id` Telegram y figure en clair. Ce n'est pas un secret dans ce dépôt — il est
déjà présent dans plusieurs scripts committés — mais garde-le en tête si ce dépôt devient
public un jour.
