#!/usr/bin/env bash
# Enveloppe du cron d'export. Notifie Telegram UNIQUEMENT en cas d'échec :
# le silence doit signifier « tout va bien », jamais « le cron est mort ».
#
# Pourquoi une enveloppe plutôt que la commande nue dans le crontab : un cron qui
# ne journalise que dans un fichier est un cron dont personne ne voit l'échec.
# C'est le défaut relevé sur brain-digest.sh pendant l'audit du 2026-07-27.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
UV="${UV_BIN:-/home/moi/.local/bin/uv}"

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

# Clé DÉDIÉE, sans passphrase, pour les opérations git de ce cron.
#
# Pourquoi : ~/.ssh/config route github.com vers ~/.ssh/id_github, qui EST protégée
# par passphrase — donc utilisable seulement via un agent, que cron n'a pas. D'où
# « git@github.com: Permission denied (publickey) ». Diagnostic du 2026-08-09 : le
# défaut était LATENT depuis l'installation. Les jours « aucun changement à
# capturer » sortaient avant d'atteindre le réseau, donc rien n'échouait ; seuls le
# 30/07 puis les 07 et 08/08, quand il y avait vraiment de l'état à pousser, ont
# revélé le problème. Un cron qui ne touche son point de défaillance qu'un jour sur
# dix met dix jours à se signaler.
#
# `IdentitiesOnly=yes` est indispensable : sans lui ssh proposerait d'abord les clés
# de l'agent ou de ~/.ssh/config et GitHub refuserait avant d'arriver à celle-ci.
# La clé est une *deploy key* limitée à ce seul dépôt, pas une clé de compte : elle
# n'ouvre rien d'autre, et la clé interactive garde sa passphrase.
export GIT_SSH_COMMAND="ssh -i ${HOME:-/home/moi}/.ssh/id_hermes_state -o IdentitiesOnly=yes -o BatchMode=yes"

cd "$HERE" || exit 2
echo "=== $(date -u +%FT%TZ) hermes-state export ==="
sortie=$("$UV" run --quiet --with pyyaml python hermes_state.py export --commit 2>&1)
rc=$?
echo "$sortie"
if [ "$rc" != "0" ]; then
  notify "⚠️ hermes-state export a échoué (code $rc)
${sortie: -400}"
fi
exit "$rc"
