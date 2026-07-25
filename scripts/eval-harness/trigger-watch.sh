#!/usr/bin/env bash
# Pont Telegram → éval modèles. Tu demandes l'éval à Hermes depuis Telegram ; il pose un
# fichier-drapeau dans /opt/data/triggers (son seul chemin writable) ; ce watcher (cron pc,
# toutes les 5 min) le voit via `kubectl exec`, le consomme, et lance poll-candidates.sh
# (qui notifie Telegram lui-même : démarrage, verdict, PR).
#
# Pourquoi ce design : Hermes n'a PAS kubectl/docker (l'éval a besoin des deux) et son PVC
# est uid-10000 (hostpath illisible sans sudo) → le drapeau + kubectl exec évitent à la fois
# une clé SSH dans le pod et un port en écoute sur pc. Aucune surface d'attaque ajoutée.
#
# Le PR reste le gate humain. MAX_PER_CYCLE borne les restarts LocalAI par déclenchement.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=hermes
FLAG=/opt/data/triggers/run-eval
LOCK="${TMPDIR:-/tmp}/trigger-watch.lock"

# un seul run à la fois (l'éval dure ~15 min/candidat, le cron tique toutes les 5 min)
exec 9>"$LOCK" || exit 0
flock -n 9 || { echo "run déjà en cours, skip"; exit 0; }

kubectl config use-context microk8s >/dev/null 2>&1 || true
POD=$(kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/hermes-agent/{print $1}' | head -1)
[ -z "$POD" ] && { echo "pod hermes introuvable"; exit 0; }

kubectl exec -n $NS "$POD" -c main -- test -f "$FLAG" 2>/dev/null || exit 0

# consomme le drapeau AVANT de lancer (évite une double exécution au tick suivant)
kubectl exec -n $NS "$POD" -c main -- rm -f "$FLAG" >/dev/null 2>&1
echo "=== drapeau consommé, lancement du pipeline $(date -u +%FT%TZ) ==="
MAX_PER_CYCLE="${MAX_PER_CYCLE:-2}" "$HERE/poll-candidates.sh"
echo "=== pipeline terminé $(date -u +%FT%TZ) ==="
