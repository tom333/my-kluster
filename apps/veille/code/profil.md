# Profil — ma stack, par rôle (2026-11-13)

Ce fichier est injecté dans chaque appel LLM de la veille. Il sert à JUGER la pertinence
d'une nouvelle (« ça touche quoi chez moi ? ») et à REPÉRER les alternatives (« qui joue le
même rôle et gagne du terrain ? »). Il ne sert jamais à exclure un sujet : un outil qui
remplace l'un des composants ci-dessous est précisément ce que je veux voir.

## Matériel
- Un PC `pc` : RTX 3060 **12 Go VRAM**, un seul GPU, partagé entre LLM, image, 3D.
- Cluster Kubernetes MicroK8s **single-node** sur ce PC, GitOps ArgoCD, NAS NFS.

## Inférence LLM locale
- Serveur : **LocalAI** v4.12 (API OpenAI-compatible), backend `cuda12-llama-cpp`
  = **llama.cpp** CUDA 12, backend réinstallé le 2026-10-31. Un seul modèle résident.
- Modèle courant : **gemma-4-12b-it-qat** (Google, QAT Q4_0, GGUF ~6,7 Go, ~10 Go VRAM
  à 131 072 de contexte grâce à la SWA, tool-calling via template jinja). Au banc maison
  (projet Python à réparer, 44 tests) : 41/44 à 49 152 de contexte. Remplaçants déjà
  battus : qwen3-coder-30b (32/44, 1 bit), qwopus3.5-9b (20/44).
- Ce qui ferait changer de modèle : meilleur en code + appel d'outils fiable, GGUF
  ≤ ~9 Go, provenance officielle ou QAT (un finetune communautaire casse souvent le
  template d'outils), contexte ≥ 64k (plancher Hermes Agent).
- Autres backends installés : vllm, diffusers, stablediffusion-ggml, trellis2cpp, bonsai,
  transformers, piper, qwen-tts.

## Agents et harnais de codage
- **Hermes Agent** (chat Telegram, modèle cloud deepseek-v4-flash via OpenRouter ;
  recherche web Tavily). Un modèle local le remplacerait s'il tenait le multi-tours.
- Harnais testés au banc : pi, nu, aider, opencode ; **Claude Code** au quotidien ;
  **Paseo** orchestre les agents de code. Critères : comment le harnais pousse
  l'information au modèle, taille du préambule, format d'édition, support des serveurs
  OpenAI-compatibles locaux.

## Data et orchestration
- Orchestrateur : **Dagster** (K8sRunLauncher, DuckLake). Kestra testé puis retiré.
- Données : **DuckDB** / DuckLake, **Polars**, **marimo**, JupyterHub, MLflow, RustFS
  (S3), Qdrant, PostgreSQL. Python outillé par uv et ruff.
- Mémoire sémantique : **txtai**.

## Veille elle-même
- **Miniflux** (lecteur et état lu/non-lu) + **RSSHub**, planification **Dkron**,
  sortie **Telegram** (mobile et web). Un outil qui ferait mieux ce travail m'intéresse.

## Génération d'assets 3D
- Chaîne : concept 2D (**Klein** via **ComfyUI**) → maillage (**TRELLIS.2**, cible
  15 000 faces) → finition **Blender** (cuisson AO). Le temps se perd dans les reprises
  (géométrie fausse, texture décalée), pas dans le débit. Tout doit tenir en 10 Go de VRAM.

## Jeux
- Moteurs : **Unreal Engine** (jeux récents), **Godot** (jeux passés).

## Auto-hébergement
- Médias : stack ***arr** (Radarr, Sonarr, Prowlarr, Bazarr, Lidarr, recyclarr), Jellyfin.
- Infra : Traefik, cert-manager, Sealed Secrets, oauth2-proxy, CrowdSec, Beszel,
  Renovate, Ansible. Dev : code-server, Termix.
