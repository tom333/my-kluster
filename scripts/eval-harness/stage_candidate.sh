#!/usr/bin/env bash
# P2 — staging candidat : déploie un modèle en ÉPHÉMÈRE sur LocalAI (PVC, HORS git),
# lance le harness d'éval, compare au baseline. Si gagnant → P3 (PR). Sinon → --cleanup.
#
# Usage :
#   stage_candidate.sh --name qwen2.5-coder-3b --gguf <URL.gguf> [--draft <URL>] [--ctx 8192] [--baseline ornith-1.0-9b-mtp]
#   stage_candidate.sh --cleanup --name qwen2.5-coder-3b     # retire le candidat + reverte
#
# Méthode : écrit /models/<name>.yaml sur le PVC LocalAI + restart (LocalAI télécharge
# le GGUF au boot, ne hot-load pas). Manuel/occasionnel → le restart est acceptable.
set -euo pipefail
NS=localai
NAME=""; GGUF=""; DRAFT=""; CTX=8192; BASELINE="ornith-1.0-9b-mtp"; CLEANUP=0
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;;
  --gguf) GGUF="$2"; shift 2;;
  --draft) DRAFT="$2"; shift 2;;
  --ctx) CTX="$2"; shift 2;;
  --baseline) BASELINE="$2"; shift 2;;
  --cleanup) CLEANUP=1; shift;;
  *) echo "arg inconnu: $1"; exit 2;;
esac; done
[ -z "$NAME" ] && { echo "--name requis"; exit 2; }
POD() { kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/localai/{print $1}' | head -1; }

restart_wait() {
  echo "restart LocalAI + attente ready (téléchargement GGUF au boot, peut être long)..."
  kubectl delete pod -n $NS "$(POD)" >/dev/null 2>&1 || true
  for i in $(seq 1 240); do
    p=$(POD); r=$(kubectl get pod -n $NS "$p" --no-headers 2>/dev/null | awk '{print $2}')
    [ "$r" = "1/1" ] && { echo "ready: $p"; return 0; }
    sleep 15
  done
  echo "TIMEOUT ready"; return 1
}

if [ "$CLEANUP" = "1" ]; then
  p=$(POD)
  echo "cleanup candidat $NAME (yaml + gguf sur PVC)..."
  kubectl exec -n $NS "$p" -c localai -- sh -c "rm -f /models/${NAME}.yaml; ls /models/*.gguf 2>/dev/null" >/dev/null 2>&1 || true
  echo "⚠️ GGUF laissés (supprime à la main si besoin). Yaml retiré. Restart pour reverter :"
  restart_wait
  exit 0
fi

[ -z "$GGUF" ] && { echo "--gguf requis (URL du .gguf)"; exit 2; }
GGUF_FILE="$(basename "$GGUF")"
TMP=$(mktemp)
{
  echo "name: $NAME"
  echo "backend: llama-cpp"
  echo "known_usecases: [chat]"
  echo "context_size: $CTX"
  echo "gpu_layers: 99"
  echo "f16: true"
  echo "flash_attention: true"
  echo "mmap: true"
  echo "cache_type_k: q8_0"
  echo "cache_type_v: q8_0"
  [ -n "$DRAFT" ] && echo "draft_model: $(basename "$DRAFT")"
  echo "parameters:"
  echo "  model: $GGUF_FILE"
  echo "  temperature: 0.6"
  echo "  top_p: 0.95"
  echo "  top_k: 20"
  echo "download_files:"
  echo "  - filename: $GGUF_FILE"
  echo "    uri: $GGUF"
  if [ -n "$DRAFT" ]; then
    echo "  - filename: $(basename "$DRAFT")"
    echo "    uri: $DRAFT"
  fi
  echo "options:"
  echo "  - use_jinja:true"
  [ -n "$DRAFT" ] && { echo "  - spec_type:draft-mtp"; echo "  - draft_max:2"; }
  echo "function:"
  echo "  automatic_tool_parsing_fallback: true"
  echo "  grammar:"
  echo "    disable: true"
  echo "template:"
  echo "  use_tokenizer_template: true"
  echo "stopwords:"
  echo '  - "<|im_end|>"'
  echo '  - "<|endoftext|>"'
} > "$TMP"

echo "=== config candidat $NAME ==="; cat "$TMP"
kubectl cp "$TMP" "$NS/$(POD):/models/${NAME}.yaml" -c localai
rm -f "$TMP"
restart_wait
echo "=== candidat listé ? ==="
kubectl exec -n $NS "$(POD)" -c localai -- sh -c "curl -s http://127.0.0.1:8080/v1/models -H \"Authorization: Bearer \$API_KEY\" | grep -o '\"$NAME\"' | head -1" 2>&1

echo "=== ÉVAL candidat vs baseline $BASELINE ==="
cd "$(dirname "$0")"
uv run run_eval.py --model "$NAME" --tag candidate --compare-to "$BASELINE" 2>&1 | grep -vE "Downloading|Downloaded|Installed|INFO mlflow"
echo ""
echo "→ Si gagnant : P3 (PR my-kluster add $NAME + remove ancien + résumé MLflow)."
echo "→ Sinon : stage_candidate.sh --cleanup --name $NAME"
