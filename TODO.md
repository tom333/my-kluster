# TODO — Améliorations du cluster my-kluster

## ✅ Récemment terminé (mai 2026)

- [x] **Migration GitOps des secrets vers Sealed Secrets** (Bitnami)
  - Installation du controller `sealed-secrets-controller` (ns `kube-system`)
  - Migration de 13 SealedSecrets dans `sealed/` (localai, github-auth, rustfs, postgresql, mlflow-s3, openai, arr-stack, etc.)
  - Refactor `postgresql-app.yaml` : password externalisé via `auth.existingSecret`
  - Split `rustfs-credentials-dagster` → séparation RustFS / POSTGRES_PASSWORD
  - Décommissionnement complet d'**External Secrets Operator + Akeyless**
  - Suppression de tous les fichiers plaintext dans `secrets/`
  - Hook pre-commit + workflow CI **gitleaks** pour bloquer les secrets en clair

- [x] **Activer Renovate sur les charts custom locaux**
  - `helm-values` manager sur `charts/mlflow/values.yaml` (tag standard `ghcr.io/mlflow/mlflow:vX.Y.Z`)
  - `customManagers` regex sur `charts/localai/values.yaml` (suffixe non-standard `-gpu-nvidia-cuda-12`, versioning regex custom)

- [x] **Nettoyage déchets `config/` et `.github/`**
  - Suppression `config/test-volume.yaml` (Pod test `test-read-static` + PVC orphelin `jellyfin-media-pvc`)
  - Suppression `config/jellyfin-nas-pv.yaml.old`, `config/mlflow-pvc.yaml.old`, `.github/workflows/coder-docker-image.yml.old`

## 🟠 Dette technique

- [ ] **Fixer `rustfs` `targetRevision: main`** → pointer sur un tag sémantique ou un commit SHA stable
- [ ] **Résoudre le bug RustFS #1844** (readinessProbe `/health/ready` retourne 403) pour réactiver `selfHeal: true`
- [ ] **Nettoyer le namespace `accidents`** — pods en `ContainerStatusUnknown` / `CreateContainerConfigError` depuis 20+ jours (`accidents-api-*`, `streamlit-app-*`)

## 🟡 Améliorations

- [ ] **Ajouter `description` aux AppProjects** pour améliorer la lisibilité dans l'UI ArgoCD

- [ ] **Documenter le build des images custom locales**
  - `localhost:32000/accidents-dagster` (Dagster user code)
  - `localhost:32000/custom-jupyter` (JupyterLab custom)
  - `tom333/coder` (code-server + DinD)

- [ ] **Renommer `dagster/rustfs-credentials-dagster`** → `dagster/rustfs-credentials` (le suffixe `-dagster` n'a plus de sens depuis le split de phase 6b)

- [ ] **Évaluer Reflector** pour dédupliquer les secrets partagés entre namespaces
  - Cas pertinent : Sonarr/Radarr API keys dupliquées dans `arrconf-env`, `configarr-env`, `recyclarr-api-keys`
  - Cas pertinent : `localai-api-key` (même valeur dans ns `localai` et `openwebui`)
  - Décision actuelle : duplication acceptée (rotation rare, scellement scriptable en une commande)

---

## 🔵 Utilisation du pattern bjw-s/app-template

> **Chart** : `https://bjw-s-labs.github.io/helm-charts` — `app-template`
> **Pertinence** : uniquement pour les apps sans chart upstream dédié (éviter de maintenir un mini-chart custom)

### ✅ Migration prioritaire : `charts/mlflow/` → `app-template`

Le chart custom `charts/mlflow/` (Chart.yaml + templates/ + values.yaml) peut être entièrement remplacé.

**Avant** (app actuelle `mlflow-app.yaml`) :
```yaml
source:
  repoURL: https://github.com/tom333/my-kluster.git
  targetRevision: HEAD
  path: charts/mlflow
```

**Après** (avec app-template) :
```yaml
source:
  repoURL: https://bjw-s-labs.github.io/helm-charts
  chart: app-template
  targetRevision: 4.6.2   # à mettre à jour via Renovate
  helm:
    values: |
      controllers:
        main:
          containers:
            main:
              image:
                repository: ghcr.io/mlflow/mlflow
                tag: "v3.10.1"
                pullPolicy: IfNotPresent
      service:
        main:
          controller: main
          ports:
            http:
              port: 5000
      ingress:
        main:
          annotations:
            cert-manager.io/cluster-issuer: "letsencrypt-prod"
          hosts:
            - host: mlflow.tgu.ovh
              paths:
                - path: /
                  pathType: Prefix
      persistence:
        data:
          type: persistentVolumeClaim
          storageClass: microk8s-hostpath
          size: 10Gi
          globalMounts:
            - path: /mlflow
```

**Gains** :
- Supprime le dossier `charts/mlflow/` du dépôt
- Le tag d'image `ghcr.io/mlflow/mlflow` devient détectable par Renovate via le chart versionné
- API claire et maintenue par la communauté

**Tâches** :
- [ ] Créer la nouvelle `mlflow-app.yaml` avec app-template
- [ ] Désactiver l'ancienne (`mlflow-app.yaml.disable` existe déjà — vérifier son contenu)
- [ ] Supprimer `charts/mlflow/` une fois la migration validée
- [ ] Ajouter `bjw-s-labs.github.io/helm-charts` à la liste `sourceRepos` de `datalab-project`

### ⚠️ Cas non pertinents (ne pas migrer)

Les apps suivantes ont des charts upstream bien maintenus — **ne pas remplacer par app-template** :
- `dagster`, `certmanager`, `oauth2-proxy`, `postgresql`, `qdrant`, `sealed-secrets`
- `rustfs` (chart dans le dépôt upstream)
- `freshrss`, `komga`, `kubetail`, `jupyter`, `code-server`
