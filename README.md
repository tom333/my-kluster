
# Init

kubectl apply -f cluster-secrets.yaml
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace