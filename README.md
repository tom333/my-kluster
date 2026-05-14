
# Init

kubectl apply -f cluster-secrets.yaml
helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace

## Récupération du mot de passe admin pour argo cd
kubectl -n argocd get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}" | base64 -d



kubectl patch deployment rustfs -n ia-lab --type=json -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path", "value": "/health"}]'




# ménage : 
- suppression pod completed: 
kubectl delete pod --field-selector=status.phase=Succeeded -A

- suppression images non utilisées: 
microk8s ctr images prune --all
