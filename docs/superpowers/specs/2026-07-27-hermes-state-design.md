# hermes-state — réconciliation Git ↔ PVC de la configuration Hermes

**Date** : 2026-07-27
**Statut** : conception validée, non implémentée

---

## 1. Problème

Hermes possède son état et le réécrit. Le dépôt veut que Git soit la vérité. Aujourd'hui la
collision est résolue par la force (un initContainer réécrit `config.yaml` à chaque boot) et par
des copies manuelles (`kubectl cp` documenté dans `hermes-runtime/README.md`). Les deux fuient.

### Constats mesurés (audit du 2026-07-27)

| Artefact | État réel |
|---|---|
| `config.yaml` | **divergent structurellement** : 2 152 o dans le pod contre ~7 500 o en Git, réécrit **42 h après le démarrage du pod**, clés ajoutées par Hermes (`plugins`, `_config_version: 33`, `onboarding`), commentaires supprimés |
| `jobs.json` | **8 crons, ~18 000 caractères de prompts, zéro Git.** Perte du PVC = perte de tout le travail de veille |
| skill `veille-digest` | présent sur le PVC, **versionné nulle part**, alors qu'il alimente le pipeline d'éval |
| `index_digests.py` | **divergent** entre PVC et Git, sans savoir quelle version fait foi |
| `bonsai_watch.py` | identique, mais **non suivi** par Git (`?? scripts/bonsai-watcher/`) |
| `SOUL.md`, `HERMES.md`, 2 skills | identiques — le miroir manuel est en phase *par chance*, rien ne le garantit |

Le `README.md` de `hermes-runtime/` dit lui-même que ces fichiers « ne sont **pas** appliqués
automatiquement ». Rien ne compare Git au PVC : la dérive n'est pas détectable.

### Ce que l'usage réel impose

Sur 52 jours et 236 sessions : **206 sessions de cron (87 %)** contre 27 de Telegram. Les crons
sont le cœur de la valeur. Or c'est justement l'artefact le moins protégé, et celui qui s'édite
le plus confortablement **dans le dashboard**. Toute solution qui interdit l'édition au dashboard
dégrade l'usage principal pour satisfaire un principe.

---

## 2. Décision : réconciliation asymétrique

Ne pas trancher globalement « qui gagne ». Déclarer la propriété **artefact par artefact**.

- **`owner: git`** — Git fait foi. `apply` écrase le pod.
- **`owner: hermes`** — le pod fait foi. `export` capture vers Git pour l'historique et la
  sauvegarde ; `apply` n'y touche **jamais**.

Conséquence directe : tu continues d'éditer tes crons au dashboard, et Git les capture seul.
Aucun geste nouveau sur la partie la plus utilisée.

---

## 3. Composants

### 3.1 Emplacement

`scripts/hermes-state/` — exécuté sur `pc`, seule machine disposant de kubectl **et** du dépôt.
Script Python `uv` PEP723 (même convention que `scripts/eval-harness/hf-discover.py`) : la
comparaison sémantique YAML et la normalisation JSON excluent une solution shell.

Transport : `kubectl exec` / `kubectl cp`, pattern déjà éprouvé par
`scripts/eval-harness/publish-queue-status.sh`, y compris le `chown 10000:10000` obligatoire
(`kubectl exec` tourne en root, l'agent en uid 10000 — sans chown, le fichier écrit est
invisible pour l'agent, sans aucune erreur).

### 3.2 Le manifeste

`scripts/hermes-state/manifest.yaml` — source unique de la propriété. Schéma :

```yaml
artifacts:
  - name: soul                       # identifiant court, utilisé dans les sorties
    pod: /opt/data/SOUL.md           # chemin dans le conteneur `main`
    git: hermes-runtime/SOUL.md      # chemin relatif à la racine du dépôt
    owner: git                       # git | hermes
    mode: text                       # text | tree | yaml-subset | json-spec | json
    also: []                         # destinations supplémentaires (même contenu)
    restart_required: false          # apply le signale, ne l'exécute jamais
```

Contenu initial :

| name | pod | git | owner | mode | restart |
|---|---|---|---|---|---|
| `soul` | `/opt/data/SOUL.md` | `hermes-runtime/SOUL.md` | git | text | non |
| `hermes-md` | `/workspace/HERMES.md` (+ `also: /workspace/AGENTS.md`) | `hermes-runtime/HERMES.md` | git | text | non |
| `skill-eval-modeles` | `/opt/data/skills/eval-modeles/SKILL.md` | `hermes-runtime/skills/eval-modeles.SKILL.md` | git | text | non |
| `skill-decouvertes` | `/opt/data/skills/decouvertes/SKILL.md` | `hermes-runtime/skills/decouvertes.SKILL.md` | git | text | non |
| `skill-web-fetch` | `/opt/data/skills/web-fetch/SKILL.md` | `hermes-runtime/skills/web-fetch.SKILL.md` | git | text | non |
| `skill-veille-digest` | `/opt/data/skills/veille-digest/` | `hermes-runtime/skills/veille-digest/` | git | **tree** | non |
| `script-index-digests` | `/opt/data/scripts/index_digests.py` | `scripts/veille-digest-indexer/index_digests.py` | git | text | non |
| `script-index-telegram` | `/opt/data/scripts/index_telegram.py` | `scripts/telegram-indexer/index_telegram.py` | git | text | non |
| `script-bonsai-watch` | `/opt/data/scripts/bonsai_watch.py` | `scripts/bonsai-watcher/bonsai_watch.py` | git | text | non |
| `config` | `/opt/data/config.yaml` | *(bloc `config.yaml` de `argocd/argocd-apps/hermes-agent-app.yaml`)* | git | yaml-subset | **oui** |
| `crons` | `/opt/data/cron/jobs.json` | `hermes-runtime/state/jobs.json` | hermes | json-spec | — |
| `seen-state` | `/opt/data/seen-*.json` | `hermes-runtime/state/seen/` | hermes | json | — |

Deux notes sur ce tableau :

- `skill-veille-digest` et `script-bonsai-watch` sont `owner: git` mais **absents de Git** au
  départ. Leur première capture passe par `export --adopt` (cf. §4).
- `config` n'a pas de fichier Git dédié : sa source est le bloc YAML inline du manifeste ArgoCD.
  L'outil l'extrait pour comparer, et **ne l'applique jamais** — écrire `config.yaml` dans le pod
  créerait un second chemin d'écriture concurrent de l'initContainer et d'ArgoCD, pour un effet
  nul puisque Hermes réécrit le fichier à chaud de toute façon. `apply` sur `config` est donc
  refusé explicitement, pas silencieusement ignoré. Seul `diff` a du sens.
  Son `restart_required: true` porte sur le **chemin normal** : tu édites le bloc dans Git, ArgoCD
  sync le ConfigMap, et il faut un redémarrage du pod pour que l'initContainer le re-seede. `diff`
  le rappelle quand il détecte un écart sur cet artefact.

### 3.3 Modes de comparaison

**`text`** — un fichier, comparaison d'octets après normalisation des fins de ligne.

**`tree`** — un répertoire entier, nécessaire pour `veille-digest` qui contient `SKILL.md` **et**
`references/github-releases-api.md`. Comparaison fichier par fichier sur l'union des deux arbres ;
un fichier présent d'un seul côté est une dérive. `apply` en mode `tree` **n'efface pas** les
fichiers surnuméraires du pod : il les signale. Supprimer des fichiers dans le pod depuis Git est
un pouvoir qu'on ne donne pas à une commande de synchronisation.

**`yaml-subset`** — pour `config.yaml`. On compare **uniquement les clés déclarées côté Git**,
récursivement. Toute clé présente dans le pod et absente de Git est ignorée. Justification : Hermes
ajoute `_config_version`, `plugins`, `onboarding` et supprime les commentaires à chaque réécriture.
Une comparaison stricte signalerait une dérive permanente, l'outil deviendrait du bruit et
cesserait d'être lu. Ce mode répond à « les valeurs que je déclare sont-elles respectées ? », qui
est la vraie question.

**`json-spec`** — pour `jobs.json`. Le fichier est un objet `{"jobs": [...], "updated_at": …}`.
Export de la **définition seule**. Décomptes vérifiés sur les 8 jobs réels : 30 champs distincts,
dont 21 de définition et 9 volatils.

```
racine    : `jobs` conservé ; `updated_at` ÉCARTÉ (réécrit à chaque sauvegarde)

conservés (21) : id, name, schedule, schedule_display, prompt, model, provider, base_url,
                 skill, skills, script, enabled, deliver, workdir, context_from,
                 enabled_toolsets, no_agent, repeat, profile, origin, created_at
écartés (9)    : last_run_at, next_run_at, last_status, last_error, last_delivery_error,
                 fire_claim, paused_at, paused_reason, state
```

Sortie : JSON trié par `id`, clés triées, indenté 2, saut de ligne final. Sans cette
normalisation, `next_run_at` et `updated_at` changent en permanence et l'export produit un commit
quotidien vide de sens. Avec elle, **un commit n'apparaît que si un prompt ou un horaire a
changé** — c'est exactement l'historique manquant.

Un champ inconnu apparaissant dans une future version de Hermes est **conservé** et signalé sur
stderr : mieux vaut capturer un champ de trop qu'en perdre un silencieusement. Seule la liste des
9 volatils est en dur.

Le `chat_id` Telegram (`843341688`) est capturé tel quel : il figure déjà en clair dans 8 scripts
committés du dépôt, le capturer n'ajoute aucune exposition et garde l'export directement
restaurable.

**`json`** — pour `seen-*.json` : JSON trié, sans filtrage de champs.

### 3.4 Interface

```
hermes-state diff
    Compare les deux classes. Une ligne par artefact :
        =  identique        ~  diverge
        +  absent du pod    -  absent de Git
    Code retour : 0 si tout est aligné, 1 s'il existe au moins une dérive,
    2 en cas d'erreur d'accès. Utilisable en cron et en CI.

hermes-state export [--adopt] [--commit]
    pod → Git, artefacts owner=hermes. Normalise selon `mode`.
    N'écrit un fichier que si le contenu normalisé change.
    --adopt : capture aussi les artefacts owner=git absents de Git (amorçage).
    --commit : git add des chemins concernés + commit + push (cf. §5).

hermes-state apply [--only <name>...] --yes
    Git → pod, artefacts owner=git UNIQUEMENT. Refuse explicitement owner=hermes,
    et refuse `config` (voir §3.2 : son seul chemin d'écriture est ArgoCD + boot).
    Écriture atomique (fichier temporaire dans le pod puis `mv`), puis
    chown 10000:10000, puis relecture de vérification.
    Affiche la liste des artefacts dont restart_required=true, sans redémarrer.
    Sans --yes : dry-run détaillé.
```

`apply` ne touche jamais un artefact `owner: hermes`. C'est la garantie qu'une commande mal tapée
ne peut pas détruire un cron édité au dashboard.

---

## 4. Flux de données

```
cron quotidien (pc)
  export --commit ──▶ lit jobs.json + seen-*.json via kubectl exec
                  ──▶ normalise (json-spec / json)
                  ──▶ écrit hermes-runtime/state/  SI le contenu change
                  ──▶ git add <ces chemins> + commit + push
                  ──▶ notification Telegram en cas d'échec uniquement

à la demande
  diff            ──▶ « ~ script-index-digests diverge »
                      « - skill-veille-digest absent de Git »
  apply --yes     ──▶ écrit les artefacts owner=git + chown + vérifie
                  ──▶ « config nécessite un redémarrage du pod (non effectué) »
```

Amorçage, une fois : `export --adopt --commit` capture `veille-digest` et `bonsai_watch.py`, puis
`diff` doit rendre `=` partout sauf `script-index-digests`, dont la divergence est une décision
humaine à trancher (cf. §8).

---

## 5. Politique de commit automatique

Le cron commit **sur `main`**, et pousse. Un commit local seul ne protégerait de rien : la
perte du poste emporterait l'historique, alors que la protection est l'objectif.

Garde-fous, tous nécessaires :

- `git add` et `git commit` portent **exclusivement** sur les chemins exportés. Un working tree
  sale par ailleurs n'est ni committé ni perturbé.
- Si un rebase, un merge ou un cherry-pick est en cours (`.git/REBASE_HEAD`, `MERGE_HEAD`),
  l'outil **n'écrit rien et sort en 2**.
- Si la branche courante n'est pas `main`, il exporte mais ne commit pas.
- Si le `push` échoue (branche divergée), il **abandonne sans forcer** et notifie. Jamais de
  `--force`.
- Identité Git : le dépôt est sous `/data/projets/perso/`, donc compte **perso** (`tom333`),
  résolu par `~/.gitconfig`. L'outil ne pose aucun override.
- Message : `chore(hermes): capture état runtime` suivi de la liste des artefacts changés, par
  exemple `(jobs.json: llm-veille-daily, digest-indexer)`.

---

## 6. Gestion d'erreurs

| Situation | Comportement |
|---|---|
| Pod absent, `Pending` ou `0/1` | sortie 2, aucune écriture, message explicite |
| `kubectl exec` échoue en cours de lecture | l'artefact est marqué en erreur et **ignoré** ; les autres continuent ; sortie 2 en fin de course |
| `jobs.json` lu pendant une écriture d'Hermes (`.jobs.lock` présent) | lecture retentée une fois après 5 s ; si le JSON ne parse toujours pas, artefact ignoré — **jamais de capture d'un fichier tronqué** |
| `apply` : écriture réussie mais `chown` échoue | échec de l'artefact signalé, car un fichier root est invisible pour l'agent sans erreur visible |
| `apply` : la relecture ne correspond pas à la source | échec de l'artefact, sortie non nulle |
| Dérive détectée par le `diff` en cron | **aucune action corrective automatique**. Rapport seul |
| Échec du cron d'export | notification Telegram via le pattern durci de `eval-pipeline.sh` (token lu depuis un fichier, `http_code` vérifié, jamais d'échec silencieux) |

Principe : **aucune écriture partielle, aucune correction implicite.** `diff` observe, `apply`
n'agit que sur demande explicite.

---

## 7. Tests

La contrainte structurante est de pouvoir tester sans écrire dans le pod de production.

**Fonctions pures, testées sur fixtures** — c'est là qu'est la logique :

- `normalize_jobs()` : un `jobs.json` réel (8 jobs) en entrée ; vérifie que les 9 champs
  volatils disparaissent, que les 21 champs de définition subsistent, que la sortie est stable
  (deux appels → octets identiques).
- **Idempotence** : `normalize_jobs(normalize_jobs(x)) == normalize_jobs(x)`.
- **Insensibilité au statut** : deux `jobs.json` ne différant que par `last_run_at`,
  `next_run_at` et la racine `updated_at` produisent une sortie **identique** — c'est la propriété
  qui empêche les commits quotidiens vides. C'est le test le plus important du lot : s'il casse,
  l'auto-commit pollue `main` tous les jours et l'outil devient nuisible.
- **Champ inconnu** : un job portant une clé absente des 30 connues est exporté **avec** cette
  clé, et un avertissement est émis.
- `yaml_subset_diff()` : un `config.yaml` de Git et la version du pod (avec `plugins`,
  `_config_version`, sans commentaires) → **aucune** dérive. Puis en changeant une valeur
  déclarée (`agent.max_turns`) → dérive signalée sur cette clé seule.
- `load_manifest()` : rejette un `owner` inconnu, un `mode` inconnu, un chemin Git en doublon.

**Garde-fous de sûreté, tests unitaires** — les deux vérifiés par injection d'un exécuteur factice
qui échoue s'il est appelé, ce qui prouve qu'aucun `kubectl` n'a lieu :

- `apply` sur un artefact `owner: hermes` lève une erreur.
- `apply` sur `config` lève une erreur.
- `apply` en mode `tree` sur un pod contenant un fichier surnuméraire le **signale** et ne le
  supprime pas.

**Intégration, lecture seule** : `diff` contre le pod réel — sans effet de bord, donc sûr en CI
locale. Sert de test de fumée du transport.

**Non testé automatiquement** : `apply` en écriture réelle. Validé une fois à la main sur un
artefact inoffensif (`web-fetch.SKILL.md`), avec vérification du propriétaire résultant.

---

## 8. Questions laissées ouvertes, volontairement

1. **`index_digests.py` diverge** entre le PVC et Git. Laquelle fait foi ? C'est une décision
   humaine, pas un défaut de l'outil. À trancher avant le premier `apply`, sinon `apply`
   écraserait la version qui tourne. Un `diff` textuel des deux versions doit précéder.
2. **Les `.bak` en cascade** (79 `.env.bak`, 80 `config.yaml.bak`) : leur producteur n'est pas
   identifié — le pod n'a pas redémarré depuis le 2026-07-25 alors que des `.bak` datent du
   2026-07-10, donc l'hypothèse « écrits au boot » ne tient pas. Ne pas construire de purge
   automatique avant d'avoir compris qui écrit.

---

## 9. Hors périmètre

- **Les 3 tokens** de `~/.config/brain/` (Telegram, txtai, LocalAI) : ils ne peuvent pas aller
  dans Git en clair. Problème de sauvegarde chiffrée, pas de réconciliation. Le pattern existe
  déjà (rôle Ansible `sealed-secrets-backup`, `age` vers le NAS) — projet distinct.
- **`state.db`** (331 Mo) : état d'exécution, pas configuration.
- **Élagage des 67 skills upstream**, rotation du token `arrconf`, purge des `.bak` : actions
  mécaniques immédiates, sans conception. Traitées hors de cette spec.
- **Opérations cluster depuis Hermes** : abandonné. L'audit montre que c'est le travail de
  Claude Code, déjà outillé, et qu'un token de ServiceAccount dans ce pod vaudrait cluster-admin
  puisque l'addon RBAC de MicroK8s est désactivé.

---

## 10. Alternatives écartées

**Tout déclaratif** — rendre `jobs.json` depuis un YAML Git, appliqué au boot comme `config.yaml`.
Écartée pour une raison technique, pas de préférence : `jobs.json` **mélange spécification et
statut dans le même objet** (`prompt`, `schedule`, `script` côtoient `last_run_at`, `next_run_at`,
`fire_claim`, `last_status`). Le rendre depuis Git écraserait l'état d'ordonnancement à chaque
boot, et Hermes n'offre aucune séparation spec/status. En prime, cela supprimerait l'édition au
dashboard, c'est-à-dire l'ergonomie de l'usage majoritaire.

**Sauvegarde seule** — instantané périodique vers le NAS, sans `diff` ni `apply`. Supprime le
risque de perte catastrophique pour un coût quasi nul, mais n'apporte aucune visibilité sur la
dérive — or la dérive est un fait mesuré, pas une hypothèse. Reste un repli acceptable si
l'implémentation complète devait être repoussée.

---

## 11. Effets de bord attendus

- `hermes-runtime/README.md` devient obsolète : la procédure manuelle de `kubectl cp` est
  remplacée par `hermes-state apply`. À réécrire dans la même livraison, en conservant
  l'avertissement sur l'uid 10000, qui reste vrai.
- Nouveau répertoire `hermes-runtime/state/`, dont le contenu est **généré** : à signaler comme
  tel dans le README pour que personne ne l'édite à la main.
- Un cron de plus sur `pc`. La planification du poste n'est toujours pas reproductible depuis Git
  (constat de l'audit) ; ce projet ne corrige pas ce point et ne l'aggrave pas.
