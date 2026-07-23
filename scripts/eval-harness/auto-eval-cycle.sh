#!/usr/bin/env bash
# Cycle auto (pc) — à planifier APRÈS la veille. Scrape les lignes structurées
# `CANDIDAT: name|gguf|[draft]|[ctx]` émises par la veille (skill veille-digest v1.5)
# dans state.db Hermes → ajoute les NOUVEAUX à la file → SEMI-AUTO notifie
# "N candidats en file" (tu lances poll-candidates), ou --run exécute le pipeline.
#
# Fiable : parse une ligne machine (pas de prose). PR = gate humain. --run cap MAX_PER_CYCLE.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
QUEUE="${MODEL_CANDIDATES_QUEUE:-$HOME/.config/brain/model-candidates.queue}"
RUN=0; [ "${1:-}" = "--run" ] && RUN=1
SINCE=$(date -d '2 days ago' +%s 2>/dev/null || echo 0)

notify() {
  local tok; tok="$(cat "$HOME/.config/brain/telegram-bot-token" 2>/dev/null || true)"
  [ -z "$tok" ] && return 0
  curl -s -4 "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" -o /dev/null || true
}

kubectl config use-context microk8s >/dev/null 2>&1 || true
HPOD=$(kubectl get pods -n hermes --no-headers 2>/dev/null | awk '/hermes-agent/{print $1}' | head -1)
[ -z "$HPOD" ] && { echo "pod hermes introuvable"; exit 1; }

# scrape les lignes CANDIDAT: des digests veille (cron) récents
LINES=$(kubectl exec -n hermes "$HPOD" -c main -- python3 - "$SINCE" <<'PY' 2>/dev/null
import sqlite3, re, sys
since=float(sys.argv[1])
c=sqlite3.connect('file:/opt/data/state.db?mode=ro',uri=True)
seen=set()
for (sid,) in c.execute("select id from sessions where source='cron' and started_at > ? order by started_at",(since,)):
    for (content,) in c.execute("select content from messages where session_id=? and role='assistant' and content is not null",(sid,)):
        for m in re.findall(r'CANDIDAT:\s*([^\n`]+)', content):
            line=m.strip().strip('`').strip()
            if '|' in line and line not in seen:
                seen.add(line); print(line)
PY
)

added=""
while IFS= read -r line; do
  [ -z "$line" ] && continue
  name="${line%%|*}"
  grep -qF "$line" "$QUEUE" 2>/dev/null && continue   # déjà en file
  echo "$line" >> "$QUEUE"
  added="$added $name"
done <<< "$LINES"

if [ -z "$added" ]; then
  echo "aucun nouveau candidat scrapé."; exit 0
fi
echo "nouveaux candidats en file:$added"

if [ "$RUN" = "1" ]; then
  notify "🔁 Cycle auto : candidats$added → évaluation en cours (pipeline, PR-gated)."
  MAX_PER_CYCLE="${MAX_PER_CYCLE:-1}" "$HERE/poll-candidates.sh"
else
  notify "🆕 Veille : candidat(s) modèle en file :$added
Lance l'éval : \`~/brain/... poll-candidates.sh\` sur pc (chaque candidat = 1 restart LocalAI ~15min)."
fi
