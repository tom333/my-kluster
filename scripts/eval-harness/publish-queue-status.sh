#!/usr/bin/env bash
# Publie l'état de la file de candidats modèles dans le PVC d'Hermes, pour qu'il
# puisse RÉPONDRE aux questions d'état sans deviner.
#
# Pourquoi : la file vit sur pc (~/.config/brain/model-candidates.queue) et Hermes
# n'a ni kubectl ni accès à pc → interrogé sur "qu'est-ce qui est en attente ?", il
# cherchait dans /opt/data, ne trouvait rien, et concluait à tort "file vide".
# pc pousse donc un instantané JSON que le skill `eval-modeles` lit.
#
# Cron pc (toutes les 15 min) + appelé en fin de hf-discover / trigger-watch.
set -uo pipefail
NS=hermes
DEST=/opt/data/eval/queue-status.json
QUEUE="${MODEL_CANDIDATES_QUEUE:-$HOME/.config/brain/model-candidates.queue}"
DONE="${MODEL_CANDIDATES_DONE:-$HOME/.cache/model-candidates.done}"

# Comparaison EXACTE sur le champ 2 du done-cache. Un `grep -qF "$name"` faisait
# du sous-chaîne : `ornith-1.0-9b` matchait `ornith-1.0-9b-mtp` → candidat
# faussement annoncé comme déjà traité (0 en attente alors qu'il y en avait 1).
pending=(); while IFS='|' read -r name gguf rest; do
  case "$name" in ""|\#*) continue;; esac
  awk -v m="$name" '$2==m{found=1} END{exit !found}' "$DONE" 2>/dev/null && continue
  pending+=("$name")
done < "$QUEUE" 2>/dev/null

# NB: pas de `| read` (sous-shell → variable perdue) — substitution de commande.
running=$(pgrep -af "eval-pipeline.sh" 2>/dev/null | grep -oE -- '--name [^ ]+' | awk '{print $2}' | head -1)
running="${running:-none}"

# les 8 derniers verdicts (depuis les results json)
HERE="$(cd "$(dirname "$0")" && pwd)"
recent=$(python3 - "$HERE/results" <<'PY' 2>/dev/null
import json, glob, os, sys
out=[]
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*-candidate.json")), key=os.path.getmtime, reverse=True)[:8]:
    try:
        d=json.load(open(f)); m=d.get("metrics",{})
        out.append({"model": os.path.basename(f).replace("-candidate.json",""),
                    "overall": round(m.get("overall",0),3),
                    "agentic": round(m.get("agentic_success_rate",0),3),
                    "hermes_ready": bool(m.get("hermes_ready")),
                    "unreachable": bool(d.get("unreachable"))})
    except Exception:
        pass
print(json.dumps(out))
PY
)

payload=$(python3 - "$running" "${recent:-[]}" "${pending[@]:-}" <<'PY'
import json, sys, datetime
running=sys.argv[1]; recent=json.loads(sys.argv[2]); pending=[p for p in sys.argv[3:] if p]
print(json.dumps({
  "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
  "pending_count": len(pending), "pending": pending,
  "running": running, "recent_verdicts": recent,
  "note": "Instantané publié par pc. La file réelle vit sur pc, Hermes ne peut que la LIRE ici.",
}, ensure_ascii=False, indent=1))
PY
)

POD=$(kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/hermes-agent/{print $1}' | head -1)
[ -z "$POD" ] && { echo "pod hermes introuvable"; exit 0; }
printf '%s' "$payload" | kubectl exec -i -n $NS "$POD" -c main -- sh -c "mkdir -p /opt/data/eval && cat > $DEST && chown -R 10000:10000 /opt/data/eval" 2>/dev/null \
  && echo "publié: ${#pending[@]} en attente, running=$running" || echo "WARN publication échouée"
