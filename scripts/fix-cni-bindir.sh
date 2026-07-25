#!/usr/bin/env bash
# FIX incident CNI : le rollback du 000-switch-to-calico a laissé containerd
# bin_dir="${SNAP}/opt/cni/bin" (snap read-only, SANS calico) alors que calico
# est dans "${SNAP_DATA}/opt/cni/bin" -> "failed to find plugin calico" -> tous
# les sandboxes échouent -> 1 pod Running.
# Fix = repointer bin_dir vers SNAP_DATA (ce que 000-commit fait) + restart containerd.
# À lancer en root : sudo bash scripts/fix-cni-bindir.sh
set -eu
TPL=/var/snap/microk8s/current/args/containerd-template.toml
[ "$(id -u)" -eq 0 ] || { echo "root requis (sudo)."; exit 1; }

echo "avant: $(grep bin_dir "$TPL")"
sed -i 's|bin_dir = "${SNAP}/opt/cni/bin"|bin_dir = "${SNAP_DATA}/opt/cni/bin"|' "$TPL"
echo "après: $(grep bin_dir "$TPL")"

echo "restart containerd..."
systemctl restart snap.microk8s.daemon-containerd
sleep 5
systemctl restart snap.microk8s.daemon-kubelite
echo "OK — pods devraient repartir (CNI trouve calico). Surveiller get pods."
