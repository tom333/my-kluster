#!/usr/bin/env bash
# P4 — runner bout-en-bout pour UN candidat : stage+éval (P2) → gate+PR si gagnant
# (P3) → notification Telegram → cleanup. Tourne sur pc (kubectl+docker+gh+git).
#
#   eval-pipeline.sh --name <n> --gguf <url> [--draft <url>] [--ctx N] [--incumbent ornith-1.0-9b-mtp]
#
# Le PR reste le gate humain (jamais d'auto-merge). Le candidat est nettoyé après
# (s'il gagne, il revient via la PR mergée → ArgoCD).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=""; GGUF=""; DRAFT=""; CTX=8192; INCUMBENT="ornith-1.0-9b-mtp"
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;; --gguf) GGUF="$2"; shift 2;;
  --draft) DRAFT="$2"; shift 2;; --ctx) CTX="$2"; shift 2;;
  --incumbent) INCUMBENT="$2"; shift 2;; *) echo "arg?: $1"; exit 2;;
esac; done
[ -z "$NAME" ] || [ -z "$GGUF" ] && { echo "--name + --gguf requis"; exit 2; }

notify() {
  local tok; tok="$(cat "$HOME/.config/brain/telegram-bot-token" 2>/dev/null || true)"
  [ -z "$tok" ] && return 0
  curl -s -4 "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" -o /dev/null || true
}

notify "🔬 Pipeline modèle : éval candidat $NAME démarrée (vs $INCUMBENT)…"
DRAFTARG=""; [ -n "$DRAFT" ] && DRAFTARG="--draft $DRAFT"
"$HERE/stage_candidate.sh" --name "$NAME" --gguf "$GGUF" $DRAFTARG --ctx "$CTX" --baseline "$INCUMBENT" \
  2>&1 | grep -vE "Downloading|Downloaded|Installed|INFO mlflow" | tail -40

# gate + PR (promote.sh gère la décision ; crée la PR si PROMOTE)
PROMO="$("$HERE/promote.sh" --candidate "$NAME" --incumbent "$INCUMBENT" 2>&1)"
echo "$PROMO"
VERDICT="$(echo "$PROMO" | grep -oE 'gate: (PROMOTE|REJECT)' | head -1)"
PRLINE="$(echo "$PROMO" | grep -oE 'https://github.com/[^ ]+/pull/[0-9]+' | head -1)"

if echo "$VERDICT" | grep -q PROMOTE; then
  notify "🟢 $NAME BAT $INCUMBENT sur le harness → PR ouverte (review + merge manuel) : ${PRLINE:-voir GitHub}"
else
  notify "⚪ $NAME non promu vs $INCUMBENT (harness). Détails MLflow localai-model-eval."
fi

echo "=== cleanup candidat $NAME ==="
"$HERE/stage_candidate.sh" --cleanup --name "$NAME" >/dev/null 2>&1 || true
echo "pipeline terminé pour $NAME ($VERDICT)"
