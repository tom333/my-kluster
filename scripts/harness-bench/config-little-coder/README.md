# Configuration little-coder du banc

`little-coder` v1.19.0 (`npm i -g little-coder`) — *« A harness optimized to
smaller LLMs »*. C'est pi + 35 extensions + 30 fiches de compétence, lancé avec
`--no-extensions` : **seul son jeu charge**, `~/.pi/agent/settings.json` est
ignoré (pi-lens, context7…) sauf `--with-pi-extensions`.

## Modèles : un registre à part

little-coder n'enregistre ses fournisseurs que depuis **son** `models.json`
(paquet) et l'override `~/.config/little-coder/models.json` (ou
`LITTLE_CODER_MODELS_FILE`). Jamais depuis `~/.pi/agent/models.json`.

`models.json` ici est le **gabarit** : `apiKey` y est un **nom de variable**.
Le banc génère à chaque lancement `/tmp/harness-bench-little-coder-models.json`
(0600, hors du workdir archivé) avec la valeur, et le passe par
`LITTLE_CODER_MODELS_FILE`.

**Pourquoi** : l'extension `llama-cpp-provider` ne résout le nom de variable que
pour sa sonde `/props` (`resolveApiKey`) ; `pi.registerProvider` reçoit la chaîne
brute et l'envoie comme Bearer → `401 An authentication key is required`.
Vérifié le 2026-09-16 : avec la valeur littérale, l'essai passe. (Le
`export LLAMACPP_API_KEY=noop` du README amont « marche » parce qu'un llama.cpp
sans `--api-key` accepte n'importe quel Bearer.)

## Ce que le modèle voit vraiment (capturé le 2026-09-16)

| | little-coder | omp (pour mémoire) |
|---|---|---|
| requête initiale | **~6 300 tokens** | ~18 000 |
| prompt système | 12 012 car. | 22 538 |
| outils | **26** (12 836 car.) | 11 (48 880 car.) |
| `temperature` | non envoyée pour `localai` | non envoyée |
| `max_completion_tokens` | 16 384 (celui du modèle) | 16 384 |

Les 26 outils : `bash edit read write glob webfetch websearch dispatch`,
Browser×7, Evidence×3, Shell×8. Loin des « 4 outils » du README, mais des
descriptions dix fois plus courtes que celles d'omp. Risque connu : `qwen3-coder`
bascule en XML au-delà de ~5 outils (goose#6883) ; à surveiller sur gemma.

Le profil par défaut (`.pi/settings.json` du paquet) déclare `temperature: 0.3`
et `max_tokens: 4096`, mais la température n'est injectée que pour
`llamacpp|ollama|lmstudio` (`DEFAULT_TEMPERATURE_PROVIDERS`) et `max_tokens`
n'atteint pas la requête. L'échantillonnage reste donc celui du serveur, comme
pour tous les bras du banc — un seul facteur change à la fois.

## Réglages du banc

- `LITTLE_CODER_PERMISSION_MODE=accept-all` : sa liste blanche bash ne contient
  ni `pytest` ni `flutter`. Choix de banc, pas correctif (cf. README du banc).
- `--no-update-check` : sinon le lanceur interroge le registre npm à chaque essai.
- Fumée du 2026-09-16 : `PRET` écrit en 5 s, 1 appel `write`, pic 6 040 tokens.

## Bras B : `little-coder-lens` (2026-09-16)

Même argv, plus `LITTLE_CODER_EXTRA_EXTENSIONS=~/.pi/agent/npm/node_modules/pi-lens/dist/index.js`.
Le lanceur garde `--no-extensions`, donc rien d'autre de `~/.pi/agent` ne charge.

Fumée : le résultat du `write` porte le diagnostic **isolé** —
`🔴 STOP — 2 issue(s) must be fixed: L1: Target of URI doesn't exist: 'nope.dart'.`
C'est le levier qui a distingué le seul succès de la semaine (opencode + lsp), et
que little-coder seul n'a pas : à l'essai 2 du bras A, la même erreur était
enfouie dans 3 892 caractères de gradle et le modèle a rejoué la même commande
quatre fois.

Coût : 34 outils (+`lens_diagnostics`, `symbol_search`, `pi_lens_activate_tools`,
23 288 car.), ~8 950 tokens par requête (bras A : ~6 300).

**Piège de lancement** : pi lit un stdin-tube comme un prompt à venir et attend
l'EOF indéfiniment (« Reading prompt from piped stdin »). Tout lancement hors
`nohup` doit fermer stdin ; le banc pose `stdin=DEVNULL`.
