#!/usr/bin/env bash
# P5 — watcher backend LocalAI. Compare le digest quay du backend cuda12-llama-cpp
# au digest INSTALLÉ (metadata.json du pod). Alerte Telegram sur drift.
# Full auto-update (re-pull + éval + PR) = REPORTÉ (risque : casse tous les modèles ;
# + backend pas déclaratif en git). Procédure de maj = manuelle, GATÉE par le harness.
# Cron pc (needs kubectl). State pour alerter 1×/digest.
set -uo pipefail
NS=localai
TAG="${BACKEND_TAG:-latest-gpu-nvidia-cuda-12-llama-cpp}"
STATE="${BACKEND_WATCH_STATE:-$HOME/.cache/backend-watch.json}"
mkdir -p "$(dirname "$STATE")"

POD=$(kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/localai/{print $1}' | head -1)
INSTALLED=$(kubectl exec -n $NS "$POD" -c localai -- sh -c "grep -o 'sha256:[a-f0-9]*' /backends/cuda12-llama-cpp/metadata.json 2>/dev/null | head -1" 2>/dev/null)
LATEST=$(curl -s "https://quay.io/api/v1/repository/go-skynet/local-ai-backends/tag/?specificTag=${TAG}&limit=1" 2>/dev/null \
  | python3 -c "import sys,json; t=json.load(sys.stdin).get('tags',[]); print(t[0]['manifest_digest'] if t else '')" 2>/dev/null)

echo "installed=$INSTALLED"
echo "latest   =$LATEST"
[ -z "$INSTALLED" ] || [ -z "$LATEST" ] && { echo "digest indéterminé → skip (pas d'alerte)"; exit 0; }

if [ "$INSTALLED" = "$LATEST" ]; then
  echo "backend à jour."; exit 0
fi

# drift : déjà alerté pour ce latest ?
LAST=$(python3 -c "import json; print(json.load(open('$STATE')).get('alerted',''))" 2>/dev/null || echo "")
if [ "$LAST" = "$LATEST" ]; then
  echo "drift déjà signalé pour $LATEST."; exit 0
fi

MSG="🧰 Nouveau backend LocalAI cuda12-llama-cpp dispo.
installé : ${INSTALLED:0:19}
latest   : ${LATEST:0:19}
Maj GATÉE par le harness (pas d'auto) :
1) LOCALAI_EXTERNAL_BACKENDS=llama-cpp + rm /backends/cuda12-llama-cpp + restart
2) run_eval.py sur les modèles clés → vérifier zéro régression
3) si OK, garder ; sinon revert."
tok="$(cat "$HOME/.config/brain/telegram-bot-token" 2>/dev/null || true)"
[ -n "$tok" ] && curl -s -4 "https://api.telegram.org/bot${tok}/sendMessage" \
  --data-urlencode "chat_id=843341688" --data-urlencode "text=$MSG" -o /dev/null || true
python3 -c "import json; json.dump({'alerted':'$LATEST'}, open('$STATE','w'))"
echo "drift signalé (Telegram)."
