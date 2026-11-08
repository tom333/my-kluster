# Veille (Dkron)

Remplace Kestra depuis le 2026-11-08. Dkron 4.2.1 en serveur unique (état BoltDB embarqué sur
le PVC `dkron-data`, **aucune base externe**), UI `https://veille.tgu.ovh` (LAN + login GitHub).

| job | quand (heure NC) | fait quoi |
|---|---|---|
| `veille-matin` | 7h00 | `digest.py llm-local harnais-agents` (harnais : jeudi seulement) |
| `emploi-nc` | 7h30 | offres tech/data NC, 15 sources, dédup `/data/etat/emploi_nc_vues.json` |
| `veille-soir` | 20h00 | `digest.py korben decouvertes data-ia 3d-assets arr` (arr : samedi) |
| `watchers` | 7h, 20h | bonsai, moe-cache (scripts tirés du dépôt, état dans `/data/etat`) |
| `sentinelle` | 21h00 | signale tout job sans succès depuis `metadata.age_max_h` |
| `sync-jobs` | toutes les 10 min | aligne Dkron sur `code/jobs.json` |

## Comment ça marche

- **Le code** (`code/`) arrive par un ConfigMap généré depuis git, monté en `/code`, à nom fixe :
  il se met à jour en place (~1 min) sans redémarrer Dkron. Python stdlib, aucun paquet.
- **Les jobs** sont définis dans `code/jobs.json` (format de l'API Dkron, cron à 6 champs avec
  secondes, `timezone: Pacific/Noumea`). Appliqués au démarrage du pod (`postStart`) puis toutes
  les 10 min par `sync-jobs` ; un job retiré du fichier est supprimé.
- **Un créneau = un job** qui enchaîne ses thèmes en série dans un seul processus : gemma est
  chargé une fois et aucun digest ne l'évince. Un thème en échec n'arrête pas les suivants.
  (Le chaînage natif `parent_job` de Dkron s'arrête au premier échec : écarté.)
- **Ajouter un thème** : une catégorie Miniflux + une entrée dans `code/themes.json` + son nom
  dans la commande du job du créneau voulu.

## Alertes

- Chaque script attrape ses exceptions et envoie `🚨 Veille : … en échec` sur Telegram, puis
  sort en code 1 (exécution en échec dans Dkron).
- Le webhook natif de Dkron n'est **pas** utilisé : il part après **chaque** exécution, réussie
  ou non (`SendPostNotifications`, sans filtre).
- `sentinelle` couvre le cas muet : un job qui ne tourne plus du tout.

## Pièges

- Dkron affiche les heures de `next` en **UTC** (07h NC = 20:00Z la veille).
- Raft en nœud unique : `--bind-addr=127.0.0.1` pour une identité stable ; avec l'IP du pod,
  qui change à chaque redémarrage, le nœud refuse de s'élire.
- L'exécuteur shell hérite de l'environnement du pod (`append(os.Environ(), env...)`) : les
  secrets passent par `envFrom: veille-secrets`, jamais par `executor_config.env`.
- Tester un job : `POST /v1/jobs/<nom>` (lancement immédiat), sortie dans
  `GET /v1/jobs/<nom>/executions` (256 Ko max, tampon circulaire).
