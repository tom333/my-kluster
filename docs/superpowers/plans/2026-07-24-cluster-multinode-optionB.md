# Analyse cluster multi-nœud — ajouter `jeux` (192.168.88.150) comme worker

Date : 2026-07-24 · Révisé : 2026-07-24 (root-cause corrigée, cf. §Correction)

## Objectif
Ajouter la station gaming-PC (`jeux`, 192.168.88.150) comme **nœud worker** k8s pour
offloader le master `pc` (192.168.88.250). Source de vérité = code ArgoCD de ce repo.

---

## ⚠️ Clarification "HA"
Vrai HA MicroK8s = **quorum dqlite = 3 nœuds control-plane** (nombre impair). Avec **2 machines**
tu ne peux PAS avoir de HA. Cible réaliste = **1 control-plane (`pc`) + 1 worker (`jeux`)**.
HA réel plus tard → 3e control-plane. Donc ici : **multi-nœud (master+worker), pas HA.**

---

## 🔴 Correction de diagnostic (2026-07-24)

**Analyse initiale ERRONÉE** : j'avais vu `dqlite` lié à `127.0.0.1:19001`
(`backend/info.yaml` + `cluster.yaml`) et conclu que le master était mal configuré →
il fallait le rebinder (B1) ou tout rebuild (B2). **Faux.**

Doc officielle MicroK8s (configure-host-interfaces) :
> "By default, dqlite will bind to localhost (127.0.0.1). When forming a cluster, dqlite
> will be updated to use the address used in the `microk8s join` command."

Donc :
1. **`127.0.0.1` = défaut normal** d'un mono-nœud, pas une pathologie.
2. **Un worker ne fait PAS tourner dqlite** — il tape l'apiserver du master via un proxy
   local (kubelet/kube-proxy). Le dqlite du master peut rester sur `127.0.0.1`.
3. Le join **ne touche pas** la base ni les données du master. S'il échoue → master intact.

**Conséquence** : B1 (reconfigure dqlite) et B2 (rebuild GitOps) étaient **surdimensionnés**,
bâtis sur une prémisse fausse. Rétrogradés en **fallback** (§B1/B2 plus bas).

### Vraie cause du 501 `[ERROR] not an HA MicroK8s cluster` — ✅ DÉMONTRÉE (2026-07-25)
Test A0 effectué (token frais, channel identique, join `--worker`) → **501 reproduit**.
Hypothèses `/etc/hosts` et token **écartées**. Cause réelle, confirmée sur le master :

- ❌ ~~/etc/hosts / résolution hostname~~ — écarté (501 sur join nu).
- ✅ **Le master tourne sur la pile legacy `etcd + flannel`, addon `ha-cluster` DÉSACTIVÉ.**
  - `snap services microk8s` : `daemon-etcd` **actif**, `daemon-k8s-dqlite` **inactif**, `daemon-flanneld` **actif**.
  - `microk8s status` : `high-availability: no`, `datastore endpoints: 127.0.0.1:12379`. CNI = `flannel.conflist`.
  - Un MicroK8s etcd+flannel **refuse tout join** → 501. C'est **structurel**, pas réseau.

> **Conclusion** : le multinode exige dqlite. Seule voie = `microk8s enable ha-cluster`
> (migre **etcd→dqlite + flannel→calico**). A0 (worker-join simple) est **impossible en l'état**.
> ⚠️ `enable ha-cluster` est **potentiellement destructif** (cf. §Étapes à risque + §Correction).

---

## Option A0 — worker-join propre ⭐ (à tester en premier)

**Risque de casser la prod : quasi-nul** (ne modifie rien sur le master). Zéro downtime,
zéro backup. « Sans risque » ≠ « réussite garantie au 1er essai » : si le 501 persiste,
on itère sur la résolution réseau — toujours sans danger.

### Étapes
1. **`/etc/hosts` des deux côtés** :
   - sur `pc` (.250) : `192.168.88.150  jeux`
   - sur `jeux` (.150) : `192.168.88.250  pc`
2. Vérifier channel identique (`snap list microk8s` → 1.35/stable des deux côtés). ✅ fait.
3. Sur `pc` : `microk8s add-node` → récupérer la ligne `microk8s join .250:25000/<token> --worker`.
4. Sur `jeux` : exécuter ce `join … --worker` (token **frais**, usage unique).
5. Vérifier : `microk8s kubectl get nodes` → `jeux` `Ready`.
6. Labels/taints : `kubectl label node jeux workload=offload` (+ taint éventuel côté jeu).
7. Si échec → lire le log join sur `jeux` + `journalctl -u snap.microk8s.daemon-cluster-agent`
   sur `pc`, identifier la cause réelle, cocher/amender §hypothèses ci-dessus.

### Réversibilité
`microk8s leave` sur `jeux` + `microk8s remove-node jeux` sur `pc`. Master jamais impacté.

---

## Fallback B1 — Reconfig IP dqlite in-place (SI A0 prouve un blocage dqlite structurel)

À ne tenter QUE si le test A0 démontre que le join échoue pour une raison dqlite réelle
(pas juste résolution/token). Risque **élevé** (internals dqlite/certs).

1. **Backup** : `microk8s dbctl backup` (snapshot dqlite) + copie `backend/` + clé sealed.
2. `microk8s stop`.
3. `microk8s.dqlite ... reconfigure` OU édition `backend/info.yaml` + `cluster.yaml` :
   `127.0.0.1:19001` → `192.168.88.250:19001`.
4. Aligner args (`/var/snap/microk8s/current/args/*`) sur `.250`.
5. Certs : SAN apiserver + cert dqlite doivent inclure `.250` (`microk8s refresh-certs`).
6. `microk8s start` → vérif nœud sain, dqlite sur `.250:19001`. Puis A0 (add-node/join).

> ⚠️ Le safety mechanism dqlite refuse de binder une IP absente des interfaces hôte
> (protège le cluster). `.250` étant sur `enp4s0`, OK.

---

## Fallback B2 — Rebuild GitOps (dernier recours)

À ne tenter QUE si A0 ET B1 échouent, ou si on veut repartir propre. Long (~2-4 h),
risque faible mais coûteux. Le repo est fait pour se re-bootstrapper (cf. CLAUDE.md).

### Classification PVC (repo + live, Sablier inclus)

#### 🔴 À sauvegarder + restaurer (irremplaçable)
| PVC (ns) | Taille | Contenu | Note |
|---|---|---|---|
| `data-postgresql-0` (datalab) | 8Gi | DBs applicatives | critique |
| `data-dagster-postgresql-0` (dagster) | 8Gi | metadata runs | Sablier scale-0 mais PVC vit |
| `mlflow-data` (ia-lab) | 10Gi | expériences/modèles | Sablier scale-0 |
| `rustfs-data` (ia-lab) | 20Gi | S3 (DuckLake/artefacts) | critique |
| `hermes-agent-data` (+`-files`) | 10+5Gi | mémoire/cron/workspace | critique |
| `qdrant-storage-*` (datalab, cv) | 10Gi ×2 | vector DBs | ré-embeddable, coûteux |
| **`registry-claim`** (container-registry) | 20Gi | **images custom locales** | ⚠️ Dockerfiles hors-repo (sauf ttyd-ssh) → back up ou re-push |
| `accidents-models-pvc`, `dagster-models-pvc` | — | modèles ML | back up si non-réentraînables |
| `txtai` | — | index sémantique | ré-indexable (~/.claude) mais long |

#### 🟢 Recréables (pas de backup)
- `brain` → git-backed (tom333/brain), re-clone.
- crowdsec, traefik-plugins, searxng, crw, lightpanda, piped, pred → régénérés.
- **arr-stack** → configs SQLite ré-ajoutables ; média = NFS `media-nas-pvc` (5Ti) intact.
- beszel, termix, openwebui (historique chat — back up si tenu).

#### ✅ Hors nœud (survit à tout)
- `media-nas-pvc` (5Ti) = NFS sur NAS.

### Étapes
1. Backup PVC 🔴 → NAS + export/re-push images `localhost:32000/*`.
2. Reset/réinstall MicroK8s (rôle `k8s-node-bootstrap` master).
3. Re-bootstrap ArgoCD : clé sealed → `helm install argocd` → app-of-apps → resync 30 apps.
4. Restore données : par app 🔴, scale 0 → rsync backup → scale up.
5. Re-push images custom.
6. Vérif : 30 apps Synced/Healthy, Sablier, LocalAI GPU, ingress.
7. Add worker (A0).

---

## Recommandation
**Tester A0 (worker-join propre) en premier** — quasi-sans-risque pour la prod, réversible,
zéro backup. Le 501 est presque sûrement un problème de résolution/token, **à démontrer au
test**. B1/B2 = fallback uniquement si A0 révèle un blocage structurel réel.
