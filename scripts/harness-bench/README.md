# harness-bench — banc de montée en charge pour harnais de codage

Compare des **harnais** de codage agentique et des **modèles locaux** sur une tâche
identique, avec une vérification qui ne regarde que l'état du disque après coup.

Complémentaire de `scripts/eval-harness/`, qui mesure un **modèle** sur des prompts
courts (tool-calling isolé, coding d'une fonction). Ici on mesure la **boucle
complète** : plusieurs fichiers, une vingtaine de tours, un objectif binaire.

## Pourquoi ce scénario

Un projet Python `taskmgr` avec **7 défauts semés** dans 5 modules et 19 tests, dont
13 échouent au départ. La consigne : faire passer les tests.

C'est le seul type de tâche qui **se transpose à tous les harnais** : pi le résout
avec ses outils `read`/`edit`/`write`/`bash`, aider par diff textuel sans aucun
schéma d'outil. Le prompt (`PROMPT.txt`, figé, identique pour tous) ne mentionne
jamais le mot « outil ».

Réparti sur 5 fichiers, donc l'agent doit lire plusieurs modules, en éditer
plusieurs, relancer les tests et itérer : la montée en tours est structurelle.

## Les trois vérifications

| garde | ce qu'elle attrape |
|---|---|
| `pytest` = 19 passed | l'objectif, binaire |
| `tests/` + `conftest.py` comparés octet à octet | l'agent qui « corrige » le test au lieu du code |
| empreinte AST des signatures publiques | **le renommage de symbole** |

La troisième vise un mode de défaillance précis : à l'éval, `bonsai-27b` (Q1_0,
~1,1 bit/poids) a échoué 5 fois sur 5 en coding par des `NameError` — la bonne
logique écrite sous un autre nom. À très bas quant, ce qui se dégrade est la
restitution exacte d'un identifiant, pas le raisonnement. Ici c'est détecté et
compté comme échec.

## Usage

```bash
python3 bench.py --harness pi    --model localai/qwen3-coder-30b-a3b-instruct
python3 bench.py --harness pi    --model localai/bonsai-27b
python3 bench.py --harness aider --model localai/qwen3-coder-30b-a3b-instruct
python3 bench.py --list-harnesses
```

Chaque run part d'une copie fraîche de `fixture/` dans `/tmp/harness-bench-<slug>/`,
conservée après coup pour inspection. Résultats JSON dans `results/` ; les
transcripts (~1,7 Mo) sont gitignorés et régénérés en relançant.

`pytest` est pris à `/usr/bin/pytest` (surchargeable via `BENCH_PYTEST`) : le python
de pyenv n'a pas le module.

## Ajouter un harnais

Deux fonctions dans `bench.py`, puis une entrée dans `HARNESSES` :

- un **constructeur de commande** `(model, workdir) -> argv`
- un **parseur de transcript** `(texte) -> dict de métriques`

Le parseur est optionnel : `no_metrics` sert de repli et le verdict objectif reste
valable. Un harnais sans instrumentation est donc comparable, à la précision des
tokens près.

## Métriques

Tours · appels d'outils · **format d'appel** (`json` / `xml` / `aucun`, détecté par
fuite de `<function=` ou `<parameter=` dans le texte) · pic d'entrée · total in/out ·
durée · verdict · gardes violées · diff d'API · fichiers modifiés.

Le **format d'appel** n'est pas cosmétique. `qwen3-coder:30b` bascule en XML au-delà
d'environ 5 outils exposés (goose#6883) : le harnais ne reconnaît plus les appels et
la boucle casse. C'est ce qui disqualifie Goose (11 outils par défaut) et ce qui rend
pi viable (4 outils).

## Référence

`pi 0.82.1` + `qwen3-coder-30b-a3b-instruct` @ ctx 32768, 28/07/2026 :

```
verdict  PASS 19/19        tours 26         appels 25 (read/edit/write/bash)
format   json              pic_input 11074 / 32768 = 33,8 %
durée    93,7 s            total in 190931  out 4059
gardes   aucune violation  API intacte      5 fichiers modifiés
```

Les 7 correctifs produits sont identiques à la solution de référence. Le pic reste à
un tiers de la fenêtre sur 26 tours : **sur ce type de tâche, le contexte n'est pas
le facteur limitant.**

## Limites connues

- `.pytest_cache/` est créé dans le workdir et pollue un `diff -r` manuel. Sans
  effet sur le verdict, qui ne compare que les `.py`.
- Une seule fixture, un seul langage. Un modèle pourrait la mémoriser si elle
  circule ; elle n'est pas un benchmark public, juste un instrument local.
- `total_input` est un cumul : LocalAI ne réutilise pas le cache KV entre tours,
  donc chaque tour réexpédie tout le contexte. Ce n'est pas comparable à un
  fournisseur avec prompt caching.
