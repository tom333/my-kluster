# TODO — Améliorations du cluster my-kluster

## ✅ Récemment terminé (mai 2026)

- [x] **Extension Ansible : common-cli-tools + dev-workstation + work-laptop monitoring**
  - Nouveau rôle `common-cli-tools` (factor des outils CLI partagés : apt + deb-get + timer hebdo deb-get-upgrade)
  - Nouveau rôle `dev-workstation` (pipx + uv/ruff user-scope, VS Code via deb-get, wezterm via deb-get, lazygit + chezmoi via GitHub releases binary, git config global avec commit.gpgsign)
  - Refactor `k8s-node-bootstrap` (extract de tasks/10_packages.yml + templates deb-get-upgrade vers common-cli-tools)
  - Refactor `inventory.yml` (nouveau groupe `dev_workstations`) + `playbook.yml` (3 plays)
  - `work-laptop` (Linux Mint 22.3, 192.168.88.211) ajouté + monitoré par Beszel + provisionné par dev-workstation
  - Repo dotfiles privé `tom333/dotfiles` créé (chezmoi init manuel à faire après gh ssh-key add)
  - Documentation : spec `2026-05-25-devworkstation-design.md` + plan `2026-05-25-devworkstation.md`

- [x] **Extension Ansible : disaster recovery + bootstrap k8s-node**
  - Rôle `sealed-secrets-backup` : backup quotidien chiffré `age` de la clé master vers NAS, alerte Telegram on failure, timer systemd
  - Rôle `k8s-node-bootstrap` : OS + nvidia-container-toolkit + NFS + sysctl + MicroK8s + addons + workaround gpu-operator NVIDIA #430, idempotent, garde-fou hostname, sous-tâches taguées
  - Refactor `inventory.yml` (groupe `k8s_nodes`) + `playbook.yml` (2 plays)
  - Outils CLI : btop, ncdu, ripgrep, fd, bat, plus dust + gh via deb-get (auto-upgrade hebdo dim 4h via timer systemd)
  - Documentation : spec `2026-05-25-ansible-extension-design.md` + plan `2026-05-25-ansible-extension.md`

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

- [x] **Retrait du workaround RustFS #1844** ([upstream corrigé](https://github.com/rustfs/rustfs/issues/1844))
  - Suppression des overrides `livenessProbe`/`readinessProbe` (path `/health` forcé)
  - Suppression du bloc `ignoreDifferences` sur `/spec/template/spec/containers/0/readinessProbe/httpGet/path`
  - Réactivation de `selfHeal: true`
  - Pinning `targetRevision: 1.0.0-beta.3` (au lieu de `main`) + `image.tag: 1.0.0-beta.3` (au lieu de `latest`)
  - Cleanup des mentions dans `CLAUDE.md` (workaround kubectl patch, règle "ne pas activer selfHeal sur rustfs", item TODO)

- [x] **Migration `charts/mlflow/` → `bjw-s/app-template` 5.0.1**
  - `mlflow-app.yaml` réécrit avec values inline (controllers + initContainer `mlflow db upgrade` + service + ingress + persistence)
  - `persistence.data.forceRename: mlflow-data` pour préserver le PVC existant (SQLite des expériences)
  - Suppression du dossier `charts/mlflow/` (Chart.yaml + 6 templates)
  - Renovate `helm-values` manager sur `charts/mlflow/` retiré (devenu sans objet)

- [x] **Monitoring multi-machines Beszel + Ansible**
  - Hub Beszel sur cluster k8s (namespace `monitoring`), ingress LAN-only `beszel.tgu.ovh`
  - Agents déployés via Ansible sur N machines (cf. `ansible/inventory.yml`)
  - 8 alertes Telegram configurées (disque, RAM, CPU, agent down, Docker, température)
  - Documentation : spec `2026-05-24-beszel-monitoring-design.md` + plan `2026-05-24-beszel-monitoring.md`

## 🟠 Dette technique


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

## 🔵 Pattern bjw-s/app-template — où l'utiliser à l'avenir

> **Chart** : `https://bjw-s-labs.github.io/helm-charts` — `app-template`
> **Pertinence** : uniquement pour les apps sans chart upstream dédié, et dont les besoins restent dans le cadre "workload standard" (Deployment + Service + Ingress + PVC + ConfigMap/Secret).

**Déjà migré** : `mlflow` (cf. section "Récemment terminé").

### ⚠️ Cas non pertinents (ne pas migrer)

Les apps suivantes ont des charts upstream bien maintenus — **ne pas remplacer par app-template** :
- `dagster`, `certmanager`, `oauth2-proxy`, `postgresql`, `qdrant`, `sealed-secrets`
- `rustfs` (chart dans le dépôt upstream)
- `freshrss`, `komga`, `kubetail`, `jupyter`, `code-server`
- `localai` — chart custom récent et stable, Renovate déjà géré via `customManager` regex (suffixe `-gpu-nvidia-cuda-12`), patterns atypiques (GPU exclusif, ConfigMap seed via initContainer, multi-modèles à venir avec la RTX 3060)
