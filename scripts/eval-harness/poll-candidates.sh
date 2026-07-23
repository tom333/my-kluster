#!/usr/bin/env bash
# P4 — traite la file de candidats modèles. Chaque ligne NON déjà traitée lance
# eval-pipeline.sh. File alimentée semi-manuellement (toi) ou par une suggestion de
# la veille (format copiable). Cron pc (ex: quotidien) ou à la demande.
#
# Format file (~/.config/brain/model-candidates.queue), lignes :
#   <name>|<gguf-url>[|<draft-url>|<ctx>]
#   # les lignes vides / commençant par # sont ignorées
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
QUEUE="${MODEL_CANDIDATES_QUEUE:-$HOME/.config/brain/model-candidates.queue}"
DONE="${MODEL_CANDIDATES_DONE:-$HOME/.cache/model-candidates.done}"
mkdir -p "$(dirname "$DONE")"; touch "$DONE"
[ -f "$QUEUE" ] || { echo "pas de file $QUEUE"; exit 0; }

while IFS='|' read -r name gguf draft ctx; do
  case "$name" in ""|\#*) continue;; esac
  sig="$(printf '%s|%s' "$name" "$gguf" | sha1sum | cut -d' ' -f1)"
  grep -q "$sig" "$DONE" 2>/dev/null && continue   # déjà traité
  echo "=== candidat: $name ==="
  args=(--name "$name" --gguf "$gguf")
  [ -n "${draft:-}" ] && args+=(--draft "$draft")
  [ -n "${ctx:-}" ] && args+=(--ctx "$ctx")
  "$HERE/eval-pipeline.sh" "${args[@]}" || echo "WARN pipeline $name a échoué"
  echo "$sig  $name  $(date -u +%FT%TZ)" >> "$DONE"
done < "$QUEUE"
echo "file traitée."
