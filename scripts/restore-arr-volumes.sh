#!/usr/bin/env bash
# Restaure les volumes de configuration des applications *arr depuis les PV
# conservés (phase Released, reclaim policy Retain) vers les PVC actifs.
#
# POURQUOI. Le 2026-08-28, l'auto-merge Renovate de arr-stack v0.53.9 a fait passer
# app-template de 5.0.1 à 5.1.0 — une RUPTURE pour ce chart parapluie : le rendu est
# tombé de 59 à 6 ressources. ArgoCD, en `prune: true`, a supprimé les PVC ; le chart
# les a recréés VIDES. Les applications tournent depuis sur des bases vierges pendant
# que les vraies données dorment dans les anciens volumes.
# Mesuré : radarr.db 44,1 Mo contre 696 Ko ; sonarr.db 19,7 Mo contre 455 Ko.
#
# COMPATIBILITÉ VÉRIFIÉE avant d'écrire ce script — le niveau de schéma des bases
# anciennes est IDENTIQUE à celui des bases neuves :
#   sonarr 217=217 · radarr 242=242 · prowlarr 44=44 (table VersionInfo)
# Donc aucune rétrogradation, aucun risque du type « SQLite Error: no such column »
# qui avait cassé cleanuparr lors d'un précédent retour arrière.
#
# NON DESTRUCTIF POUR L'ANCIEN. Les répertoires sources ne sont JAMAIS modifiés ni
# supprimés : ils restent en Retain et redeviennent le filet si quelque chose casse.
# Les volumes actifs sont sauvegardés avant écrasement.
#
# Usage :  bash scripts/restore-arr-volumes.sh          # plan, ne modifie rien
#          bash scripts/restore-arr-volumes.sh --go     # exécute
# Pas de sudo : les volumes sont en drwxrwxrwx moi:moi.
set -euo pipefail

BASE=/var/snap/microk8s/common/default-storage
NS=selfhost
APP=arr-stack
PARENT=applications        # app-of-apps qui réécrit $APP depuis Git
HORODATAGE=$(date +%Y%m%d-%H%M%S)
# PAS sous /data/kube : ce répertoire appartient à root en drwxr-xr-x. Seuls les
# répertoires de volumes qu'il contient sont ouverts (drwxrwxrwx moi:moi) — d'où un
# `mkdir: Permission denied` constaté le 2026-08-28, qui a laissé la pile arrêtée.
SAUVEGARDE="${HOME}/restore-backup-$HORODATAGE"

# app  ancien_uid  nouveau_uid — relevés le 2026-08-28. Le script VÉRIFIE chaque
# paire avant de copier : si un UID ne correspond plus (PVC recréé entre-temps),
# il s'arrête plutôt que d'écraser le mauvais répertoire.
PAIRES=(
  "sonarr      0dcac172-7f11-4105-a791-1fdf7f78f8cc  412eae3c-12cd-460c-aba9-598ef90b1c3f"
  "radarr      030fa76b-2cce-4d34-ae9d-f401ee03462e  1a95d5aa-6b53-47b1-ac4c-104890f825f9"
  "prowlarr    0bca50a9-d772-40d5-bba0-8814c0f31425  917124fe-d349-4822-b054-52439c9faa4a"
  "qbittorrent f85854e2-6fc9-4df2-ab27-2016a7598b29  e30cf346-82cc-4db9-b65c-4b41fbe4b04d"
  "seerr       18624528-a85f-4d51-8b4f-2d1e60b2a24b  d3ed6879-fd3b-4de0-b3df-ea5b9b1ef006"
  "jellyfin    94626ad5-6833-40eb-85d8-144505549c06  e114f9d0-5795-43e6-8b48-cfd76c47b274"
  "cleanuparr  c262f4eb-ac3f-4791-b5ae-d1f415233888  e9bc2f20-b63c-4c4a-8eda-6f66cdc8261e"
)

EXEC=0
[ "${1:-}" = "--go" ] && EXEC=1

echo "=== [0] Vérifications ==="
command -v rsync >/dev/null || { echo "ERREUR: rsync requis."; exit 1; }
besoin=0
for p in "${PAIRES[@]}"; do
  read -r app old new <<<"$p"
  do_=$BASE/selfhost-$app-pvc-$old
  dn=$BASE/selfhost-$app-pvc-$new
  [ -d "$do_" ] || { echo "ERREUR: source absente pour $app : $do_"; exit 2; }
  [ -d "$dn" ]  || { echo "ERREUR: cible absente pour $app : $dn"; exit 2; }
  # Le PVC actif DOIT pointer sur le nouveau volume attendu, sinon on écraserait
  # un volume qui n'est plus celui de l'application.
  lie=$(kubectl get pvc "$app" -n "$NS" -o jsonpath='{.spec.volumeName}' 2>/dev/null || echo "")
  [ "$lie" = "pvc-$new" ] || { echo "ERREUR: $app est lié à '$lie', pas à 'pvc-$new'. Abandon."; exit 3; }
  o=$(du -sb "$do_" | cut -f1); n=$(du -sb "$dn" | cut -f1)
  besoin=$((besoin + o + n))
  printf "  %-12s ancien %6.1f Mo -> cible %6.1f Mo\n" "$app" "$((o/1000))e-3" "$((n/1000))e-3" 2>/dev/null \
    || printf "  %-12s ancien %s o -> cible %s o\n" "$app" "$o" "$n"
done
dispo=$(df -B1 --output=avail "$BASE" | tail -1)
echo "  espace requis (copie + sauvegarde) : $((besoin/1000000)) Mo · disponible : $((dispo/1000000)) Mo"
[ "$dispo" -gt "$((besoin * 2))" ] || { echo "ERREUR: marge disque insuffisante."; exit 4; }

if [ "$EXEC" -eq 0 ]; then
  cat <<PLAN

  Rien n'a été modifié. Avec --go, le script :
    1. coupe la synchro auto d'ArgoCD sur $PARENT ET $APP — les deux niveaux, car
       l'app-of-apps réécrit sinon $APP depuis Git et rétablit selfHeal, qui relance
       les pods EN PLEINE COPIE ;
    2. met les 7 déploiements à 0 et attend l'arrêt réel des pods, pour que SQLite
       ferme proprement ses journaux -wal ;
    3. sauvegarde les volumes actifs dans $SAUVEGARDE ;
    4. rsync -a --delete ancien -> actif (droits, horodatages, -wal et -shm inclus) ;
    5. remet les déploiements et la synchro auto ;
  Les répertoires ANCIENS ne sont jamais modifiés ni supprimés.
PLAN
  exit 0
fi

echo "=== [1] Suspension de la synchro automatique d'ArgoCD ==="
# DEUX NIVEAUX, et c'est indispensable. Suspendre seulement `arr-stack` ne tient pas :
# son objet Application est lui-même géré par l'app-of-apps `applications`, qui le
# réécrit depuis Git en quelques minutes et rétablit selfHeal. Constaté le 2026-08-28 :
# les pods étaient relancés en boucle et le script attendait un arrêt qui n'arrivait
# jamais. L'app-of-apps, elle, porte `managed-by=Helm` sans tracking-id ArgoCD —
# personne ne la réconcilie, donc la patcher tient.
for cible in "$PARENT" "$APP"; do
  kubectl patch application "$cible" -n argocd --type json \
    -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]' >/dev/null 2>&1 \
    && echo "  $cible : synchro auto suspendue" || echo "  $cible : (déjà suspendue)"
done

remettre_argocd() {
  for cible in "$APP" "$PARENT"; do
    # patch merge : `automated` est rétabli sans toucher aux syncOptions existantes.
    kubectl patch application "$cible" -n argocd --type merge \
      -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true,"prune":true}}}}' >/dev/null 2>&1 \
      && echo "  $cible : synchro auto rétablie" \
      || echo "  ATTENTION: rétablir à la main la synchro auto de $cible"
  done
}
relever_apps() {
  for p in "${PAIRES[@]}"; do
    read -r app _ _ <<<"$p"
    kubectl scale deployment "$app" -n "$NS" --replicas=1 >/dev/null 2>&1 || true
  done
}
# EXIT et pas seulement INT/TERM : sous `set -e`, n'importe quelle commande qui
# échoue sort du script. Sans ce filet, la synchro reste suspendue et les 7
# déploiements à zéro — c'est-à-dire la pile arrêtée. Constaté le 2026-08-28.
trap 'code=$?; if [ $code -ne 0 ]; then echo "ÉCHEC (code $code) — rétablissement"; relever_apps; remettre_argocd; fi' EXIT
trap 'echo "INTERROMPU — rétablissement"; relever_apps; remettre_argocd; exit 130' INT TERM

echo "=== [2] Arrêt des applications ==="
for p in "${PAIRES[@]}"; do
  read -r app _ _ <<<"$p"
  kubectl scale deployment "$app" -n "$NS" --replicas=0 >/dev/null 2>&1 || true
done
for i in $(seq 1 60); do
  restants=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null \
    | grep -cE "^(sonarr|radarr|prowlarr|qbittorrent|seerr|jellyfin|cleanuparr)-" || true)
  [ "${restants:-0}" -eq 0 ] && break
  sleep 5
done
echo "  pods restants : ${restants:-0}"
# GARDE-FOU CRITIQUE. Sans lui, le script copiait alors que les applications
# écrivaient encore dans les répertoires cibles — bases SQLite incohérentes
# garanties. Mieux vaut abandonner et rendre la main que produire ça.
if [ "${restants:-0}" -ne 0 ]; then
  echo "ERREUR: $restants pod(s) toujours actifs après 5 min — on NE COPIE PAS."
  echo "        Cause probable : une synchro ArgoCD les relance. Vérifier que"
  echo "        $PARENT et $APP ont bien perdu leur bloc automated."
  remettre_argocd
  exit 5
fi

echo "=== [3] Sauvegarde des volumes actifs ==="
mkdir -p "$SAUVEGARDE"
for p in "${PAIRES[@]}"; do
  read -r app _ new <<<"$p"
  rsync -a --omit-dir-times "$BASE/selfhost-$app-pvc-$new/" "$SAUVEGARDE/$app/"
  echo "  $app sauvegardé"
done

echo "=== [4] Restauration ==="
# --delete : la cible devient une copie EXACTE de la source. Sans lui, des fichiers
# de la base vierge survivraient et pourraient contredire la base restaurée.
for p in "${PAIRES[@]}"; do
  read -r app old new <<<"$p"
  # --omit-dir-times : les répertoires de `seerr` appartiennent à root:root (en 777,
  # donc inscriptibles), et poser une date sur un répertoire exige d'en être
  # propriétaire — rsync échouait là-dessus seul, après avoir tout copié. Les
  # applications ne dépendent pas de l'horodatage des dossiers.
  rsync -a --omit-dir-times --delete "$BASE/selfhost-$app-pvc-$old/" "$BASE/selfhost-$app-pvc-$new/"
  echo "  $app restauré ($(du -sh "$BASE/selfhost-$app-pvc-$new" | cut -f1))"
done

echo "=== [5] Redémarrage ==="
for p in "${PAIRES[@]}"; do
  read -r app _ _ <<<"$p"
  kubectl scale deployment "$app" -n "$NS" --replicas=1 >/dev/null 2>&1 || true
done
trap - EXIT INT TERM
remettre_argocd

cat <<FIN

Restauration terminée.
  sauvegarde des volumes vierges : $SAUVEGARDE
  volumes ANCIENS : intacts, toujours en Retain — filet de sécurité conservé

À VÉRIFIER dans les interfaces avant de considérer que c'est bon :
  Sonarr   : la liste des séries est revenue
  Radarr   : la bibliothèque de films est revenue
  Prowlarr : les indexeurs sont revenus
  qBittorrent : les torrents actifs sont revenus
Si quelque chose cloche, les anciens volumes n'ont pas bougé et la sauvegarde
ci-dessus permet de revenir à l'état vierge.
FIN
