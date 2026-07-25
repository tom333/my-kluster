#!/usr/bin/env bash
# Migration datastore etcd -> dqlite, reproduction fidèle de l'upgrade officiel
# 001-switch-to-dqlite/commit-master.sh, MAIS :
#   - snapctl (indispo hors contexte snap) remplacé par systemctl
#   - édition args apiserver en sed direct (évite distributed_op.py)
# Le wrapper `microk8s enable ha-cluster` est inutilisable ici : son étape
# 000-switch-to-calico restart containerd -> tous les pods bouncent -> le
# `--wait-ready --timeout 30` échoue sur ce cluster à 82 pods -> rollback auto.
#
# NON-DESTRUCTIF : `k8s-dqlite migrator` dump etcd puis restore dans dqlite.
# L'etcd (12379) n'est jamais modifié -> revert possible (scripts/revert-dqlite-to-etcd.sh).
#
# À lancer en root : sudo bash scripts/migrate-etcd-to-dqlite.sh
set -eu

export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export SNAP_NAME=microk8s
export PATH="/snap/bin:$PATH"   # sudo ne met pas /snap/bin dans le PATH
MICROK8S=/snap/bin/microk8s
ARGS="$SNAP_DATA/args"
BACKUP_DIR="$SNAP_DATA/var/tmp/upgrades/001-switch-to-dqlite"
DB_DIR="$BACKUP_DIR/db"
MANUAL_BAK="$SNAP_DATA/var/tmp/manual-etcd-to-dqlite-bak"

[ "$(id -u)" -eq 0 ] || { echo "ERREUR: à lancer en root (sudo)."; exit 1; }

is_apiserver_ready() {
  ${SNAP}/usr/bin/curl -sL --cert ${SNAP_DATA}/certs/server.crt --key ${SNAP_DATA}/certs/server.key \
    --cacert ${SNAP_DATA}/certs/ca.crt https://127.0.0.1:16443/readyz 2>/dev/null | grep -q "ok"
}

echo "=== [0] Pré-flight + backup args ==="
mkdir -p "$MANUAL_BAK" "$BACKUP_DIR/args"
cp -a "$ARGS/kube-apiserver" "$ARGS/etcd" "$MANUAL_BAK/"
[ -f "$SNAP_DATA/var/lock/no-etcd" ] && { echo "etcd déjà désactivé — déjà migré ?"; exit 1; }
echo "  args sauvés dans $MANUAL_BAK"

echo "=== [1] CNI: arrêter flannel (calico déjà primaire, évite dual-overlay) ==="
touch "$SNAP_DATA/var/lock/no-flanneld"
systemctl stop snap.microk8s.daemon-flanneld 2>/dev/null || true
rm -f "$ARGS/cni-network/flannel.conflist"
# nettoie d'éventuelles interfaces vxlan flannel résiduelles
for l in $(ip -o link show type vxlan 2>/dev/null | grep -E 'flannel' | awk -F': ' '{print $2}' | tr -d ' '); do
  ip link delete "$l" 2>/dev/null || true
done
echo "  flannel arrêté, flannel.conflist retiré"

echo "=== [2] microk8s stop ==="
$MICROK8S stop || true

echo "=== [3] Reconfig apiserver: etcd -> dqlite (kine.sock) ==="
# retire les lignes etcd/storage, ajoute l'endpoint kine dqlite
sed -i -E '/^--(storage-backend|storage-dir|etcd-servers|etcd-cafile|etcd-certfile|etcd-keyfile)=/d' "$ARGS/kube-apiserver"
printf '%s\n' '--etcd-servers=unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379' >> "$ARGS/kube-apiserver"

echo "=== [4] args/etcd en clair (http, pour lecture migrator) ==="
cat > "$ARGS/etcd" <<'EOT'
--data-dir=${SNAP_COMMON}/var/run/etcd
--advertise-client-urls=http://127.0.0.1:12379
--listen-client-urls=http://0.0.0.0:12379
--enable-v2=true
EOT

echo "=== [5] wipe backend dqlite périmé (garde: seulement en mode etcd) + init frais ==="
# Sécurité: ne wipe QUE si on est bien en mode etcd (lock no-k8s-dqlite présent),
# jamais sur un dqlite vivant.
if [ -e "$SNAP_DATA/var/lock/no-k8s-dqlite" ]; then
  rm -rf "$SNAP_DATA/var/kubernetes/backend"
  echo "  backend dqlite périmé wipé"
else
  echo "  ERREUR: pas en mode etcd (no-k8s-dqlite absent) — abort par sécurité"; exit 4
fi
if [ ! -e "$SNAP_DATA/var/kubernetes/backend/cluster.key" ]; then
  mkdir -p "$SNAP_DATA/var/kubernetes/backend"
  echo "Address: 127.0.0.1:19001" > "$SNAP_DATA/var/kubernetes/backend/init.yaml"
  DNS=$(hostname)
  mkdir -p "$SNAP_DATA/var/tmp/"
  cp "$SNAP/certs/csr-dqlite.conf.template" "$SNAP_DATA/var/tmp/csr-dqlite.conf"
  sed -i "s/HOSTNAME/${DNS}/g;s/HOSTIP/127.0.0.1/g" "$SNAP_DATA/var/tmp/csr-dqlite.conf"
  "${SNAP}/openssl.wrapper" req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout "$SNAP_DATA/var/kubernetes/backend/cluster.key" \
    -out "$SNAP_DATA/var/kubernetes/backend/cluster.crt" \
    -subj "/CN=k8s" -config "$SNAP_DATA/var/tmp/csr-dqlite.conf" -extensions v3_ext
  chmod -R o-rwX "$SNAP_DATA/var/kubernetes/backend/"
  chgrp microk8s -R --preserve=mode "$SNAP_DATA/var/kubernetes/backend/" || true
  echo "  dqlite backend initialisé"
else
  echo "  backend déjà présent, skip init"
fi

echo "=== [6] retire lock no-k8s-dqlite + restart dqlite/kubelite ==="
rm -f "$SNAP_DATA/var/lock/no-k8s-dqlite"
systemctl restart snap.microk8s.daemon-k8s-dqlite
systemctl restart snap.microk8s.daemon-kubelite

echo "=== [7] Migration données etcd -> dqlite ==="
# restart (pas start) : etcd doit relire args/etcd (http) sinon reste en https -> migrator hang
systemctl restart snap.microk8s.daemon-etcd
sleep 15
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
echo "  -- backup (dump etcd) --"
$SNAP/bin/k8s-dqlite migrator --mode backup --endpoint "http://127.0.0.1:12379" --db-dir "$DB_DIR" --debug
chmod 600 "$DB_DIR"
echo "  -- attente apiserver (dqlite-backed), max 120s --"
start=$(date +%s)
while ! is_apiserver_ready; do
  sleep 5
  [ $(( $(date +%s) - start )) -gt 120 ] && { echo "  TIMEOUT apiserver"; break; }
done
if is_apiserver_ready; then
  echo "  -- restore (dump -> dqlite) --"
  $SNAP/bin/k8s-dqlite migrator --mode restore \
    --endpoint "unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379" --db-dir "$DB_DIR" --debug
else
  echo "  ERREUR: apiserver pas prêt -> restore non lancé. Voir revert."; exit 2
fi
sleep 10

echo "=== [8] désactive etcd, active dqlite ==="
touch "$SNAP_DATA/var/lock/no-etcd"
systemctl stop snap.microk8s.daemon-etcd
rm -f "$SNAP_DATA/var/lock/no-k8s-dqlite"

echo "=== [9] finalisation ==="
rm -rf "$SNAP_DATA/var/lock/cni-loaded"
touch "$SNAP_DATA/var/lock/ha-cluster"   # marque le node HA-ready (joinable)
$MICROK8S start
$MICROK8S status --wait-ready --timeout 120 || true

echo "=== [10] Vérif ==="
snap services microk8s | grep -Ei 'dqlite|etcd|flanneld'
microk8s status | grep -iE 'high-avail|datastore'
echo "OK migration terminée. (revert dispo: scripts/revert-dqlite-to-etcd.sh)"
