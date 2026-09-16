# Flux Kestra — veille

Ce répertoire est la **source de vérité** des flux Kestra : le flux d'amorçage
`system.sync-from-git` (déclaré dans `argocd/argocd-apps/kestra-app.yaml`, chargé
au démarrage via `--flow-path /flows`) le synchronise toutes les 10 minutes avec
`io.kestra.plugin.git.SyncFlows`, `delete: true`. **Un flux édité dans l'UI est
écrasé au sync suivant.** On édite ici, on commite, on attend dix minutes — ou on
lance `system.sync-from-git` à la main depuis l'UI.

## Pourquoi (POC du 2026-09-16)

La veille tournait comme crons Hermes : une boucle d'agent à ~30 outils par run.
Mesuré sur un mois (181 sessions) : 20 % des appels d'outils servaient à *chercher*
les outils (`tool_search` + `tool_describe`), `read_file`/`search_files` fouillaient
`/opt/data`, et la mise à jour d'image v2026.9.14 (rejeu des `reasoning_details`
vers DeepSeek) a fait boucler 4 jobs sur 4 le même jour. Une veille est un
pipeline : **collecte déterministe → dédup → un appel LLM → Telegram**. C'est la
chaîne que la communauté emploie (n8n/Kestra + RSSHub + lecteur RSS) ; Kestra est
retenu pour ses flux **YAML versionnés en git**.

Hermes garde le chat Telegram. Voir `PASSATION`/notes dans `hermes-runtime/`.

## Conventions

- Un fichier par flux, `namespace: veille`, id = sujet (`korben`, …).
- Aucun secret dans les flux : `{{ secret('TELEGRAM_TOKEN') }}`,
  `{{ secret('LOCALAI_API_KEY') }}` — variables `SECRET_*` du SealedSecret
  `kestra-flow-secrets` (valeurs **base64**, convention Kestra).
- Python via `io.kestra.plugin.core.runner.Process` dans le conteneur standalone
  (pas de docker-in-docker) ; dépendances installées dans un venv par
  `beforeCommands`.
- LLM : LocalAI en cluster (`localai.localai.svc.cluster.local:8080`), modèle
  `gemma-4-12b-it-qat`, **un** appel par run, texte brut (rien à échapper pour
  Telegram).
- État « déjà vu » : KV store du namespace (`<sujet>_vus`, liste JSON bornée),
  écrit **après** l'envoi — un envoi raté rejoue les items au run suivant.
- Silence sur vide : pas de message « rien de neuf ».

## Infrastructure (hors de ce répertoire)

| pièce | où |
|---|---|
| App ArgoCD, chart `kestra/kestra` 2.0.2, valeurs | `argocd/argocd-apps/kestra-app.yaml` |
| Middleware Traefik `lan-only` (ns `kestra`) | `config/traefik-middlewares.yaml` |
| Secret config (mot de passe Postgres, basic-auth UI) | `sealed/kestra-config.yaml` |
| Secrets de flux (`SECRET_TELEGRAM_TOKEN`, `SECRET_LOCALAI_API_KEY`) | `sealed/kestra-flow-secrets.yaml` |
| Base `kestra`, rôle `kestra` | PostgreSQL partagé `postgresql.datalab` — **créés à la main** le 2026-09-16 (`ALTER DATABASE template1 REFRESH COLLATION VERSION` a été nécessaire : glibc 2.36 → 2.43) |
| UI | `https://kestra.tgu.ovh` (LAN), `admin@tgu.ovh`, mot de passe dans `~/.config/kestra/admin-password` |

Le jeton Telegram est celui du bot Hermes : `sendMessage` seul, pas de polling,
donc aucun conflit avec la passerelle.

## Flux

| flux | remplace | déclencheur |
|---|---|---|
| `veille/korben.yaml` | cron Hermes « Résumé Korben soir » (`e8c4b8c91103`) | `30 9 * * *` UTC (20:30 NC) |
