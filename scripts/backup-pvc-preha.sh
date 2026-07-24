#!/usr/bin/env bash
# Backup des PVC irremplaçables avant migration ha-cluster (etcd+flannel -> dqlite+calico).
# Cible LOCALE /data (survit à `microk8s reset` : reset ne wipe que /var/snap/microk8s).
# À lancer en root : sudo bash scripts/backup-pvc-preha.sh
set -euo pipefail

# default-storage est un symlink (-> /data/kube/default-storage) : résoudre le vrai
# chemin, sinon `find` ne suit pas le lien et ne trouve rien.
STORE="$(readlink -f /var/snap/microk8s/common/default-storage)"
DEST="/data/pvc-backup-20260725"
mkdir -p "$DEST"
# Nettoyer les fichiers vides laissés par un run précédent raté.
find "$DEST" -maxdepth 1 -type f -size 0 -delete 2>/dev/null || true

# Consolider les dumps logiques k8s (générés en `moi` au préalable) dans DEST.
K8SDUMP="/tmp/claude-1000/-data-projets-perso-my-kluster/26b6daf4-ae1a-4141-b9f2-d271fa42e3bf/scratchpad/k8s-dump"
if compgen -G "$K8SDUMP/*.yaml" >/dev/null; then
  cp "$K8SDUMP"/*.yaml "$DEST"/ && echo "== dumps k8s logiques consolidés dans DEST =="
else
  echo "== WARN: dumps k8s introuvables dans $K8SDUMP (les regénérer en 'moi') =="
fi

# 🔴 PVC irremplaçables : "nom_logique  vol-UID". Dir réel = $STORE/*<vol-UID>.
# (localai-models/backends/output, voice, brain, arr, media-nas => volontairement EXCLUS : recréables.)
PVCS=(
  "registry-claim            pvc-55cb139c-a76c-4604-bd87-71304eb89369"
  "datalab-postgresql        pvc-4a6d6b8a-c7f6-4b34-9e37-ed19d09d3eda"
  "dagster-postgresql        pvc-b8350a70-87e6-4603-a385-4a3a07aaa1e2"
  "mlflow-data               pvc-8800a61b-5358-4af1-85bd-c800e346b473"
  "rustfs-data               pvc-8f76a6ea-b8ae-459f-a827-329a77c83fa1"
  "hermes-agent-data         pvc-ce6692cf-04e5-4f46-84c5-8a8fb85b455e"
  "hermes-agent-files        pvc-7cf8e9d2-338a-401d-8b10-ee8935f43b7e"
  "qdrant-datalab            pvc-d205fcfa-b3f0-4fd1-b4f5-2a546cd2b468"
  "qdrant-cv                 pvc-13c8f1c6-99d6-4ec0-a9b0-9a1a89c5db8d"
  "dagster-models            pvc-5fff892b-2016-483d-89d9-2c37b6187df7"
  "txtai                     pvc-b2f4d5f0-8c34-4e43-a822-710826dcbc3b"
  "openwebui                 pvc-8075e251-37be-4613-ba29-406830e52cbf"
)

echo "== Cible: $DEST (dispo: $(df -h /data | awk 'NR==2{print $4}')) =="

# Note : le dump logique de l'état k8s est fait séparément en tant que `moi`
# (microk8s kubectl a besoin du kubeconfig du groupe microk8s, indispo en root).

# Backup des données PVC 🔴
for entry in "${PVCS[@]}"; do
  name=$(awk '{print $1}' <<<"$entry")
  uid=$(awk '{print $2}' <<<"$entry")
  dir=$(find "$STORE" -maxdepth 1 -type d -name "*${uid}" 2>/dev/null | head -1)
  if [[ -z "$dir" ]]; then
    echo "  [SKIP] $name : dossier introuvable ($uid)"
    continue
  fi
  sz=$(du -sh "$dir" 2>/dev/null | awk '{print $1}')
  echo "  [TAR ] $name ($sz) <- $(basename "$dir")"
  tar -I 'zstd -3 -T0' -cf "$DEST/${name}.tar.zst" -C "$STORE" "$(basename "$dir")"
done

# 3) Récap + checksums
echo "== Récap =="
ls -lh "$DEST"
( cd "$DEST" && sha256sum ./*.tar.zst > SHA256SUMS && echo "checksums -> $DEST/SHA256SUMS" )
echo "== Total: $(du -sh "$DEST" | awk '{print $1}') =="
echo "OK. Backup dans $DEST"
