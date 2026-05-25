# AGENTS.md — Guide pour agents IA (Cursor, Copilot, Gemini, etc.)

Ce fichier décrit l'architecture, les conventions et les règles de ce dépôt GitOps.
**Lis ce fichier en entier avant de proposer ou d'appliquer toute modification.**

---

## Vue d'ensemble

Ce dépôt contient la configuration GitOps d'un cluster **MicroK8s** single-node géré par **ArgoCD**.
L'infrastructure est entièrement déclarative : toute modification doit passer par ce dépôt.

- **Domaine principal** : `*.tgu.ovh`
- **Ingress controller** : NGINX (installé via MicroK8s addon)
- **TLS** : cert-manager + Let's Encrypt (`letsencrypt-prod`)
- **Authentification** : oauth2-proxy (GitHub OAuth, whitelist : `tom333`, `tguyader`)
- **Secrets management** : **Sealed Secrets** (Bitnami) — tous les secrets sont chiffrés dans `sealed/` et committés dans Git. Le controller `sealed-secrets-controller` (ns `kube-system`) les déchiffre à la volée vers des Secrets K8s natifs.
- **Mise à jour automatique des charts** : Renovate (auto-merge pour minor/patch)
- **Registry locale** : `localhost:32000` (MicroK8s registry addon)
- **Hygiène secrets** : pre-commit + gitleaks (cf. `.pre-commit-config.yaml` et `.github/workflows/gitleaks.yml`) bloquent l'ajout accidentel de credentials en clair

---

## Structure du dépôt

```
my-kluster/
├── argocd/
│   ├── argocd-install/          # Chart Helm wrapper pour installer ArgoCD lui-même
│   │   ├── Chart.yaml           # Dépendance sur argoproj/argo-cd
│   │   └── values.yaml          # Config ArgoCD : ingress, domaine, kustomize options
│   ├── argocd-install-apps/     # App-of-Apps bootstrap (appliqué manuellement à l'init)
│   │   └── values.yaml          # Définit les 3 apps racines : argocd, applications, projects
│   ├── argocd-apps/             # Toutes les Application ArgoCD (synchées auto par ArgoCD)
│   │   ├── *-app.yaml           # Applications actives
│   │   └── *-app.yaml.disable   # Applications désactivées (ignorées par ArgoCD)
│   └── argocd-appprojects/      # AppProjects ArgoCD (ségrégation RBAC par domaine)
├── charts/
│   └── localai/                 # Chart Helm custom pour LocalAI (stocké dans ce dépôt)
├── config/                      # Manifestes Kubernetes bruts (synchés par l'app "config")
│   ├── letsencrypt-issuer.yaml  # ClusterIssuer Let's Encrypt
│   ├── sc-nfs.yaml              # StorageClass NFS (NAS 192.168.88.103)
│   ├── dashboard-ingress.yaml   # Ingress K8s Dashboard (protégé oauth2-proxy)
│   └── *.yaml.disable           # Configs désactivées
├── sealed/                      # SealedSecrets chiffrés (synchés par l'app "sealed")
│   └── *.yaml                   # Un fichier par secret K8s (ou groupe logique multi-doc)
└── secrets/                     # (vide ; gitignored ; usage local éphémère pour kubeseal)
```

> `secrets/` est dans `.gitignore` et ne contient plus aucun fichier en clair. Tout secret K8s vit désormais dans `sealed/` sous forme chiffrée.

---

## Pattern App-of-Apps

Le bootstrap suit un pattern App-of-Apps en 3 niveaux :

```
argocd-install-apps (Helm, manuel)
    ├── App "argocd"         → gère ArgoCD lui-même (argocd/argocd-install/)
    ├── App "applications"   → surveille argocd/argocd-apps/ (recurse: true)
    └── App "projects"       → surveille argocd/argocd-appprojects/ (recurse: true)
```

**Règle** : L'app "applications" découvre automatiquement tous les fichiers `*.yaml` dans `argocd/argocd-apps/`.
Les fichiers `.disable` sont ignorés. Pour désactiver une app, suffixe son fichier avec `.disable`.

---

## AppProjects (ségrégation RBAC)

| Project              | Namespaces cibles                                           | Usage                        |
|----------------------|-------------------------------------------------------------|------------------------------|
| `argocd`             | `argocd`                                                    | Méta-apps ArgoCD             |
| `infra-project`      | `infra`, `cert-manager`, `kube-system`, `dagster`, `*`     | Infrastructure transverse    |
| `datalab-project`    | `datalab`, `ia-lab`, `auth`, `kubeflow`, `kserve`, `*`     | Data/ML workloads            |
| `selfhost-project`   | `selfhost`                                                  | Applications self-hosted     |
| `jupyter-project`    | (voir fichier)                                              | JupyterHub                   |
| `code-server`        | (voir fichier)                                              | Code-server IDE              |

---

## Applications actives

### Infrastructure

| Application        | Namespace      | Source                          | Version   | Notes                                  |
|--------------------|----------------|---------------------------------|-----------|----------------------------------------|
| `certmanager`      | `cert-manager` | charts.jetstack.io              | v1.20.0   | CRDs installées, sans Prometheus       |
| `sealed-secrets`   | `kube-system`  | bitnami-labs.github.io/sealed-secrets | 2.16.2 | Controller de déchiffrement, Service `sealed-secrets-controller` |
| `sealed`           | `kube-system`  | ce dépôt → `sealed/`           | HEAD      | App qui déploie tous les `SealedSecret` du repo |
| `config`           | `infra`        | ce dépôt → `config/`           | HEAD      | Manifestes bruts (issuer, ingress...)  |
| `oauth2-proxy`     | `kube-system`  | oauth2-proxy.github.io          | 10.1.4    | GitHub OAuth, `.tgu.ovh`, sans Redis   |
| `kubetail`         | `kube-system`  | kubetail-org.github.io          | 0.18.2    | Logs agrégés, protégé oauth2-proxy     |

### Data / ML (namespace `ia-lab` ou `datalab`)

| Application   | Namespace  | Source                          | Version   | Notes                                         |
|---------------|------------|---------------------------------|-----------|-----------------------------------------------|
| `mlflow`      | `ia-lab`   | bjw-s-labs.github.io/helm-charts | 5.0.1     | `app-template`, image `ghcr.io/mlflow/mlflow:v3.12.0`, initContainer `mlflow db upgrade`, PVC `mlflow-data` 10Gi |
| `rustfs`      | `ia-lab`   | github.com/rustfs/rustfs        | 1.0.0-beta.3 | S3-compatible, probes par défaut du chart      |
| `dagster`     | `dagster`  | dagster-io.github.io/helm       | 1.12.19   | K8sRunLauncher, image locale, DuckLake config |
| `postgresql`  | `datalab`  | charts.bitnami.com              | 18.6.6    | `auth.existingSecret: postgresql-credentials` (SealedSecret) |
| `qdrant`      | `datalab`  | qdrant.to/helm                  | 1.17.0    | Vector DB, config minimale                    |
| `jupyter`     | `datalab`  | tom333.github.io/my-charts      | 0.1.18    | Image custom, DuckDB, Marimo, JupyterLSP      |
| `localai`     | `localai`  | ce dépôt → `charts/localai/`   | HEAD      | LocalAI GPU NVIDIA, MVP Qwen2.5-1.5B Q4_K_M, ingress LAN-only + token API |
| `openwebui`   | `openwebui`| helm.openwebui.com              | 7.0.0     | UI chat (CPU), upstream LocalAI, 2 ingress (public oauth2-proxy + LAN whitelist) |

### Monitoring (namespace `monitoring`)

| Application | Namespace    | Source                            | Version | Notes                                                                  |
|-------------|--------------|-----------------------------------|---------|------------------------------------------------------------------------|
| `beszel`    | `monitoring` | bjw-s-labs.github.io/helm-charts  | 5.0.1   | Hub Beszel (henrygd/beszel 0.10.0). Ingress LAN-only `beszel.tgu.ovh`. Alertes Telegram. |

Agents déployés via Ansible (`ansible/` du repo) sur toutes les machines monitorées.
Documentation déploiement : `docs/superpowers/specs/2026-05-24-beszel-monitoring-design.md`.

### Self-hosted

| Application  | Namespace  | Source                    | Version  | Notes                              |
|--------------|------------|---------------------------|----------|------------------------------------|
| `freshrss`   | `selfhost` | tccr.io/truecharts        | 21.15.0  | RSS reader, ingress désactivé      |
| `komga`      | `komga`    | rubxkube.github.io/charts | 0.0.10   | Bibliothèque BD/manga, 1Go uploads |

### Développement

| Application   | Namespace  | Source                          | Version   | Notes                                          |
|---------------|------------|---------------------------------|-----------|------------------------------------------------|
| `code-server` | `coder`    | github.com/coder/code-server    | v4.111.0  | VSCode web + DinD, image custom `tom333/coder` |
| `cv`          | `cv`       | github.com/tom333/cv            | main      | CV personnel (dépôt externe)                   |

---

## Conventions et règles critiques

### Fichiers de configuration

1. **Activer/désactiver une app** : renomme le fichier (ajoute/enlève `.disable`), ne supprime jamais.
2. **Fichiers temporaires ou en cours** : suffixe `.old` pour les anciens manifestes (ex: `mlflow-pvc.yaml.old`).
3. **Nommage** : `<service>-app.yaml` pour les ArgoCD Applications, `<service>-project.yaml` pour les AppProjects.
4. **Extension doublon** : le fichier `code-server-app.yaml.yaml` a une extension dupliquée — à corriger.

### Gestion des secrets — Sealed Secrets

Tous les secrets K8s sont chiffrés (Bitnami Sealed Secrets) et committés dans `sealed/`. Le controller `sealed-secrets-controller` (ns `kube-system`) déchiffre à la volée vers des Secret natifs.

**Workflow pour ajouter / mettre à jour un secret** :

```bash
# 1. Créer le secret en clair en mémoire et le sceller directement
#    Les flags --controller-name / --controller-namespace sont OBLIGATOIRES sur ce cluster
#    (le service ne s'appelle pas "sealed-secrets" mais "sealed-secrets-controller").
kubectl create secret generic <name> \
  --namespace=<ns> \
  --from-literal=<key>=<value> \
  --dry-run=client -o yaml \
| kubeseal \
    --controller-name=sealed-secrets-controller \
    --controller-namespace=kube-system \
    --format=yaml \
  > sealed/<name>.yaml

# Astuce : exporter une fois pour toutes pour éviter de répéter les flags
#   export SEALED_SECRETS_CONTROLLER_NAME=sealed-secrets-controller
#   export SEALED_SECRETS_CONTROLLER_NAMESPACE=kube-system

# 2. Commit + push — ArgoCD synchronise l'app "sealed" et le Secret apparaît dans le cluster
git add sealed/<name>.yaml
git commit -m "feat(sealed): add <name>"
git push
```

**Règles** :
- Tout `kind: Secret` plaintext dans un manifest committé est **interdit** (bloqué par gitleaks + hook pre-commit).
- Les images d'application qui consomment un secret doivent référencer par `secretKeyRef`/`envFrom`/`secretName` — jamais inliner une valeur.
- **Convention de nommage** : `sealed/<source>-secret.yaml` ou `sealed/<resource-name>.yaml` (cf. fichiers existants).
- Pour transférer ownership d'un Secret existant non géré au controller (cas migration) : `kubectl annotate secret <name> sealedsecrets.bitnami.com/managed=true --overwrite` AVANT d'appliquer le SealedSecret.

**Clé master du controller** :
- Stockée dans le namespace `kube-system` sous label `sealedsecrets.bitnami.com/sealed-secrets-key=active`
- **CRITIQUE** : à backup hors-cluster (password manager / NAS chiffré). Sans elle, impossible de déchiffrer les SealedSecrets en cas de rebuild du cluster.
- Rotation auto tous les 30j (`keyrenewperiod: 720h`) → re-backup périodique.

```bash
# Backup
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > ~/sealed-secrets-master-$(date +%Y%m%d).key.backup
```

### Syncronisation ArgoCD

- **selfHeal: true** sur toutes les apps.
- **prune: true** activé partout : tout ce qui n'est plus dans Git sera supprimé.
- **ServerSideApply** utilisé pour `sealed-secrets` et `rustfs` (gestion des CRDs).
- L'app `argocd` elle-même a `helm.sh/resource-policy: keep` pour éviter sa suppression accidentelle.
- L'app `sealed-secrets` ignore un drift cosmétique sur `GOMEMLIMIT` (voir `ignoreDifferences` dans `sealed-secrets-app.yaml`).

### Ingress et TLS

- Toutes les routes exposées utilisent `cert-manager.io/cluster-issuer: "letsencrypt-prod"`.
- Les applications sensibles (Dagster, code-server, kubetail, dashboard) sont protégées par oauth2-proxy :
  ```yaml
  nginx.ingress.kubernetes.io/auth-url: "https://auth.tgu.ovh/oauth2/auth"
  nginx.ingress.kubernetes.io/auth-signin: "https://auth.tgu.ovh/oauth2/start?rd=https://<service>.tgu.ovh"
  ```
- **MLflow** et **RustFS** ne sont PAS protégés par oauth2-proxy (accès réseau direct ou auth interne).
- **LocalAI** (`localai.tgu.ovh`) : pas d'oauth2-proxy, accès restreint via `nginx.ingress.kubernetes.io/whitelist-source-range: "192.168.88.0/24,10.1.0.0/16"` + token `Authorization: Bearer <api-key>` (secret `localai-api-key`).
- **Open WebUI** expose **2 ingress** pointant sur le même service :
  - `chat.tgu.ovh` : public + oauth2-proxy (managé par le chart Helm, dans `openwebui-app.yaml`)
  - `chat-lan.tgu.ovh` : whitelist LAN sans oauth (manifest brut dans `config/openwebui-lan-ingress.yaml`)

### GPU NVIDIA (workloads ML)

- **GPU Operator** : installé hors GitOps via `microk8s enable gpu`. Géré dans le namespace `gpu-operator-resources` (CRDs + DaemonSets).
- **Workaround obligatoire** sur cette install : patcher la `ClusterPolicy` avec `DISABLE_DEV_CHAR_SYMLINK_CREATION=true` (bug NVIDIA gpu-operator #430, le validator essaie de recréer des symlinks `/dev/char/` déjà présents).
- Allocation GPU : **exclusive** (`nvidia.com/gpu: 1` en `requests` ET `limits`). **Pas de Time-Slicing** (provoque des erreurs mémoire).
- Carte actuelle : **RTX 3060, 12 GB** (Ampere CC 8.6, tensor cores FP16/BF16, supporte Flash Attention natif).
- LocalAI est aujourd'hui le seul consommateur GPU. Toute autre Application demandant `nvidia.com/gpu` entrera en compétition (file d'attente Pending).

### Spécificités MicroK8s

- **StorageClass par défaut** : `microk8s-hostpath` (single-node, pas HA)
- **Registry locale** : `localhost:32000/<image>:<tag>` — images buildées en local
- **Ingress** : NGINX activé via addon MicroK8s (`microk8s enable ingress`)
- **NAS** : `192.168.88.103` (NFS v3, share `/Public`)

### Ansible (déploiement multi-machines)

- Dossier : `ansible/` du repo.
- Inventaire : `ansible/inventory.yml`. Groupe `k8s_nodes` (juste `k8s-node` aujourd'hui) reçoit le pack complet bootstrap+backup+monitoring. Les autres machines ne reçoivent que `beszel-agent`.
- Secrets chiffrés via Ansible Vault dans `ansible/group_vars/vault.yml` (password local en `~/.vault-password.txt`, jamais commité).
- Variables non-sensibles dans `ansible/group_vars/all.yml` (dont la pubkey `age` `sealed_backup_age_pubkey`).
- Commande pleine : `cd ansible/ && ansible-playbook -i inventory.yml playbook.yml --vault-password-file ~/.vault-password.txt --ask-become-pass`.
- Exécution partielle via tags : `--tags bootstrap` (k8s-node-bootstrap), `--tags filesystem`/`microk8s`/`packages`/`nvidia`/`gpu_operator` (sous-étapes du bootstrap).
- Ajout machine monitorée : éditer `inventory.yml` (hors `k8s_nodes`), runner avec `--limit <nouveau-host>`.

Rôles disponibles :
- `beszel-agent` : install/update agent Beszel.
- `sealed-secrets-backup` : backup quotidien chiffré (`age`) de la clé master Sealed Secrets vers NAS, notification Telegram en cas d'échec. Timer systemd 03h00.
- `k8s-node-bootstrap` : OS + nvidia-container-toolkit + mount NFS + sysctl + MicroK8s + addons + workaround gpu-operator NVIDIA #430 + outils dev (htop/btop/ncdu/ripgrep/fd/bat) + deb-get (dust, gh, upgrade hebdo). Idempotent. Garde-fou hostname.

**Disaster recovery — clé master Sealed Secrets** :
Les backups sont sur `192.168.88.103:/Public/backups/sealed-secrets/` (chiffrés `.yaml.age`). La clé privée `age` correspondante (`~/.config/age/sealed-backup.key`) est **CRITIQUE** : sans elle les backups sont inutilisables. À conserver hors-machine (password manager + clé USB, et à terme copie sur un autre hôte via Ansible).

Procédure de restore (machine fraîchement bootstrappée) :
```bash
age -d -i ~/.config/age/sealed-backup.key \
  /mnt/nas/backups/sealed-secrets/<latest>.yaml.age | kubectl apply -f -
```

---

## Initialisation du cluster (bootstrap)

Grâce à Sealed Secrets, **un seul secret d'amorçage** est nécessaire : la clé master du controller.

```bash
# 1. Restaurer la clé master Sealed Secrets (depuis backup hors-cluster)
kubectl create namespace kube-system 2>/dev/null || true
kubectl apply -f ~/sealed-secrets-master-XXXXXXXX.key.backup

# 2. Installer ArgoCD via Helm
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace

# 3. Récupérer le mot de passe admin ArgoCD
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 4. Déployer les app-of-apps (bootstrap)
helm install argocd-apps argocd/argocd-install-apps/ --namespace argocd

# ArgoCD installe ensuite sealed-secrets-controller (qui détecte la clé restaurée),
# puis l'app "sealed" déploie tous les SealedSecrets → tous les Secrets natifs sont créés,
# puis les autres apps démarrent dans l'ordre des dépendances.
```

**Sans la clé master backup, le rebuild est impossible** : les SealedSecrets dans Git ne pourront pas être déchiffrés et toutes les apps consommatrices échoueront au démarrage.

---

## Maintenance courante

```bash
# Supprimer les pods en état Completed
kubectl delete pod --field-selector=status.phase=Succeeded -A

# Nettoyer les images MicroK8s non utilisées
microk8s ctr images prune --all
```

---

## Renovate

Configuré dans `renovate.json` :
- Surveille `argocd/argocd-apps/*.yaml` pour les mises à jour de charts
- **Auto-merge** pour minor, patch, pin et digest
- **Exception** : `authentik-app.yaml` (ignoré)
- Les fichiers `.disable` ne sont pas auto-mergés (Renovate ne les voit pas)

---

## Ce que tu NE dois PAS faire

- ❌ Ne pas éditer `argocd/argocd-install-apps/values.yaml` sans comprendre l'impact sur le bootstrap
- ❌ Ne pas committer de `kind: Secret` plaintext (gitleaks bloque, mais le geste reste interdit). Toujours passer par `kubeseal` → `sealed/`.
- ❌ Ne pas désinstaller `sealed-secrets` sans avoir d'abord migré les Secrets ou backup la clé master.
- ❌ Ne pas changer la `targetRevision` d'une app sans vérifier la compatibilité MicroK8s
- ❌ Ne pas modifier les `sourceRepos: ["*"]` des AppProjects sans analyse RBAC
- ❌ Ne pas créer de nouveau namespace sans l'ajouter à l'AppProject correspondant
- ❌ Ne pas utiliser `image: tag: latest` en production sauf pour les images locales (`localhost:32000`)

---

## Choses à faire / améliorations connues

Voir `TODO.md` pour la liste complète. Items principaux restants :
- [ ] Corriger l'extension dupliquée de `code-server-app.yaml.yaml` → `code-server-app.yaml`
- [ ] Ajouter un `ClusterIssuer` DNS-01 OVH pour les wildcards `*.tgu.ovh`
- [ ] Nettoyer les fichiers `.old` et `test-volume.yaml` du dossier `config/`
- [ ] Documenter le processus de build des images custom (`localhost:32000/accidents-dagster`, `custom-jupyter`)
- [ ] Activer Renovate pour le chart custom `charts/mlflow` (versionner le tag d'image)
