---
name: veille-digest
title: Veille web périodique → digest Telegram
description: "Veille web récurrente, dédup par mémoire → digest Telegram."
version: 1.5.0
author: tom333
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [veille, monitoring, web, telegram, digest, rss, dedup, news]
    category: research
    requires_toolsets: [web]
---

# Veille web périodique → digest Telegram

Procédure réutilisable pour TOUT job de veille récurrent : collecter des infos web
sur un thème, ne garder QUE les nouveautés, produire un résumé concis livré sur Telegram.

Le job appelant fournit : le **thème**, les **sources**, le **format de sortie**, et le
message « rien de neuf ». Cette procédure porte le reste (dédup mémoire, discipline
outils, règles de liens, discipline de sortie).

## When To Use This Skill

- Cron de veille quotidienne/hebdomadaire sur un sujet (tech, emploi, RSS, releases…)
- Tout digest récurrent qui doit éviter de répéter ce qui a déjà été envoyé
- Tout job « résume les nouveautés et envoie sur Telegram »

## Procédure

> ⚠️ **Ce skill est déjà dans ton contexte.** N'essaie pas de le charger : il n'existe
> aucun outil pour ça. Constaté le 2026-07-29 dans `agent.log` — un appel à
> `mcp__arrconf__get_prompt` avec `veille-digest` a échoué (`Unknown prompt`), un tour
> gâché par exécution de cron. `arrconf` sert la configuration des *arr, rien d'autre.

### 1. Dédup — via le second-brain txtai (tool `mcp__txtai__search_search_get`)
- Tu disposes du tool **`mcp__txtai__search_search_get`** — index de TOUS tes digests de veille passés
  (bien plus fiable que le contexte, qui se fait compacter entre runs).
- Pour CHAQUE item candidat (AVANT de l'inclure dans le digest), interroge-le :
  `select text,date from txtai where similar('<titre ou sujet de l item>') and source='veille' limit 3`
  → si un digest passé couvre déjà ce sujet/lien, **skip-le** (pas nouveau).
- Ne rapporte QUE les items sans correspondance = les **vraies nouveautés** sur tout l'historique.
- ⚠️ N'écris AUCUN fichier, ne crée AUCUN script. La dédup = requêtes `mcp__txtai__search_search_get`, point.
- Sujet jamais vu (aucune correspondance txtai) = rapporté normalement.

### 2. Collecte — releases GitHub et listes awesome (outils `mcp__veille__*`)

Tu disposes de trois outils qui parlent à l'API GitHub à ta place. **Utilise-les en
premier** : le filtrage par date se fait côté serveur, tu reçois quelques lignes au lieu
des ~200 000 caractères tronqués que `web_extract` ramenait pour un seul dépôt.

- `mcp__veille__releases_recentes(jours)` — les releases publiées dans la fenêtre, sur
  les dépôts suivis. Rend dépôt, version, date, url, début des notes.
- `mcp__veille__ajouts_listes(jours)` — les projets **ajoutés** aux listes awesome
  suivies, avec leur section. Source de découverte déjà structurée.
- `mcp__veille__depot("owner/repo")` — métadonnées d'un dépôt : étoiles, langage,
  dernière poussée, `archive`. Sert à écarter un projet mort sans le rapporter.

La liste des dépôts et des listes suivis vit dans `sources.json` du serveur
(`argocd/argocd-apps/veille-mcp-app.yaml`), pas dans le prompt du job : **ne les
énumère pas ici**, appelle l'outil sans argument de dépôt.

Les deux outils de collecte rendent un champ `erreurs` par source : s'il est non vide,
mentionne la source en défaut en une ligne dans le digest plutôt que de la passer sous
silence.

Un dépôt HORS de `sources.json` (ex. un projet découvert en cours de run) n'est pas
couvert par `releases_recentes` — tombe alors sur la méthode `curl` de la section ⚠️.

**Alternative pour le changelog** : après avoir identifié la version via l'API, tu peux
extraire le changelog détaillé via `web_extract` sur l'URL individuelle de la release :
`https://github.com/org/repo/releases/tag/vX.Y.Z`. Contrairement à la page liste
(`/releases`), les pages individuelles rendent assez de contenu statique pour que
`web_extract` récupère la description des changements.

### 3. Collecte — pages web
- **Pages listées explicitement par le job** : `web_extract` sur l'URL EXACTE.
  N'utilise JAMAIS `web_search` pour une page listée — va lire la page directement.
  `browser_navigate` UNIQUEMENT si `web_extract` rend vide (et si le toolset browser est dispo).
- **Tendances communautaires** : `web_search` sur Reddit (r/selfhosted, r/sonarr, r/radarr),
  forums, blogs. Utile pour détecter des discussions, problèmes de sécurité, ou breaking changes.
- **Outils MCP disponibles** : si le job surveille un déploiement local, utilise les
  outils MCP disponibles (ex: `mcp__arrconf__*`) pour obtenir l'état : bibliothèque,
  file d'attente, téléchargements bloqués, vitesses de transfert.
- Sites à connexion/anti-bot (LinkedIn, Indeed…) : ignore-les.

### 3quater. Collecte — signal d'engagement communautaire (Reddit RSS + HN Algolia)

`web_search` retourne ce qu'un moteur indexe. Ces deux sources retournent ce que des gens
ont **voté**, ce qui est un signal différent et souvent plus précoce : sur les quants, les
runtimes et les modèles locaux, quelqu'un a déjà essayé avant toi et dit si ça marche.
Aucune clé, aucune dépendance à installer.

```bash
# Reddit — RSS public, remplace <sub> (ex: LocalLLaMA, selfhosted). t=day|week
curl -sL 'https://www.reddit.com/r/<sub>/top/.rss?t=day' -o /tmp/reddit_<sub>.xml

# Hacker News — API Algolia publique, triée par date, filtrable sur les points
curl -sL 'https://hn.algolia.com/api/v1/search_by_date?query=<terme>&numericFilters=points>20' \
  -o /tmp/hn_<terme>.json
```

- Extrais titre + URL + score (`ups` dans le RSS Reddit, `points` chez HN) et **classe par
  score**. Un item très voté vaut plus qu'un item bien référencé.
- Le RSS Reddit est du XML : lis-le avec `search_files` (ripgrep), pas avec `grep -o` — même
  raison que pour le JSON compact de GitHub (cf. Common Mistakes).
- **Ces sources servent à hiérarchiser, pas à conclure.** Un fil très voté reste une
  opinion : le contrôle obligatoire de la section 3ter et le harness d'éval tranchent.
- Dédup normale via `mcp__txtai__search_search_get` avant de rapporter.

### 3bis. Collecte — vidéos YouTube (yt-dlp), QUAND le thème s'y prête
- `yt-dlp` est sur $PATH. Utilise-le UNIQUEMENT si des vidéos récentes peuvent enrichir
  le thème (LLM, data/IA, outils, self-host, releases…). Thèmes sans vidéo pertinente
  (offres d'emploi locales, etc.) : **SAUTE** cette étape.
- Chercher des vidéos récentes (mode cron : `terminal` puis `read_file`, JAMAIS de pipe) :
  `yt-dlp "ytsearch6:<sujet + mots-clés>" --skip-download --dateafter now-14days --print "%(id)s ||| %(title)s ||| %(upload_date)s ||| %(channel)s"`
- Déduplique chaque candidat via `mcp__txtai__search_search_get`
  (`select text from txtai where similar('<titre>') and source in ('veille','youtube') limit 3`) → skip les déjà-vus.
- Pour 1-2 vidéos VRAIMENT pertinentes, récupère le transcript (fichier puis `read_file`) :
  `mkdir -p /tmp/yt && yt-dlp --skip-download --write-auto-subs --sub-langs "fr.*,en.*" --convert-subs srt -o "/tmp/yt/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=<ID>"`
  puis `read_file` sur le `.srt`. Résume les points clés dans le digest **avec le lien**.
- TOUJOURS `--skip-download` (jamais la vidéo). **Max 1-2 transcripts/run** (coût/temps).

### 3. Liens — règle stricte
- Récupère le VRAI lien (attribut `href`) de chaque item.
- Ne RECONSTRUIS JAMAIS une URL depuis le texte du lien.
- Pas de href fiable → mets l'URL de la page source. N'invente jamais d'URL.

### 4. Consigner dans la mémoire (tool `mcp__hindsight__retain`)

⚠️ CET ORDRE EST VOLONTAIRE : consigner vient AVANT la sortie Telegram.

Livrer le digest est ta réponse finale, et une réponse finale TERMINE LE TOUR — tout ce
qui est demandé « après » n'arrive jamais. Constaté le 2026-08-10 : deux exécutions de
suite ont ignoré cette étape quand elle était placée après la livraison, alors que le
modèle allait bien chercher l'outil. Inversée, elle est appelée du premier coup. C'est
le même mécanisme que le contrat de terminaison d'un harnais : ce qui suit la réponse
finale n'existe pas.

Donc : quand le digest est RÉDIGÉ et avant de l'envoyer, appelle

```
mcp__hindsight__retain(
  content = <le digest que tu vas livrer, en texte>,
  context = "veille",
  tags    = [<le nom du job>]
)
```

L'outil n'est PAS visible par défaut — il est différé. Va le chercher avec
`tool_search`, comme tu le fais pour les outils `mcp__veille__*`.

Puis livre le digest, sans mentionner cet appel.

POURQUOI. Le digest part sur Telegram et s'y perd : rien ne le rend interrogeable trois
mois plus tard. Hindsight en extrait des faits atomiques, datés et reliés — « quand
ai-je vu passer X pour la première fois ? » devient une question à laquelle on peut
répondre. La déduplication txtai de l'étape 1 évite de REDIRE deux fois la même chose ;
celle-ci évite de PERDRE ce qui a été dit.

⚠️ NE RETIENS RIEN si le digest est un « rien de neuf ». Un `retain` coûte environ
70 secondes de GPU sur le modèle local (mesuré le 2026-08-10), et consigner une absence
n'apprend rien tout en évinçant le modèle pour les autres usages.

⚠️ Une source en ERREUR n'est pas une source vide : si tu as signalé une source non
consultée, dis-le aussi dans ce que tu retiens. Un trou connu vaut mieux qu'un silence
pris pour une absence de nouveauté.

`retain` est ASYNCHRONE : il rend la main immédiatement (mesuré à 0,02 s), l'extraction
se fait en tâche de fond. N'attends pas sa réponse et ne la commente pas.

### 5. Sortie Telegram
- Livre UNIQUEMENT le résultat final. PAS de plan, PAS de next_steps, PAS de JSON
  brut, PAS de description de ta démarche.
- Suis exactement le format demandé par le job.
- Si AUCUN item nouveau vs le digest précédent : envoie uniquement le message
  « rien de neuf » fourni par le job. Rien d'autre.

### 3ter. Candidat modèle local (veille modèles/LLM uniquement, sinon SAUTE)

Le modèle courant est celui vers lequel pointe l'alias `current` de LocalAI
(`charts/localai/values.yaml`) — **ne code JAMAIS son nom en dur ici**, il change. Au
2026-07-29 : `gemma-4-12b-it-qat`, mesuré jusqu'à 41/44 sur le scénario `tetris` du banc
`scripts/harness-bench`.

Si tu repères un modèle **local-exécutable** (GGUF dispo, ~≤12 GB en Q4, orienté
coding/agentic) qui SEMBLE dépasser le courant, applique d'abord le **contrôle
obligatoire** ci-dessous, puis ajoute en FIN de digest UNE ligne copiable :

`CANDIDAT: <name>|<gguf-url-du-FICHIER>|<provenance>[|<draft-url>|<ctx>]`

- `<gguf-url-du-FICHIER>` = l'URL du **.gguf précis**, jamais celle du dépôt. Unsloth
  documente que `Q4_0` est **moins bon** que `UD-Q4_K_XL` **malgré une taille
  supérieure** : le choix du fichier décide autant que le modèle.
- **Compte les transformations empilées, et REJETTE au-delà d'une.** Chaque
  transformation est une perte non mesurée : élagage (`REAP`, `pruned`), abliteration
  (`abliterated`, `heretic`), fusion (`merge`, `slerp`), distillation, quantification
  exotique non documentée. La quantification standard (`Q4_K_M`, `UD-Q4_K_XL`…) ne compte
  pas — c'est le format normal. Vu le 2026-07-31 :
  `lmcoleman/Laguna-XS-2.1-REAP50-MagicQuant-GGUF` empilait **élagage de la moitié des
  experts MoE + une méthode de quantification non documentée**, sur un excellent modèle de
  base (`poolside/Laguna-XS-2.1`, 29 567 dl). Signale plutôt le **modèle de base** et
  attends un quant standard.
- **Regarde qui a validé le dépôt.** Un re-quant à **112 téléchargements et 0 like créé
  l'avant-veille** n'a été éprouvé par personne. Compare toujours au dépôt de base : si
  l'écart est de deux ordres de grandeur, c'est un travail non validé, pas une trouvaille.
- **Vérifie que le backend sait lire l'architecture, et DEPUIS QUAND.** Même piège que le
  Q2_0 de bonsai. Si l'API HF annonce une `architecture` inhabituelle (`laguna`, `nanbeige`,
  `bonsai`…), cherche le PR de support dans `ggml-org/llama.cpp` et compare sa date de merge
  à celle de l'image backend en place (`latest-gpu-nvidia-cuda-12-llama-cpp` sur quay).
  Exemple : le support Laguna a été mergé le 28/07, l'image datait du 15/07 → **illisible**.
- `<provenance>` = `officiel` ou `finetune`. Un finetune peut garder la compétence en
  code et **casser le template d'appel d'outil** : mesuré le 2026-07-29 sur
  `yuxinlu1/gemma-4-12B-coder-…`, qui écrivait 17/44 de code correct dans son message de
  chat sans jamais appeler `write`. Un `finetune` n'est pas disqualifié, mais il doit
  être signalé comme tel.
- Ne JUGE pas sur les benchmarks annoncés (SWE-bench, ToolCall-N…) : ils n'ont rien
  prédit. `qwopus3.5-9b` annonçait 53,89 % SWE-bench Verified et fait 20/44 au banc.
  Le harness d'éval tranche.
- 1 seule ligne CANDIDAT/digest max (le plus prometteur). Pas de GGUF / trop gros /
  backend exotique (ex: ternaire Q2_0 non-mergé) → n'émets RIEN.

#### Contrôle obligatoire avant d'émettre un CANDIDAT — 1 requête, 0 téléchargement

L'API HF renvoie en une fois les métadonnées du GGUF : `context_length`, la liste
**exacte** des fichiers avec leurs tailles, et le **chat template complet**. C'est ce qui
permet de rejeter un mauvais candidat sans dépenser une seconde de GPU.

```bash
curl -sL 'https://huggingface.co/api/models/<org>/<repo>?full=true' -o /tmp/hf_cand.json
```

Trois vérifications dans le JSON, à reporter dans le digest :

| champ | ce qu'on vérifie | rejet si |
|---|---|---|
| `gguf.context_length` | fenêtre native | `< 32768` |
| `siblings[].rfilename` | le `.gguf` visé existe vraiment, et sa taille | fichier absent, ou > ~10 Go |
| `gguf.chat_template` | contient bien des **tokens d'appel d'outil** (`tool_call`, `<|tool`, `function`, `tool_use`…) | **aucune trace d'outil → REJET, c'est le piège du finetune cassé** |

Si le template ne mentionne pas d'outils, n'émets PAS de CANDIDAT : signale-le en une
ligne dans le digest (« template sans tokens d'appel d'outil → écarté »). C'est le
contrôle qui aurait économisé une demi-journée le 2026-07-29.

## Common Mistakes

- Écrire un fichier d'état ou un script (/tmp, /workspace) → REFUSÉ par le guard, et
  inutile : la dédup est en mémoire (contexte injecté), pas sur disque.
- Prétendre avoir « mis à jour l'état » : il n'y a pas d'état fichier. Ne mens pas.
- Utiliser `web_search` au lieu de `web_extract` sur une page listée → on manque les
  items pourtant présents dans le HTML de la page.
- Reconstruire un lien depuis le texte affiché → lien mort.
- Re-rapporter un item déjà dans le digest précédent → dédup ratée.

### ⚠️ GitHub release pages — ne pas utiliser web_extract

Les pages GitHub Releases (`https://github.com/org/repo/releases`) sont des applis
React dynamiques. `web_extract` échoue systématiquement (contenu vide ou « Uh oh!
Please reload this page »).

Pour les dépôts suivis, la réponse est `mcp__veille__releases_recentes` (section 2).
Ce qui suit ne sert que pour un dépôt **hors** `sources.json` :

```
# 1. Télécharger les 2 dernières releases (pas de pipe vers python3 — bloqué en cron)
curl -sL 'https://api.github.com/repos/org/repo/releases?per_page=2' -o /tmp/gh_repo.json

# 2. Extraire les infos — préférer search_files (ripgrep) à grep
#    grep -o peut échouer sur du JSON compact (pas de retour à la ligne)
#    search_files est fiable même sur JSON minifié :
search_files pattern='"tag_name"' path=/tmp/gh_repo.json context=0
search_files pattern='"published_at"' path=/tmp/gh_repo.json context=0
search_files pattern='"prerelease"' path=/tmp/gh_repo.json context=0
```

**⚠️ `grep` peut échouer sur du JSON compact** — l'API GitHub renvoie parfois
du JSON sans sauts de ligne, ce qui fait que `grep -o '"tag_name":"[^"]*"'` ne
matche rien. Utilise `search_files` (ripgrep) qui est fiable sur tous les formats.

**Alternative pour le changelog** : les pages individuelles de release
(`https://github.com/org/repo/releases/tag/vX.Y.Z`) fonctionnent avec `web_extract`
pour récupérer la description des changements, contrairement à la page liste `/releases`.

**Pas de `curl | python3`** — le pipe vers un interpréteur déclenche le scanner de
sécurité tirith (bloqué en mode cron). Toujours : `curl -o fichier`, puis outil de
lecture séparé (`read_file`, `search_files`, `grep`).

### ⚠️ Restrictions en mode cron job

- `execute_code` est bloqué — pas de scripts Python automatisés.
- `curl | python3` / tout pipe vers interpréteur → bloqué par tirith.
- Utilise `terminal` pour les téléchargements simples, puis `read_file` / `search_files`
  / `grep` pour l'extraction des données.
- `browser_navigate` n'est pas disponible en mode cron.
