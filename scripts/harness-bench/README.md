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

## ⚠️ Un seul essai n'est pas une mesure

La température n'est pas nulle (0.6). Constaté le 2026-07-29 : **deux exécutions de
la même paire modèle/harnais sur tetris ont donné 38/44 puis 21/44** — un écart de
17 tests que rien ne permettait d'attribuer soit au changement testé, soit au hasard.

`--runs` vaut donc **3 par défaut**, et c'est la **médiane** qui fait foi. Le gate de
`promote.sh` refuse une promotion appuyée sur moins de 3 essais
(`PROMOTE_MIN_RUNS` pour outrepasser, à ses risques). Chaque essai part d'une copie
fraîche dans `/tmp/harness-bench-<slug>-r<N>/`.

Tous les résultats antérieurs au 2026-07-29 dans `results/` sont des tirages uniques :
à lire comme des indications, pas comme des mesures.

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

## Scénario `tetris` — 28/07/2026, ctx 32768

Écrire `tetris/` depuis zéro pour satisfaire 44 tests. Départ : 0/44 (erreur de
collecte, le paquet n'existe pas).

| harnais | modèle | tests | tours | pic d'entrée | sortie | fin | durée |
|---|---|---|---|---|---|---|---|
| little-coder | qwen3-coder-30b | **34/44** | 6 | 24 456 → 75 % | 12 886 | budget | 393 s |
| pi | qwen3-coder-30b | **33/44** | 19 | **29 704 → 90,6 %** | 12 777 | **`length`** | 377 s |
| pi | bonsai-27b | 13/44 | 8 | 17 434 | 7 041 | `length` | 303 s |
| little-coder | bonsai-27b | 11/44 | 7 | 23 621 | 4 419 | **`aborted`** | 406 s |

### Qwopus3.5-9B-Coder Q6_K — le meilleur résultat, et il renverse l'intuition « plus gros »

`Jackrong/Qwopus3.5-9B-Coder-MTP-GGUF`, Q6_K, 7,56 Go. Base Qwen3.5-9B, entraîné
explicitement à l'agentique (ToolCall-15 100/100, traces d'exécution d'outils réelles
de GLM-5.1 et Kimi-4.6, SWE-bench Verified 53,89 %).

| harnais | tests | tours | pic d'entrée | durée |
|---|---|---|---|---|
| **pi** | **38/44** | **9** | **11 342 → 34,6 %** | **185,9 s** |
| little-coder | 0/44 | 2 | 9 673 | **TIMEOUT 1200 s** |

**Un 9B bat le 30B incumbent de 5 tests**, en 9 tours au lieu de 19, avec un pic à
34,6 % de la fenêtre au lieu de 90,6 %.

La leçon n'est PAS « un Q4+ code mieux » : `gemma-4-12b-coder` était en Q4_K_M et a
fait 0/44. C'est la **conjonction** de trois choses :

1. un quant honnête (Q6, pas un quant de désespoir à 1 bit) ;
2. un entraînement agentique explicite — ce que gemma n'avait pas, lui qui
   comprenait parfaitement le contrat et n'agissait jamais ;
3. des poids assez légers pour laisser respirer le KV.

⚠️ **`little-coder` + `qwopus` : timeout.** Le code généré contient une boucle
infinie ; l'agent lance `pytest` lui-même, son appel pend, et il ne reprend jamais la
main — 2 tours en 1200 s. `pi` avec le même modèle finit en 185,9 s. pi documente un
champ `timeout` par commande sur son outil bash ; l'équivalent chez little-coder n'a
pas pu être établi, donc **l'écart est mesuré mais le mécanisme reste une hypothèse**.
Le plafond de 1200 s (au lieu de 2400) rend cette ligne non strictement comparable.

**Le banc discrimine enfin.** Sur `repair`, les deux modèles faisaient 19/19 — une
égalité qui ne disait rien. Ici l'écart est de **2,6×** : ~75 % pour `qwen3-coder`,
~27 % pour `bonsai`. La différence de quantification devient visible dès qu'il faut
concevoir au lieu de réparer.

### Ici, le contexte EST le facteur limitant

Conclusion inverse de celle de `repair`, et c'est le résultat le plus important.

`pi` + `qwen3-coder` s'arrête sur `stopReason: length` à **29 704 tokens d'entrée,
soit 90,6 % de la fenêtre**, en n'ayant produit qu'**un seul token** sur son dernier
tour. Il n'a pas échoué faute de savoir : il n'avait plus de place. Les trois autres
runs finissent aussi par manquer de budget (`length` ou arrêt prématuré) avec des
entrées de 17 k à 24 k et une progression rapide.

Sur une tâche de réparation à 26 tours, le pic plafonnait à 34 %. Sur une tâche de
conception, on touche le plafond en 19 tours. **Ce n'est pas la longueur de la boucle
qui remplit la fenêtre, c'est la quantité de code à tenir en tête.**

### Conception propre ≠ code correct

Inversion inattendue :

| | fichiers produits | tests |
|---|---|---|
| `bonsai` sous pi | **5 modules** (`__init__`, `bag`, `board`, `game`, `piece`) | 13/44 |
| `qwen3-coder` sous pi | **1 fichier** `tetris.py` | 33/44 |

`bonsai` a produit la plus belle architecture — celle que le contrat suggérait — et le
code le plus faux. `qwen3-coder` a pris le raccourci d'un module unique (valide :
`from tetris import ...` fonctionne avec `tetris.py`) et passe 2,5× plus de tests.
Sous budget contraint, le raccourci est **adaptatif** : moins de tokens de structure,
plus de tokens de logique.

### Le mode de défaillance de `bonsai` : la boucle

`little-coder` + `bonsai` finit en `aborted`, et son transcript contient **8 318
répétitions** du même message :

```
Error. I need to either use a property with a backing variable, or
Error: can't set attribute 'size'
```

Il a défini `size` en propriété sans accesseur en écriture, puis a tenté de
l'affecter, et a tourné en boucle sur cette seule erreur des milliers de fois.

C'est exactement ce que la littérature annonce pour les quants très bas en usage
agentique : *« it makes it unreliable at long tool calls »*, *« ends up stuck in loops
while reasoning »*, et ACBench mesurant −10 à −15 % sur les tâches d'agent
bout-en-bout là où l'usage d'outils isolé ne perd que 1-3 %. Le scénario `repair`
ne l'a jamais fait apparaître ; celui-ci le fait en un run.

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
