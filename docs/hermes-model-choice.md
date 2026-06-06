# Hermes Agent — choix du modèle d'inférence

> Décision (2026-06-07) : l'**agent** Hermes tourne sur **`z-ai/glm-4.5-air:free` via OpenRouter**.
> LocalAI / `qwen3-8b` est conservé pour le chat direct, les embeddings et le fallback,
> mais n'est plus le modèle de l'agent.

Ce document garde la trace du raisonnement, parce que la conclusion est contre-intuitive
(on a abandonné le 100 % local) et que les `:free` d'OpenRouter tournent — il faudra
probablement reswitcher un jour.

## Contexte / contraintes

- **Usage** : agent piloté **entièrement par Telegram** (l'UI EKKOLearn ne sert qu'à l'admin).
- **Besoin réel** : mémoire + apprentissage + **tool-calling fiable** (créer des cron, lancer
  des scripts, terminal, web_search…).
- **Matériel** : **RTX 3060 12 GB** — c'est la contrainte qui décide de tout.
- **Charge Hermes** : system prompt ~16-19k tokens + ~31 schémas de tools + multi-étapes.

## Le symptôme qui a tout déclenché

Demande Telegram : *« planifie ces 2 scripts tous les jours, sortie sur Telegram »*.
Le modèle **narrait les commandes** (`crontab -e`, `systemctl…` hallucinés) au lieu d'**appeler
le tool `cronjob`**. Il appelait parfois `cronjob` avec `schedule="daily"` (invalide), puis
n'exécutait jamais la version corrigée — il l'écrivait seulement en texte. Résultat : 0 cron créé.

## Ce qu'on a éliminé (et pourquoi)

| Hypothèse | Verdict | Preuve |
|---|---|---|
| **Format / parser LocalAI** | ❌ pas la cause | Test direct : `qwen3-8b` sort un `tool_calls` **structuré parfait** sur un prompt simple (`get_weather` → `{"city":"Paris"}`). |
| **Modèle co-conçu Hermes-3-8B** | ❌ n'aide pas | Même classe 8B ; et il **erreur/échoue** sur notre LocalAI (note historique confirmée). |
| **Backend (vLLM / Ollama)** | ❌ pas la cause | Ollama = même moteur llama.cpp + bugs qwen3 tool-call 2026. vLLM ne force les tools qu'en `tool_choice:required` (Hermes envoie `auto`) **et** ne sait pas faire l'offload-experts MoE → on perdrait le 35B. Le 8B émet déjà des tool_calls corrects → le backend n'est pas le frein. |
| **Framework (OpenClaw)** | ❌ même mur | OpenClaw est **encore plus** orienté modèles frontier ; ses docs déconseillent les petits modèles quantisés. Switcher = recréer le problème. |
| **35B MoE local (`qwen3.6-35b-a3b`)** | ❌ inutilisable pour l'agent | Experts offloadés en RAM/CPU (`-ot ffn_exps=CPU`, seul moyen de tenir sur 12 GB) → **prefill des gros prompts CPU-bound** → `APITimeoutError` (744s observés). Rapide en chat direct (prompt minuscule), pas sous la charge agent. |

## La vraie cause : plafond de capacité du 8B sous charge

Le 8B sort un tool-call nickel sur *« météo à Paris »* mais **s'effondre sous 19k de system
prompt + 31 tools + tâche multi-étapes**. Ce n'est pas un problème de *format* (réparable par
grammaire/forçage) mais de *décision/jugement* (le modèle choisit de narrer le plan) — qu'aucun
decoding contraint ne corrige.

Évidence externe convergente : le tool-calling agentique fiable commence à **~14-32B**
(Qwen3.5-27B ≈ 97 %). En dessous, narration et confusion de concepts sont attendues.

→ **C'est une limite matérielle, pas logicielle.** Le tier fiable ne rentre pas (assez vite)
sur une RTX 3060 12 GB. Aucun framework ni backend ne contourne ça.

## Décision : OpenRouter, modèles `:free`

On lâche le 100 % local **pour l'agent** (gardé pour chat direct / embeddings / fallback).
Modèle retenu : **`z-ai/glm-4.5-air:free`** — MoE ~100B, conçu agent, contexte 131k (> le
plancher 64k de Hermes), `tools` + `tool_choice` supportés. Assez gros pour **décider ET appeler**
sous la charge. Résultat en prod : les 2 crons ont été créés, modèle nettement plus performant.

Fallbacks si l'ID `:free` est déprécié/404 :
`openai/gpt-oss-120b:free` → `qwen/qwen3-next-80b-a3b-instruct:free`.

### Coûts / contraintes du `:free`
- **$0 / token**, mais cap **50 req/jour** sauf si un achat unique de **$10** a été fait →
  **1000 req/jour à vie** (fait).
- **Prompt-training obligatoirement activé** (openrouter.ai/settings/privacy) sinon
  `404 data-policy`. ⇒ les prompts (Telegram + I/O tools) peuvent servir à l'entraînement.
- **Rotation** : les IDs `:free` changent → prévoir de reswitcher `model.default`.
- Latence/disponibilité variables (endpoints free dépriorisés).

### Si la privacy ou la fiabilité gênent
Passer un modèle **payant** au token (centimes/jour à ce volume) : pas de logging imposé,
latence stable. Même provider OpenRouter, juste un autre `model.default`.

## Câblage (référence)

`config.yaml` (seedé via le bootstrap, cf. `argocd/argocd-apps/hermes-agent-app.yaml`) :

```yaml
model:
  default: z-ai/glm-4.5-air:free
  provider: openrouter
  context_length: 131072
providers:
  openrouter:
    name: openrouter
    base_url: https://openrouter.ai/api/v1
    key_env: OPENROUTER_API_KEY      # dans le SealedSecret hermes-secrets
    default_model: z-ai/glm-4.5-air:free
  localai:                            # gardé pour chat direct / embeddings / fallback
    name: localai
    base_url: http://localai.localai.svc.cluster.local:8080/v1
    key_env: OPENAI_API_KEY
    default_model: qwen3-8b
```

### Pièges rencontrés
- **`envFrom` ne relit pas un Secret à chaud.** Ajouter `OPENROUTER_API_KEY` au SealedSecret
  **et** changer la config dans le même push fait rouler le pod sur la nouvelle config *avant*
  que le Secret propage → la clé manque dans l'env → `401 Missing Authentication header`.
  Correctif : **redémarrer le pod** une fois le Secret à jour.
- La clé doit atteindre le **process gateway** (EKKOLearn spawn le gateway avec un env filtré) ;
  vérifié OK pour `OPENROUTER_API_KEY` (pas besoin de seeder `/opt/data/.env`).

## Si on veut re-tenter le local plus tard
- Viser un **dense 14B+** ou attendre un meilleur MoE qui tienne *prefill compris* sur 12 GB.
- Ou monter en VRAM (≥24 GB) pour un 27-32B → tool-calling fiable en local.
- Le 35B MoE reste le meilleur cerveau local **si** le prefill devient acceptable
  (GPU plus gros, ou ik_llama.cpp / optimisations d'offload — cf. `charts/localai/IK-LLAMA-CPP.md`).
