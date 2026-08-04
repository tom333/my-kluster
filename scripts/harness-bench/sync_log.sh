#!/bin/bash
# Reverse le journal COMPLET du serveur actif dans son fichier de capture.
#
# Motif (2026-08-05) : `serveur.sh` capture avec `nohup podman logs -f > fichier &`,
# et cette capture s'est TAIE en cours de campagne. Le processus etait toujours
# vivant — donc un `pgrep` le declarait sain — mais 91 536 octets manquaient au
# fichier, dont l'unique trace du 500 qui avait tue un tirage. J'ai conclu deux fois
# de suite sur un journal ampute, dont une fois « ce 500 n'apparait pas dans le
# journal » alors qu'il y etait, cote conteneur.
#
# `podman logs` sans `-f` rend TOUT le journal depuis le demarrage du conteneur :
# c'est un sur-ensemble du fichier, donc l'ecraser est idempotent et ne peut que
# completer. A lancer apres chaque campagne, et AVANT tout `podman rm` — le
# conteneur tourne en `--rm`, sa disparition emporte le journal.
#
#   ./sync_log.sh            # serveur declare dans logs-serveur/actif.json
#   ./sync_log.sh <nom> <fichier>
set -eu
ICI="$(dirname "$0")"

if [ $# -eq 2 ]; then
  NOM="$1"; FICHIER="$2"
else
  ACTIF="$ICI/logs-serveur/actif.json"
  [ -f "$ACTIF" ] || { echo "pas de $ACTIF, et aucun (nom, fichier) donne" >&2; exit 1; }
  lire() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$ACTIF" "$1"; }
  NOM=$(lire nom)
  # `log` est relatif au dossier du banc ; on accepte aussi un chemin deja resolu.
  FICHIER=$(lire log)
  [ -f "$FICHIER" ] || FICHIER="$ICI/$FICHIER"
fi

podman container exists "$NOM" || { echo "conteneur $NOM absent : journal deja perdu" >&2; exit 1; }

AVANT=$( [ -f "$FICHIER" ] && wc -c < "$FICHIER" || echo 0 )
# Ecriture atomique : un `podman logs` interrompu ne doit pas laisser un journal
# plus COURT que celui qu'il remplace.
TMP=$(mktemp "${FICHIER}.XXXXXX")
podman logs "$NOM" > "$TMP" 2>&1
APRES=$(wc -c < "$TMP")

if [ "$APRES" -lt "$AVANT" ]; then
  rm -f "$TMP"
  echo "REFUS : $APRES octets cote conteneur contre $AVANT dans le fichier." >&2
  echo "Le conteneur a probablement redemarre (journal remis a zero). Fichier garde." >&2
  exit 1
fi

mv "$TMP" "$FICHIER"
chmod 664 "$FICHIER"
echo "$NOM : $AVANT -> $APRES octets (+$((APRES - AVANT))) | $FICHIER"
