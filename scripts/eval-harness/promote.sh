#!/usr/bin/env bash
# P3 — si un candidat BAT le modèle courant sur le harness, génère une PR my-kluster
# (add candidat + remove incumbent + résumé). JAMAIS d'auto-merge (PR = gate humain).
#
#   promote.sh --candidate <name> [--incumbent ornith-1.0-9b-mtp] [--margin 0.02] [--dry-run]
#
# Gate : overall(cand) - overall(base) >= margin  ET  toolcall(cand) >= toolcall(base) - 0.05
# (pas de régression agentique). Lit results/<name>-candidate.json + <incumbent>-baseline.json.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=""; INCUMBENT="ornith-1.0-9b-mtp"; MARGIN="0.02"; DRY=0
while [ $# -gt 0 ]; do case "$1" in
  --candidate) NAME="$2"; shift 2;;
  --incumbent) INCUMBENT="$2"; shift 2;;
  --margin) MARGIN="$2"; shift 2;;
  --dry-run) DRY=1; shift;;
  *) echo "arg inconnu: $1"; exit 2;;
esac; done
[ -z "$NAME" ] && { echo "--candidate requis"; exit 2; }
CAND_JSON="$HERE/results/${NAME}-candidate.json"
BASE_JSON="$HERE/results/${INCUMBENT}-baseline.json"
[ -f "$CAND_JSON" ] || { echo "résultats candidat absents: $CAND_JSON (lance stage_candidate.sh d'abord)"; exit 1; }
[ -f "$BASE_JSON" ] || { echo "baseline absent: $BASE_JSON"; exit 1; }

# --- gate + résumé (python) ---
GATE=$(python3 - "$CAND_JSON" "$BASE_JSON" "$MARGIN" <<'PY'
import json, sys
cand=json.load(open(sys.argv[1]))["metrics"]; base=json.load(open(sys.argv[2]))["metrics"]; margin=float(sys.argv[3])
d_overall=cand["overall"]-base["overall"]
d_tool=cand["toolcall_acc"]-base["toolcall_acc"]
promote = d_overall>=margin and d_tool>=-0.05
reasons=[]
if d_overall<margin: reasons.append(f"overall Δ {d_overall:+.3f} < marge {margin}")
if d_tool<-0.05: reasons.append(f"toolcall Δ {d_tool:+.3f} < -0.05 (régression agentique)")
rows="\n".join(f"| {k} | {cand.get(k,0):.3f} | {base.get(k,0):.3f} | {cand.get(k,0)-base.get(k,0):+.3f} |"
  for k in ["overall","coding_pass_rate","toolcall_acc","format_acc","reasoning_acc","mean_tokps"])
print("PROMOTE" if promote else "REJECT")
print("REASONS::" + ("; ".join(reasons) if reasons else "gate OK"))
print("TABLE::"+rows.replace("\n","§"))
PY
)
DECISION=$(echo "$GATE" | sed -n '1p')
REASONS=$(echo "$GATE" | sed -n '2p' | sed 's/^REASONS:://')
TABLE=$(echo "$GATE" | sed -n '3p' | sed 's/^TABLE:://; s/§/\n/g')

echo "=== gate: $DECISION — $REASONS ==="
printf "| métrique | %s | %s | Δ |\n|---|---|---|---|\n%s\n" "$NAME" "$INCUMBENT" "$TABLE"

if [ "$DECISION" != "PROMOTE" ]; then
  echo "→ candidat NON promu. Rien à faire (cleanup via stage_candidate.sh --cleanup)."
  exit 0
fi

# --- build PR ---
BODY=$(printf "## Model swap: %s → %s\n\nÉval automatique (harness deterministic, exp MLflow \`localai-model-eval\`). Candidat > courant sur le gate (marge %s, pas de régression tool-call).\n\n| métrique | %s (candidat) | %s (courant) | Δ |\n|---|---|---|---|\n%s\n\n**Généré par le pipeline model-autodeploy (P3). Review + merge manuel requis.**\n" "$NAME" "$INCUMBENT" "$MARGIN" "$NAME" "$INCUMBENT" "$TABLE")
BRANCH="model-swap/${NAME}"

echo "=== édition values.yaml (add $NAME, remove $INCUMBENT) ==="
DRYFLAG=""; [ "$DRY" = "1" ] && DRYFLAG="--dry-run"
python3 "$HERE/edit_values.py" --add-file "$HERE/results/${NAME}.model.yaml" --add-name "$NAME" --remove "$INCUMBENT" $DRYFLAG

if [ "$DRY" = "1" ]; then
  echo "=== [dry-run] PR qui SERAIT créée (branch $BRANCH) ==="
  echo "$BODY"
  exit 0
fi

cd /data/projets/perso/my-kluster
git checkout -b "$BRANCH" 2>&1 | tail -1
git add charts/localai/values.yaml
git commit -q -m "feat(localai): swap agentic model $INCUMBENT → $NAME (auto-eval)

$REASONS. Cf PR body / MLflow localai-model-eval."
TOK=$(gh auth token -u tom333 2>/dev/null)
git push "https://x-access-token:${TOK}@github.com/tom333/my-kluster.git" "$BRANCH:$BRANCH" 2>&1 | tail -2
gh auth switch --user tom333 >/dev/null 2>&1
gh pr create --repo tom333/my-kluster --base main --head "$BRANCH" \
  --title "Model swap: $NAME → replace $INCUMBENT (auto-eval)" --body "$BODY" 2>&1 | tail -2
gh auth switch --user tguyader >/dev/null 2>&1
git checkout main 2>&1 | tail -1
echo "→ PR créée. Review + merge MANUEL (jamais auto)."
