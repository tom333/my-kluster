# my-kluster

Configuration GitOps d'un cluster **MicroK8s** single-node géré par **ArgoCD**.
Voir [`CLAUDE.md`](CLAUDE.md) pour l'architecture complète, les conventions et les règles.

## Bootstrap

```bash
# 1. Restaurer la clé master Sealed Secrets (depuis backup hors-cluster)
kubectl apply -f ~/sealed-secrets-master-XXXXXXXX.key.backup

# 2. Installer ArgoCD
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace

# 3. Récupérer le mot de passe admin
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# 4. Déployer les app-of-apps
helm install argocd-apps argocd/argocd-install-apps/ --namespace argocd
```

ArgoCD installe ensuite `sealed-secrets-controller`, déchiffre tous les `SealedSecret` du dossier `sealed/`, puis déploie l'ensemble des applications.

## Maintenance courante

```bash
# Supprimer les pods Completed
kubectl delete pod --field-selector=status.phase=Succeeded -A

# Nettoyer les images MicroK8s non utilisées
microk8s ctr images prune --all

# Patch manuel RustFS (workaround bug upstream #1844 readinessProbe)
kubectl patch deployment rustfs -n ia-lab --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path", "value": "/health"}]'
```

## Ajouter un secret

```bash
kubectl create secret generic <name> --namespace=<ns> \
  --from-literal=<key>=<value> --dry-run=client -o yaml \
  | kubeseal --format=yaml > sealed/<name>.yaml

git add sealed/<name>.yaml && git commit -m "feat(sealed): add <name>" && git push
```

ArgoCD synchronise l'app `sealed` et le Secret apparaît dans le cluster.

## Hooks pre-commit

```bash
pre-commit install
```

Bloque les commits contenant des secrets en clair via `gitleaks` (CI redondante dans `.github/workflows/gitleaks.yml`).
