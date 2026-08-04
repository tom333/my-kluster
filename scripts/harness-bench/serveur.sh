#!/bin/bash
# Demarre un llama-server nomme ET capture son log dans logs-serveur/.
#
# Motif (2026-08-04) : le banc archive les transcripts et les trajectoires, mais
# JAMAIS la verite cote serveur — tokens de prompt et de generation par requete,
# acceptation du drafter, reutilisation de slot, clamps. `podman rm` l'effacait.
# Trois erreurs d'analyse dans la meme journee auraient ete evitees, dont une ou
# les logs necessaires ont ete detruits au moment precis ou il les fallait.
#
#   ./serveur.sh <nom> <modele.gguf> [drapeaux supplementaires...]
set -eu
NOM="$1"; MODELE="$2"; shift 2
M=/var/snap/microk8s/common/default-storage/localai-localai-models-pvc-1372f466-79e5-4542-8d6f-36a705d8464f
HORO=$(date +%Y%m%d-%H%M%S)
LOG="$(dirname "$0")/logs-serveur/${NOM}-${HORO}.log"

podman rm -f "$NOM" >/dev/null 2>&1 || true
sleep 2
podman run -d --rm --name "$NOM" --device nvidia.com/gpu=all \
  -p 127.0.0.1:8080:8080 -v "$M":/models:ro \
  ghcr.io/ggml-org/llama.cpp:server-cuda-b10156 \
  --model "/models/$MODELE" --ctx-size 49152 --parallel 1 \
  -fa on -ctk q8_0 -ctv q8_0 --jinja --no-webui \
  --host 0.0.0.0 --port 8080 "$@" >/dev/null

# La config ACTIVE du serveur, publiee pour que bench.py la recopie dans chaque
# resultat. Motif (2026-08-04) : `-n 16384` plafonnait en silence le rejeu de
# troncature et a invalide trois campagnes d'Ornith. L'argv serveur doit voyager
# AVEC les scores, pas rester dans ma memoire.
python3 - "$NOM" "$MODELE" "$LOG" "$@" <<'PY'
import json, sys
from pathlib import Path
nom, modele, log, *drapeaux = sys.argv[1:]
Path(log).parent.mkdir(parents=True, exist_ok=True)
Path(Path(log).parent / "actif.json").write_text(json.dumps({
    "nom": nom, "modele": modele, "log": log, "drapeaux": drapeaux,
    "ctx_size": 49152, "parallel": 1, "flash_attn": True, "kv": "q8_0",
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

# Capture DETACHEE : elle survit au `podman rm` du conteneur.
nohup podman logs -f "$NOM" > "$LOG" 2>&1 &
until curl -sf -o /dev/null http://127.0.0.1:8080/health; do sleep 5; done
echo "$NOM pret | vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader) | log=$LOG"
