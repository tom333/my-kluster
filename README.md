
# Init

kubectl apply -f cluster-secrets.yaml
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace

## Récupération du mot de passe admin pour argo cd
kubectl -n argocd get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d

