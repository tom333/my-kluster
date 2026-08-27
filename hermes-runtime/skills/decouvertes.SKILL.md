---
name: decouvertes
version: 1.2.0
description: Digest QUOTIDIEN de DÉCOUVERTE (exploration ciblée) — surface LARGE pilotée par les facettes de l'user (txtai), pertinence STRICTE. Vise 2-3 pépites relevantes. Silence si vraiment rien.
---

# Découvertes — surface large, pertinence stricte (facet-driven)

But : **te faire découvrir du NEUF pertinent**. Le secret : ratisser **très large** mais **ancré sur les facettes de ton monde** → beaucoup de candidats *pertinents* → garder les 2-3 meilleurs sans baisser la barre. Large ≠ générique.

## Étape 0 — Dériver les FACETTES (via mémoire, OBLIGATOIRE d'abord)
Avant toute recherche, interroge `mcp_txtai_search` (surfaces vault/repo/sessions/telegram) pour extraire **6-10 facettes actives** de l'user : ses projets et intérêts récurrents. Ex typiques (à confirmer/actualiser via txtai, ne pas hardcoder) : LLM & inference locale, self-host/k8s/homelab, agents IA & MCP, data engineering, hardware/GPU, dev tooling, quantization, sécurité self-host… Ces facettes **pilotent** toute la recherche.

## Étape 1 — Sourcing LARGE, multi-angle par facette
Pour **chaque facette**, explore son espace **adjacent et émergent** (pas ce que l'user suit déjà — un cran à côté) sur un MAX de sources. Ratisse fort (budget élevé de recherches, c'est le cœur de la valeur) :
- **Hacker News** : top + best (7j) + **Show HN** + **Ask HN** — et **lis les commentaires** (les meilleurs sous-liens y sont souvent).
- **Reddit** : subreddits mappés aux facettes (r/LocalLLaMA, r/selfhosted, r/homelab, r/kubernetes, r/MachineLearning, r/dataengineering, r/programming…).
- **GitHub trending** : global **+ par topic** (llm, ai-agents, self-hosted, kubernetes…) + nouveaux entrants d'`awesome-*` listes.
- **Hugging Face** : trending models/datasets/**spaces**.
- **Papers with Code** : trending ; **arXiv** : cs.AI/DC/SE/CL + 1 catégorie hors-CS.
- **Lobsters** (tags), **dev.to** top, **Product Hunt**, **changelog.com**, archives newsletters (TLDR…).
- 1-2 **wildcards latéraux** vrais (science, hardware, design) pour la sérendipité pure.

Multi-angle : plusieurs requêtes ciblées par facette, pas un seul passage générique. Privilégie ce qui **décolle** (vélocité stars, une HN, buzz).

## Étape 2 — Filtre STRICT (barre haute restaurée)
Chaque candidat passe les 3 tests, sinon **jette** :
1. **Nouveau** — `mcp_txtai_search` toutes surfaces : déjà connu/traité → jette (sauf angle vraiment neuf).
2. **Pertinent** — mappe à une **facette** de l'user (lien concret), OU est une **pépite de sérendipité exceptionnelle** (rare, à ne pas galvauder). "Juste intéressant en général" **ne suffit PAS**.
3. **Signal** — substance réelle, URL vérifiée `web_extract`. Hype/marketing → jette.

## Étape 3 — Sélection : 2-3 pépites relevantes
Garde les **2-3 meilleurs** en pertinence+nouveauté, **diversité de facettes** (pas 3 fois le même thème). 1 si vraiment qu'un excellent. **Silence (réponse vide) seulement si rien ne passe le filtre strict** — mais avec la surface large, ça doit être rare.

## Étape 4 — Consigner AVANT de livrer (tool `mcp__openviking__remember`)

⚠️ CET ORDRE EST VOLONTAIRE : consigner vient AVANT la sortie Telegram.

Livrer la réponse TERMINE le tour — tout ce qui est demandé « après » n'arrive jamais.
Constaté le 2026-08-10 sur `veille-digest` : deux exécutions de suite ont ignoré l'étape
placée après la livraison, alors que le modèle allait bien chercher l'outil. Inversée,
elle est appelée du premier coup.

Quand les pépites sont choisies et avant d'envoyer :

```
mcp__openviking__remember(
  messages = [{"role": "assistant",
               "content": "Decouvertes du <date>. <les 2-3 pepites en UNE SEULE LIGNE :
                           titre, url, le quoi, le pourquoi toi — separes par des points,
                           sans retour a la ligne>"}]
)
```

Date en clair dans le contenu : OpenViking n'a pas de champ `tags` ni `context`, c'est
le texte lui-meme qui doit porter de quoi s'y retrouver plus tard.

⚠️ NE PASSE PAS LE CONTENU MIS EN FORME. `remember` est atteint à travers l'enveloppe
`tool_call`, donc son contenu doit être encodé en JSON. Les blocs de code, encadrés,
emoji et retours à la ligne CASSENT cet encodage — constaté le 2026-08-21 sur
`veille-3d-assets` : quatre tentatives rejetées d'affilée (« 'arguments' is not valid
JSON: Unterminated string », puis « Invalid control character »), chacune rejouant tout
le contenu dans le contexte, qui a gonflé à 92 148 tokens. Le run a duré 40 minutes et
n'a livré qu'un seul caractère.

Passe donc les FAITS en TEXTE PLAT : une ou deux phrases par trouvaille, sans saut de
ligne, sans bloc de code, sans encadré. OpenViking en extrait de toute façon des
entités et des événements — lui donner du markdown mis en forme n'apporte rien et casse
l'appel. La mise en forme est pour Telegram, pas pour la mémoire.


L'outil n'est PAS visible par défaut, il est différé : va le chercher avec `tool_search`.
`remember` est ASYNCHRONE : il rend la main en 0,06 s (mesuré le 2026-08-27, deux
appels) et répond « Stored N message(s) and committed for memory extraction » —
l'extraction sémantique se fait en tâche de fond. N'attends pas, ne commente pas sa
réponse, appelle-le UNE FOIS et passe à la suite.

POURQUOI ICI EN PARTICULIER. Ce cron est le seul des six à ne pas appliquer
`veille-digest`, donc le seul qui ne consignait rien — vérifié le 2026-08-21, aucun appel
à l'outil de mémoire dans ses journaux alors que les cinq autres en font. Or c'est celui dont les
trouvailles sont les plus volatiles : une pépite adjacente vue une fois et jamais
retrouvée est une pépite perdue.

⚠️ NE RETIENS RIEN si la sortie est vide (rien n'a passé le filtre strict). Un
`remember` mobilise le GPU local pour l'extraction sémantique, et consigner une absence
n'apprend rien.

## Sortie (Telegram)
```
🔭 Découvertes — <date>

1. <titre> — <url>
   Quoi : <1 phrase factuelle>
   Pourquoi TOI : <facette/projet concret touché, ou pourquoi c'est une pépite rare>

2. … (2-3, facettes variées)
```
**Si rien** → **RÉPONSE VIDE, aucun texte** (jamais "rien aujourd'hui").

## Common Mistakes
- ❌ Baisser la pertinence pour remplir → NON. On remplit par la **surface** (plus de candidats), pas en acceptant du tiède.
- ❌ Recherche générique non-ancrée facettes → beaucoup de bruit. Toujours partir des facettes txtai.
- ❌ Ne pas lire les commentaires HN / ne pas suivre les sous-liens → on rate les meilleures trouvailles.
- ❌ Ressortir ce que l'user suit déjà (job des veilles) → ici l'**adjacent** de ses facettes, du neuf.
- ❌ Hallucination : chaque item = URL réelle vérifiée `web_extract`.
