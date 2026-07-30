# POC — harnais minimal au-dessus de llama-server

> Notes prises le 2026-07-29, à reprendre dans un **autre projet**. Modèle de base :
> **gemma-4-12B-it-qat**. Rien n'est implémenté ici ; ce fichier consigne l'idée, les
> décisions déjà prises et surtout **les pièges qui ont coûté une journée** et que le POC
> doit contourner d'emblée.

## L'idée

Écrire **notre propre boucle d'agent**, d'environ cent lignes, directement au-dessus de
`/v1/chat/completions` :

```
1. construire le message utilisateur (la tâche)
2. POST /v1/chat/completions  avec les schémas d'outils
3. si la réponse contient des tool_calls : les exécuter localement, renvoyer les
   résultats en messages role=tool, reboucler
4. si elle n'en contient pas : le tour est fini
5. arrêter sur : succès mesuré, plafond de tours, plafond de tokens
```

### Pourquoi, alors qu'il existe déjà quatre harnais

Le banc `scripts/harness-bench` compare `pi`, `little-coder`, `aider` et (piloté à la main)
`openfox`. Il manque le **témoin de référence** : un harnais à **préambule nul**.

| harnais | préambule mesuré |
|---|---|
| harnais nu (ce POC) | **0** — seulement les schémas d'outils |
| `pi` | 1 603 tokens |
| `little-coder` | 4 528 tokens |
| `openfox` (mode builder) | 5 227 tokens, 15 outils |
| Claude Code | 27 169 tokens |

Sans ce plancher, on ne sait pas ce qui, dans un score, revient au **modèle** et ce qui
revient au **prompt système du vendeur**. Tous les autres harnais se mesureraient alors en
écart par rapport à la capacité brute.

C'est aussi moins de travail que de piloter un harnais tiers sans tête : le pilotage
d'openfox a demandé de contourner quatre pièges (voir plus bas) pour un résultat qui
restait dépendant de son préambule.

### Pourquoi llama-server et pas LocalAI

Deux raisons, l'une positive, l'autre subie.

**Positive** : llama-server expose toute la surface d'options de llama.cpp en direct —
`--ctx-size`, `-ctk/-ctv`, `--cache-reuse`, `--reasoning-budget`, `--parallel`, `-fit`,
`--swa-full`… Sur LocalAI, ces réglages passent par une traduction (`options: [clé:valeur]`)
dont la couverture n'est pas garantie, et dont les échecs ne remontent aucun message.

**Subie** : llama-server a bien des outils intégrés (`--tools read_file, write_file,
edit_file, grep_search, file_glob_search, exec_shell_command, get_datetime` et `--agent`)
et un support MCP (`--ui-mcp-proxy`), **mais la boucle d'agent vit dans la Web UI**. La doc
dit « through the Web UI », le flux MCP précise que l'exécution est déclenchée par *« the UI
calling the `executeTool` method on the MCP store »*, et le champ exposé dans `/props`
s'appelle `cors_proxy_enabled`. `/v1/chat/completions` est un endpoint OpenAI ordinaire :
il n'exécute aucun outil, il n'y a pas de boucle serveur.

⇒ **On ne peut pas réutiliser sa boucle. Donc on l'écrit, et on en profite pour qu'elle ne
coûte rien en préambule.**

**llama-server n'est pas qu'une API : c'est un serveur d'inférence + une application web
complète**, et la Web UI est **activée par défaut**. Indices : `--ui/--webui/--no-ui/
--no-webui` (défaut activé), `--path` pour servir des statiques, `--ui-config` /
`--ui-config-file`, un répertoire `tools/ui/` avec sa propre doc de flux, et `/props` qui
renvoie `ui`, `ui_settings`, `cors_proxy_enabled`.

⇒ Deux conséquences pour le POC : **lancer avec `--no-webui`** (un banc n'en a pas besoin
et elle élargit la surface exposée), et comprendre que les fonctions d'agent sont des
fonctionnalités *de cette UI*, pas du serveur. Ce n'est pas une lacune de llama.cpp, c'est
un choix d'architecture : l'agent est un client de l'API.

Constat plus large : openfox, llama-server et LocalAI mettent tous leur boucle dans un
navigateur. **La boucle n'est donc pas la partie difficile** — ce qui coûte, c'est le
préambule empilé autour. D'où l'intérêt d'écrire les cent lignes nous-mêmes.

*Point non tranché* : « accès au système de fichiers via la Web UI » est ambigu — les outils
sont probablement exécutés côté serveur mais orchestrés par le client. Sans effet sur la
conclusion (l'orchestration est côté navigateur), mais à vérifier si on voulait un jour
réutiliser leurs implémentations d'outils.

## Modèle de base

`unsloth/gemma-4-12B-it-qat-GGUF` — le **QAT officiel**, seul GGUF principal du dépôt :

```
gemma-4-12B-it-qat-UD-Q4_K_XL.gguf      6,72 Go   <- le modèle
MTP/mtp-gemma-4-12B-it-Q4_0.gguf        254 Mo    <- drafter, celui qui marche
MTP/mtp-gemma-4-12B-it-Q8_0.gguf        444 Mo    <- testé, moins bon (cf. pièges)
mmproj-BF16.gguf                        175 Mo    <- vision, INUTILE pour du code
```

- `context_length` métadonnée : **262144** (256K natif).
- **Fenêtre glissante de 1024 tokens** : gemma-4 alterne attention locale et globale.
  llama.cpp alloue deux caches (`llama_kv_cache_iswa`) et plafonne les couches SWA à 1024
  cellules quel que soit `--ctx-size`. **Conséquence : agrandir la fenêtre est presque
  gratuit en VRAM** (mesuré : 32768 → 49152 = 9711 → 9655 MiB sur RTX 3060 12 Go).
- Unsloth déconseille `Q4_0` (moins bon **malgré** une taille supérieure) ; `UD-Q4_K_XL`
  est le quant recommandé. Le QAT est « any-to-any » : il survit de `Q3_K_L` à `Q5_K_M`,
  mais **aucun de ces fichiers n'existe dans le dépôt QAT** — monter en précision impose
  de quitter le QAT.

### Format d'appel d'outil : un DSL à tokens spéciaux

Ce n'est **ni du JSON, ni la syntaxe Python**. Extrait du template embarqué dans le GGUF :

```
<|tool>declaration:read{description:<|"|>…<|"|>,parameters:{…}}<tool|>
<|tool_call>call:read{path:<|"|>tests/test_tetris.py<|"|>}<tool_call|>
<|tool_response>response:read{…}<tool_response|>
<|channel>thought … <channel|>
```

**Le POC ne doit PAS tenter de sérialiser ça à la main.** On envoie des schémas OpenAI
standard et on laisse le template jinja de llama-server (`--jinja`, activé par défaut) faire
la traduction dans les deux sens. C'est exactement ce que fait déjà LocalAI avec
`template.use_tokenizer_template: true`.

Le template expose aussi un `enable_thinking` : quand il est faux, il **pré-ferme** le canal
de pensée (`<|channel>thought\n<channel|>`). Réglable via `--chat-template-kwargs
'{"enable_thinking":false}'`.

## Les pièges à contourner

Chacun a été payé comptant le 2026-07-29. Détail complet dans
`scripts/harness-bench/README.md`.

### Sur la mesure elle-même

1. **Un zéro n'est pas un résultat tant qu'une requête n'a pas abouti.** Six essais à 0/44
   en 1,4 s se sont révélés être des HTTP 404 (modèle plus servi) déguisés en mesure.
   ⇒ **préchauffage obligatoire, abandon si ≠ 200.**
2. **Les serveurs journalisent à la complétion, pas à la réception.** Une requête en vol
   pendant 900 s n'apparaît **nulle part** dans les logs. J'en ai conclu à tort « le client
   n'a rien émis ». ⇒ ne jamais déduire l'absence de requête de l'absence de ligne de log ;
   instrumenter côté client.
3. **Un budget en secondes mélange qualité et débit.** Le banc mesure « ce que le modèle
   finit en 900 s », pas ce dont il est capable. C'est ce qui rend l'effet du MTP illisible.
   ⇒ **budget en tours et en tokens, pas en temps.** Le temps reste une métrique, pas une
   limite de comparaison.
4. **n=1 n'est pas une mesure.** À température 0,6, deux tirages de la même paire ont donné
   38 et 11. ⇒ **médiane sur ≥3 essais, et toujours publier l'étendue.** Avec des étendues
   de 0–41 observées, même une médiane sur 3 reste un signal faible : le dire.
5. **Une fixture unique ne peut pas valider un modèle entraîné sur ses traces.** Une
   **seconde fixture de rétention** est un prérequis à tout fine-tuning, pas une amélioration.
6. **Compter les erreurs sans les lire mène à de faux diagnostics.** Deux fois : un « chemin
   relatif qui échoue » était en réalité un chemin absolu amputé de sa barre oblique ; un
   « 0/44 » était un `SyntaxError` d'une ligne qui masquait 17/44.

### Sur la boucle d'agent

6bis. **Aucune requête vers un AUTRE modèle pendant une mesure.** Avec un GPU unique et
   `LOCALAI_SINGLE_ACTIVE_BACKEND=true`, toute requête sur un autre modèle **évince le
   backend chargé**, y compris au milieu d'une génération en cours. Signature du dégât :
   score 0, **0 tour**, pic 0, durée = timeout exact, transcript de 0 octet, GPU à 0 %
   d'utilisation avec de la VRAM occupée. J'ai détruit deux séries de mesures en lançant
   des diagnostics concurrents pour comprendre… pourquoi les mesures échouaient. ⇒ un banc
   prend un **verrou exclusif** sur le GPU ; tout diagnostic attend son tour.

7. **Timeout par commande obligatoire.** Le code généré contient des boucles infinies : un
   `pytest` a pendu et bloqué la suite à 36 tests sur 44, consommant tout le budget.
   `pi` passe un `timeout` à `bash` ; `little-coder` n'en a pas d'établi et a laissé un run
   tourner 1 200 s.
8. **Plafonner `max_tokens` par tour et le nombre de tours.** Sans cap, le modèle génère
   jusqu'au plafond de contexte : un essai à **54 693 tokens** pour 22 tours et 10/44.
9. **Tuer le groupe de processus, pas l'enfant.** Sinon les petits-fils (`bash` → `pytest`)
   restent orphelins à 100 % de CPU. `start_new_session=True` + `os.killpg`.
10. **Attention aux motifs de recherche qui matchent votre propre ligne de commande.**
    Trois fois dans la journée : `pkill -f "bench.py"` a tué son propre shell ; `pgrep -cf`
    s'est compté lui-même ; `grep "pi --model"` a matché
    `bench.py --harness pi --model …`. ⇒ ancrer les motifs, exclure le PID courant.
11. **Borner la taille des transcripts.** 587 Mo de traces accumulées, dont un fichier de
    15,4 Mo pour un seul essai.

### Sur le modèle et le backend

12. **Ne jamais déduire une incapacité sans mesure.** Une note de mémoire affirmait que
    gemma-4-12b-it-qat n'était « pas pour le tool-calling agentique ». C'était faux, et
    l'avoir cru a fait chercher pendant des heures du côté de la grammaire de décodage, du
    contrat de boucle du harnais et d'un `response_regex`, alors que le modèle qui marche
    était déjà déployé depuis six semaines.
13. **Un finetune peut casser le template d'appel d'outil.** `yuxinlu1/gemma-4-12B-coder-…`
    a gardé la compétence en code (17/44 hors ligne) et perdu les tokens de contrôle : il
    émet ses appels en syntaxe Python dans le texte, que personne ne parse. Le QAT officiel,
    même prompt, rend un `tool_calls` valide. ⇒ **vérifier le tool-calling d'un finetune
    avant tout le reste**, avec un prompt LONG (sur une tâche courte, il retombe dans le bon
    format et le défaut est invisible).
14. **L'optimum de fenêtre n'est pas le maximum.** Médianes mesurées : 0/44 à 32768
    (travaux tronqués), **34/44 à 49152**, 19/44 à 131072 (il tourne en rond). Le POC doit
    balayer la fenêtre, pas la pousser au plafond.
15. **Le décodage spéculatif n'est pas neutre en pratique.** Changer le drafter (Q4_0 →
    Q8_0) a fait tomber la médiane de 34/44 à 0/44. L'explication la plus économe est un
    débit dégradé qui fait dépasser le budget de temps — pas une altération de la sortie.
    ⇒ **à trancher dans le POC**, en budget de tours : comparer avec et sans drafter, à
    tours égaux. Ça vaut aussi pour le drafter actif en production.
16. **`--parallel` par défaut multiplie le KV.** Le log de LocalAI affiche `parallel="4"` :
    quatre slots, donc quatre fois le KV cache. C'est probablement ce qui empêche
    `qwen3-coder-30b` (attention pleine) de charger à 49152 là où gemma passe grâce à la
    SWA. ⇒ **`--parallel 1` pour un banc mono-requête.**
17. **Syntaxe des options LocalAI, si on garde un pied dedans** : `clé:valeur` **sans `--`
    et avec des tirets bas** (`parallel:1`, `cache_reuse:256`, `context_shift:true`), pas la
    forme ligne de commande. J'ai perdu deux redémarrages sur `"--cache-reuse:256"`, et j'en
    ai conclu à tort que le passe-plat d'options était inutilisable.
18. **Le watchdog d'inactivité de LocalAI compte depuis la dernière requête *terminée*.**
    Une génération longue est prise pour de l'inactivité et le backend est tué en pleine
    course. Corrigé ici à 30 min, mais à ne pas reproduire.

### Sécurité — non négociable

19. **`exec_shell_command` donne un shell dans le conteneur.** llama.cpp restreint
    volontairement `--cors-origins` à localhost dès qu'on active ces outils ou `--agent`.
    ⇒ **jamais derrière un ingress**, jamais sur `*.tgu.ovh`. Le POC tourne en localhost ou
    en LAN restreint, point.
20. **La fixture doit être jetable et isolée.** Le harnais exécute du code généré : copie de
    la fixture dans un répertoire temporaire, jamais sur l'arbre de travail réel.

## Forme visée du POC

```
harnais-nu/
├── boucle.py          # ~100 lignes : POST, exécution des tool_calls, rebouclage
├── outils.py          # read, write, edit, bash — 4 outils, schémas OpenAI, rien de plus
└── serveur.md         # invocation llama-server de référence
```

Invocation de départ à valider :

```bash
llama-server \
  -m gemma-4-12B-it-qat-UD-Q4_K_XL.gguf \
  --ctx-size 49152 --parallel 1 \
  -fa on -ctk q8_0 -ctv q8_0 \
  --jinja --no-webui --no-agent \
  --host 127.0.0.1 --port 8080
```

Métriques à enregistrer par essai, pour rester comparable au banc existant : score,
**nombre de tours**, pic de tokens d'entrée, tokens de sortie cumulés, durée, format des
appels observé, et le compte d'appels par outil.

### `--no-kv-offload` : une dimension du banc, pas une option du harnais

`--no-kv-offload` garde le KV cache en **RAM hôte** au lieu de la VRAM. C'est un flag de
**lancement de llama-server**, pas un paramètre de requête : le harnais ne peut pas le
changer en cours de route. Mais comme le POC possède l'invocation du serveur, ça devient
une dimension à balayer, au même titre que `--ctx-size` et `--parallel`.

**Inutile sur gemma-4** : sa fenêtre glissante de 1024 tokens rend le KV quasi gratuit
(mesuré : 32768 → 49152 pour **56 MiB de moins**). Déplacer en RAM un cache qui ne coûte
rien ne fait que perdre du débit.

**Mais c'est le bon levier pour les modèles à attention pleine**, et on a le cas :
`qwen3-coder-30b-a3b` (IQ1_S, 8,3 Go) **refuse de charger à 49152** — crash au démarrage,
KV trop gros. C'est ce qui empêche la comparaison appariée avec gemma à fenêtre égale, la
mesure qui manque encore au dossier.

Ordre à respecter, du moins cher au plus cher :

1. **`--parallel 1` d'abord.** LocalAI alloue 4 slots par défaut, donc **4× le KV**.
   Testé sur gemma seulement, où ça n'a rien changé (son KV est minuscule : 9655 → 9177
   MiB). Sur qwen, dont c'est justement le KV qui bloque, diviser par 4 peut suffire —
   et c'est gratuit en débit.
2. **`-ctk`/`-ctv` plus agressifs** (`q5_1`, `q4_0`, `iq4_nl` au lieu de `q8_0`) : encore
   en VRAM, donc sans coût PCIe.
3. **`--no-kv-offload` en dernier.** L'attention relit tout le KV à chaque token ; à
   l'échelle du gigaoctet, le PCIe devient le goulot et le débit tombe à quelques tokens
   par seconde.

⚠️ **Et ça ne se mesure PAS sous un budget en secondes.** Le ralentissement PCIe se lirait
comme une baisse de qualité — c'est exactement le défaut de méthode identifié au piège 3.
Ces trois options doivent être comparées **à budget de tours égal**, le temps étant
rapporté comme métrique séparée.

## Questions ouvertes

- Le drafter MTP est-il neutre sur la sortie, à tours égaux ? (piège 15)
- `--parallel 1` libère-t-il assez de KV pour que `qwen3-coder-30b` tienne à 49152, et son
  score bouge-t-il ? (piège 16) — c'est la comparaison appariée qui manque encore.
- Si `--parallel 1` ne suffit pas à qwen : jusqu'où `--no-kv-offload` remonte-t-il la
  fenêtre, et à quel coût en tokens/s ? À mesurer en budget de TOURS, pas de secondes.
- `--cache-reuse` réduit-il vraiment le coût du préfixe sur une boucle de 12 à 26 tours ?
- `enable_thinking:false` aide-t-il, ou le raisonnement de gemma est-il utile quand la
  fenêtre n'est plus contrainte ?
- Quel écart de score entre le harnais nu et `pi` — autrement dit, que valent réellement
  ces 1 603 tokens de préambule ?
