# llm-bench

Compare deux endpoints OpenAI-compat sur le workload cron-agent NC
(tool-calling, gros system prompt, long contexte browser_snapshot).

Mesure **bout-en-bout tel que déployé** (stack HTTP incluse) :

| métrique | sens |
|---|---|
| `decode tok/s` | vitesse génération — le chiffre headline |
| `prefill tok/s` | coût d'avaler le prompt (~46k tok en S3) |
| `TTFT` | latence ressentie (dominée par le prefill ici) |
| `tool_ok %` | `tool_calls` émis en JSON valide avec la bonne fonction (S1/S3) |

Quand le serveur renvoie un bloc `timings` (llama-server / ik_llama.cpp), ses
tok/s mesurés serveur priment sur le calcul client. LocalAI le strip en général
→ calcul client (`tokens / temps`).

## Scénarios (fixtures synthétiques)

- **S1** — tool-call court (météo) : decode + validité JSON tool_call
- **S2** — system prompt ~16k, réponse simple : stress prefill
- **S3** — ~16k system + ~30k browser_snapshot + tool-call : le vrai cas cron

Séquentiel, single-stream. `--runs N` (run 1 = warmup, droppé ; médiane du reste).

## Lancer

```bash
# 1) Prod LocalAII (depuis le LAN, whitelist ingress)
export LOCALAI_API_KEY=<api-key>      # secret localai-api-key
./bench.py --endpoint localai --out localai.json

# 2) Option B — llama-server ik_llama.cpp CUDA buildé sur le host
./bench.py --endpoint optionb --optionb-url http://<host>:8080/v1 --out optionb.json

# 3) Les deux d'un coup (si les deux endpoints sont joignables)
./bench.py --endpoint both --runs 5 --out results.json
```

Overrides utiles : `--scenario S1,S3`, `--localai-model`, `--optionb-model`,
`--timeout` (S3 peut être long au premier prefill 46k).

## Historique reproductible (comparer des configs dans le temps)

Reproductibilité assurée par : scénarios fixes (fixtures synthétiques versionnées ici),
warmup droppé + médiane, single-stream, **seed pinné** (`--seed`, défaut 42 → longueur de
sortie stable entre runs), et **`git_sha`** enregistré (relie chaque mesure à l'état du repo).

`--history <fichier.jsonl>` **append** une ligne par (endpoint, scénario) — jamais d'écrasement :

```bash
export LOCALAI_API_KEY=...
# bencher UN modèle précis sur la prod, décode propre via S2 (sans tools)
./bench.py --endpoint localai --localai-model gemma-4-26b-a4b-heretic --scenario S2 \
  --runs 5 --history history.jsonl --note "heretic UD-Q4_K_XL fit+ot THREADS4"

# après un changement de config (ex: retrait override_tensor, THREADS=5), re-bencher :
./bench.py --endpoint localai --localai-model gemma-4-26b-a4b-heretic --scenario S2 \
  --runs 5 --history history.jsonl --note "heretic fit-only THREADS5"
```

Chaque ligne JSONL : `ts, git_sha, note, seed, endpoint, model, scenario, decode_tps,
prefill_tps, ttft_s, prompt/completion_tokens, tool_ok_rate, n_ok`.

Lire / comparer l'historique (jq) :

```bash
# tableau decode par (modèle, note, date)
jq -r '[.ts[5:16], .model, .note, (.decode_tps|tostring)] | @tsv' history.jsonl | column -t

# évolution decode d'un modèle
jq -r 'select(.model=="gemma-4-26b-a4b-heretic" and .scenario=="S2")
       | [.ts[5:16], .note, .decode_tps] | @tsv' history.jsonl | column -t
```

⚠️ Comparer des lignes de **même scénario** (S2 = décode propre sans tools). Le débit
absolu varie avec la charge cluster → toujours ≥3 runs (médiane) et noter la contention.

## Findings (baseline LocalAI qwen3-8b, RTX 3060)

Mesuré 2026-06-05, 2 runs médiane (warmup droppé) :

| scé | total s | prefill tok/s | decode tok/s | tool_ok | prompt tok |
|---|---|---|---|---|---|
| S1 (tool court) | 3.4 | — | — | 100% | 174 |
| S2 (16k sys) | 15.1* | 1517 | **84** | — | 12695 |
| S3 (34k + tool) | 37.9 | ~895† | — | 100% | 33882 |

\* un run à 19s (contention cluster) ; médiane.
† prefill S3 sous-estimé : voir buffering tools ci-dessous. Métrique honnête S3 = **total wall-clock**.

Trois trouvailles à connaître avant d'interpréter :

1. **YaRN non actif** : `values.yaml` déclare `context_size: 65536` (rope_scaling yarn) mais
   le serveur plafonne à **40960** (natif). Toute requête >40960 tok → `HTTP 500
   "exceeds available context size"`. Donc le 8b prod **ne peut PAS** traiter les vrais
   contextes cron ~46-55k. Option B (Qwen3.6, 131072 natif) les avale → avantage capacité
   décisif, indépendant de la vitesse. *(Bug conf à traiter à part, hors bench.)*

2. **Buffering tools** : quand `tools` est passé, LocalAI bufferise toute la complétion et
   la renvoie groupée en fin de stream (pour parser les tool_calls) → `TTFT == total`,
   split prefill/decode impossible côté client. Sur scénarios tool (S1/S3) : seuls
   **latence totale** + **tool_ok** sont fiables. Le decode tok/s propre vient de S2 (sans tools).

3. **decode tok/s headline = 84** (qwen3-8b Q4_K_M, S2). C'est le chiffre à comparer au
   decode d'Option B (où llama-server renvoie un bloc `timings` → decode propre même avec tools).

## Notes équité

- Sampling par reco modèle (8b temp 0.7, 35b temp 0.6) — n'affecte pas la vitesse.
- `max_tokens` capé par scénario → counts decode comparables.
- On compare LocalAI-gRPC-wrapper vs llama-server-raw : **voulu**, c'est le path
  prod réel de chacun. Pour un plafond decode décorrélé du HTTP : `llama-bench` brut
  côté Option B en complément.
