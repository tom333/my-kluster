# Plan — Noeud k8s secondaire (X299/7820X) + offload pods (scénario 1)

Date : 2026-07-07

## Objectif
Soulager le noeud primaire `pc` (i5-9400F 6c/6t **saturé** : load ~5.5, swap 100% plein)
en ajoutant le X299/i7-7820X (**8c/16t**, 24→64 Go DDR4, **24/7**) comme **worker
MicroK8s** qui absorbe les **pods CPU/RAM**. La 3060 (idle, 15%) + LocalAI **restent
sur `pc`**. Jeu (rare, qq h/sem) sur le X299 en parallèle du worker.

Décision actée : **scénario 1** (pas de déplacement de GPU — le GPU n'est pas le goulot,
l'IA est idle ; ~90% du gain = déplacer les pods CPU/RAM, commun à tous les scénarios).

## Contraintes (faits)
- **Stockage = `microk8s-hostpath` PARTOUT** (local au noeud), sauf `selfhost/media-nas-pvc`
  (5Ti NFS). SC `nfs-csi` (NAS) dispo mais quasi inutilisée.
  → **Un pod stateful ne migre PAS sans déplacer ses données** (le dir hostpath est sur `pc`).
- **Réseau inter-noeud = 1 GbE** (~125 Mo/s) → **co-localiser les pods data-chatty** ;
  éviter le shuffle cross-noeud (DB↔consumers, S3/DuckLake).
- Node master actuel = `pc` (control-plane). Nouveau worker = `jeux` (X299).
- Jeu **rare** → RAM du X299 dispo pour les pods ~99% du temps.

## Cible
| Noeud | Rôle | Garde |
|---|---|---|
| `pc` (i5, 3060, 62 Go) | master + **LocalAI/GPU** + station dev + ingress (Traefik) + control-plane | infra système |
| `jeux` (7820X, 1050 Ti, →64 Go) | **worker** : pods CPU/RAM offloadés + jeu sporadique | — |

## Phase 0 — Prérequis (avant tout pod)
1. X299 monté + Ubuntu Server 24.04 + rôles `desktop`/`gaming` (déjà écrits) → PC de jeu OK.
2. **+DDR4 → 64 Go** (host des pods).
3. **Join worker** : sur `pc` `microk8s add-node` → sur `jeux` la commande `microk8s join …`.
   (Rôle `k8s-node-bootstrap` : variante worker — pas de re-bootstrap control-plane.)
4. **Label** le worker pour le scheduling ciblé :
   `kubectl label node jeux workload=offload`
5. Vérif : `kubectl get nodes` → `jeux` Ready.
6. **Aucune** app ne bouge tant que Phase 0 pas verte.

## Ne JAMAIS bouger (restent sur `pc`)
- `localai` (GPU 3060), `gpu-operator-resources` (DaemonSets GPU).
- Control-plane : `argocd`, `kube-system`, `cert-manager`, `sealed-secrets`.
- `ingress` (Traefik) : hostPort + IP d'entrée LAN pointée sur `pc` + CrowdSec global.
- Station dev (hors k8s).

## Classement des apps + méthode
Storage → méthode de migration :
- **Stateless** (0 PVC) : `nodeSelector` seul, migre direct.
- **NFS** (`media-nas-pvc` / converti `nfs-csi`) : migre direct (storage réseau).
- **hostpath petit** (config 1-2 Go) : rsync du dir + pin — rapide.
- **hostpath DB/gros** : rsync + pin, à froid (scale 0), **co-localiser consumers**.

| App / ns | Storage | Méthode | Cible | Vague |
|---|---|---|---|---|
| `searxng` | stateless | nodeSelector | jeux | 1 |
| `hermes` (crw, lightpanda) | stateless | nodeSelector | jeux | 1 |
| `piped` | hostpath 2Gi | rsync+pin | jeux | 1 |
| `cv` (qdrant 10Gi + web) | hostpath | rsync+pin, co-loc | jeux | 2 |
| **`selfhost`** (*arr : sonarr/radarr/prowlarr/qbittorrent/jellyfin/seerr/cross-seed/cleanuparr/configarr/suggestarr) | 14× hostpath **petits** (config 1-2Gi) + **media NFS 5Ti** | rsync configs + pin **tout le ns ensemble** (data-chatty + NFS partagé) | jeux | 2 |
| `openwebui` (10Gi+2Gi) | hostpath | rsync+pin (upstream = LocalAI sur pc → **trafic cross-noeud 1GbE**, acceptable, chat léger) | jeux | 3 |
| `ia-lab` (mlflow 10Gi, rustfs 20Gi+2Gi) | hostpath | rsync+pin, **co-loc mlflow+rustfs** (S3) | jeux | 3 |
| `dagster` (postgres 8Gi + models 5Gi) | hostpath DB | rsync+pin à froid, **co-loc postgres+runners** | jeux | 4 |
| `datalab` (postgres 8Gi, qdrant 10Gi) | hostpath DB | rsync+pin à froid, **co-loc avec ses consumers** | jeux | 4 |
| `hermes-agent` (data 10Gi + files 5Gi) | hostpath | rsync+pin à froid | jeux | 4 |
| `shell` (termix), `monitoring` (beszel), `crowdsec` (config/db) | hostpath petit | rsync+pin | jeux | 3 |
| `container-registry` (20Gi) | hostpath | **rester sur pc** (registry local `localhost:32000` bindé pc) ou rsync+pin | pc | — |

> Vérifier les **requests CPU/RAM** par app avant chaque move (`kubectl describe node pc | grep -A30 Allocated`) pour ne pas surcharger `jeux`.

## Procédures génériques

### A. Stateless (0 PVC)
1. Git : ajouter au values/manifest de l'app
   ```yaml
   nodeSelector: { workload: offload }
   ```
2. Commit+push → ArgoCD sync → pod reschedule sur `jeux`. Vérifier `-o wide`.

### B. hostpath (config OU DB) — déplacement des données
> Le dir hostpath est **local à `pc`** : il faut le copier sur `jeux` au **même chemin**.
1. **Repérer le PV + son dir** :
   ```
   kubectl get pvc -n <ns> <pvc> -o jsonpath='{.spec.volumeName}'
   kubectl get pv <pv> -o jsonpath='{.spec.hostPath.path}{"\n"}'
   kubectl get pv <pv> -o yaml | grep -A6 nodeAffinity   # noter si affinité=pc
   ```
2. **Arrêter l'app** (à froid, stop écritures) : replicas→0 via Git (ArgoCD selfHeal), attendre pod terminé.
3. **rsync le dir** `pc → jeux` au même chemin (root requis sous /var/snap) :
   ```
   sudo rsync -aHX --info=progress2 <path>/ \
     -e ssh moi@jeux: --rsync-path="sudo rsync" <path>/
   ```
   (créer le parent sur `jeux` d'abord si besoin.)
4. **Pin** : Git → `nodeSelector: { workload: offload }`. Si le PV a `nodeAffinity=pc`
   → patcher/recréer le PV avec `nodeAffinity=jeux` (même hostPath) sinon le pod reste collé à `pc`.
5. Remonter replicas via Git → ArgoCD sync → pod démarre sur `jeux`, monte le dir copié.
6. **Vérifier données + santé**, puis supprimer l'ancien dir sur `pc` (après validation seulement).

### C. Alternative — convertir en NFS (`nfs-csi`) [non-DB]
Pour les apps non-DB, éviter le pinning : recréer le PVC en `storageClassName: nfs-csi`,
migrer les données une fois → le pod tourne partout (storage NAS). **Pas pour les DB**
(NFS = perf DB médiocre + 1 GbE).

## Co-location 1 GbE (règles)
- `selfhost` : **tout ensemble sur `jeux`** (les *arr se parlent + partagent le media NFS).
- `datalab/postgres` + ses consumers (jupyter, apps) : **même noeud**.
- `dagster/postgres` + runners : **même noeud**.
- `ia-lab` : mlflow + rustfs (S3) **même noeud**.
- `openwebui`→`localai` : reste cross-noeud (chat léger, OK à 1 GbE).

## Mode jeu (X299 = worker + jeu)
Jeu **rare** → les pods CPU tournent pendant le jeu (16 threads, `resources.limits` pour laisser
de la marge). Si session lourde : optionnel
```
kubectl cordon jeux        # + scaler les pods non-critiques, ou rien
# après: kubectl uncordon jeux
```
Vu la fréquence, probablement **rien à faire** (limits suffisent). Pas de GPU k8s sur `jeux`
(1050 Ti = jeu only).

## Rollback (par pod)
1. Git : retirer `nodeSelector` (revert commit) → ArgoCD reschedule sur `pc`.
2. Si données déplacées : rsync retour `jeux → pc` (le dir n'a pas été supprimé tant que non validé).
Chaque migration est **atomique + réversible** (1 app = 1 commit).

## Ordre d'exécution (vagues, 1 pod à la fois)
1. **Vague 1** (stateless + petit hostpath) : searxng, hermes/crw, piped → **valide le worker + la procédure**.
2. **Vague 2** (selfhost bloc + cv) : gros gain pod-count.
3. **Vague 3** (mlflow/rustfs, openwebui, shell/beszel/crowdsec).
4. **Vague 4** (DBs : datalab, dagster, hermes-agent) — à froid, co-loc.
Après chaque : `kubectl get nodes` (charge), `kubectl top pods` si metrics, vérif app.

## Critère de succès
- `pc` : load < 3, swap non saturé, RAM libre > 8 Go.
- Apps offloadées Running sur `jeux`, données intactes.
- LocalAI/ingress/dev inchangés sur `pc`.
