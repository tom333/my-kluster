#!/usr/bin/env bash
# Migration datastore dqlite -> etcd. Inverse de scripts/migrate-etcd-to-dqlite.sh.
#
# POURQUOI. Depuis la migration etcd->dqlite du 2026-07-25, les caches de veille de
# l'apiserver gèlent et ne se réparent jamais seuls : le flux qui les alimente décroche,
# et à la reprise l'apiserver redemande une révision que la compaction a effacée, en
# bouclant dessus au lieu de relire à neuf. Bugs amont OUVERTS, sans correctif annoncé :
# canonical/microk8s#5153 et #5568. Le 2026-08-27 la fenêtre entre deux gels était
# tombée à ~15 min, rendant toute réparation en ligne impossible.
# Analyse complète : docs/superpowers/specs/2026-08-27-dqlite-panne-plan-de-controle.md
#
# POURQUOI CE CHEMIN MARCHE QUAND LE RESTE ÉCHOUE : tout se fait cluster arrêté. Aucune
# étape ne dépend du scheduler, des caches ni d'une fenêtre saine.
#
# NON DESTRUCTIF. On LIT dqlite et on ÉCRIT dans etcd. Le backend dqlite n'est JAMAIS
# effacé : le retour arrière consiste à rebasculer deux verrous et un fichier d'arguments
# (procédure imprimée en fin d'exécution, et rappelée en cas d'échec).
#
# ⚠️ CONSÉQUENCE ASSUMÉE : l'appartenance de `jeux` au cluster vit dans dqlite. Le worker
# SORTIRA du cluster. Le rejoindre passerait par l'API v1 de join, qui câble flannel en
# dur (`update_flannel` dans scripts/wrappers/join.py) — donc les deux nœuds sur flannel,
# et les 7 NetworkPolicies du chart ArgoCD cesseraient d'être appliquées. Décision
# volontairement REPORTÉE : on remet `pc` debout d'abord.
#
# Usage :  sudo bash scripts/migrate-dqlite-to-etcd.sh --go
#          (sans --go : affiche le plan et l'état, ne modifie rien)
set -eu

export SNAP=/snap/microk8s/current
export SNAP_DATA=/var/snap/microk8s/current
export SNAP_COMMON=/var/snap/microk8s/common
export SNAP_NAME=microk8s
export PATH="/snap/bin:$PATH"       # sudo ne met pas /snap/bin dans le PATH
MICROK8S=/snap/bin/microk8s
ARGS="$SNAP_DATA/args"
LOCKS="$SNAP_DATA/var/lock"
KINE="unix://${SNAP_DATA}/var/kubernetes/backend/kine.sock:12379"
ETCD_URL="http://127.0.0.1:12379"
ETCD_DATA="${SNAP_COMMON}/var/run/etcd"
BAK="$SNAP_DATA/var/tmp/manual-dqlite-to-etcd-bak"
DB_DIR="$BAK/db"

[ "$(id -u)" -eq 0 ] || { echo "ERREUR: à lancer en root (sudo)."; exit 1; }

etcd_ready() {
  "$SNAP/etcdctl" --endpoints="$ETCD_URL" endpoint health >/dev/null 2>&1
}

rappel_rollback() {
  cat <<ROLLBACK

  ── RETOUR ARRIÈRE (les données dqlite sont intactes) ──
    sudo cp -a $BAK/kube-apiserver $ARGS/kube-apiserver
    sudo rm -f  $LOCKS/no-k8s-dqlite
    sudo touch  $LOCKS/no-etcd
    sudo touch  $LOCKS/ha-cluster
    sudo microk8s stop && sudo microk8s start
ROLLBACK
}

echo "=== [0] Pré-flight ==="
[ -e "$LOCKS/no-k8s-dqlite" ] && { echo "ERREUR: no-k8s-dqlite présent — déjà en mode etcd ?"; exit 1; }
[ -S "${SNAP_DATA}/var/kubernetes/backend/kine.sock" ] || { echo "ERREUR: kine.sock absent — dqlite ne tourne pas."; exit 1; }
[ -x "$SNAP/etcd" ] || { echo "ERREUR: binaire etcd absent du snap."; exit 1; }
echo "  mode dqlite confirmé, etcd disponible ($("$SNAP/etcd" --version | head -1))"
echo "  nœuds actuellement dans le cluster :"
$MICROK8S kubectl get nodes --no-headers 2>/dev/null | awk '{print "    "$1" "$2}' || echo "    (apiserver injoignable — sans conséquence, la migration lit dqlite directement)"

if [ "${1:-}" != "--go" ]; then
  cat <<PLAN

  Rien n'a été modifié. Plan si tu relances avec --go :
    1. sauvegarder args + dumper dqlite  (aucune modification)
    2. arrêter kubelite  (coupe l'agitation d'écriture, dqlite reste debout)
    3. dump dqlite -> $DB_DIR
    4. arrêter dqlite, vider le datadir etcd (état vieux d'un mois), démarrer etcd
    5. restaurer le dump dans etcd, et VÉRIFIER qu'il contient des clés
    6. basculer l'apiserver sur etcd + verrous
    7. démarrer et vérifier
  Le backend dqlite n'est jamais effacé.
PLAN
  exit 0
fi

echo "=== [1] Sauvegarde des arguments ==="
mkdir -p "$BAK"
cp -a "$ARGS/kube-apiserver" "$BAK/kube-apiserver"
[ -f "$ARGS/etcd" ] && cp -a "$ARGS/etcd" "$BAK/etcd"
chmod -R go-rwx "$BAK"
echo "  args sauvés dans $BAK"

echo "=== [2] Arrêt de kubelite (dqlite reste debout pour la lecture) ==="
# Couper l'apiserver met la base au repos : le dump se fait sur une cible qui ne
# bouge plus, au lieu de concourir avec ~2,7 écritures/s.
systemctl stop snap.microk8s.daemon-kubelite
sleep 5
echo "  kubelite arrêté"

echo "=== [3] Dump de dqlite ==="
rm -rf "$DB_DIR"; mkdir -p "$DB_DIR"
"$SNAP/bin/k8s-dqlite" migrator --mode backup-dqlite --endpoint "$KINE" --db-dir "$DB_DIR"
nb=$(find "$DB_DIR" -type f | wc -l)
[ "$nb" -gt 0 ] || { echo "ERREUR: dump vide — on ne bascule PAS."; systemctl start snap.microk8s.daemon-kubelite; exit 2; }
chmod -R go-rwx "$DB_DIR"
echo "  $nb fichiers dumpés dans $DB_DIR"

echo "=== [4] Arrêt de dqlite, etcd propre ==="
systemctl stop snap.microk8s.daemon-k8s-dqlite
# Le datadir etcd contient l'état d'avant le 2026-07-25. Restaurer par-dessus
# mélangerait deux générations de cluster : on repart d'une base vide.
rm -rf "$ETCD_DATA"
mkdir -p "$ETCD_DATA"
# Écoute en BOUCLE LOCALE uniquement. Les arguments hérités de juillet écoutaient
# en clair sur 0.0.0.0 — acceptable pour une lecture ponctuelle, inadmissible pour
# un datastore permanent : un etcd sans authentification joignable depuis le LAN
# donne le contrôle total du cluster. Mono-nœud, l'apiserver est local : loopback suffit.
cat > "$ARGS/etcd" <<'EOT'
--data-dir=${SNAP_COMMON}/var/run/etcd
--advertise-client-urls=http://127.0.0.1:12379
--listen-client-urls=http://127.0.0.1:12379
EOT
rm -f "$LOCKS/no-etcd"
systemctl restart snap.microk8s.daemon-etcd
start=$(date +%s)
until etcd_ready; do
  sleep 3
  [ $(( $(date +%s) - start )) -gt 90 ] && { echo "ERREUR: etcd ne démarre pas."; rappel_rollback; exit 3; }
done
echo "  etcd prêt sur $ETCD_URL (boucle locale)"

echo "=== [5] Restauration du dump dans etcd ==="
"$SNAP/bin/k8s-dqlite" migrator --mode restore-etcd --endpoint "$ETCD_URL" --db-dir "$DB_DIR"
cles=$("$SNAP/etcdctl" --endpoints="$ETCD_URL" get /registry --prefix --keys-only 2>/dev/null | grep -c . || echo 0)
# Garde-fou : basculer l'apiserver sur un etcd vide donnerait un cluster vierge —
# toutes les ressources disparues. On refuse tant que la restauration n'est pas prouvée.
[ "$cles" -gt 100 ] || { echo "ERREUR: seulement $cles clés dans etcd — restauration douteuse, on ne bascule PAS."; rappel_rollback; exit 4; }
echo "  $cles clés restaurées sous /registry"

echo "=== [6] Bascule de l'apiserver sur etcd ==="
sed -i -E '/^--etcd-servers=/d' "$ARGS/kube-apiserver"
printf '%s\n' "--etcd-servers=$ETCD_URL" >> "$ARGS/kube-apiserver"
touch "$LOCKS/no-k8s-dqlite"      # dqlite ne redémarrera pas
rm -f "$LOCKS/ha-cluster"          # nœud non-HA : c'est le mode etcd
echo "  apiserver -> $ETCD_URL, dqlite verrouillé"

echo "=== [7] Démarrage ==="
$MICROK8S start
$MICROK8S status --wait-ready --timeout 180 || true

echo "=== [8] Vérification ==="
snap services microk8s | grep -Ei 'dqlite|etcd' || true
$MICROK8S status | grep -iE 'high-avail|datastore' || true
echo "  --- écart de cache (doit rester faible et le rester) ---"
$MICROK8S kubectl get --raw "/api/v1/pods?limit=1" 2>/dev/null \
  | python3 -c 'import json,sys; print("  quorum =", json.load(sys.stdin)["metadata"]["resourceVersion"])' || true
$MICROK8S kubectl get --raw "/api/v1/pods?limit=1&resourceVersion=0" 2>/dev/null \
  | python3 -c 'import json,sys; print("  cache  =", json.load(sys.stdin)["metadata"]["resourceVersion"])' || true
echo "  --- nœuds ---"
$MICROK8S kubectl get nodes --no-headers 2>/dev/null | awk '{print "    "$1" "$2}' || true

cat <<'FIN'

OK. `jeux` est attendu ABSENT (son appartenance vivait dans dqlite) — voir l'en-tête
du script avant de le rejoindre : le chemin de join en mode etcd impose flannel.

À surveiller les prochaines heures, c'est le juge de paix :
  journalctl -u snap.microk8s.daemon-kubelite --since -10min | grep -c "Too large resource version"
0 = la classe d'incident a disparu.
FIN
rappel_rollback
