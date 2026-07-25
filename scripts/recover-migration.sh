#!/usr/bin/env bash
# Reprise de migrate-etcd-to-dqlite.sh interrompu (bug PATH: microk8s stop KO +
# etcd resté en HTTPS -> migrator backup bloqué). État actuel :
#   - apiserver déjà reconfiguré sur kine.sock (dqlite, vide)
#   - args/etcd déjà réécrits en http MAIS etcd tourne encore en https
#   - backend dqlite initialisé, no-k8s-dqlite retiré, kubelite/dqlite restart faits
# Ce script reprend à l'étape [7] : etcd RESTART (http) -> migrator backup/restore -> finalise.
# etcd data-dir intact -> revert toujours possible (scripts/revert-dqlite-to-etcd.sh).
#
# À lancer en root : sudo bash scripts/recover-migration.sh
set -eu
export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export PATH="/snap/bin:$PATH"
MICROK8S=/snap/bin/microk8s
DB_DIR="$SNAP_DATA/var/tmp/upgrades/001-switch-to-dqlite/db"

[ "$(id -u)" -eq 0 ] || { echo "ERREUR: root requis (sudo)."; exit 1; }

is_apiserver_ready() {
  ${SNAP}/usr/bin/curl -sL --cert ${SNAP_DATA}/certs/server.crt --key ${SNAP_DATA}/certs/server.key \
    --cacert ${SNAP_DATA}/certs/ca.crt https://127.0.0.1:16443/readyz 2>/dev/null | grep -q "ok"
}

echo "=== [7a] restart etcd (relit args http) ==="
systemctl restart snap.microk8s.daemon-etcd
sleep 8
echo "  test etcd http:"; ${SNAP}/usr/bin/curl -s http://127.0.0.1:12379/version && echo || { echo "  etcd pas en http -> STOP"; exit 2; }

echo "=== [7b] backup (dump etcd) ==="
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
$SNAP/bin/k8s-dqlite migrator --mode backup --endpoint "http://127.0.0.1:12379" --db-dir "$DB_DIR" --debug
chmod 600 "$DB_DIR"
echo "  dump fait: $(ls -1 "$DB_DIR" | wc -l) fichier(s)"

echo "=== [7c] attente apiserver (dqlite), max 120s ==="
start=$(date +%s)
while ! is_apiserver_ready; do
  sleep 5; [ $(( $(date +%s) - start )) -gt 120 ] && { echo "  TIMEOUT apiserver"; break; }
done

echo "=== [7d] restore (dump -> dqlite) ==="
if is_apiserver_ready; then
  $SNAP/bin/k8s-dqlite migrator --mode restore \
    --endpoint "unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379" --db-dir "$DB_DIR" --debug
else
  echo "  ERREUR: apiserver pas prêt -> restore non lancé."; exit 3
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
echo "OK reprise terminée."
