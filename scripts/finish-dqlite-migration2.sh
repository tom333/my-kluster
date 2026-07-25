#!/usr/bin/env bash
# Finalise la migration : etcd ne démarrait pas (--enable-v2 inconnu de cette version
# d'etcd) -> migrator bloqué. Fix: args/etcd http SANS enable-v2 + reset-failed +
# modes migrator corrects de cette version (backup-etcd / restore-dqlite).
# État attendu: microk8s stoppé, dqlite+kubelite up (apiserver sur dqlite vide),
# backend dqlite initialisé, etcd DOWN.
# À lancer en root : sudo bash scripts/finish-dqlite-migration2.sh
set -eu
export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export PATH="/snap/bin:$PATH"
MICROK8S=/snap/bin/microk8s
ARGS="$SNAP_DATA/args"
DB_DIR="$SNAP_DATA/var/tmp/upgrades/001-switch-to-dqlite/db"

[ "$(id -u)" -eq 0 ] || { echo "root requis (sudo)."; exit 1; }

is_apiserver_ready() {
  ${SNAP}/usr/bin/curl -sL --cert ${SNAP_DATA}/certs/server.crt --key ${SNAP_DATA}/certs/server.key \
    --cacert ${SNAP_DATA}/certs/ca.crt https://127.0.0.1:16443/readyz 2>/dev/null | grep -q "ok"
}

echo "=== [7a] args/etcd http SANS --enable-v2 ==="
cat > "$ARGS/etcd" <<'EOT'
--data-dir=${SNAP_COMMON}/var/run/etcd
--advertise-client-urls=http://127.0.0.1:12379
--listen-client-urls=http://0.0.0.0:12379
EOT
systemctl reset-failed snap.microk8s.daemon-etcd 2>/dev/null || true
systemctl restart snap.microk8s.daemon-etcd
echo "  attente etcd http..."
for i in $(seq 1 12); do
  h=$(${SNAP}/usr/bin/curl -s http://127.0.0.1:12379/health 2>/dev/null)
  [ -n "$h" ] && { echo "  etcd OK: $h"; break; }
  sleep 3
done
[ -n "${h:-}" ] || { echo "  ERREUR: etcd toujours down"; systemctl status snap.microk8s.daemon-etcd --no-pager | tail -5; exit 2; }

echo "=== [7b] backup-etcd (dump) ==="
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
$SNAP/bin/k8s-dqlite migrator --mode backup-etcd --endpoint "http://127.0.0.1:12379" --db-dir "$DB_DIR" --debug
echo "  dump: $(ls -1 "$DB_DIR" 2>/dev/null | wc -l) fichier(s)"

echo "=== [7c] attente apiserver (dqlite), max 120s ==="
start=$(date +%s)
while ! is_apiserver_ready; do
  sleep 5; [ $(( $(date +%s) - start )) -gt 120 ] && { echo "  TIMEOUT apiserver"; break; }
done

echo "=== [7d] restore-dqlite (load) ==="
if is_apiserver_ready; then
  $SNAP/bin/k8s-dqlite migrator --mode restore-dqlite \
    --endpoint "unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379" --db-dir "$DB_DIR" --debug
else
  echo "  ERREUR: apiserver pas prêt -> restore non lancé (revert dispo)."; exit 3
fi
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
