# Analyse Option B — cluster multi-nœud (débloquer le join du worker)

Date : 2026-07-24

## Objectif
Ajouter la station gaming-PC (`jeux`, 192.168.88.150) comme **nœud k8s** pour ajouter
de la capacité au cluster. Source de vérité = **code ArgoCD de ce repo** ; PVC surtout
recréables ; seuls quelques-uns portent des données irremplaçables.

## ⚠️ Clarification "HA"
Vrai HA MicroK8s = **quorum dqlite = 3 nœuds control-plane minimum**. Avec **2 machines**
tu ne peux PAS avoir de HA. Cible réaliste = **1 control-plane (station `pc`) + 1 worker
(`jeux`)**. Pour du HA réel plus tard → 3e nœud control-plane (nombre impair). Donc ici :
multi-nœud (master+worker), pas HA.

## Blocage racine (confirmé)
Le dqlite du master est **lié à `127.0.0.1:19001`** (`backend/info.yaml` + `cluster.yaml`) —
jamais clusterisé. Un nœud distant ne peut pas l'atteindre → join refusé
(`[ERROR 501] not an HA MicroK8s cluster`). Il faut que dqlite écoute sur **`192.168.88.250`**.

---

## Deux voies

| | **B1 — Reconfig IP dqlite in-place** | **B2 — Rebuild GitOps** ⭐ |
|---|---|---|
| Principe | Éditer l'adresse dqlite `127.0.0.1`→`.250` sur le cluster vivant | Réinstaller MicroK8s (dqlite lié `.250` d'emblée) + re-bootstrap ArgoCD |
| Downtime | court (~15-30 min) | long (resync 30 apps + re-pull images + restore PVC, ~2-4 h) |
| Risque | **élevé** (internals dqlite/certs ; raté = cluster cassé → rebuild forcé) | **faible** (chemin GitOps prévu ; état déterministe) |
| Données | restent en place | à sauvegarder + restaurer (les irremplaçables) |
| Corrige la fragilité localhost | oui (si réussi) | **oui, proprement** |
| Effort | faible (si ça marche) | élevé mais balisé |

**Reco : B2** — tu ajoutes de la charge + veux un cluster sain pour grandir → autant repartir
sur une base **correctement bindée**, via le chemin GitOps pour lequel le repo est conçu
(cf. section bootstrap du CLAUDE.md). B1 = pari plus rapide mais fragile.

---

## Classification PVC (repo + live, Sablier inclus)

### 🔴 À SAUVEGARDER + restaurer (irremplaçable)
| PVC (ns) | Taille | Contenu | Note |
|---|---|---|---|
| `data-postgresql-0` (datalab) | 8Gi | DBs applicatives | critique |
| `data-dagster-postgresql-0` (dagster) | 8Gi | historique/metadata runs | Sablier scale-0 mais PVC vit |
| `mlflow-data` (ia-lab) | 10Gi | expériences/modèles | Sablier scale-0 |
| `rustfs-data` (ia-lab) | 20Gi | S3 (DuckLake/artefacts) | critique |
| `hermes-agent-data` (+`-files`) | 10+5Gi | mémoire/cron/workspace Hermes | critique |
| `qdrant-storage-*` (datalab, cv) | 10Gi ×2 | vector DBs | ré-embeddable mais coûteux |
| **`registry-claim`** (container-registry) | 20Gi | **images custom locales** | ⚠️ **Dockerfiles hors-repo (sauf ttyd-ssh) → back up ou re-push** |
| `accidents-models-pvc`, `dagster-models-pvc` | — | modèles ML | back up si non-réentraînables |
| `txtai` | — | index sémantique | ré-indexable (~/.claude) mais long |

### 🟢 Recréables (ArgoCD/app régénèrent — pas de backup)
- `brain` → **git-backed** (GitHub tom333/brain), re-clone.
- crowdsec (config/db), traefik-plugins, searxng, crw, lightpanda, piped, pred → régénérés.
- **arr-stack** (sonarr/radarr/prowlarr/qbittorrent/seerr/cleanuparr/configarr/cross-seed/suggestarr) → configs SQLite : ré-ajoutables (indexers/réglages) ; **le média = NFS `media-nas-pvc` (5Ti, sur NAS) → intact**. Back up les configs seulement si tu tiens au setup.
- beszel (historique perdable), termix (SSH configs, petits), openwebui (historique chat — back up si tenu).

### ✅ Hors nœud (survit à tout)
- `media-nas-pvc` (5Ti) = **NFS sur NAS** → aucun impact rebuild.

---

## B2 — Rebuild GitOps (détaillé)

### Pré-checks
- **Clé master Sealed Secrets** backupée (fait 2026-07-24) — SANS elle, rebuild impossible.
- **IP .250 statique** sur `enp4s0` (fait) → au fresh install, dqlite bindera `.250`
  (MicroK8s prend l'IP de la route par défaut). Vérifier `/etc/hosts` ne mappe pas le
  hostname sur 127.0.1.1 (sinon dqlite re-localhost).
- Canal microk8s = **1.35/stable** (défaut rôle corrigé).

### Étapes
1. **Backup PVC 🔴** : pour chaque, `tar`/rsync `/var/snap/microk8s/common/default-storage/<ns>-<pvc>-*` → NAS. + **registry** : `microk8s ctr images export` des `localhost:32000/*` OU re-push après.
2. **Reset/réinstall** MicroK8s sur la station (dqlite lié `.250`). `microk8s reset` (ou snap remove+install). Ré-appliquer le rôle `k8s-node-bootstrap` (master) via Ansible.
3. **Re-bootstrap ArgoCD** : restaurer la clé Sealed Secrets → `helm install argocd` → app-of-apps → ArgoCD resynce **les 30 apps** depuis Git. (Les .disable restent off.)
4. **Restore données** : par app 🔴, scale 0 → rsync le backup dans le nouveau dir PVC → scale up. (Même pattern rsync+pin que le plan offload.)
5. **Re-push images custom** dans la registry locale (ou restaurer registry-claim).
6. **Vérif** : 30 apps Synced/Healthy, Sablier réveille dagster/mlflow/etc, LocalAI GPU, ingress.
7. **Add worker** : `microk8s add-node` → `join --worker` sur `jeux` (dqlite=.250 → **join OK**) → label `workload=offload`.

### Risque
Faible mais **long** ; le point sensible = restore PVC (ordre, dirs) + images registry.
Rollback = les disques station conservent l'ancien default-storage tant que non-wipé.

---

## B1 — Reconfig IP dqlite in-place (alternative rapide/risquée)

1. **Backup** : `microk8s dbctl backup` (snapshot dqlite) + copie `backend/` + clé sealed.
2. `microk8s stop`.
3. Éditer `backend/info.yaml` + `backend/cluster.yaml` : `127.0.0.1:19001` → `192.168.88.250:19001`.
4. Vérifier/aligner les args (`/var/snap/microk8s/current/args/*` : kube-apiserver `--advertise-address`, kubelet `--node-ip`) sur `.250`.
5. Certs : le cert dqlite (`cluster.crt`) + apiserver SAN doivent inclure `.250` (regénérer si besoin : `microk8s refresh-certs`).
6. `microk8s start` → vérifier nœud unique sain, dqlite sur `.250:19001`.
7. `add-node` + `join --worker`.

**Risque élevé** : incohérence certs/args/dqlite → cluster ne démarre plus → restore backup
ou bascule sur B2. Peu supporté officiellement (méthodes communautaires).

---

## Recommandation finale
**B2 (rebuild GitOps)**. Tu veux ajouter de la charge et clusterer → une base dqlite
correctement bindée `.250` est le bon socle, et le repo est **fait pour se re-bootstrapper**.
Le coût = fenêtre de maintenance + backup/restore de ~10 PVC 🔴 (+ images registry). B1 = à
ne tenter que si downtime long impossible ET avec backup pour re-basculer en B2 si ça casse.

## À trancher avant exécution
- Registry `registry-claim` : les images custom sont-elles **rebuildables** (sources ailleurs)
  ou faut-il **exporter/re-push** ? (déterminant pour le backup).
- Fenêtre de maintenance acceptable (~2-4 h) ? (cluster + IA + dev + média down ; HA reste up).
