#!/usr/bin/env bash
# P4 — runner bout-en-bout pour UN candidat : stage+éval (P2) → gate+PR si gagnant
# (P3) → notification Telegram → cleanup. Tourne sur pc (kubectl+docker+gh+git).
#
#   eval-pipeline.sh --name <n> --gguf <url> [--draft <url>] [--ctx N] [--incumbent qwen3-coder-30b-a3b-instruct]
#
# Le PR reste le gate humain (jamais d'auto-merge). Le candidat est nettoyé après
# (s'il gagne, il revient via la PR mergée → ArgoCD).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=""; GGUF=""; DRAFT=""; CTX=8192; INCUMBENT="qwen3-coder-30b-a3b-instruct"
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;; --gguf) GGUF="$2"; shift 2;;
  --draft) DRAFT="$2"; shift 2;; --ctx) CTX="$2"; shift 2;;
  --incumbent) INCUMBENT="$2"; shift 2;; *) echo "arg?: $1"; exit 2;;
esac; done
[ -z "$NAME" ] || [ -z "$GGUF" ] && { echo "--name + --gguf requis"; exit 2; }

# NE JAMAIS échouer en silence : un `return 0` muet a déjà fait croire que le
# pipeline n'avait pas tourné (token introuvable sous cron car $HOME absent →
# aucune notif, aucune trace). Toute défaillance est désormais logguée.
notify() {
  local f="${TELEGRAM_TOKEN_FILE:-${HOME:-/home/moi}/.config/brain/telegram-bot-token}"
  local tok; tok="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$tok" ]; then
    echo "WARN notify: token Telegram illisible ($f) — message NON envoyé: ${1:0:60}…" >&2
    return 0
  fi
  local code
  code=$(curl -s -4 -m 20 -o /dev/null -w '%{http_code}' "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" 2>/dev/null || echo 000)
  [ "$code" = "200" ] || echo "WARN notify: Telegram a répondu http=$code — message NON délivré" >&2
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

# résumé chiffré du changement (lignes du tableau comparatif de promote.sh)
SUMMARY="$(echo "$PROMO" | grep -E '^\| (overall|coding_pass_rate|toolcall_acc|format_acc|reasoning_acc|agentic_success_rate|mean_tokps) ' \
  | sed 's/^| //; s/ |$//; s/ | / /g')"
HERMES="$(echo "$PROMO" | grep -oE 'Hermes-readiness.*: .*' | head -1)"
if echo "$VERDICT" | grep -q PROMOTE; then
  notify "🟢 Swap proposé : $NAME → remplace $INCUMBENT
(métrique · candidat · courant · Δ)
$SUMMARY
🧠 $HERMES

PR ouverte, review + merge MANUEL :
${PRLINE:-voir github.com/tom333/my-kluster/pulls}"
else
  notify "⚪ $NAME NON promu vs $INCUMBENT
(métrique · candidat · courant · Δ)
$SUMMARY
🧠 $HERMES

(gate non franchi ; détails MLflow localai-model-eval)"
fi

echo "=== cleanup candidat $NAME ==="
"$HERE/stage_candidate.sh" --cleanup --name "$NAME" >/dev/null 2>&1 || true
echo "pipeline terminé pour $NAME ($VERDICT)"
