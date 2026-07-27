# Récupération fiable des releases GitHub via l'API REST

## Pourquoi pas web_extract ?

Les pages GitHub Releases sont des apps React — `web_extract` renvoie du contenu vide
ou une erreur « Uh oh! Please reload this page ». L'API REST GitHub est la seule méthode
fiable (rate limit : 60 req/h sans clé, suffisant pour une veille hebdomadaire).

## Pattern de base (bloqué en cron)

```bash
# ❌ N'UTILISE PAS — pipe vers python3 déclenche tirith
curl -s 'https://api.github.com/repos/org/repo/releases?per_page=2' | python3 -c "..."
```

## Pattern qui fonctionne en cron

```bash
# 1. Télécharger proprement
# 2. Extraire les infos — méthode fiable

## ⚠️ grep peut échouer sur du JSON compact

L'API GitHub renvoie parfois du JSON sans sauts de ligne (tout sur une seule ligne).
Dans ce cas, `grep -o '"tag_name":"[^"]*"'` ne matche rien car grep lit ligne par ligne.

**Solution fiable : `search_files` (ripgrep)**

```bash
# search_files est fiable même sur JSON minifié — il utilise ripgrep
search_files pattern='"tag_name"' path=/tmp/gh_repo.json context=0
# → tag_name":"v6.3.0.10514"
search_files pattern='"published_at"' path=/tmp/gh_repo.json context=0
# → published_at":"2026-07-18T..."
search_files pattern='"prerelease"' path=/tmp/gh_repo.json context=0
```

## Extraire le changelog — deux méthodes

### Méthode A : depuis le JSON (body field)

```bash
search_files pattern='"body"' path=/tmp/gh_repo.json context=5
```
Le champ `body` contient le changelog complet (Markdown). Attention : il peut être
très long (plusieurs ko). Combine avec `limit=10` pour un aperçu.

### Méthode B : via web_extract sur la page individuelle

Les pages liste `/releases` sont React et échouent avec `web_extract`, mais les
pages individuelles `/releases/tag/vX.Y.Z` rendent assez de contenu statique :

```
web_extract urls=['https://github.com/org/repo/releases/tag/v6.3.0.10514']
```

Utile pour obtenir le changelog formaté quand le body JSON est trop long ou encodé.

## Repos surveillés (écosystème *arr)

| App | Repo | URL API |
|-----|------|---------|
| Radarr | `radarr/radarr` | `https://api.github.com/repos/radarr/radarr/releases?per_page=2` |
| Sonarr | `sonarr/sonarr` | `https://api.github.com/repos/sonarr/sonarr/releases?per_page=2` |
| Prowlarr | `prowlarr/prowlarr` | `https://api.github.com/repos/prowlarr/prowlarr/releases?per_page=2` |
| Bazarr | `morpheus65535/bazarr` | `https://api.github.com/repos/morpheus65535/bazarr/releases?per_page=2` |
| Lidarr | `lidarr/lidarr` | `https://api.github.com/repos/lidarr/lidarr/releases?per_page=2` |
| Readarr | `readarr/readarr` | `https://api.github.com/repos/readarr/readarr/releases?per_page=2` |
| Whisparr | `whisparr/whisparr` | `https://api.github.com/repos/whisparr/whisparr/releases?per_page=2` |
| Recyclarr | `recyclarr/recyclarr` | `https://api.github.com/repos/recyclarr/recyclarr/releases?per_page=2` |
| Configarr | `raydak-labs/configarr` | `https://api.github.com/repos/raydak-labs/configarr/releases?per_page=2` |
| cross-seed | `cross-seed/cross-seed` | `https://api.github.com/repos/cross-seed/cross-seed/releases?per_page=2` |
| autobrr | `autobrr/autobrr` | `https://api.github.com/repos/autobrr/autobrr/releases?per_page=2` |
| Cleanuparr | `Cleanuparr/Cleanuparr` | `https://api.github.com/repos/Cleanuparr/Cleanuparr/releases?per_page=2` |

## Références

- [GitHub REST API — Releases](https://docs.github.com/en/rest/releases/releases)