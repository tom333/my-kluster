# préparation
helm repo add argo-cd https://argoproj.github.io/argo-helm
helm dep update


# mot passe par défaut d'argocd
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

helm upgrade -f values.yaml argocd . --version argo-cd-1.0.0 --namespace argocd