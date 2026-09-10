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

# LES ÉCARTÉS, sans quoi la veille repropose ce qu'on a déjà jugé. Vu le 2026-09-11 :
# elle a présenté Ornith-1.5-9B comme « nouveau modèle » alors qu'il était mesuré
# deux jours plus tôt (deux campagnes, 1 réussite sur 6, écarté sur le coût) et
# COMMENTÉ dans la file avec son motif. L'instantané ne publiait que les candidats en
# attente : tout le savoir accumulé sur les rejets restait invisible à Hermes.
#
# `familles` sert au rapprochement : la veille parle de « Ornith-1.5-9B » quand la file
# dit `ornith-1.5-9b-mtp-iq4xs`. On publie donc aussi la racine sans les suffixes de
# quantification, pour que la comparaison n'échoue pas sur un `-q4_k_m` de différence.
juges=$(python3 - "$QUEUE" "$DONE" <<'PYJUGES' 2>/dev/null
import json, re, sys

MOTIF_MAX = 240
QUANTS = re.compile(
    r"-(?:q\d(?:_[0-9kmsxl]+)*|iq\d[a-z_]*|ud-q\d[a-z_]*|mtp|f16|bf16|"
    r"q\dkm|q\dks|xs|instruct|gguf)$", re.I)

def famille(nom):
    """Racine du nom, suffixes de quantification retirés (plusieurs passes)."""
    prec = None
    while prec != nom:
        prec, nom = nom, QUANTS.sub("", nom)
    return nom

juges, familles = [], set()
motif = []
try:
    lignes = open(sys.argv[1], encoding="utf-8").read().splitlines()
except OSError:
    lignes = []
for ligne in lignes:
    depouille = ligne.strip()
    # Ligne de candidat COMMENTÉE = écartée. Le motif est le bloc de commentaires
    # qui la précède immédiatement.
    m = re.match(r"^#\s*([A-Za-z0-9._-]+)\|https?://", depouille)
    if m:
        nom = m.group(1)
        juges.append({"nom": nom, "etat": "ecarte",
                      "motif": " ".join(motif)[:MOTIF_MAX] or "motif non consigné"})
        familles.add(famille(nom.lower()))
        motif = []
        continue
    if depouille.startswith("#"):
        texte = depouille.lstrip("#").strip()
        if texte:
            motif.append(texte)
        if len(motif) > 12:      # garde le plus RÉCENT, le plus proche de la ligne
            motif = motif[-12:]
        continue
    motif = []                   # une ligne active ou vide clôt le bloc courant

try:
    for l in open(sys.argv[2], encoding="utf-8"):
        champs = l.split("|")
        if len(champs) > 1 and champs[1].strip():
            nom = champs[1].strip()
            juges.append({"nom": nom, "etat": "traite", "motif": "évalué, cf. verdicts"})
            familles.add(famille(nom.lower()))
except OSError:
    pass

# Dédoublonne en gardant la PREMIÈRE occurrence : un écarté motivé prime sur un
# simple « traité » du cache.
vus, uniques = set(), []
for j in juges:
    if j["nom"] not in vus:
        vus.add(j["nom"])
        uniques.append(j)
print(json.dumps({"juges": uniques, "familles": sorted(familles)}, ensure_ascii=False))
PYJUGES
)
# Pas de `${juges:-{...}}` : en bash l'expansion se termine sur la PREMIÈRE
# accolade fermante du défaut, ce qui colle un `}"` parasite et corrompt le JSON.
if [ -z "$juges" ]; then juges='{"juges":[],"familles":[]}'; fi

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

payload=$(python3 - "$running" "${recent:-[]}" "$juges" "${pending[@]:-}" <<'PY'
import json, sys, datetime
running=sys.argv[1]; recent=json.loads(sys.argv[2])
juges=json.loads(sys.argv[3]); pending=[p for p in sys.argv[4:] if p]
print(json.dumps({
  "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
  "pending_count": len(pending), "pending": pending,
  "running": running, "recent_verdicts": recent,
  "juges": juges["juges"], "familles_jugees": juges["familles"],
  "note": "Instantané publié par pc. La file réelle vit sur pc, Hermes ne peut que la LIRE ici. `juges` = modèles DÉJÀ jugés (écartés avec motif, ou évalués) : à consulter AVANT de proposer un candidat.",
}, ensure_ascii=False, indent=1))
PY
)

# Une charge utile vide signifie que la génération a échoué. La publier
# remplacerait l'instantané par un fichier illisible, ce qui est PIRE qu'un
# instantané périmé : Hermes ne saurait plus rien au lieu de savoir un peu tard.
if [ -z "$payload" ]; then echo "WARN charge utile vide, publication annulée"; exit 0; fi

POD=$(kubectl get pods -n $NS --no-headers 2>/dev/null | awk '/hermes-agent/{print $1}' | head -1)
[ -z "$POD" ] && { echo "pod hermes introuvable"; exit 0; }
printf '%s' "$payload" | kubectl exec -i -n $NS "$POD" -c main -- sh -c "mkdir -p /opt/data/eval && cat > $DEST && chown -R 10000:10000 /opt/data/eval" 2>/dev/null \
  && echo "publié: ${#pending[@]} en attente, running=$running" || echo "WARN publication échouée"
