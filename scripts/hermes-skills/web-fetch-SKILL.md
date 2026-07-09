---
name: web-fetch
title: Récupérer / résumer des pages web (le bon outil, sans flailing)
description: "Use when fetching, reading or summarizing web pages / links — especially Hacker News or Reddit."
version: 1.0.0
author: tom333
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [web, fetch, summarize, scrape, hackernews, reddit, extract]
    category: research
    requires_toolsets: [web]
---

# Récupérer / résumer des pages web

`web_extract` EST l'outil pour lire une page (fetch → markdown propre → tu résumes).
Ce skill dit QUAND utiliser l'API d'un site plutôt que scraper, et interdit le
flailing (lancer 10 scripts python quand une extraction échoue).

## When To Use This Skill

- On te demande de lire / résumer / extraire une ou plusieurs **pages web** ou **liens**.
- Un lien **Hacker News** ou **Reddit** est impliqué.
- Un `web_extract` a renvoyé un blocage, du vide, ou un contenu énorme illisible.

## Règles de récupération

### 1. Article / blog / doc normal
- `web_extract` sur l'URL. **Un seul appel suffit** — il rend du markdown propre.

### 2. Hacker News — utilise l'API, NE scrape PAS le HTML
- Un lien `news.ycombinator.com/item?id=<ID>` scrapé = 500 KB de commentaires
  imbriqués (ou page "Sorry." si rate-limit) → illisible.
- À la place : `web_extract` sur **`https://hn.algolia.com/api/v1/items/<ID>`**
  → JSON propre : `title`, `url` (l'article lié), `text` (le post), `children[]`
  (commentaires structurés). Résume la story + les commentaires les plus pertinents.
- Si le lien HN pointe vers un article externe (`url`), tu peux aussi `web_extract`
  cet article pour le fond, + l'API HN pour la discussion.

### 3. Reddit — ajoute `.json`
- Pour `reddit.com/r/.../comments/...` → `web_extract` sur la **même URL + `.json`**
  → JSON structuré (post + commentaires). NE scrape pas le HTML Reddit.

## Anti-flailing (IMPORTANT)

- `web_extract` est l'outil. **N'écris PAS de scripts python** (requests/urllib/
  BeautifulSoup) pour fetch/parser des pages — surtout pas en boucle.
- Si un `web_extract` renvoie un blocage ("Sorry.", captcha), du vide, ou 100 KB+
  de bruit : **1-2 tentatives max**, essaie l'API du site (HN/Reddit ci-dessus),
  sinon **signale** « page <url> non extractible (blocage/anti-bot) » et continue.
- N'invente jamais le contenu d'une page que tu n'as pas pu lire.

## Common Mistakes

- Scraper le HTML d'un item HN → 500 KB imbriqués / "Sorry.". Utilise l'API Algolia.
- Enchaîner des `execute_code` python pour contourner une extraction ratée → boucle
  de 10 scripts. Interdit : essaie l'API, sinon signale.
- Résumer une page bloquée en inventant → jamais.
