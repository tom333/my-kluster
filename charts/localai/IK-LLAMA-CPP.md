# Backend ik-llama-cpp + Qwen3.6-35B-A3B (MoE) sur LocalAI

> Doc de déploiement. Objectif : faire tourner un MoE A3B (savoir d'un 35B, vitesse
> d'un 3B) sur le nœud RTX 3060 12 GB via le backend `ik-llama-cpp` de LocalAI,
> avec MTP (speculative decoding) + offload hybride GPU/CPU.
>
> Statut : **investigation terminée, déploiement à faire.** Lire la section
> « Bloquant » avant de commencer — l'image OCI GPU n'existe pas, il faut la builder.

## Pourquoi ce modèle

Workload cible : crons agent (Hermes Agent, job-hunt NC) — tool-calling répété,
gros system-prompt (~16 k), contexte long (browser_snapshot HTML ~30 k/run).

| Modèle | Vitesse 12 GB | « Cerveau » | Tool-call |
|---|---|---|---|
| qwen3-8b (prod actuelle) | ~50 tok/s | 8B dense | ✅ mature |
| gemma-4-12B | ~30 tok/s | ~26B-ish | ⚠️ day-1 |
| **Qwen3.6-35B-A3B** (cible) | ~40–65 tok/s* | **35B MoE** | ✅ Qwen agent |

\* Sur RTX 3060. Le post de référence atteint **110 tok/s** mais sur RTX 4070 Super
(~504 GB/s vs ~360 GB/s pour la 3060) + Ryzen 9700X + DDR5-6000. Notre nœud
(i5-9400F, DDR4-2666, pas d'AVX-512) plafonnera plus bas. Toujours > gemma-4-12B,
et nettement plus « malin » que qwen3-8b.

Source : https://www.reddit.com/r/LocalLLaMA/comments/1tjh7az/ (Qwen3.6-35B-A3B + ik_llama.cpp).

### Pourquoi ik_llama.cpp (fork ikawrakow) plutôt que llama.cpp mainline
- +20–23 % de débit sur MoE (meilleur taux d'acceptation MTP).
- Quants exclusifs IQK / repacking → meilleure qualité/Go.
- Meilleur offload hybride CPU+GPU (critique : le modèle ne tient pas en 12 GB).
- ⚠️ Gains constatés surtout **sous Linux** (décevant sous Windows — non concerné, nœud Linux).

## Quant retenu

Repo : `byteshape/Qwen3.6-35B-A3B-MTP-GGUF` (le `-MTP-` embarque les têtes drafter).

| Fichier | Taille | Usage 3060 12 GB |
|---|---|---|
| `Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf` | **18.61 GB** | qualité max ≈ Q4_K_XL, offload ~7 GB en RAM |
| `Qwen3.6-35B-A3B-IQ4_XS-3.97bpw.gguf` | 17.64 GB | compromis |
| `Qwen3.6-35B-A3B-IQ3_S-3.06bpw.gguf` | 13.61 GB | si RAM/VRAM serrées |
| `mmproj-bf16.gguf` | 0.90 GB | **vision** (optionnel — screenshots au lieu de dumps HTML) |

Budget VRAM (post de réf, 12 GB) : ~11 GB VRAM / ~10 GB RAM, 18 layers full-GPU +
23 hybrides, ctx 131072, KV q8_0. → tient sur la 3060 avec offload.

⚠️ **Contrainte chart** : `resources.limits.memory: 16Gi` (values.yaml). L'offload
RAM (~7–8 GB) + le process LocalAI peut friser la limite. Prévoir de **monter à 24Gi**
(le nœud a 62 GB) avant de lancer l'IQ4_XS-4.19bpw.

## 🚧 Bloquant : pas d'image OCI GPU pour ce backend

Le backend a été ajouté à LocalAI par la **PR mudler/LocalAI#9326**
(`feat(backends): add ik-llama-cpp`, mergée le 2026-04-12).

**MAIS** dans `backend/index.yaml`, le backend ne publie qu'une capacité :

```yaml
- &ikllamacpp
  name: "ik-llama-cpp"
  capabilities:
    default: "cpu-ik-llama-cpp"   # <-- CPU UNIQUEMENT, pas de nvidia/cuda
```

(Comparer au backend `turboquant` juste en dessous qui, lui, a
`nvidia: cuda12-turboquant`.)

Conséquence : l'image gallery prête-à-l'emploi `cpu-ik-llama-cpp` tourne **100 % CPU**.
Sur notre i5-9400F → estimé **~10–18 tok/s**, sans offload GPU. Inutilisable pour la
recette « hybride 110 tok/s ».

Le Makefile du backend supporte pourtant CUDA :
`backend/cpp/ik-llama-cpp/Makefile` → `BUILD_TYPE=cublas` ajoute `-DGGML_CUDA=ON`.
L'image CUDA n'est juste pas **publiée** dans la gallery.

## Chemins de déploiement

### Option A — Builder une image OCI `cuda12-ik-llama-cpp` (rester dans LocalAI) ✅ recommandé
1. Cloner LocalAI, builder le backend en cublas :
   ```bash
   git clone https://github.com/mudler/LocalAI && cd LocalAI
   make -C backend/cpp/ik-llama-cpp build BUILD_TYPE=cublas
   # ou via le flow de packaging OCI : backend/cpp/ik-llama-cpp/package.sh
   ```
2. Packager en image OCI (cf. `Dockerfile.ik-llama-cpp`, ajouter base CUDA 12 +
   `BUILD_TYPE=cublas`), push vers un registre accessible au cluster.
3. Référencer l'image custom comme external backend (cf. mécanique `/backends` PVC,
   bloc `env.LOCALAI_EXTERNAL_BACKENDS` dans `values.yaml` — réactiver
   temporairement le temps de l'install, voir le commentaire existant).
4. Dans le modèle : `backend: ik-llama-cpp`.

> Effort principal : produire l'OCI CUDA. Une fois dans `/backends`, le boot est <5 min
> (même logique que `cuda12-llama-cpp` aujourd'hui).

### Option B — ik_llama.cpp standalone hors cluster + proxy
`llama-server` (ik_llama.cpp) buildé CUDA sur le host, exposé en OpenAI-compat, et
LocalAI/Hermes pointe dessus. Plus simple à débuguer, sort du chart. Bon pour valider
la recette **avant** d'investir dans l'image OCI (Option A).

### Option C — image CPU `cpu-ik-llama-cpp` telle quelle ❌
Déployable de suite mais **CPU-only** → trop lent sur i5-9400F. À écarter sauf test
fonctionnel rapide.

## Config modèle (à ajouter dans `values.yaml` → `modelsConfigs`)

À utiliser une fois le backend GPU (Option A) ou le proxy (Option B) en place.

```yaml
  # Qwen3.6-35B-A3B — MoE 35B total / ~3B actifs. Backend ik-llama-cpp (CUDA).
  # Remplace à terme qwen3-8b pour les crons agent : plus malin (35B MoE) et
  # plus rapide grâce au MTP. Contexte natif 131072 (PAS de YaRN, contrairement
  # à qwen3-8b).
  #
  # VRAM/RAM (réf post reddit, 3060 12GB) : ~11 GB VRAM + ~10 GB RAM offload,
  # 18 layers full-GPU + 23 hybrides. Bumper resources.limits.memory à 24Gi.
  # Si OOM : descendre sur IQ3_S-3.06bpw (13.61 GB) ou augmenter fit-margin.
  qwen3.6-35b-a3b: |
    name: qwen3.6-35b-a3b
    backend: ik-llama-cpp
    known_usecases:
      - chat
    context_size: 131072
    gpu_layers: 99            # ik-llama gère l'offload hybride ; il garde ce qui rentre
    f16: true
    flash_attention: true
    mmap: false               # post : --no-mmap + --mlock pour stabilité offload
    cache_type_k: q8_0
    cache_type_v: q8_0
    parameters:
      model: Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
      temperature: 0.6        # recommandé Qwen (0.0 = bench uniquement)
      top_p: 0.95
      top_k: 20
    download_files:
      - filename: Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
        uri: https://huggingface.co/byteshape/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-IQ4_XS-4.19bpw.gguf
    options:
      - use_jinja:true
      # --- Flags ik_llama.cpp (du post de réf, calibrés 12 GB) ---
      # ⚠️ À VALIDER : confirmer que le gRPC server du backend ik-llama-cpp de
      # LocalAI honore ces flags (lire backend/cpp/ik-llama-cpp/grpc-server.cpp
      # et utils.hpp). MTP peut nécessiter un câblage spécifique côté yaml.
      # Flags CLI équivalents côté ik_llama.cpp standalone :
      #   --multi-token-prediction --draft-p-min 0.75 --draft-max 3
      #   --cache-type-k-draft q8_0 --cache-type-v-draft q8_0
      #   --fit --fit-margin 2048   (2048 car pas d'iGPU : l'écran réserve ~1 GB
      #                              sur la 3060 ; commencer haut, baisser si marge)
      #   --no-mmap --mlock --threads 8
    template:
      use_tokenizer_template: true
    function:
      automatic_tool_parsing_fallback: true
      grammar:
        disable: true
    stopwords:
      - "<|im_end|>"
      - "<|endoftext|>"
```

### Note hardware (pas d'iGPU)
Le nœud (i5-9400F) **n'a pas d'iGPU** → l'écran tire ~1 GB sur la 3060, donc moins de
VRAM dispo qu'au post. D'où `--fit-margin 2048` (vs 1664 au post). Si serveur headless
(pas d'affichage X actif), la marge se récupère.

## À valider avant bascule prod (ne PAS débrancher qwen3-8b avant)

- [ ] Image OCI `cuda12-ik-llama-cpp` buildée + poussée (Option A) **ou** proxy standalone (Option B).
- [ ] Backend `ik-llama-cpp` honore bien les flags MTP/fit via `options:` (sinon adapter).
- [ ] `resources.limits.memory` monté à 24Gi.
- [ ] Tool-calling validé sur un cron NC réel (le MoE émet bien des `tool_calls` JSON, pas du texte).
- [ ] Débit réel mesuré sur la 3060 (objectif : > 50 tok/s, sinon l'intérêt vs qwen3-8b chute).
- [ ] Décider vision : ajouter `mmproj-bf16.gguf` si on passe les screenshots browser en image (gros gain tokens vs HTML).

## Annexe — gemma-4-12B (piste alternative, en veille)

Évaluée avant Qwen3.6 ; reste un bon plan B (dense 12B, 128k natif, sliding-window KV
léger, vision native). Un watcher surveille la sortie du **QAT officiel Google**
(qualité ≈ bf16 à VRAM Q4) :
- Script : `~/bin/gemma4-watch.py` (hors repo, sur le host).
- Config LocalAI esquissée : `~/gemma-4-12b.yaml`.
- Le QAT `google/gemma-4-12b-it-qat-q4_0-gguf` n'existe pas encore à ce jour.
```
