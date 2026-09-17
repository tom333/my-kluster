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
| Secrets de flux (`SECRET_TELEGRAM_TOKEN`, `SECRET_LOCALAI_API_KEY`, `SECRET_MINIFLUX_TOKEN`, `SECRET_GITHUB_TOKEN`, `SECRET_TXTAI_TOKEN` — valeurs en base64) | `sealed/kestra-flow-secrets.yaml` |
| Base `kestra`, rôle `kestra` | PostgreSQL partagé `postgresql.datalab` — **créés à la main** le 2026-09-16 (`ALTER DATABASE template1 REFRESH COLLATION VERSION` a été nécessaire : glibc 2.36 → 2.43) |
| UI | `https://kestra.tgu.ovh` (LAN), `admin@tgu.ovh`, mot de passe dans `~/.config/kestra/admin-password` |

Le jeton Telegram est celui du bot Hermes : `sendMessage` seul, pas de polling,
donc aucun conflit avec la passerelle.

## Architecture des flux

- **`digest`** (générique) : non-lus d'une catégorie Miniflux → **un** appel gemma
  selon la consigne du thème → Telegram (découpé ≤ 3 800 car.) → **txtai** (un
  document par bloc, `source='veille'`, `job=<catégorie>`, `allowFailure`) → marquer lu.
  Sentinelle `RIEN_DE_NEUF` = silence sur vide (entrées quand même marquées lues,
  rien d'indexé).
- **`watcher`** (générique) : script Python du dépôt tiré à l'exécution, état en KV,
  stdout non vide = alerte Telegram.
- Un **mini-flux par job** porte le cron et la consigne, et appelle le générique
  (`Subflow`). Ajouter un thème = une catégorie Miniflux + un fichier de 25 lignes.

## Flux (transposition des 12 crons Hermes, 2026-09-16)

| flux Kestra | catégorie Miniflux | cron (UTC) | remplace le cron Hermes |
|---|---|---|---|
| `korben` | korben | `30 9 * * *` | Résumé Korben soir (`e8c4b8c91103`) |
| `decouvertes` | decouvertes | `0 9 * * *` | decouvertes-quotidienne (`2ee2afd955cb`) |
| `data-ia` | data-ia | `0 10 * * *` | veille-data-ia-quotidienne (`a03a6a8792b2`) |
| `llm-local` | llm-local | `30 21 * * *` | llm-veille-daily (`a6bd90e76dfa`) |
| `harnais-agents` | harnais-agents | `0 22 * * 3` | harnais-et-agents-veille (`3f1c9a2b7d84`) |
| `3d-assets` | 3d-assets | `0 6 * * *` | veille-3d-assets (`7c4e1b9a2f60`) |
| `arr` | arr | `30 10 * * 6` | Veille écosystème *arr (`89e560928622`) |
| `emploi-nc` | — (14 pages HTML, KV) | `0 20 * * *` | job-scraper-data-ia (`a38355a79f36`) |
| `bonsai-watch` | — (script, KV) | `15 8,20 * * *` | bonsai-backend-watch (`7ebbddc10caa`) |
| `k2horizon-watch` | — (script, KV) | `45 8,20 * * *` | k2horizon-watch (`b7c3e1a4f902`) |
| `moe-cache-watch` | — (script, KV) | `0 9,21 * * *` | moe-cache-watch (`42a01f72da31`) |
| *(intégré à `digest`)* | tâche `indexer` | à chaque digest | digest-indexer (`d1965700c0de`) — indexait les digests Hermes dans txtai toutes les heures ; la dédup vit dans Miniflux, l'indexation suit l'envoi |

Ce qui n'est plus couvert par rapport aux prompts Hermes : le statut du cluster *arr via
le MCP arrconf, et le contrôle API Hugging Face (`context_length`, template d'outils)
des candidats GGUF — deux appels d'outil que le pipeline ne fait pas. À réintroduire
comme tâches `http.Request` si le besoin se confirme.

Les **flux RSS s'ajoutent dans l'UI Miniflux** (Feeds → Add feed, ou import OPML) dans
la catégorie du thème ; aucun changement côté Kestra. 60 flux amorcés le 2026-09-16
(releases GitHub, topics et trending via RSSHub, hnrss, HF papers, console.dev,
Product Hunt, Reddit, duckdb.org, 80.lv). Reddit limite à 429 sur les ajouts en rafale :
r/blender, r/gamedev, r/sonarr restent à ajouter à la main.

## Points d'API utiles (Kestra 2.0.2, vérifiés)

Le payload de `GET /api/v1/main/executions/{id}` **ne porte plus les sorties**.
- Sorties d'une tâche : `GET /api/v1/main/outputs/tasks/{executionId}/{taskRunId}`
- Sorties du flux : `GET /api/v1/main/outputs/executions/{executionId}`
- Évaluer une expression dans le contexte d'une tâche (« Debug Outputs ») :
  `POST /api/v1/main/executions/{executionId}/actions/eval/{taskRunId}` (corps : l'expression)
- Valider un flux avant push : `POST /api/v1/main/flows/validate` (YAML)
- Le paramètre `minLevel` de `/logs/{executionId}` est ignoré : filtrer côté client.
- OpenAPI : `/swagger/kestra.yml`.

## Leçons du premier run (2026-09-16)

- gemma-4 via LocalAI raisonne par défaut : `max_tokens: 2048` partaient
  entièrement en `reasoning`, `content` vide → Telegram `message text is empty`.
  `reasoning_effort: "none"` règle le problème (20 s, digest complet).
- Le venv Python de l'image n'a ni `pip` ni `ensurepip` : scripts en stdlib.
- `options.timeout` du client HTTP : `connectTimeout` + `readIdleTimeout` seulement
  en 2.0.2 ; le défaut de lecture est de 10 s.
- **Limite de message de la file : 1 Mo** (`kestra.queue.message-protection.limit`).
  Une sortie de tâche plus grosse (ex. `http.Request` sur 100 entrées Miniflux avec
  leur HTML = 1,9 Mo) fait échouer l'exécution **sans tâche en échec** (l'erreur est
  dans les logs : `MessageTooBigException`, puis `Unable to find prepare`). data-ia et
  llm-local ont raté leur 1er run planifié pour ça (16/09). Parade : `http.Download`
  → `outputs.uri` (stockage interne) consommé via `inputFiles`, et ne tirer que
  `max_entrees`.
