# Déployer un MoE A3B/A4B sur LocalAI (nœud RTX 3060 12 GB)

> Objectif : faire tourner un modèle Mixture-of-Experts (savoir d'un gros modèle,
> vitesse de ses ~3-4B actifs) sur le nœud RTX 3060 12 GB, via **offload des experts
> MoE en RAM** + attention/couches denses sur GPU.
>
> **Bonne nouvelle : le backend `llama-cpp` déjà installé (`cuda12-llama-cpp`) suffit.**
> Pas besoin de builder ik_llama.cpp pour une première version qui marche. ik_llama
> reste une optim (+~20 %) documentée en fin de page.

## Preuve terrain (même carte que nous)

r/LocalLLaMA, user **Skyline34rGt**, **RTX 3060 12 GB**, LM Studio (= llama.cpp
mainline), full GPU offload + **offload MoE** :

| Modèle (q4_k_m) | Débit |
|---|---|
| Qwen3.5-35B-A3B | **> 35 tok/s** |
| gemma-4-26B-A4B | **> 30 tok/s** |

> ⚠️ **RAM : il faut ~48 GB.** Il le dit explicitement : 16 GB insuffisant (taille
> modèle + système). Notre nœud a 62 GB → OK, **mais voir « Contrainte chart » :
> le pod est aujourd'hui limité à 16Gi.**

LM Studio n'utilise PAS ik_llama.cpp — juste llama.cpp mainline avec l'offload MoE.
Donc reproductible avec notre backend actuel.

## Pourquoi MoE pour notre workload

Crons agent (Hermes Agent, job-hunt NC), tool-calling répété, contexte long.
MoE A3B/A4B = qualité d'un 26-35B au prix-vitesse d'un 3-4B actif.

| Modèle | Vitesse 3060 | « Cerveau » | Tool-call | Notes |
|---|---|---|---|---|
| qwen3-8b (**prod actuelle**) | ~50 tok/s | 8B dense | ✅ mature | baseline |
| gemma-4-12B (dense) | ~30 tok/s | ~26B-ish | ⚠️ day-1 | 128k natif, vision |
| **Qwen3.6-35B-A3B** | ~35-65 tok/s | 35B MoE | ✅ Qwen agent | MTP dispo |
| **gemma-4-26B-A4B** | ~30 tok/s | 26B MoE | ⚠️ day-1 | vision (mmproj) |

## Shortlist datée (vérifiée 2026-06-05)

Tailles q4_k_m réelles (HF). Tout tient en RAM (62 GB) ; les petits ≤14 GB débordent
à peine → quasi full-GPU. Classé pour notre usage agent (tool-calling = priorité).

| Modèle | Actif | q4_k_m | Offload RAM | Tool-call | Vision | Source |
|---|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B** ⭐ défaut | 3B | 18.6 GB | ~7 GB | ✅✅ Qwen agent | ✅ mmproj | byteshape / ggml-org / unsloth |
| Qwen3.5-28B-A3B-REAP | 3B | 17.3 GB | ~6 GB | ✅✅ | — | mradermacher (élagué) |
| gemma-4-26B-A4B | 4B | 17.0 GB | ~6 GB | ⚠️ day-1 | ✅✅ natif | unsloth / ggml-org / bartowski |
| LiquidAI LFM2-24B-A2B | **2B** | 14.4 GB | ~3 GB | ⚠️ peu prouvé agent | — | LiquidAI / bartowski |
| gemma-4-19B-A4B-REAP | 4B | **12.3 GB** | ~1 GB | ⚠️ day-1 | possible | mradermacher (élagué) |

**Choix par défaut : `Qwen3.6-35B-A3B`** — meilleur tool-calling (critique pour les
crons agent), prouvé sur 3060, source fiable, MTP dispo. Les variantes **REAP**
(experts élagués → plus petites, **même vitesse car actif inchangé**) et **LiquidAI
A2B** sont des optims de *taille/vitesse*, pas de « cerveau » — à réserver aux tâches
non-agent.

État génération (2026-06-05) : **rien de plus récent en GGUF** que Qwen3.6 / gemma-4
(pas de Qwen3.7 / Qwen3-Next / gemma-5). Le watcher `~/bin/moe-watch.py` (RETIRÉ le 2026-07-27, voir section dédiée)
préviendra quand une nouvelle gen débarquera.

## Candidats (GGUF de confiance, vérifiés)

### Qwen3.6-35B-A3B
- Repo MTP : `byteshape/Qwen3.6-35B-A3B-MTP-GGUF` (têtes drafter incluses → MTP)
- `Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf` = **18.61 GB** (≈ qualité Q4_K_XL), + `mmproj-bf16.gguf` (0.9 GB, vision)
- Sans MTP : `byteshape/Qwen3.6-35B-A3B-GGUF` ou autre q4_k_m
- Format chat : ChatML (`<|im_start|>` / `<|im_end|>`) — comme nos autres Qwen

### gemma-4-26B-A4B
- `unsloth/gemma-4-26B-A4B-it-GGUF` → `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` = **16.95 GB** + `mmproj-BF16.gguf` (1.19 GB, vision)
- Autres : `ggml-org/...`, `bartowski/google_gemma-4-26B-A4B-it-GGUF`
- Format chat : gemma (`<start_of_turn>` / `<end_of_turn>`)

Les deux : weights > 12 GB → **offload obligatoire** (experts en RAM, reste sur GPU).

## 🔧 Le débloquage : options LocalAI vérifiées (backend llama-cpp)

Source : `backend/cpp/llama-cpp/grpc-server.cpp` (master). Tout passe par `options:`
dans le YAML modèle (forme `clé:valeur`).

| But | Option YAML | = flag upstream |
|---|---|---|
| **Offload experts MoE → CPU** | `override_tensor:<regex>=CPU` | `--override-tensor` / `-ot` |
| Auto-fit VRAM | `fit:on` + `fit_target:512` | `--fit` / `--fit-target` |
| MTP (spec decode) | `spec_type:draft-mtp` | `--spec-type draft-mtp` |
| MTP draft max | `draft_max:3` | `--spec-draft-n-max` |
| MTP proba min | `draft_p_min:0.75` | `--spec-draft-p-min` |
| KV draft K/V | `draft_cache_type_k:q8_0` / `draft_cache_type_v:q8_0` | `--cache-type-k/v-draft` |

> ⚠️ Pas de `fit_margin` côté mainline (ça c'est ik_llama). Utiliser `fit_target`.

### ⛔ CORRECTION 2026-08-07 — la contrainte ci-dessus est PÉRIMÉE

Ce document affirmait : *« pas de `--n-cpu-moe` câblé pour le main model dans LocalAI ;
seulement la variante draft »*, et en déduisait qu'il fallait passer par une régex
`override_tensor` poussant **tous** les experts en RAM.

**C'est faux aujourd'hui, et ça aurait coûté cher.** Vérifié le 2026-08-07 sur
l'installation réelle, pas sur la doc :

| vérification | résultat |
|---|---|
| doc officielle (`docs/content/advanced/model-configuration.md`) | `cpu_moe` et `n_cpu_moe` listés **pour le modèle principal** |
| source (`backend/cpp/llama-cpp/grpc-server.cpp`) | `} else if (optname[0] == '-') {` → *« generic passthrough: any entry starting with '-' is a raw upstream llama-server flag, forwarded verbatim »* |
| binaire réellement déployé (`/backends/cuda12-llama-cpp/llama-cpp-grpc`, installé le 2026-07-16) | `cpu_moe` ×2, `n-cpu-moe` ×3, `override_tensor` ×1, `override-tensor` ×3 |

**Donc n'importe quel drapeau de `llama-server` est atteignable depuis `options:`.**

```yaml
options:
  - "--n-cpu-moe:24"       # equivalent exact du reglage du banc
```

Ce que la régex aurait coûté, mesuré au banc sur KAT-Coder (40 couches) :

    -ncmoe 40 (tous les experts en RAM = ce que fait la regex)   33,7 tok/s
    -ncmoe 24 (retenu au banc)                                   47,2 tok/s

Soit **29 % de débit perdu** pour rien.

> ⚠️ **Piège de méthode** : ma première sonde du binaire a répondu « 0 partout » à
> cause d'un `grep -cx` (ancrage sur la ligne entière), alors que les littéraux C sont
> concaténés dans le binaire. J'ai failli conclure l'inverse de la vérité sur la foi de
> mon propre outil de mesure. Sans ancrage, tout était là.

> ⚠️ **Attention aux versions** : le backend `llama-cpp` est installé **séparément**
> dans le PVC `/backends`, donc sa date (2026-07-16) ne suit pas celle de l'image
> LocalAI (v4.8.0). C'est **lui** qui parse les `options:` — c'est donc lui qu'il faut
> interroger, pas la version de LocalAI.

### Ce qui n'est PAS reproductible : les paramètres par REQUÊTE

Mesuré le 2026-08-07 sur le LocalAI déployé, trois requêtes identiques à
`qwen2.5-1.5b-instruct` (temperature 0) sauf un champ :

    base                                completion_tokens = 81
    + "n_predict": 3                     completion_tokens = 81   (sortie identique)
    + "reasoning_budget_tokens": 16       completion_tokens = 81   (sortie identique)

`n_predict` est le nom llama.cpp du plafond de tokens ; s'il était transmis, la sortie
serait coupée à 3 tokens. Elle ne l'est pas. **LocalAI jette silencieusement les champs
non-OpenAI d'une requête** — HTTP 200, aucun avertissement.

Conséquence pour le banc : le seul levier qui ait survécu à l'appariement
(`reasoning_budget_tokens` 8192 + message de clôture) est **inerte en production s'il
est envoyé par requête**. Il reste atteignable **au démarrage**, `llama-server` ayant
le drapeau correspondant :

```yaml
options:
  - "--reasoning-budget:8192"   # -rea/--reasoning pour activer/couper
```

Suffisant pour un déploiement, qui ne sert qu'un régime — mais ce n'est pas le même
bouton : un bras de banc qui fait varier ce champ par tirage n'a pas d'équivalent
par requête en production.

Régex experts (Qwen3 & gemma MoE nomment leurs tenseurs `ffn_(gate|up|down)_exps`) :
```
override_tensor:\.ffn_.*_exps\.=CPU
```
→ garde attention + couches denses sur GPU, pousse TOUS les experts en RAM.
Ajuster (ex : garder quelques experts sur GPU) si VRAM dispo.

## ⚠️ Contrainte chart — RAM

`values.yaml` actuel : `resources.limits.memory: 16Gi`. **Insuffisant** pour ces MoE
(Skyline : ~48 GB nécessaires). Avant déploiement :

```yaml
resources:
  limits:
    cpu: "6"           # i5-9400F = 6 cœurs ; laisser de la marge système
    memory: 56Gi       # nœud = 62 GB ; offload experts ~17-21 GB + KV + système
    nvidia.com/gpu: 1
  requests:
    memory: 32Gi
    nvidia.com/gpu: 1
```

Sans ça → OOM-kill du pod au chargement (ou offload qui déborde).

## Config modèle — chemin PRIMAIRE (backend existant)

À ajouter dans `values.yaml` → `modelsConfigs`. Exemple gemma-4-26B-A4B (plus petit,
16.95 GB ; pour Qwen3.6 adapter filename/URI + stopwords ChatML).

```yaml
  # gemma-4-26B-A4B — MoE 26B total / ~4B actifs. Backend llama-cpp (existant).
  # Experts offloadés en RAM via override_tensor ; attention/denses sur GPU.
  # Terrain : >30 tok/s sur 3060 (LM Studio/mainline, Skyline34rGt). Besoin ~48GB RAM.
  gemma-4-26b-a4b: |
    name: gemma-4-26b-a4b
    backend: llama-cpp
    known_usecases:
      - chat
    context_size: 32768          # monter si la VRAM le permet (gemma = 128k natif)
    gpu_layers: 99               # tout le « dense » sur GPU ; les experts partent en RAM via -ot
    f16: true
    flash_attention: true
    mmap: false                  # offload plus stable sans mmap (cf. recettes reddit)
    cache_type_k: q8_0
    cache_type_v: q8_0
    parameters:
      model: gemma-4-26B-A4B-it-UD-Q4_K_M.gguf
      temperature: 1.0           # défauts gemma
      top_p: 0.95
      top_k: 64
    download_files:
      - filename: gemma-4-26B-A4B-it-UD-Q4_K_M.gguf
        uri: https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf
    options:
      - use_jinja:true
      # --- Offload des experts MoE en RAM (LE knob qui fait tenir le modèle) ---
      - "override_tensor:\\.ffn_.*_exps\\.=CPU"
      # --- Auto-fit VRAM ---
      - fit:on
      - fit_target:512
    template:
      use_tokenizer_template: true
    function:
      automatic_tool_parsing_fallback: true
      grammar:
        disable: true
    stopwords:
      - "<end_of_turn>"
      - "<eos>"
```

### Variante Qwen3.6-35B-A3B + MTP (vitesse max)
Mêmes principes, plus le bloc MTP (nécessite le GGUF `-MTP-` byteshape) :
```yaml
    parameters:
      model: Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
    download_files:
      - filename: Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
        uri: https://huggingface.co/byteshape/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
    options:
      - use_jinja:true
      - "override_tensor:\\.ffn_.*_exps\\.=CPU"
      - fit:on
      - fit_target:512
      # MTP / speculative decoding (têtes drafter du GGUF -MTP-)
      - spec_type:draft-mtp
      - draft_max:3
      - draft_p_min:0.75
      - draft_cache_type_k:q8_0
      - draft_cache_type_v:q8_0
    stopwords:
      - "<|im_end|>"
      - "<|endoftext|>"
```

## Optimisation (plus tard) : backend ik_llama.cpp = +~20 %

Le fork ikawrakow donne +20-23 % sur MoE (meilleur taux d'acceptation MTP, quants IQK).
LocalAI a le backend (**PR mudler/LocalAI#9326**, mergé 2026-04-12), backend name
`ik-llama-cpp`. **MAIS** seule l'image OCI `cpu-ik-llama-cpp` est publiée
(`backend/index.yaml` : `capabilities.default: cpu-ik-llama-cpp`, pas de variante
nvidia). Pour le GPU il faut builder soi-même :
```
make -C backend/cpp/ik-llama-cpp build BUILD_TYPE=cublas   # -> -DGGML_CUDA=ON
```
puis packager l'OCI (`Dockerfile.ik-llama-cpp`, `package.sh`) et le pousser.
À faire **seulement après** avoir validé que le MoE vaut le coup via le chemin primaire.
ik_llama ajoute `--fit-margin` (non dispo en mainline) et un draft autotune.

## À valider avant bascule prod (ne PAS débrancher qwen3-8b avant)

- [ ] `resources.limits.memory` monté à ~56Gi.
- [ ] Le pod charge le MoE sans OOM, offload experts OK (vérifier logs + `nvidia-smi`).
- [ ] Débit réel mesuré sur la 3060 (cible > 35 tok/s, sinon intérêt vs qwen3-8b faible).
- [ ] Tool-calling validé sur un cron NC réel (le MoE émet bien des `tool_calls` JSON).
- [ ] Pas d'iGPU sur i5-9400F → l'écran réserve ~1 GB VRAM ; si serveur headless on récupère la marge.
- [ ] Vision (optionnel) : ajouter `mmproj-*.gguf` si on passe les screenshots browser en image (gros gain tokens vs HTML).
- [ ] Choix final Qwen3.6-35B-A3B (MTP, ChatML) vs gemma-4-26B-A4B (vision native).

## Watcher — RETIRÉ le 2026-07-27

`~/bin/moe-watch.py` surveillait HF pour les nouveaux MoE A-xB utilisables via offload
RAM. **Supprimé**, pour quatre raisons cumulées :

1. **Le cron prescrit ici n'a jamais existé**, et n'aurait pas fonctionné : il appelait
   `notify-send`, qui exige un `DISPLAY` absent sous cron. Le script est resté dormant
   7 semaines (état figé au 2026-06-09).
2. **Sa liste d'exclusions bannissait `heretic`, `uncensored` et `abliterated`** — or le
   seul MoE-offload déployé EST `gemma-4-26b-a4b-heretic`. Il n'aurait jamais pu
   suggérer le modèle qui tourne.
3. **Son résultat était un cul-de-sac** : une notification. `scripts/eval-harness/hf-discover.py`
   (cron 21:45, versionné) alimente au contraire la file d'éval — ses trouvailles
   finissent mesurées.
4. **Le créneau visé ne sert plus l'objectif.** L'offload RAM est CPU-bound au prefill :
   `qwen3.6-35b-a3b` mesurait **744 s par tour**. Or les crons Hermes font en moyenne
   34 messages et 22 appels d'outil — soit des heures par session. Un MoE offloadé ne
   peut donc pas être agentique sur ce nœud, quelle que soit son intelligence. Il reste
   utile au chat et à la vision, où un seul tour suffit.

**Conséquence pour la recherche de modèles** : la cible est l'agentique, donc un modèle
qui **tient en VRAM**. Un candidat « qui fait les deux » devrait être multimodal ET ≤ 12 Go
(type `gemma-4-12b` + `mmproj`), pas un MoE offloadé. ⚠️ Le harness d'éval **ne mesure pas
la vision** : cet axe reste invérifiable automatiquement.

Archive du script : `~/.local/state/archive/moe-watch-20260727.tar.gz`.

## Annexe — gemma-4-12B dense (plan B en veille)

Dense 12B, 128k natif, sliding-window (KV léger), vision native. Bon plan B si on
veut un dense plus simple à faire tenir (pas d'offload). Le QAT officiel Google
(qualité ≈ bf16) `google/gemma-4-12b-it-qat-q4_0-gguf` n'existe pas encore.
Config esquissée : `~/gemma-4-12b.yaml`.
```
