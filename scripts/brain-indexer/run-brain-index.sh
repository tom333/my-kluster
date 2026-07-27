#!/usr/bin/env bash
# Réindexe le vault ~/brain dans txtai. Cron pc, toutes les 6 h.
#
# POURQUOI CE SCRIPT EXISTE
# `~/brain/bin/index-brain.py` était appelé UNIQUEMENT par `brain-sync.sh push`,
# c'est-à-dire au moment où l'utilisateur pousse ses notes à la main. Or le vault
# s'édite via SilverBullet en cluster (app `brain`), qui commit et pousse
# lui-même : `brain-sync.sh push` ne tourne donc jamais, et la réindexation avec.
# Résultat mesuré le 2026-07-27 : index figé au 2026-07-20, 15 notes suivies sur 18.
#
# On appelle DÉLIBÉRÉMENT `brain-sync.sh pull` et jamais `push` : le mode push fait
# un `git add -A` + commit + push, ce qu'un cron ne doit pas décider tout seul.
#
# Notifie Telegram UNIQUEMENT en cas d'échec : le silence doit signifier « tout va
# bien », jamais « le cron est mort ».
set -uo pipefail
VAULT="${BRAIN_DIR:-${HOME:-/home/moi}/brain}"
TOKEN_FILE="${TXTAI_TOKEN_FILE:-${HOME:-/home/moi}/.config/brain/txtai-token}"

notify() {
  local f="${TELEGRAM_TOKEN_FILE:-${HOME:-/home/moi}/.config/brain/telegram-bot-token}"
  local tok; tok="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$tok" ]; then
    echo "WARN notify: token Telegram illisible ($f) — message NON envoyé" >&2; return 0
  fi
  local code
  code=$(curl -s -4 -m 20 -o /dev/null -w '%{http_code}' \
    "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" 2>/dev/null || echo 000)
  [ "$code" = "200" ] || echo "WARN notify: Telegram http=$code — non délivré" >&2
}

echo "=== $(date -u +%FT%TZ) reindexation du vault brain ==="
sortie=$(
  set -o pipefail
  cd "$VAULT" 2>/dev/null || { echo "vault introuvable: $VAULT"; exit 2; }
  "$VAULT/bin/brain-sync.sh" pull 2>&1 || echo "WARN pull en echec, on indexe l'etat local"
  TXTAI_URL="${TXTAI_URL:-https://txtai.tgu.ovh}" \
  TXTAI_TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null)" \
    /usr/bin/python3 "$VAULT/bin/index-brain.py" 2>&1
)
rc=$?
echo "$sortie"
if [ "$rc" != "0" ]; then
  notify "⚠️ réindexation du vault brain en échec (code $rc)
${sortie: -400}"
fi
exit "$rc"
