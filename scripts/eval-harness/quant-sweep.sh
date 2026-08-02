#!/usr/bin/env bash
# Boucle pilotée par OBJECTIF : trouver un modèle local fort sur les DEUX axes.
#
#   OBJECTIF   : agentic_success_rate >= 1.0  ET  coding_pass_rate >= 0.929
#   ARRÊT      : objectif atteint · liste épuisée · cap MAX_ITER
#   VÉRIFICATEUR : le harness déterministe (run_eval), pas un jugement du modèle
#
# Pourquoi cette boucle : ornith-1.0-9b bloquait en multi-tours en Q4_K_M
# (agentic ~0) et passe 6/6 en Q6_K → les dégâts de quantification frappent
# l'agentique en premier. Les candidats forts sur UN axe, mesurés en quant basse,
# méritent donc un second passage en quant supérieure. L'espace est énumérable et
# le critère binaire → boucle déterministe (aucun token LLM), tourne sans surveillance.
#
# NB: qwen3-coder-30b (déployé) ne peut PAS monter en quant : un 30B au-delà de
# IQ1_S dépasse les 12 Go de la carte. Son agentic 0.833 est un plafond structurel.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BASELINE="${BASELINE:-qwen3-coder-30b-a3b-instruct}"
MAX_ITER="${MAX_ITER:-5}"
GOAL_AGENTIC="${GOAL_AGENTIC:-1.0}"
GOAL_CODING="${GOAL_CODING:-0.929}"
LOCK="${TMPDIR:-/tmp}/quant-sweep.lock"

# Ordre = valeur attendue décroissante (on s'arrête au premier qui satisfait tout).
# Nom suffixé par le quant : garde les résultats de la mesure basse quant intacts.
CANDIDATES=(
  # coding déjà 0.929 en Q4_K_M mais agentic 0.50 → le meilleur espoir des 2 axes
  "gemma-4-12b-coder-q6k|https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF/resolve/main/gemma4-coding-Q6_K.gguf"
  # overall 0.941 mais agentic 0.00 en Q4_K_M — suspect pour un modèle dit "agentic"
  "gemma-4-12b-agentic-q6k|https://huggingface.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF/resolve/main/gemma4-v2-Q6_K.gguf"
  # agentic déjà 1.00 en MXFP4 ; reste à faire monter le coding
  "qwen3.6-14b-a3b-q5km|https://huggingface.co/tvall43/Qwen3.6-14B-A3B-FableVibes-GGUF/resolve/main/Qwen3.6-14B-A3B-FableVibes-Q5_K_M.gguf"
  # Q6_K donne déjà agentic 1.0 / coding 0.714 → Q8_0 pour tenter le coding
  "ornith-1.0-9b-q8|https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/resolve/main/ornith-1.0-9b-Q8_0.gguf"
)

notify() {
  local f="${TELEGRAM_TOKEN_FILE:-${HOME:-/home/moi}/.config/brain/telegram-bot-token}"
  local tok; tok="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$tok" ]; then echo "WARN notify: token illisible ($f)" >&2; return 0; fi
  local code
  code=$(curl -s -4 -m 20 -o /dev/null -w '%{http_code}' "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" 2>/dev/null || echo 000)
  [ "$code" = "200" ] || echo "WARN notify: Telegram http=$code" >&2
}

# une seule campagne à la fois (chaque itération redémarre LocalAI)
exec 9>"$LOCK" || exit 1
flock -n 9 || { echo "balayage déjà en cours, abandon"; exit 0; }

metric() {  # metric <fichier> <clé>
  python3 -c "
import json,sys
try: print(json.load(open(sys.argv[1]))['metrics'].get(sys.argv[2], 0))
except Exception: print(0)
" "$1" "$2" 2>/dev/null
}

notify "🔬 Balayage de quantification lancé — objectif : agentic ≥ ${GOAL_AGENTIC} ET coding ≥ ${GOAL_CODING}
Hypothèse : les dégâts de quantification frappent l'agentique en premier (ornith : 0 en Q4 → 1.0 en Q6_K).
${MAX_ITER} candidats max, ~15-20 min chacun. Arrêt dès l'objectif atteint."

n=0; best_name=""; best_score="-1"; winner=""
for entry in "${CANDIDATES[@]}"; do
  [ "$n" -ge "$MAX_ITER" ] && { echo "cap MAX_ITER=$MAX_ITER atteint"; break; }
  name="${entry%%|*}"; url="${entry#*|}"
  n=$((n+1))
  echo "=== [$n/$MAX_ITER] $name  $(date -u +%FT%TZ) ==="

  "$HERE/stage_candidate.sh" --name "$name" --gguf "$url" --baseline "$BASELINE" 2>&1 \
    | grep -vE "Downloading|Downloaded|Installed|INFO mlflow|^ *$" | tail -25

  res="$HERE/results/${name}-candidate.json"
  ag=$(metric "$res" agentic_success_rate); co=$(metric "$res" coding_pass_rate)
  ov=$(metric "$res" overall);            hr=$(metric "$res" hermes_ready)
  echo "→ agentic=$ag coding=$co overall=$ov hermes_ready=$hr"

  ok=$(python3 -c "print(1 if float('$ag')>=float('$GOAL_AGENTIC') and float('$co')>=float('$GOAL_CODING') else 0)" 2>/dev/null || echo 0)
  # score de suivi : l'agentique prime (c'est l'axe rare), le coding départage
  sc=$(python3 -c "print(round(float('$ag')*2+float('$co'),4))" 2>/dev/null || echo 0)
  if python3 -c "exit(0 if float('$sc')>float('$best_score') else 1)" 2>/dev/null; then
    best_score="$sc"; best_name="$name (agentic $ag / coding $co)"
  fi

  if [ "$ok" = "1" ]; then
    winner="$name"
    notify "🏆 OBJECTIF ATTEINT — $name
agentic $ag (≥$GOAL_AGENTIC) · coding $co (≥$GOAL_CODING) · overall $ov · hermes_ready $hr
Balayage stoppé. Candidat crédible comme cerveau Hermes 100 % local.
Je tente la PR (gate LocalAI, qui reste pondéré coding)."
    "$HERE/promote.sh" --candidate "$name" --incumbent "$BASELINE" 2>&1 | tail -12
    break
  fi

  notify "⚪ $name — objectif non atteint
agentic $ag (cible ≥$GOAL_AGENTIC) · coding $co (cible ≥$GOAL_CODING) · overall $ov
Passage au candidat suivant."
  "$HERE/stage_candidate.sh" --cleanup --name "$name" >/dev/null 2>&1 || true
done

if [ -z "$winner" ]; then
  notify "🔻 Balayage terminé sans succès ($n candidat(s) testé(s)).
Meilleur : ${best_name:-aucun}
Aucun modèle local ne satisfait les deux axes dans 12 Go de VRAM. Piste restante : plus de VRAM, ou deux modèles spécialisés (coding + agentique)."
else
  "$HERE/stage_candidate.sh" --cleanup --name "$winner" >/dev/null 2>&1 || true
fi
"$HERE/publish-queue-status.sh" >/dev/null 2>&1 || true
echo "=== balayage terminé $(date -u +%FT%TZ) — gagnant: ${winner:-aucun} ==="
