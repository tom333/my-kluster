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

# PREFLIGHT — lit l'EN-TÊTE du GGUF par requête HTTP Range et écarte le candidat
# AVANT de télécharger les gigaoctets. Motif : le 2026-09-08, neutrino-8b-fv5 a
# coûté 4,09 Go téléchargés, un restart LocalAI et un créneau de file pour être
# rejeté ensuite — alors que son en-tête (5,9 Mo) suffisait à voir qu'il déclare
# des types de tenseurs 43/44 que llama.cpp ne connaît pas (max = Q2_0 = 42).
# Le preflight est fail-OPEN : réseau indisponible ou en-tête illisible => on
# laisse passer et le pipeline reste juge. Seule une incompatibilité CERTAINE
# écarte le candidat.
PF_OUT="$(python3 "$HERE/gguf_preflight.py" "$GGUF" 2>&1)"; PF_RC=$?
echo "$PF_OUT"
if [ "$PF_RC" = "3" ]; then
  notify "⛔ $NAME écarté AVANT téléchargement

$PF_OUT

Aucun octet téléchargé, aucun redémarrage LocalAI, créneau de file préservé."
  echo "pipeline terminé pour $NAME (preflight REJECT)"
  exit 0
fi

notify "🔬 Pipeline modèle : éval candidat $NAME démarrée (vs $INCUMBENT)…"
DRAFTARG=""; [ -n "$DRAFT" ] && DRAFTARG="--draft $DRAFT"
# Le code de sortie de stage_candidate.sh doit être CONSERVÉ. Avant, il partait dans
# un tube (`| grep | tail`) : le statut du pipeline était celui de `tail`, donc
# toujours 0. Résultat, un échec du garde-fou d'appel d'outil continuait jusqu'à
# promote.sh, qui ne trouvait aucun résultat et envoyait un « NON promu » au tableau
# VIDE, indiscernable d'un modèle mesuré et moins bon. C'est ce qui a fait attendre
# 98 minutes sur neutrino-8b le 2026-09-08.
STAGE_OUT="$("$HERE/stage_candidate.sh" --name "$NAME" --gguf "$GGUF" $DRAFTARG --ctx "$CTX" --baseline "$INCUMBENT" 2>&1)"
STAGE_RC=$?
echo "$STAGE_OUT" | grep -vE "Downloading|Downloaded|Installed|INFO mlflow" | tail -40

if [ "$STAGE_RC" != "0" ]; then
  # On NOMME la cause. L'erreur utile est soit le message llama.cpp (`Error: ...`),
  # soit la ligne ECHEC/ERREUR du garde-fou.
  CAUSE="$(echo "$STAGE_OUT" | grep -oE "Error: [^\"}]+" | head -1)"
  [ -z "$CAUSE" ] && CAUSE="$(echo "$STAGE_OUT" | grep -E "ECHEC|ERREUR|TIMEOUT" | head -2 | tr '\n' ' ')"
  notify "⛔ $NAME : éval NON lancée — le modèle ne charge pas, ou n'appelle pas d'outil.

${CAUSE:-cause non identifiée, voir ~/.cache/trigger-watch.log}

(garde-fou d'appel d'outil : un modèle qui échoue ici est inutilisable en agentique.
Il peut rester bon en autocomplétion.)"
  echo "=== cleanup candidat $NAME ==="
  "$HERE/stage_candidate.sh" --cleanup --name "$NAME" >/dev/null 2>&1 || true
  echo "pipeline terminé pour $NAME (STAGE FAIL rc=$STAGE_RC)"
  exit 0
fi

# gate + PR (promote.sh gère la décision ; crée la PR si PROMOTE)
PROMO="$("$HERE/promote.sh" --candidate "$NAME" --incumbent "$INCUMBENT" 2>&1)"
echo "$PROMO"
VERDICT="$(echo "$PROMO" | grep -oE 'gate: (PROMOTE|REJECT)' | head -1)"
PRLINE="$(echo "$PROMO" | grep -oE 'https://github.com/[^ ]+/pull/[0-9]+' | head -1)"

# résumé chiffré du changement (lignes du tableau comparatif de promote.sh)
SUMMARY="$(echo "$PROMO" | grep -E '^\| (overall|coding_pass_rate|coding_truncated|toolcall_acc|format_acc|reasoning_acc|agentic_success_rate|mean_tokps) ' \
  | sed 's/^| //; s/ |$//; s/ | / /g')"
HERMES="$(echo "$PROMO" | grep -oE 'Hermes-readiness.*: .*' | head -1)"

# TRIAGE — dit POURQUOI les items ont échoué, sans toucher au verdict. Motif : le
# harnais rapportait un symptôme (`NameError`) sans sa cause (budget parti en
# raisonnement, code jamais écrit), et ce trou a masqué un plafond de mesure
# pendant des semaines. Déterministe, aucun token de LLM.
TRIAGE="$(python3 "$HERE/triage.py" "$HERE/results/${NAME}-candidate.json" --court 2>/dev/null | head -5)"
# L'alarme qui compte : un item soluble raté par les N derniers candidats d'affilée
# accuse la MESURE, pas les modèles. Vérifié : `calc_ii` l'était par 13 candidats
# consécutifs, pour un taux global de 16 % qu'aucun seuil de rareté ne voyait.
SERIES="$(python3 "$HERE/triage.py" --items 2>/dev/null | grep '^  SÉRIE' | head -3)"
if echo "$VERDICT" | grep -q PROMOTE; then
  notify "🟢 Swap proposé : $NAME → remplace $INCUMBENT
(métrique · candidat · courant · Δ)
$SUMMARY
🧠 $HERMES

PR ouverte, review + merge MANUEL :
${PRLINE:-voir github.com/tom333/my-kluster/pulls}

${TRIAGE}
${SERIES:+
⚠️ ALERTE MESURE :
$SERIES}"
else
  notify "⚪ $NAME NON promu vs $INCUMBENT
(métrique · candidat · courant · Δ)
$SUMMARY
🧠 $HERMES

(gate non franchi ; détails MLflow localai-model-eval)

${TRIAGE}
${SERIES:+
⚠️ ALERTE MESURE :
$SERIES}"
fi

echo "=== cleanup candidat $NAME ==="
"$HERE/stage_candidate.sh" --cleanup --name "$NAME" >/dev/null 2>&1 || true
echo "pipeline terminé pour $NAME ($VERDICT)"
