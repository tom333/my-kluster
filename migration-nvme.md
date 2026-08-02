# Migration vers NVMe — procédure

Ce document décrit la migration de **MicroK8s storage** + **~/projets** vers un NVMe nouvellement installé.

**Hardware cible** : WD Blue SN580 1 TB (ou SN850X selon achat), slot M.2 PCIe 3.0 x4 (Z370 → Gen4 → Gen3 négocié).

**Estimation** : ~2-3h en tout, dont 1h-2h de rsync (selon volume réel).

---

## 1. Pré-requis matériel

Avant de couper la machine :

- [ ] Le NVMe est livré et physiquement présent
- [ ] Vis M.2 disponible (souvent dans la boîte d'origine de la carte mère, sinon vis **M2x3** universelle ~1€)
- [ ] Dissipateur passif M.2 (optionnel mais utile, évite le throttling thermique sous charge soutenue)
- [ ] Boîtier accessible (vis de capot + visse au mur OK)
- [ ] Une session terminal de secours disponible (autre PC, smartphone via SSH) au cas où

---

## 2. Backups avant intervention

Le NVMe lui-même ne peut pas casser de données existantes (elles restent sur sda/sdb). Mais on prend des précautions pour ce qu'on s'apprête à toucher.

```bash
# 1. Backup de la master key Sealed Secrets
#    CRITIQUE : sans elle, impossible de déchiffrer les SealedSecrets en cas de rebuild k8s
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > ~/sealed-secrets-master-$(date +%Y%m%d).key.backup
cp ~/sealed-secrets-master-*.key.backup /media/data/backups/   # double-stockage

# 2. Backup de la SQLite MLflow (expériences)
kubectl -n ia-lab exec deploy/mlflow -c main -- \
  sqlite3 /data/mlflow.db ".backup /tmp/mlflow.db.bak"
kubectl -n ia-lab cp \
  ia-lab/$(kubectl -n ia-lab get pod -l app.kubernetes.io/instance=mlflow -o jsonpath='{.items[0].metadata.name}'):/tmp/mlflow.db.bak \
  /media/data/backups/mlflow-$(date +%Y%m%d).db.bak

# 3. Snapshot ArgoCD apps (au cas où)
kubectl -n argocd get applications -o yaml > /media/data/backups/argocd-apps-$(date +%Y%m%d).yaml

# 4. (Recommandé) Push de toutes les branches locales sur les remotes
cd ~/projets/perso/my-kluster && git status && git push --all 2>&1 | tail -5
# Idem pour tous les autres projets actifs
```

---

## 3. Installation physique

```bash
# 1. Scale down les workloads GPU pour éviter les pods en error pendant l'arrêt
kubectl -n localai scale deploy localai --replicas=0
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\t"}{.spec.containers[*].resources.requests.nvidia\.com/gpu}{"\n"}{end}' | grep -v "^\S*\s*$"

# 2. Arrêt explicite de MicroK8s pour flush etcd proprement.
#    systemd shutdown -h aurait tué le service avec un timeout 90s — pas idéal
#    pour etcd qui doit terminer ses writes en cours.
sudo systemctl stop snap.microk8s.daemon-kubelite
sudo systemctl status snap.microk8s.daemon-kubelite | grep "Active:" | head -1
# Doit afficher "inactive (dead)"

# 3. Stop aussi containerd (qui retient les sockets vers les images en cours d'usage)
sudo systemctl stop snap.microk8s.daemon-containerd

# 4. Shutdown propre
sudo shutdown -h now
```

**Note sur le redémarrage après reboot** : MicroK8s va redémarrer automatiquement
au boot (les services snap sont enabled par défaut). C'est ce qu'on veut — on
veut juste que pendant la fenêtre de migration (section 5), il soit à l'arrêt
contrôlé, pas crashed. Si pour une raison quelconque tu veux empêcher le
redémarrage auto au prochain boot (rare) :

```bash
# AVANT le shutdown : désactiver l'auto-start
sudo systemctl disable snap.microk8s.daemon-kubelite snap.microk8s.daemon-containerd

# APRÈS la migration terminée et validée : réactiver
sudo systemctl enable snap.microk8s.daemon-kubelite snap.microk8s.daemon-containerd
```

**Installation physique** :

1. Débrancher l'alimentation (côté secteur)
2. Maintenir le bouton Power 5s pour décharger les condensateurs
3. Ouvrir le capot, mettre une main au châssis pour décharger l'électrostatique
4. Repérer **M2_1** : entre le CPU et le 1er slot PCIe (celui où est le GPU)
5. Dévisser la vis M2_1 sur la carte mère, l'enlever
6. Insérer le NVMe en angle (~30°), aligner l'encoche
7. Presser à plat, revisser la vis (ne pas serrer trop fort)
8. Refermer le boîtier, rebrancher

**Pourquoi M2_1 (et pas M2_2)** : M2_2 partage des lanes avec SATA5+SATA6 sur la Z370-A PRO. Tu ne perds rien aujourd'hui mais tu limites tes options futures pour ajouter un 3e SSD/HDD.

---

## 4. Setup du disque

```bash
# 1. Vérifier la détection
lsblk
# Doit afficher "nvme0n1" 931G en plus de sda/sdb

# 2. Vérifier que le NVMe est bien en mode PCIe (et pas SATA fallback)
sudo lspci | grep -i "non-volatile"
# Doit afficher quelque chose comme "Non-Volatile memory controller: ... (rev XX)"

# 3. Partition GPT + ext4
sudo parted -s /dev/nvme0n1 mklabel gpt
sudo parted -s /dev/nvme0n1 mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L kube-data /dev/nvme0n1p1

# 4. Créer le point de montage
sudo mkdir -p /data

# 5. Ajouter au fstab (montage persistant)
echo "LABEL=kube-data /data ext4 defaults,noatime,nodiratime 0 2" | sudo tee -a /etc/fstab
sudo mount -a

# 6. Vérifier
mount | grep /data
df -h /data
# Doit afficher /dev/nvme0n1p1 mounted on /data, ~916 GB libre

# 7. Bench express (lecture séquentielle raw, sans risque)
sudo dd if=/dev/nvme0n1 of=/dev/null bs=1M count=2048 iflag=direct status=progress
# Doit afficher >2.5 GB/s. Si <1 GB/s, le NVMe est tombé en mode SATA M.2
# (signal d'achat erroné ou mauvais slot)

# 8. Créer les sous-dossiers cibles
sudo mkdir -p /data/kube /data/projets
sudo chown -R moi:moi /data/projets
# /data/kube reste à root (k8s tourne en root)
```

---

## 5. Migration MicroK8s storage

```bash
# 1. Arrêt propre du cluster
sudo systemctl stop snap.microk8s.daemon-kubelite

# Attendre que tout soit arrêté
sudo systemctl status snap.microk8s.daemon-kubelite | grep "Active:" | head -1
# Doit afficher "inactive (dead)"

# 2. Vérifier que /var/snap/microk8s/common/default-storage existe (sinon rien à migrer)
sudo ls /var/snap/microk8s/common/default-storage/ | head -5

# 3. Rsync vers le NVMe (préserve les attributs, ACLs, hardlinks, sparse files)
#    Cette étape est longue : ~70 GB à ~500 MB/s = ~3 min, mais beaucoup de petits
#    fichiers → temps réel plus proche de 15-30 min
sudo rsync -aHAX --info=progress2 --sparse \
  /var/snap/microk8s/common/default-storage/ \
  /data/kube/default-storage/

# 4. Vérifier l'intégrité (tailles identiques)
sudo du -sh /var/snap/microk8s/common/default-storage /data/kube/default-storage

# 5. Bascule via symlink (atomique)
sudo mv /var/snap/microk8s/common/default-storage \
        /var/snap/microk8s/common/default-storage.OLD
sudo ln -s /data/kube/default-storage \
            /var/snap/microk8s/common/default-storage

# 6. Vérifier le symlink
sudo ls -la /var/snap/microk8s/common/default-storage
# Doit pointer vers /data/kube/default-storage

# 7. Redémarrer k8s
sudo systemctl start snap.microk8s.daemon-kubelite
sleep 30
sudo systemctl status snap.microk8s.daemon-kubelite | grep "Active:"

# 8. Vérifier que les pods reprennent
kubectl get nodes
kubectl get pods -A | grep -v "Running\|Completed" | head
# Si certains pods sont Pending/Error, attendre 2-3 min puis re-check
```

---

## 6. Migration ~/projets

```bash
# 1. Fermer tous les outils qui utilisent ~/projets
# - VSCode (Quit, pas juste Close window)
# - Conda envs activées
# - Terminals dans des sous-dossiers de ~/projets
# - Toute fenêtre Firefox ouvrant des fichiers locaux du dossier

# Confirmer qu'aucun process n'a un fd ouvert dans ~/projets
lsof | grep "/home/moi/projets" | head -5
# Si non vide, fermer les apps concernées avant de continuer

# 2. Stats avant
du -sh ~/projets
df -h ~ /data

# 3. Rsync vers NVMe
rsync -aHAX --info=progress2 ~/projets/ /data/projets/

# 4. Vérifier
du -sh ~/projets /data/projets
diff -r ~/projets /data/projets --brief 2>&1 | head -10
# Aucune sortie = tout est identique. Quelques diffs sur des fichiers binaires
# (.git/index, .pyc) peuvent apparaître si modif pendant le rsync — pas grave.

# 5. Bascule via symlink (les éditeurs s'en remettent transparent)
mv ~/projets ~/projets.OLD
ln -s /data/projets ~/projets

# 6. Vérifier le symlink
ls -la ~/projets
# Doit pointer vers /data/projets
```

---

## 7. Validation post-migration

```bash
# k8s : tous les pods Up
kubectl get pods -A | grep -v "Running\|Completed"
# Sortie idéale : aucune ligne (à part le header)

# k8s : LocalAI répond
kubectl -n localai scale deploy localai --replicas=1
kubectl -n localai wait --for=condition=Ready pod -l app.kubernetes.io/instance=localai --timeout=5m
TOKEN="H/Kk5SCTCa0wPH+y3X8Cktuvgv3uLNaTFQGwTy+M7eE="
curl -s -H "Authorization: Bearer $TOKEN" https://localai.tgu.ovh/v1/models | jq -r '.data[].id'

# k8s : PostgreSQL répond (test au hasard sur une app qui en a un)
kubectl -n datalab exec -it sts/postgresql -- psql -U postgres -c "SELECT 1;"

# k8s : ArgoCD apps Synced/Healthy
kubectl -n argocd get app -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status

# Code : ouvrir VSCode sur ~/projets/perso/my-kluster, vérifier que les
# fichiers s'affichent normalement et qu'aucun chemin n'est cassé

# Code : bench Python sur un projet existant
cd ~/projets/<un projet Python avec tests>
time pytest --collect-only -q | tail -5
# Comparer avec le timing avant migration (mémoire ou note prise auparavant)
```

### Métriques de réussite attendues

| Indicateur | Avant migration | Après migration |
|---|---|---|
| `df -h /` | ~84% utilisé (sda2) | descend (libère ~490 GB) |
| `df -h /data` | n/a | ~50% utilisé |
| `pytest --collect-only` (gros projet) | 2-3s | 0.3-0.5s |
| VS Code "ouvrir gros projet" | 5-8s | 1-2s |
| `pip install` (gros package) | 20-30s | 5-8s |
| k8s pod boot LocalAI | 2-5 min | ~1 min (pull image + scan PVCs plus rapides) |
| LocalAI tok/s sur Qwen 7B | ~40 tok/s | identique (GPU-bound, pas I/O) |

---

## 8. Cleanup (après 24-48h sans souci) — ⚠️ NON-NÉGOCIABLE

> **Incident référence (mai 2026)** : oublier ce cleanup a maintenu sda2 à 74% utilisé
> pendant 5+ jours → kubelet image GC en boucle (threshold 75%) → containerd
> memory bloat → SIGKILL systemd → cluster down 2h30.
>
> Mettre un **rappel calendrier 48h après chaque migration `.OLD`** pour exécuter
> ces commandes. Ce n'est PAS optionnel.

```bash
# Une fois certain que tout fonctionne (au moins 2 jours d'usage normal) :

# Supprimer les backups de l'ancien storage k8s
sudo /bin/rm -rf /var/snap/microk8s/common/default-storage.OLD

# Supprimer le backup de ~/projets
/bin/rm -rf ~/projets.OLD

# Vérifier le gain final
df -h
sudo du -sh /var/snap/microk8s/common/var/lib/containerd  # encore sur sda2

# Optionnel : déplacer aussi le cache containerd (75 GB sur sda2) vers NVMe ?
# C'est faisable mais demande de couper k8s à nouveau et un rsync :
sudo systemctl stop snap.microk8s.daemon-kubelite
sudo rsync -aHAX /var/snap/microk8s/common/var/lib/containerd/ /data/kube/containerd/
sudo mv /var/snap/microk8s/common/var/lib/containerd{,.OLD}
sudo ln -s /data/kube/containerd /var/snap/microk8s/common/var/lib/containerd
sudo systemctl start snap.microk8s.daemon-kubelite
# Considérer si tu veux libérer 75 GB de plus sur sda2 et tout regrouper sur NVMe.
```

---

## 9. Rollback (si problème majeur)

Tant que les `.OLD` ne sont pas supprimés, le retour arrière est trivial :

### Rollback k8s

```bash
sudo systemctl stop snap.microk8s.daemon-kubelite
sudo /bin/rm /var/snap/microk8s/common/default-storage   # supprime le symlink, pas le dossier cible
sudo mv /var/snap/microk8s/common/default-storage.OLD /var/snap/microk8s/common/default-storage
sudo systemctl start snap.microk8s.daemon-kubelite
```

### Rollback ~/projets

```bash
/bin/rm ~/projets                    # supprime le symlink
mv ~/projets.OLD ~/projets
```

### Si le NVMe lui-même est défaillant et inutilisable

- Démonter `/data` via fstab (commenter la ligne)
- Tout retombe sur l'ancien stockage sda2/sdb1
- Pas de perte de données puisque les `.OLD` sont encore sur sda2

---

## 10. Monitoring & maintenance courante

### Surveillance hebdomadaire

```bash
# Espace disque sur tous les disques
df -h | grep -E "sda|sdb|nvme"

# Top 10 consommateurs sur le NVMe
sudo du -sh /data/* /data/kube/* /data/projets/* 2>/dev/null | sort -rh | head -10

# Vérifier la santé du NVMe (SMART)
sudo nvme smart-log /dev/nvme0n1 | grep -E "(temperature|percentage_used|critical_warning|data_units_written)"
# critical_warning doit être 0
# percentage_used montre la wear (0% = neuf, 100% = en fin de vie selon TBW garanti)
# temperature : <70°C OK, >85°C → ajouter dissipateur ou améliorer airflow
```

### Mise à jour du firmware NVMe (optionnel, à faire une fois par an)

```bash
# Lister les firmwares disponibles via fwupd
sudo fwupdmgr refresh
sudo fwupdmgr get-updates
# Si update dispo pour le NVMe :
sudo fwupdmgr update
```

---

## 11. Alertes à surveiller

| Symptôme | Cause probable | Action |
|---|---|---|
| `df -h /data` > 80% | Croissance imprévue (datasets, checkpoints) | Identifier le coupable avec `du -sh`, déplacer vers `/media/data` (HDD) |
| `kubectl get pods` montre des Pending | k8s ne peut pas créer un PVC (espace dispo ?) | `df -h /data`, libérer ou résiser |
| LocalAI boot très lent | NVMe full ou en panne (lecture lente) | `nvme smart-log`, vérifier SMART |
| Python imports lents soudainement | NVMe full → write amplification | Free up disk space |
| `nvme smart-log` `percentage_used` > 80% | Le NVMe approche fin de vie (5-10 ans typique) | Planifier remplacement |
| `temperature` > 80°C | Pas de dissipation thermique | Ajouter dissipateur passif M.2 |

---

## 12. Ce qui NE va PAS sur le NVMe

Pour préserver l'espace et la durée de vie du NVMe, on garde sur `/dev/sdb1` (HDD `/media/data` 1.8 TB) :

| Type de fichier | Pourquoi sur HDD |
|---|---|
| Torrents / médias (déjà fait) | reads séquentiels rares, le HDD suffit |
| Datasets ML (>1 GB) | reads séquentiels lors d'entraînement, archives froides |
| Checkpoints ML entraînés | rarement consultés après entraînement |
| Backups (DB, sealed-secrets keys) | archives froides |
| Cache HuggingFace si très gros | si shared avec LocalAI, peut rester sur le PVC k8s |
| ISO, images VM | trop gros, peu accédés |

**Règle simple** : *"Est-ce que je lis ce fichier en boucle pendant que je code ou pendant qu'un pod tourne ?"* → NVMe. Sinon → HDD.

---

## Architecture finale après migration

```
/dev/nvme0n1 (NVMe 1 TB, ~3500 MB/s sur ta Z370 PCIe 3.0)
└── /data (ext4, noatime, ~50% utilisé)
    ├── kube/default-storage/   ← PVCs k8s (LocalAI, Open WebUI, MLflow, registry, etc.)
    └── projets/                ← code source Python, repos Git, envs conda

/dev/sda (Samsung 860 SSD SATA, 931 GB, ~540 MB/s)
└── /        ← Ubuntu OS + /home (sans projets) + cache snap/apt/journal
              ← /var/snap/microk8s/common/var/lib/containerd (images, 75 GB)
                (optionnel : à déplacer sur NVMe plus tard si besoin de place)

/dev/sdb (WD Blue HDD, 1.8 TB, ~120 MB/s)
└── /media/data/   ← torrents, médias arr-stack, datasets ML, backups, archives
```

---

## TL;DR commandes essentielles (référence rapide)

```bash
# Setup
sudo parted -s /dev/nvme0n1 mklabel gpt && \
sudo parted -s /dev/nvme0n1 mkpart primary ext4 0% 100% && \
sudo mkfs.ext4 -L kube-data /dev/nvme0n1p1 && \
sudo mkdir -p /data && \
echo "LABEL=kube-data /data ext4 defaults,noatime,nodiratime 0 2" | sudo tee -a /etc/fstab && \
sudo mount -a && \
sudo mkdir -p /data/kube /data/projets && \
sudo chown -R moi:moi /data/projets

# Migration k8s
sudo systemctl stop snap.microk8s.daemon-kubelite && \
sudo rsync -aHAX --info=progress2 /var/snap/microk8s/common/default-storage/ /data/kube/default-storage/ && \
sudo mv /var/snap/microk8s/common/default-storage{,.OLD} && \
sudo ln -s /data/kube/default-storage /var/snap/microk8s/common/default-storage && \
sudo systemctl start snap.microk8s.daemon-kubelite

# Migration projets
rsync -aHAX --info=progress2 ~/projets/ /data/projets/ && \
mv ~/projets ~/projets.OLD && \
ln -s /data/projets ~/projets

# Cleanup (après validation)
sudo /bin/rm -rf /var/snap/microk8s/common/default-storage.OLD ~/projets.OLD
```
