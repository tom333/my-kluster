# eval-harness — batterie d'éval modèles LocalAI (P1)

Harness **déterministe** pour comparer objectivement un modèle candidat au modèle
courant (baseline). Brique P1 du pipeline d'auto-déploiement de modèles (cf.
`docs/superpowers/` + mémoire). **Pas de LLM-juge** (biais) : scoring programmatique.

## Catégories

| Catégorie | Scoring | Tâches |
|---|---|---|
| **coding** | tests unitaires exécutés en **sandbox docker `--network none`** (pass/fail) | `tasks/coding.jsonl` |
| **toolcall** | validation du `tool_calls` (nom + args requis, sélection d'outil) | `tasks/toolcall.jsonl` |
| **format** | validateurs (`equals`, `regex`, `json_keys`) | `tasks/format.jsonl` |
| **reasoning** | problèmes chiffrés, réponse numérique exacte (`ANSWER: <n>`) | `tasks/reasoning.jsonl` |
| **perf** | tok/s moyen (usage/latence) | mesuré en continu |

`overall` = moyenne des 4 taux de réussite. Ajouter des tâches = éditer les `.jsonl`.

## Usage

```bash
cd scripts/eval-harness
# baseline (modèle courant)
uv run run_eval.py --model ornith-1.0-9b-mtp --tag baseline
# candidat + comparaison au baseline
uv run run_eval.py --model <candidat> --tag candidate --compare-to ornith-1.0-9b-mtp
```

Env : `LOCALAI_URL` (défaut `https://localai.tgu.ovh/v1`), `LOCALAI_KEY` (ou
`~/.config/brain/localai-key`), `MLFLOW_TRACKING_URI` (défaut `https://mlflow.tgu.ovh`).

Résultats loggés dans MLflow, expérience **`localai-model-eval`** (params, métriques,
artefact `results.json`). Compare candidat vs baseline par requête MLflow.

## Principes (le modèle courant orchestre, ne juge pas)

- Le modèle courant **lance** ce script ; le scoring est **programmatique** (déterministe).
- Exec de code isolée : docker `--network none`, mémoire/CPU/ulimit bornés.
  ⚠️ P1 = tâches curées bénignes. Avant usage AUTO/non-curé, durcir (déjà `--network none`,
  read-only mount, ulimit cpu) — considérer un runner k8s Job dédié.
- **Effet plafond** : si le baseline sature (100% partout), le harness ne discrimine
  plus → ajouter des tâches plus dures pour garder du headroom.

## Roadmap pipeline (P1 = ce harness)
P2 staging candidat (API LocalAI) · P3 PR auto my-kluster · P4 déclencheur veille ·
P5 backend versionné + auto-update. Tous **PR-gated** (jamais d'auto-merge).

## Pipeline automation (P3-P5)

Le PR est le **gate humain** — jamais d'auto-merge.

- **P3 `promote.sh --candidate <n>`** : gate (overall Δ ≥ marge ET pas de régression tool-call) → si gagnant, PR my-kluster (add candidat + remove incumbent + résumé). `--dry-run`.
- **P4 `eval-pipeline.sh --name <n> --gguf <url>`** : chaîne stage+éval → gate+PR → notify Telegram → cleanup. `poll-candidates.sh` traite la file `~/.config/brain/model-candidates.queue` (**on-demand** : chaque candidat = 1 restart LocalAI, pas de cron aveugle). Veille → ajoute des candidats à la file (format `name|gguf|[draft]|[ctx]`).
- **P5 `backend-watch.sh`** : alerte Telegram si nouveau backend cuda12-llama-cpp sur quay (cron pc quotidien). Maj = **manuelle gatée** par le harness (auto-update reporté : risque + backend pas déclaratif git).
