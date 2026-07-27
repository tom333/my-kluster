# hermes-state — réconciliation Git ↔ PVC de la configuration Hermes

Conception : `docs/superpowers/specs/2026-07-27-hermes-state-design.md`

## Pourquoi

Hermes possède son état et le réécrit à chaud. Le dépôt veut que Git soit la vérité.
Plutôt que de trancher globalement, `manifest.yaml` déclare la propriété **artefact
par artefact** :

- `owner: git` → Git fait foi, `apply` écrase le pod.
- `owner: hermes` → le pod fait foi, `export` capture vers Git, **`apply` n'y touche jamais**.

Conséquence pratique : tu continues d'éditer tes crons dans le dashboard, où c'est
ergonomique, et Git les capture tout seul chaque nuit.

## Usage

```bash
cd scripts/hermes-state

# observer — ne modifie rien. Code retour 1 s'il existe une dérive.
uv run --quiet --with pyyaml python hermes_state.py diff

# capturer l'état possédé par Hermes (jobs.json)
uv run --quiet --with pyyaml python hermes_state.py export

# amorçage : capturer aussi les artefacts owner=git encore absents de Git
uv run --quiet --with pyyaml python hermes_state.py export --adopt

# appliquer Git -> pod (dry-run tant que --yes est absent)
uv run --quiet --with pyyaml python hermes_state.py apply --only soul --yes
```

Le cron nocturne passe par `run-export.sh`, qui notifie Telegram **uniquement en cas
d'échec** : le silence signifie « tout va bien », jamais « le cron est mort ».

## Tests

```bash
cd scripts/hermes-state
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Rien n'est installé sur le poste : `uv` monte un environnement éphémère. Le
`sys.path` est géré une fois pour toutes par `tests/conftest.py`.

## Ce qui a été appris à ses dépens

**Un champ « volatil » n'est pas inerte.** Pendant la mise au point, écrire
`next_run_at` dans le passé sur les 8 tâches a fait **déclencher les 8 crons** par
l'ordonnanceur — 5 agents LLM lancés hors horaire et autant de messages Telegram
parasites. Ce champ est *lu* pour décider quoi lancer avant d'être réécrit. C'est
exactement pourquoi l'outil, lui, refuse d'écrire un artefact `owner: hermes`.

**Un compteur peut se cacher dans un champ de définition.** `repeat` décrit la
répétition voulue (`times`), mais Hermes y range aussi `completed`, incrémenté à
chaque exécution. Sans son retrait (`VOLATILE_NESTED_FIELDS`), le cron aurait
committé chaque nuit sans changement réel. Ce défaut était **invisible en test sur
fixture** : il n'est apparu qu'après un vrai tour d'ordonnanceur.

## ⚠️ Le piège uid 10000

`kubectl exec` tourne en **root**, l'agent Hermes tourne en **uid 10000**. Un fichier
écrit sans `chown 10000:10000` est **invisible pour l'agent, sans aucune erreur**.
`podio.write()` écrit en atomique, chown, puis **relit pour vérifier**. Ne contourne
jamais ce chemin.

## `hermes-runtime/state/` est GÉNÉRÉ

Ne l'édite pas à la main : le prochain `export` écrasera tes changements. Pour
changer un cron, passe par le dashboard Hermes ; `export` le capturera.

## Structure

| Fichier | Responsabilité |
|---|---|
| `manifest.yaml` | Déclare la propriété des 11 artefacts. Source unique. |
| `normalize.py` | Fonctions **pures** : normalisation, comparaison, chargement du manifeste. N'importe ni `podio` ni `hermes_state`. |
| `podio.py` | Transport `kubectl`. Exécuteur injectable → tout le protocole est testable sans cluster. |
| `gitio.py` | Commit automatique et ses garde-fous (rebase/branche, `add` restreint, jamais de `--force`). |
| `hermes_state.py` | CLI : `diff`, `export`, `apply`. |
| `run-export.sh` | Enveloppe du cron, notifie ses échecs. |
