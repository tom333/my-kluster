#!/usr/bin/env bash
# Garde-fou : le modèle sait-il appeler un outil ? À lancer AVANT toute éval.
#
# Usage :
#   tool_call_gate.sh <nom-du-modele-localai>
#   tool_call_gate.sh current
#
# Sortie 0 = passe, 1 = échoue, 2 = erreur d'usage/infra.
#
# POURQUOI. Le 2026-07-29, `yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1` a coûté une
# demi-journée : le finetune avait GARDÉ la compétence en code (17/44 sur tetris, mesuré
# hors ligne depuis son transcript) et CASSÉ le template d'appel d'outil. Il affichait son
# code dans le message de chat et n'appelait jamais `write`. Le banc voyait 0/44 et j'ai
# cherché la cause du côté de la grammaire de décodage, du contrat de boucle du harnais,
# puis d'un response_regex — avant de comparer avec le QAT officiel, qui appelait
# correctement sur le MÊME prompt. Ce test-ci coûte 2 requêtes et tranche en 30 secondes.
#
# DISCRIMINANT : le prompt est volontairement LONG et ouvert. Sur une demande courte et
# impérative (« crée /tmp/x.py avec print(1) »), le modèle cassé retombe dans le bon
# format et le défaut est INVISIBLE. C'est la longueur de la tâche qui le révèle.
set -uo pipefail
NS=localai
NAME="${1:-}"
[ -z "$NAME" ] && { echo "usage: $0 <nom-du-modele-localai>"; exit 2; }
POD=$(kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/^localai-[0-9a-f]|^localai-[0-9]/{print $1}' | head -1)
[ -z "$POD" ] && { echo "ERREUR: pod localai introuvable"; exit 2; }

echo "=== garde-fou appel d'outil : $NAME"

kubectl exec -i -n "$NS" "$POD" -c localai -- python3 - "$NAME" <<'PY'
import json, os, subprocess, sys

nom = sys.argv[1]
cle = os.environ.get("API_KEY", "")

def outil(n, d, props, req):
    return {"type": "function", "function": {
        "name": n, "description": d,
        "parameters": {"type": "object", "properties": props, "required": req}}}

OUTILS = [
    outil("read", "Lit un fichier du disque", {"path": {"type": "string"}}, ["path"]),
    outil("write", "Ecrit un fichier sur le disque",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    outil("edit", "Remplace une chaine dans un fichier",
          {"path": {"type": "string"}, "old_string": {"type": "string"},
           "new_string": {"type": "string"}}, ["path", "old_string", "new_string"]),
    outil("bash", "Execute une commande shell", {"command": {"type": "string"}}, ["command"]),
]

# Tache longue et ouverte, deliberement : c'est ce qui fait deraper un template casse.
TACHE = (
    "Ce dossier contient une suite de tests, tests/test_tetris.py, et rien d'autre.\n"
    "Le paquet tetris/ qu'elle importe n'existe pas : ecris-le entierement pour que TOUS "
    "les tests passent.\n"
    "Le fichier de tests est le contrat : son docstring d'entete decrit le comportement "
    "attendu de chaque classe et de chaque methode publique. Lis-le en entier avant de "
    "commencer, puis lis les tests eux-memes.\n"
    "Contraintes : ne modifie aucun fichier dans tests/. Le module tetris doit exporter "
    "SHAPES, Piece, Board, Bag et Game.\n"
    "Lance pytest -q pour verifier ta progression."
)

corps = {"model": nom, "messages": [{"role": "user", "content": TACHE}],
         "tools": OUTILS, "max_tokens": 500, "temperature": 0.6}

r = subprocess.run(
    ["curl", "-s", "--max-time", "900", "-H", "Authorization: Bearer " + cle,
     "-H", "Content-Type: application/json", "-d", "@-",
     "http://127.0.0.1:8080/v1/chat/completions"],
    input=json.dumps(corps), capture_output=True, text=True)

try:
    d = json.loads(r.stdout)
except Exception:
    print("  ECHEC: reponse illisible: %s" % r.stdout[:200]); sys.exit(1)
if "error" in d:
    print("  ECHEC: %s" % str(d["error"])[:220]); sys.exit(1)

c = d["choices"][0]
m = c["message"]
appels = m.get("tool_calls") or []
texte = (m.get("content") or "").strip()

print("  finish_reason : %s" % c.get("finish_reason"))
print("  tool_calls    : %d %s" % (len(appels), [a["function"]["name"] for a in appels]))
print("  texte         : %d caracteres" % len(texte))

if appels:
    print("  -> PASSE : le modele appelle ses outils sur une tache longue.")
    sys.exit(0)

# Diagnostic utile : un appel emis en TEXTE au lieu du champ tool_calls est le
# symptome exact du template casse. On le nomme pour ne pas rechercher a l'aveugle.
import re
if re.search(r"\b(read|write|edit|bash)\s*\(", texte) or "tool_call" in texte:
    print("  -> ECHEC : appel d'outil emis EN TEXTE, pas en tool_calls.")
    print("     Template d'appel d'outil casse (typique d'un finetune). Extrait :")
    print("     %r" % texte[:200])
else:
    print("  -> ECHEC : aucun appel d'outil, reponse en prose. Extrait :")
    print("     %r" % texte[:200])
sys.exit(1)
PY
CODE=$?
if [ "$CODE" = "0" ]; then
  echo "=== garde-fou OK"
else
  echo "=== garde-fou ECHOUE : ne PAS lancer l'eval, ce modele ne peut pas agir."
  echo "    (un finetune qui echoue ici peut rester bon en autocompletion, mais il est"
  echo "     inutilisable en agentique — voir scripts/harness-bench/README.md)"
fi
exit $CODE
