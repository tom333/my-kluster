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

CTX="${CTX:-49152}"
IMAGE="${IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda-b10156}"

# L'argv EXACT, dans un tableau : c'est lui qu'on passe a podman ET qu'on recopie
# dans actif.json. Recopier des champs a la main (`ctx_size: 49152` code en dur)
# les laisse divergier du serveur reel des qu'on edite le script — constate le
# 2026-08-05, ou actif.json annoncait 49152 pour un serveur lance a 32768.
ARGS=(
  --model "/models/$MODELE" --ctx-size "$CTX" --parallel 1
  -fa on -ctk q8_0 -ctv q8_0 --jinja --no-webui
  --host 0.0.0.0 --port 8080 "$@"
)

# `--no-mmap` des qu'un expert est deporte en RAM. Deux raisons, les deux mesurees
# le 2026-08-06 en calibrant KAT-Coder :
#   1. llama.cpp le reclame lui-meme — « tensor overrides to CPU are used with mmap
#      enabled - consider using --no-mmap for better performance » ;
#   2. avec mmap, les poids se chargent PARESSEUSEMENT, donc /health repond avant
#      qu'ils soient residents. La garde anti-mauvais-modele de regle_ncmoe.sh a
#      refuse une mesure pourtant valide pour cette seule raison.
# Conditionnel et non systematique : sur un modele qui tient entierement en VRAM,
# mmap accelere le demarrage et ne coute rien.
case " $* " in
  *" --n-cpu-moe "*|*" -ncmoe "*|*" --cpu-moe "*)
    ARGS+=(--no-mmap) ;;
esac

podman rm -f "$NOM" >/dev/null 2>&1 || true
sleep 2
podman run -d --rm --name "$NOM" --device nvidia.com/gpu=all \
  -p 127.0.0.1:8080:8080 -v "$M":/models:ro \
  "$IMAGE" "${ARGS[@]}" >/dev/null

# La config ACTIVE du serveur, publiee pour que bench.py la recopie dans chaque
# resultat. Motif (2026-08-04) : `-n 16384` plafonnait en silence le rejeu de
# troncature et a invalide trois campagnes d'Ornith. L'argv serveur doit voyager
# AVEC les scores, pas rester dans ma memoire.
python3 - "$NOM" "$MODELE" "$LOG" "$IMAGE" "${ARGS[@]}" <<'PY'
import json, sys
from pathlib import Path
nom, modele, log, image, *argv = sys.argv[1:]


def valeur(drapeau, defaut=None):
    """Valeur LUE dans l'argv reel, pas une constante recopiee a cote."""
    return argv[argv.index(drapeau) + 1] if drapeau in argv else defaut


# Les drapeaux SUPPLEMENTAIRES, ceux qui distinguent deux campagnes : tout ce qui
# suit `--port 8080` dans le tableau construit par le script.
extra = argv[argv.index("--port") + 2:]
Path(log).parent.mkdir(parents=True, exist_ok=True)
Path(Path(log).parent / "actif.json").write_text(json.dumps({
    "nom": nom, "modele": modele, "log": log, "image": image,
    "drapeaux": extra,
    "ctx_size": int(valeur("--ctx-size")),
    "parallel": int(valeur("--parallel")),
    "flash_attn": valeur("-fa") == "on",
    "kv": valeur("-ctk"),
    # L'argv COMPLET, pour ne plus dependre du sous-ensemble qu'on a pense a lire.
    "argv": argv,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

# Capture DETACHEE : elle survit au `podman rm` du conteneur.
nohup podman logs -f "$NOM" > "$LOG" 2>&1 &
until curl -sf -o /dev/null http://127.0.0.1:8080/health; do sleep 5; done
echo "$NOM pret | vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader) | log=$LOG"
