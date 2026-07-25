#!/usr/bin/env bash
# REVERT d'urgence : rebascule le datastore dqlite -> etcd (known-good).
# À utiliser si migrate-etcd-to-dqlite.sh a laissé l'apiserver KO.
# L'etcd n'ayant jamais été modifié par la migration (migrator lecture seule),
# ce revert restaure l'état datastore d'avant. La CNI calico est laissée telle
# quelle (fonctionnelle) — on ne touche que le datastore.
#
# À lancer en root : sudo bash scripts/revert-dqlite-to-etcd.sh
set -eu
export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_NAME=microk8s
export PATH="/snap/bin:$PATH"   # sudo ne met pas /snap/bin dans le PATH
MICROK8S=/snap/bin/microk8s
ARGS="$SNAP_DATA/args"
MANUAL_BAK="$SNAP_DATA/var/tmp/manual-etcd-to-dqlite-bak"

[ "$(id -u)" -eq 0 ] || { echo "ERREUR: root requis (sudo)."; exit 1; }
[ -f "$MANUAL_BAK/kube-apiserver" ] || { echo "ERREUR: backup args introuvable ($MANUAL_BAK)."; exit 1; }

echo "=== stop ==="; $MICROK8S stop || true
echo "=== restore args apiserver + etcd (etcd datastore) ==="
cp -a "$MANUAL_BAK/kube-apiserver" "$ARGS/kube-apiserver"
cp -a "$MANUAL_BAK/etcd" "$ARGS/etcd"
echo "=== locks: etcd ON, dqlite OFF, ha-cluster OFF ==="
rm -f "$SNAP_DATA/var/lock/no-etcd"
touch "$SNAP_DATA/var/lock/no-k8s-dqlite"
rm -f "$SNAP_DATA/var/lock/ha-cluster"
echo "=== start ==="; $MICROK8S start
$MICROK8S status --wait-ready --timeout 120 || true
snap services microk8s | grep -Ei 'dqlite|etcd'
echo "OK revert etcd terminé."
