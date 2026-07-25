#!/usr/bin/env bash
# Finalise : etcd est UP sur http (args corrigés sans enable-v2). Il reste le migrator
# (modes corrects: backup-etcd / restore-dqlite) + finalisation.
# Fix vs finish2: curls guardés (|| true) pour ne pas tuer set -e.
# À lancer en root : sudo bash scripts/finish-dqlite-migration3.sh
set -eu
export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export PATH="/snap/bin:$PATH"
MICROK8S=/snap/bin/microk8s
DB_DIR="$SNAP_DATA/var/tmp/upgrades/001-switch-to-dqlite/db"

[ "$(id -u)" -eq 0 ] || { echo "root requis (sudo)."; exit 1; }

apiserver_ready() {
  local o
  o=$(${SNAP}/usr/bin/curl -sL --cert ${SNAP_DATA}/certs/server.crt --key ${SNAP_DATA}/certs/server.key \
    --cacert ${SNAP_DATA}/certs/ca.crt https://127.0.0.1:16443/readyz 2>/dev/null || true)
  [ "$o" = "ok" ]
}

echo "=== vérif etcd http ==="
h=$(${SNAP}/usr/bin/curl -s http://127.0.0.1:12379/health 2>/dev/null || true)
echo "  etcd: ${h:-DOWN}"
[ -n "$h" ] || { echo "ERREUR etcd down"; exit 2; }

echo "=== [7b] backup-etcd (dump) ==="
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
$SNAP/bin/k8s-dqlite migrator --mode backup-etcd --endpoint "http://127.0.0.1:12379" --db-dir "$DB_DIR" --debug
echo "  dump: $(ls -1 "$DB_DIR" 2>/dev/null | wc -l) fichier(s), taille $(du -sh "$DB_DIR" 2>/dev/null | awk '{print $1}')"

echo "=== [7c] attente apiserver (dqlite), max 90s (non-fatal) ==="
start=$(date +%s)
while ! apiserver_ready; do
  sleep 5; [ $(( $(date +%s) - start )) -gt 90 ] && { echo "  apiserver pas prêt — on tente le restore quand même (écrit sur kine.sock)"; break; }
done

echo "=== [7d] restore-dqlite (load) ==="
$SNAP/bin/k8s-dqlite migrator --mode restore-dqlite \
  --endpoint "unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379" --db-dir "$DB_DIR" --debug
sleep 10

echo "=== [8] etcd OFF, dqlite ON ==="
touch "$SNAP_DATA/var/lock/no-etcd"
systemctl stop snap.microk8s.daemon-etcd
rm -f "$SNAP_DATA/var/lock/no-k8s-dqlite"

echo "=== [9] finalisation ==="
rm -rf "$SNAP_DATA/var/lock/cni-loaded"
touch "$SNAP_DATA/var/lock/ha-cluster"
$MICROK8S start
$MICROK8S status --wait-ready --timeout 120 || true

echo "=== [10] Vérif ==="
snap services microk8s | grep -Ei 'dqlite|etcd|flanneld'
$MICROK8S status | grep -iE 'high-avail|datastore'
echo "OK migration datastore terminée."
