#!/bin/bash
# Cherche le plus PETIT `-ncmoe N` (donc le moins d'experts deportes en RAM, donc
# le plus rapide) qui tienne dans la VRAM. Chaque essai : demarrage, lecture de la
# VRAM, sonde de debit, arret.
#
# `-ncmoe N` garde en CPU les experts des N PREMIERES couches. N grand = plus en
# RAM = plus lent mais moins de VRAM. On descend donc N jusqu'a ce que ca ne tienne
# plus, et on garde le dernier qui tenait.
set -u
M=/var/snap/microk8s/common/default-storage/localai-localai-models-pvc-1372f466-79e5-4542-8d6f-36a705d8464f
MODELE="${1:?modele.gguf}"
PLAFOND_MIB="${2:-11200}"   # marge sous les 12288 de la carte
CTX="${3:-32768}"
IMG=ghcr.io/ggml-org/llama.cpp:server-cuda-b10156

sonde() {  # $1 = N
  # Liberer le port AVANT de demarrer : sinon `podman run` echoue a se lier, la
  # sonde de sante repond depuis le serveur DEJA en place et on mesure le mauvais
  # modele. C'est arrive le 2026-08-04 : gemma a ete mesure a 74,6 tok/s et
  # attribue a l'A3B, dont le vrai debit est 28,8.
  for c in $(podman ps --format '{{.Names}}'); do podman rm -f "$c" >/dev/null 2>&1; done
  sleep 2
  podman rm -f ncmoe >/dev/null 2>&1 || true
  sleep 2
  podman run -d --rm --name ncmoe --device nvidia.com/gpu=all \
    -p 127.0.0.1:8080:8080 -v "$M":/models:ro "$IMG" \
    --model "/models/$MODELE" --ctx-size "$CTX" --parallel 1 \
    -fa on -ctk q8_0 -ctv q8_0 --jinja --no-webui \
    --n-cpu-moe "$1" --host 0.0.0.0 --port 8080 >/dev/null 2>&1
  for _ in $(seq 60); do
    curl -sf -o /dev/null http://127.0.0.1:8080/health && break
    sleep 5
  done
  if ! curl -sf -o /dev/null http://127.0.0.1:8080/health; then
    echo "N=$1 : NE DEMARRE PAS"; podman logs ncmoe 2>&1 | tail -3; return 1
  fi
  # VERIFIER quel modele repond, jamais le supposer.
  curl -s http://127.0.0.1:8080/v1/models -o /tmp/ncmoe-modele.json
  SERVI=$(python3 -c "
import re
print((re.search(r'/models/[^\"\\\\]+\.gguf', open('/tmp/ncmoe-modele.json',encoding='utf-8',errors='replace').read()) or [None])[0] if re.search(r'/models/[^\"\\\\]+\.gguf', open('/tmp/ncmoe-modele.json',encoding='utf-8',errors='replace').read()) else 'inconnu'" 2>/dev/null || echo inconnu)
  case "$SERVI" in
    */"$MODELE") : ;;
    *) echo "N=$1 : MAUVAIS MODELE SERVI ($SERVI) — mesure refusee"; return 1 ;;
  esac
  VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -dc '0-9')
  curl -s http://127.0.0.1:8080/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"x","messages":[{"role":"user","content":"Write a Python linked list class with insert, delete, find and __repr__."}],"max_tokens":256}' \
    -o /tmp/ncmoe-sonde.json
  DEBIT=$(python3 -c "
import json
try: print('%.1f' % json.load(open('/tmp/ncmoe-sonde.json'))['timings']['predicted_per_second'])
except Exception: print('0')")
  echo "N=$1 : vram=${VRAM} MiB  debit=${DEBIT} tok/s  (plafond ${PLAFOND_MIB})"
  [ "$VRAM" -le "$PLAFOND_MIB" ]
}

echo "=== reglage -ncmoe pour $MODELE (ctx=$CTX)"
for N in 48 36 24 18 12 8 4 0; do
  if sonde "$N"; then
    echo ">>> RETENU : -ncmoe $N"
    exit 0
  fi
done
echo ">>> aucun N ne tient sous ${PLAFOND_MIB} MiB"
