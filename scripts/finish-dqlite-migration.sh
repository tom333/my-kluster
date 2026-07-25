#!/usr/bin/env bash
# Reprend migrate-etcd-to-dqlite.sh après l'échec de l'init (openssl.wrapper source
# utils.sh -> REAL_PATH unbound sous set -u). Ici on utilise l'openssl SYSTÈME.
# État au lancement : microk8s STOPPÉ, backend dqlite wipé, args apiserver->kine.sock,
# args/etcd en http. On fait : init dqlite (openssl système) -> migrator -> finalise.
# À lancer en root : sudo bash scripts/finish-dqlite-migration.sh
set -eu
export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export PATH="/snap/bin:$PATH"
MICROK8S=/snap/bin/microk8s
BACKEND="$SNAP_DATA/var/kubernetes/backend"
DB_DIR="$SNAP_DATA/var/tmp/upgrades/001-switch-to-dqlite/db"

[ "$(id -u)" -eq 0 ] || { echo "root requis (sudo)."; exit 1; }

is_apiserver_ready() {
  ${SNAP}/usr/bin/curl -sL --cert ${SNAP_DATA}/certs/server.crt --key ${SNAP_DATA}/certs/server.key \
    --cacert ${SNAP_DATA}/certs/ca.crt https://127.0.0.1:16443/readyz 2>/dev/null | grep -q "ok"
}

echo "=== [5b] init dqlite (openssl système) ==="
mkdir -p "$BACKEND"
echo "Address: 127.0.0.1:19001" > "$BACKEND/init.yaml"
DNS=$(hostname)
CONF="$SNAP_DATA/var/tmp/csr-dqlite.conf"
mkdir -p "$SNAP_DATA/var/tmp"
cp "$SNAP/certs/csr-dqlite.conf.template" "$CONF"
sed -i "s/HOSTNAME/${DNS}/g;s/HOSTIP/127.0.0.1/g" "$CONF"
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout "$BACKEND/cluster.key" -out "$BACKEND/cluster.crt" \
  -subj "/CN=k8s" -config "$CONF" -extensions v3_ext
chmod -R o-rwX "$BACKEND"
chgrp microk8s -R --preserve=mode "$BACKEND" || true
echo "  backend initialisé: $(ls "$BACKEND")"

echo "=== [6] retire lock no-k8s-dqlite + restart dqlite/kubelite ==="
rm -f "$SNAP_DATA/var/lock/no-k8s-dqlite"
systemctl restart snap.microk8s.daemon-k8s-dqlite
systemctl restart snap.microk8s.daemon-kubelite

echo "=== [7] migration données etcd -> dqlite ==="
systemctl restart snap.microk8s.daemon-etcd   # relit args http
sleep 10
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
echo "  -- backup (dump etcd http) --"
$SNAP/bin/k8s-dqlite migrator --mode backup --endpoint "http://127.0.0.1:12379" --db-dir "$DB_DIR" --debug
chmod 600 "$DB_DIR"
echo "  dump: $(ls -1 "$DB_DIR" | wc -l) fichier(s)"
echo "  -- attente apiserver (dqlite), max 120s --"
start=$(date +%s)
while ! is_apiserver_ready; do
  sleep 5; [ $(( $(date +%s) - start )) -gt 120 ] && { echo "  TIMEOUT apiserver"; break; }
done
if is_apiserver_ready; then
  echo "  -- restore (dump -> dqlite) --"
  $SNAP/bin/k8s-dqlite migrator --mode restore \
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
