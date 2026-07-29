#!/usr/bin/env bash
# P2 — staging candidat : déploie un modèle en ÉPHÉMÈRE sur LocalAI (PVC, HORS git),
# lance le harness d'éval, compare au baseline. Si gagnant → P3 (PR). Sinon → --cleanup.
#
# Usage :
#   stage_candidate.sh --name qwen2.5-coder-3b --gguf <URL.gguf> [--draft <URL>] [--ctx 8192] [--baseline qwen3-coder-30b-a3b-instruct]
#   stage_candidate.sh --cleanup --name qwen2.5-coder-3b     # retire le candidat + reverte
#
# Méthode : télécharge le GGUF DIRECTEMENT sur le PVC AVANT d'écrire le yaml,
# puis redémarre LocalAI. Le fichier étant déjà présent, LocalAI ne télécharge
# PAS au boot et le service devient prêt en ~40s (au lieu de 45 min bloqués par
# le download_files dans le yaml). --cleanup conserve son comportement.
set -euo pipefail
NS=localai
NAME=""; GGUF=""; DRAFT=""; CTX=8192; BASELINE="qwen3-coder-30b-a3b-instruct"; CLEANUP=0; BACKEND="llama-cpp"
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;;
  --gguf) GGUF="$2"; shift 2;;
  --draft) DRAFT="$2"; shift 2;;
  --ctx) CTX="$2"; shift 2;;
  --baseline) BASELINE="$2"; shift 2;;
  --backend) BACKEND="$2"; shift 2;;   # ex: cuda12-bonsai (ternaire Q2_0), défaut llama-cpp
  --cleanup) CLEANUP=1; shift;;
  *) echo "arg inconnu: $1"; exit 2;;
esac; done
[ -z "$NAME" ] && { echo "--name requis"; exit 2; }
POD() { kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/localai/{print $1}' | head -1; }

restart_wait() {
  echo "restart LocalAI + attente ready (modèle déjà présent sur PVC, prêt en ~40s)..."
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

# --- TÉLÉCHARGEMENT PRÉALABLE DU GGUF SUR LE PVC ---
# Pourquoi avant ?
# - LocalAI télécharge le modèle au boot uniquement si le yaml contient download_files.
# - En téléchargeant d'abord, on évite de bloquer le service 45 min pendant le transfert.
# - curl -C - permet de reprendre un transfert interrompu (débit HF instable).

MODEL_DIR="/data/kube/default-storage/localai-localai-models-pvc-"
# Trouver le PVC actif (plusieurs peuvent exister, on prend le premier)
PVC=$(ls -d "$MODEL_DIR"* 2>/dev/null | head -1)
[ -z "$PVC" ] && { echo "ERREUR: aucun PVC localai-models trouvé sous $MODEL_DIR"; exit 2; }

# Fonction de téléchargement avec reprise et vérifications
# - Content-Length : taille attendue (évite d'installer un fichier tronqué)
# - Magic bytes : 4 premiers octets = 0x47 0x55 0x47 0x46 = "GGUF"
#
# IMPORTANT : un fichier INCOMPLET ne doit JAMAIS être supprimé, sinon `curl -C -`
# repart de zéro à chaque tentative et la reprise devient inopérante — c'est
# exactement le cas qu'on corrige (7,5 Go à 500 KB/s, transfert interrompu).
# On distingue donc deux situations :
#   - trop court        -> on garde le partiel et on relance, curl reprend ;
#   - trop long ou      -> le fichier est corrompu, là on le supprime pour
#     mauvais entête       repartir proprement.
download_and_verify() {
  local url="$1"
  local dst="$2"
  local expected_size="$3"
  local attempts=0
  local max_attempts=8

  echo "Téléchargement $GGUF_FILE ($expected_size octets attendus)..."
  while [ "$attempts" -lt "$max_attempts" ]; do
    attempts=$((attempts + 1))
    have=$(stat -c%s "$dst" 2>/dev/null || echo 0)
    echo "  Tentative $attempts/$max_attempts (déjà $have octets)..."
    # -f (--fail) est indispensable : sans lui, une réponse HTTP 4xx/5xx voit son
    # CORPS écrit dans "$dst". Un 404 y dépose une page d'erreur de quelques
    # octets, qui devient un faux "partiel" que la reprise suivante prolongerait —
    # produisant un fichier définitivement corrompu.
    curl -C - -sfL --retry 5 --retry-delay 10 --max-time 7200 -o "$dst" "$url" || true

    actual_size=$(stat -c%s "$dst" 2>/dev/null || echo 0)
    if [ "$actual_size" -lt "$expected_size" ]; then
      echo "  incomplet: $actual_size / $expected_size — partiel CONSERVÉ, reprise"
      sleep 5
      continue
    fi
    if [ "$actual_size" -gt "$expected_size" ]; then
      echo "  ÉCHEC taille: $actual_size > $expected_size attendu — fichier corrompu"
      rm -f "$dst"
      sleep 5
      continue
    fi

    # Entête GGUF, lu sans dépendre de xxd (absent de certaines images).
    magic=$(head -c 4 "$dst" 2>/dev/null || echo "")
    if [ "$magic" != "GGUF" ]; then
      echo "  ÉCHEC entête: attendu 'GGUF', obtenu '$magic' — fichier corrompu"
      rm -f "$dst"
      sleep 5
      continue
    fi

    echo "  OK taille=$actual_size entête=GGUF"
    return 0
  done

  echo "ERREUR: échec après $max_attempts tentatives (partiel conservé pour reprise)"
  return 1
}

# Récupérer la taille attendue depuis l'en-tête HTTP
# -L obligatoire : HuggingFace redirige vers un CDN, et sans suivre la redirection
# on lit le Content-Length de la réponse 302, pas celui du fichier. `tail -1` prend
# la dernière en-tête de la chaîne, `tr -d '\r'` retire le CR des en-têtes HTTP.
EXPECTED_SIZE=$(curl -sIL "$GGUF" | grep -i '^content-length:' | tail -1 | tr -d '\r' | awk '{print $2}')
[ -z "$EXPECTED_SIZE" ] && { echo "ERREUR: impossible de récupérer Content-Length de $GGUF"; exit 1; }
echo "Taille attendue : $EXPECTED_SIZE octets"

# 1. Télécharger à côté du fichier final, en `.part`.
#    PAS dans un sous-dossier `.tmp/` : LocalAI scanne /models, et un GGUF partiel
#    posé là-dedans peut être ramassé par son inventaire.
PVC_FINAL="$PVC/$GGUF_FILE"
PVC_PART="${PVC_FINAL}.part"
if [ -f "$PVC_FINAL" ] && [ "$(stat -c%s "$PVC_FINAL")" = "$EXPECTED_SIZE" ]; then
  echo "GGUF déjà présent et complet sur le PVC — téléchargement sauté."
else
  if ! download_and_verify "$GGUF" "$PVC_PART" "$EXPECTED_SIZE"; then
    echo "ERREUR: téléchargement et vérification échoués. Le .part est conservé :"
    echo "  $PVC_PART"
    echo "Relancer la même commande reprendra où le transfert s'est arrêté."
    exit 1
  fi
  # 2. Publication atomique : le nom final n'apparaît qu'une fois le fichier
  #    complet et vérifié, donc LocalAI ne peut jamais voir un modèle tronqué.
  mv -f "$PVC_PART" "$PVC_FINAL"
  echo "GGUF installé : $PVC_FINAL"
fi

# 3. La tête de draft (MTP / décodage spéculatif) doit suivre le même chemin : le
#    yaml la référence via `draft_model`, donc sans pré-téléchargement le modèle
#    référencerait un fichier absent — exactement la régression qu'on corrige,
#    déplacée sur le drafter.
if [ -n "$DRAFT" ]; then
  DRAFT_FILE="$(basename "$DRAFT")"
  DRAFT_FINAL="$PVC/$DRAFT_FILE"
  DRAFT_SIZE=$(curl -sIL "$DRAFT" | grep -i '^content-length:' | tail -1 | tr -d '\r' | awk '{print $2}')
  [ -z "$DRAFT_SIZE" ] && { echo "ERREUR: Content-Length introuvable pour le draft $DRAFT"; exit 1; }
  if [ -f "$DRAFT_FINAL" ] && [ "$(stat -c%s "$DRAFT_FINAL")" = "$DRAFT_SIZE" ]; then
    echo "Draft déjà présent et complet — téléchargement sauté."
  else
    GGUF_FILE_SAVE="$GGUF_FILE"; GGUF_FILE="$DRAFT_FILE"
    if ! download_and_verify "$DRAFT" "${DRAFT_FINAL}.part" "$DRAFT_SIZE"; then
      echo "ERREUR: téléchargement du draft échoué (.part conservé)"; exit 1
    fi
    GGUF_FILE="$GGUF_FILE_SAVE"
    mv -f "${DRAFT_FINAL}.part" "$DRAFT_FINAL"
    echo "Draft installé : $DRAFT_FINAL"
  fi
fi

# --- FIN DU TÉLÉCHARGEMENT PRÉALABLE ---

# --- GÉNÉRATION DU YAML (SANS download_files) ---
TMP=$(mktemp)
{
  echo "name: $NAME"
  echo "backend: $BACKEND"
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
  # Pas de download_files : le fichier est déjà présent sur le PVC
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
# sauvegarde la config pour promote.sh (P3 : bloc à insérer dans values.yaml)
mkdir -p "$(dirname "$0")/results"; cp "$TMP" "$(dirname "$0")/results/${NAME}.model.yaml"
rm -f "$TMP"
restart_wait
echo "=== candidat listé ? ==="
kubectl exec -n $NS "$(POD)" -c localai -- sh -c "curl -s http://127.0.0.1:8080/v1/models -H \"Authorization: Bearer \$API_KEY\" | grep -o '\"$NAME\"' | head -1" 2>&1

# Garde-fou AVANT l'éval : un modèle qui n'appelle pas ses outils ne peut pas être évalué
# en agentique, et le mesurer donne un 0 qu'on prend pour un manque de compétence. Coût :
# 2 requêtes. Cf. tool_call_gate.sh pour l'incident qui a motivé ce garde-fou.
if ! "$(dirname "$0")/tool_call_gate.sh" "$NAME"; then
  echo ""
  echo "→ Éval NON lancée. Nettoyage : stage_candidate.sh --cleanup --name $NAME"
  exit 1
fi

echo "=== ÉVAL candidat vs baseline $BASELINE ==="
cd "$(dirname "$0")"
uv run run_eval.py --model "$NAME" --tag candidate --compare-to "$BASELINE" 2>&1 | grep -vE "Downloading|Downloaded|Installed|INFO mlflow"
echo ""
echo "→ Si gagnant : P3 (PR my-kluster add $NAME + remove ancien + résumé MLflow)."
echo "→ Sinon : stage_candidate.sh --cleanup --name $NAME"
