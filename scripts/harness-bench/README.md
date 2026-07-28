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

## Résultats — 28/07/2026, ctx 32768

| harnais | modèle | verdict | tours | appels | préambule | pic d'entrée | total in | durée |
|---|---|---|---|---|---|---|---|---|
| **little-coder** 0.79.10 | qwen3-coder-30b | **PASS 19/19** | **24** | **23** | 4 528 | 14 666 | 258 359 | **89,2 s** |
| **pi** 0.82.1 | qwen3-coder-30b | **PASS 19/19** | 26 | 25 | **1 603** | 11 074 | 190 931 | 93,7 s |
| **pi** 0.82.1 | bonsai-27b (Q1_0) | **PASS 19/19** | 28 | 33 | 1 603 | 13 916 | 265 508 | 249,4 s |
| **aider** 0.86.2 | qwen3-coder-30b | FAIL 15/19 | 4 | — (diff) | ~700 | 9 700 | **27 500** | 219,4 s |

Aucune garde violée, aucune dérive d'API sur les quatre runs. Le pic reste sous la
moitié de la fenêtre partout : **sur ce type de tâche, le contexte n'est pas le
facteur limitant.**

`qwen3-coder` sous pi reproduit la solution de référence à l'identique. `bonsai`
diverge une fois, et légitimement : là où la référence remplace `max` par `min`, il
garde `max` en niant les clés (`key=lambda t: (-t["priority"], -t["id"])`) —
fonctionnellement équivalent, tie-break compris.

### little-coder : les skills achètent peu, et ça se paie

Question posée : ses ~30 extensions et ~30 skills réduisent-ils le nombre
d'itérations, ou sont-ils une dépense sèche ?

**Réponse : un gain modeste, payé en tokens.** 24 tours contre 26, 23 appels contre
25, 89,2 s contre 93,7 (−5 %). En face : un préambule de **4 528 tokens contre 1 603**
(×2,8) et +35 % de tokens d'entrée cumulés. Mesuré, le préambule est nettement
*inférieur* aux ~7 000 annoncés par son README.

Sur un budget de 32 768 les deux tiennent largement. Le choix se joue donc sur autre
chose que le contexte — et pi nu reste plus simple à raisonner.

⚠️ **Un défaut d'intégration, dans sa configuration par défaut** : son extension
`permission-gate` restreint bash à une liste blanche (`SAFE_PREFIXES`) qui **ne
contient pas `pytest`**. Premier run, sans rien changer :

```
shell whitelist: "pytest" is not in SAFE_PREFIXES
→ FAIL 13/19, l'agent se declare termine avec 6 tests rouges
```

Privé de la commande de test, il perd la boucle de rétroaction — précisément le
mécanisme qui fait réussir `bonsai` malgré son quant. Le banc lève donc la barrière
(`LITTLE_CODER_PERMISSION_MODE=accept-all`, échappatoire documentée) puisque pi n'a
aucune liste blanche. **C'est un choix de banc pour comparer à armes égales, pas un
correctif de bug** : la posture par défaut de little-coder est simplement plus
prudente que celle de pi.

### aider — le paradigme sans schéma d'outil

`aider 0.86.2` + `qwen3-coder-30b`, même fixture, même prompt :

```
verdict  FAIL 15/19        tours 4          format  diff (aucun schema d'outil)
pic      9 700 / 32 768    total in 27 500  out 10 144      durée 219,4 s
gardes   aucune            API intacte      4 fichiers sur 5 corriges
```

`dates.py` est resté **inchangé** après six tentatives. Cause, dans le transcript :

```
The LLM did not conform to the edit format.
No filename provided before ``` in file listing
Only 3 reflections allowed, stopping.
```

Deux enseignements, et le second invalide une hypothèse de départ.

**Le plafond de réflexions.** En non-interactif, aider s'arrête après 3 réflexions.
Il n'existe **aucun drapeau** pour le relever (`--max-reflections` n'existe pas) :
c'est un comportement, pas une erreur de configuration. Le FAIL est légitime.

**Le format d'édition est un protocole texte non validé.** On avait retenu aider
parce qu'en n'exposant aucun schéma d'outil il contourne *par construction* la
bascule XML de `qwen3-coder` au-delà de 5 outils. C'est vrai — mais il remplace ce
risque par un autre : un appel d'outil parse en JSON ou ne parse pas, tandis qu'un
bloc d'édition aider peut être *presque* correct et échouer. Trois rejets de format
ont suffi à consommer le budget de réflexions.

**En contrepartie, il est bien plus sobre** : 27 500 tokens d'entrée au total contre
190 931 pour pi, soit ×7 moins. pi réexpédie un contexte croissant à chaque tour ;
aider envoie les fichiers une fois et itère en conversation. Le paradigme diff est
économe — il n'a simplement pas fini.

> Réserve de comparabilité : aider n'explore pas, il édite ce qu'on met dans le chat.
> Les 5 modules lui sont donc passés en `--file` et la suite de tests en `--read`,
> alors que **pi a dû découvrir les fichiers lui-même**. Usage idiomatique d'aider,
> pas une triche, mais les colonnes « tours » ne sont pas comparables.

### Ce que ce banc corrige dans eval-harness

`eval-harness` donnait `bonsai-27b` à **coding 0,643**, avec 5 échecs sur 5 en
`NameError` — la bonne logique sous un autre nom. On en avait conclu qu'à ~1,1 bit la
restitution exacte d'un symbole était cassée, et que le modèle serait donc inapte à
une tâche agentique réelle.

**C'est faux.** Ici il n'a renommé aucun symbole (`api_modifiee: []`) et il a tout
résolu. La raison : `pytest` lui renvoie l'erreur, et **la boucle corrige** ce que le
test one-shot sanctionnait définitivement.

Un test one-shot **surestime donc la pénalité d'un quant très bas** dès que le cadre
réel comporte une boucle de rétroaction. Le vrai coût n'est pas une incapacité, c'est
un nombre d'itérations : 33 appels contre 25, et ×2,66 sur le temps de mur. Une
dépense, pas un plafond.

## Limites connues

- `.pytest_cache/` est créé dans le workdir et pollue un `diff -r` manuel. Sans
  effet sur le verdict, qui ne compare que les `.py`.
- Une seule fixture, un seul langage. Un modèle pourrait la mémoriser si elle
  circule ; elle n'est pas un benchmark public, juste un instrument local.
- `total_input` est un cumul : LocalAI ne réutilise pas le cache KV entre tours,
  donc chaque tour réexpédie tout le contexte. Ce n'est pas comparable à un
  fournisseur avec prompt caching.
