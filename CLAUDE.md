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
- **Secrets management** : 
  - Akeyless via External Secrets Operator (ESO) pour les secrets dynamiques
  - Fichiers YAML plaintexts dans `secrets/` pour l'amorçage (à appliquer manuellement)
- **Mise à jour automatique des charts** : Renovate (auto-merge pour minor/patch)
- **Registry locale** : `localhost:32000` (MicroK8s registry addon)

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
│   └── mlflow/                  # Chart Helm custom pour MLflow (stocké dans ce dépôt)
├── config/                      # Manifestes Kubernetes bruts (synchés par l'app "config")
│   ├── external-secrets.yaml    # SecretStore Akeyless + ExternalSecrets
│   ├── letsencrypt-issuer.yaml  # ClusterIssuer Let's Encrypt
│   ├── sc-nfs.yaml              # StorageClass NFS (NAS 192.168.88.103)
│   ├── dashboard-ingress.yaml   # Ingress K8s Dashboard (protégé oauth2-proxy)
│   └── *.yaml.disable           # Configs désactivées
└── secrets/                     # Secrets YAML en clair (NE PAS versionner dans l'état actuel)
    ├── akeyless_creds.yaml      # Credentials Akeyless (amorçage ESO)
    ├── rustfs-secret.yaml       # Credentials RustFS + Dagster
    ├── github-auth.yaml         # OAuth2-proxy GitHub credentials
    ├── ovh-secrets.yaml         # API OVH (cert-manager DNS challenge)
    └── *.yaml                   # Autres secrets d'amorçage
```

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
| `external-secrets` | `kube-system`  | charts.external-secrets.io      | 2.1.0     | ESO avec provider Akeyless             |
| `config`           | `infra`        | ce dépôt → `config/`           | HEAD      | Manifestes bruts (issuer, ingress...)  |
| `oauth2-proxy`     | `kube-system`  | oauth2-proxy.github.io          | 10.1.4    | GitHub OAuth, `.tgu.ovh`, sans Redis   |
| `kubetail`         | `kube-system`  | kubetail-org.github.io          | 0.18.2    | Logs agrégés, protégé oauth2-proxy     |

### Data / ML (namespace `ia-lab` ou `datalab`)

| Application   | Namespace  | Source                          | Version   | Notes                                         |
|---------------|------------|---------------------------------|-----------|-----------------------------------------------|
| `mlflow`      | `ia-lab`   | ce dépôt → `charts/mlflow/`    | HEAD      | Chart custom, PVC `microk8s-hostpath`, 10Gi   |
| `rustfs`      | `ia-lab`   | github.com/rustfs/rustfs        | main      | S3-compatible, bug readinessProbe contourné   |
| `dagster`     | `dagster`  | dagster-io.github.io/helm       | 1.12.19   | K8sRunLauncher, image locale, DuckLake config |
| `postgresql`  | `datalab`  | charts.bitnami.com              | 18.5.6    | ⚠️ Mot de passe en clair dans le YAML        |
| `qdrant`      | `datalab`  | qdrant.to/helm                  | 1.17.0    | Vector DB, config minimale                    |
| `jupyter`     | `datalab`  | tom333.github.io/my-charts      | 0.1.18    | Image custom, DuckDB, Marimo, JupyterLSP      |
| `localai`     | `localai`  | ce dépôt → `charts/localai/`   | HEAD      | LocalAI GPU NVIDIA, MVP Qwen2.5-1.5B Q4_K_M, ingress LAN-only + token API |
| `openwebui`   | `openwebui`| helm.openwebui.com              | 7.0.0     | UI chat (CPU), upstream LocalAI, 2 ingress (public oauth2-proxy + LAN whitelist) |

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

### Gestion des secrets

> ⚠️ **CRITIQUE** : Les fichiers dans `secrets/` contiennent des credentials en clair.
> Ces fichiers sont destinés à l'amorçage manuel (`kubectl apply`) et ne doivent JAMAIS être appliqués par ArgoCD automatiquement.

- L'app `config` ne surveille **pas** le dossier `secrets/` — c'est intentionnel.
- Les secrets dynamiques passent par **External Secrets Operator (ESO)** + **Akeyless**.
- Le fichier `akeyless_creds.yaml` est le seul secret à appliquer avant tout le reste.
- Les secrets non gérés par ESO (ex: `rustfs-secret.yaml`, `github-auth.yaml`) sont appliqués manuellement.

### Syncronisation ArgoCD

- **selfHeal: true** sur toutes les apps sauf `rustfs` (bug readinessProbe contourné manuellement).
- **prune: true** activé partout : tout ce qui n'est plus dans Git sera supprimé.
- **ServerSideApply** utilisé pour `external-secrets` et `rustfs` (gestion des CRDs).
- L'app `argocd` elle-même a `helm.sh/resource-policy: keep` pour éviter sa suppression accidentelle.

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
- Carte actuelle : **GTX 1050 Ti, 4 GB** (Pascal CC 6.1, pas de tensor cores). Carte cible future : RTX 3060 12 GB.
- LocalAI est aujourd'hui le seul consommateur GPU. Toute autre Application demandant `nvidia.com/gpu` entrera en compétition (file d'attente Pending).

### Spécificités MicroK8s

- **StorageClass par défaut** : `microk8s-hostpath` (single-node, pas HA)
- **Registry locale** : `localhost:32000/<image>:<tag>` — images buildées en local
- **Ingress** : NGINX activé via addon MicroK8s (`microk8s enable ingress`)
- **NAS** : `192.168.88.103` (NFS v3, share `/Public`)

---

## Initialisation du cluster (bootstrap)

```bash
# 1. Appliquer les secrets d'amorçage (AVANT tout le reste)
kubectl apply -f secrets/akeyless_creds.yaml
kubectl apply -f secrets/github-auth.yaml
kubectl apply -f secrets/rustfs-secret.yaml
kubectl apply -f secrets/ovh-secrets.yaml
kubectl apply -f secrets/localai-secret.yaml  # token API LocalAI (ns localai + openwebui)
# ... autres secrets selon les apps à déployer

# 2. Installer ArgoCD via Helm
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace

# 3. Récupérer le mot de passe admin ArgoCD
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 4. Déployer les app-of-apps (bootstrap)
helm install argocd-apps argocd/argocd-install-apps/ --namespace argocd

# ArgoCD prend ensuite le relais et synchronise tout automatiquement
```

---

## Maintenance courante

```bash
# Supprimer les pods en état Completed
kubectl delete pod --field-selector=status.phase=Succeeded -A

# Nettoyer les images MicroK8s non utilisées
microk8s ctr images prune --all

# Patch manuel RustFS (workaround bug #1844 readinessProbe)
kubectl patch deployment rustfs -n ia-lab --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path", "value": "/health"}]'
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
- ❌ Ne pas ajouter de secrets en clair dans `argocd/argocd-apps/` ou `config/` — toujours utiliser ESO ou le dossier `secrets/`
- ❌ Ne pas activer `selfHeal: true` sur `rustfs` sans avoir résolu le bug upstream #1844
- ❌ Ne pas changer la `targetRevision` d'une app sans vérifier la compatibilité MicroK8s
- ❌ Ne pas modifier les `sourceRepos: ["*"]` des AppProjects sans analyse RBAC
- ❌ Ne pas créer de nouveau namespace sans l'ajouter à l'AppProject correspondant
- ❌ Ne pas utiliser `image: tag: latest` en production sauf pour les images locales (`localhost:32000`)

---

## Choses à faire / améliorations connues

- [ ] **URGENT** : Chiffrer les fichiers dans `secrets/` avec SOPS ou les migrer vers ESO
- [ ] Corriger l'extension dupliquée de `code-server-app.yaml.yaml` → `code-server-app.yaml`
- [ ] Résoudre le bug RustFS #1844 (readinessProbe) pour réactiver `selfHeal: true`
- [ ] Chiffrer le mot de passe PostgreSQL (actuellement `data`/`data` en clair dans `postgresql-app.yaml`)
- [ ] Ajouter un `ClusterIssuer` DNS-01 OVH pour les wildcards (les credentials OVH sont déjà dans `secrets/`)
- [ ] Nettoyer les fichiers `.old` et `test-volume.yaml` du dossier `config/`
- [ ] Documenter le processus de build des images custom (`localhost:32000/accidents-dagster`, `custom-jupyter`)
- [ ] Activer Renovate pour le chart custom `charts/mlflow` (versionner le tag d'image)
