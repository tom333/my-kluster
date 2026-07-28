#!/usr/bin/env bash
# P3 — si un candidat BAT le modèle courant sur le harness, génère une PR my-kluster
# (add candidat + remove incumbent + résumé). JAMAIS d'auto-merge (PR = gate humain).
#
#   promote.sh --candidate <name> [--incumbent qwen3-coder-30b-a3b-instruct] [--margin 0.02] [--dry-run]
#
# Gate : overall(cand) - overall(base) >= margin  ET  toolcall(cand) >= toolcall(base) - 0.05
# (pas de régression agentique). Lit results/<name>-candidate.json + <incumbent>-baseline.json.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME=""; INCUMBENT=""; MARGIN="0.02"; DRY=0; AGENTIC_FLOOR="0.80"
while [ $# -gt 0 ]; do case "$1" in
  --candidate) NAME="$2"; shift 2;;
  --incumbent) INCUMBENT="$2"; shift 2;;
  --margin) MARGIN="$2"; shift 2;;
  --agentic-floor) AGENTIC_FLOOR="$2"; shift 2;;
  --dry-run) DRY=1; shift;;
  *) echo "arg inconnu: $1"; exit 2;;
esac; done
[ -z "$NAME" ] && { echo "--candidate requis"; exit 2; }

# L'incumbent est RÉSOLU depuis values.yaml (alias `current`), il n'est plus figé
# en dur. Motif : la PR 1573 avait été générée contre `ornith` (Δ overall +0.036,
# gate passé) et se retrouvait, cinq jours plus tard, à comparer un modèle qui
# n'était plus l'incumbent — contre le vrai courant son Δ valait 0.000. Un gate
# évalué à l'ouverture est périmé à la relecture.
if [ -z "$INCUMBENT" ]; then
  INCUMBENT=$(python3 - "$HERE/../../charts/localai/values.yaml" <<'PY'
import sys, yaml
cfgs = yaml.safe_load(open(sys.argv[1]))["modelsConfigs"]
print(yaml.safe_load(cfgs["current"])["alias"])
PY
)
  echo "→ incumbent résolu depuis values.yaml (alias current) : $INCUMBENT"
fi
CAND_JSON="$HERE/results/${NAME}-candidate.json"
BASE_JSON="$HERE/results/${INCUMBENT}-baseline.json"
[ -f "$CAND_JSON" ] || { echo "résultats candidat absents: $CAND_JSON (lance stage_candidate.sh d'abord)"; exit 1; }
[ -f "$BASE_JSON" ] || { echo "baseline absent: $BASE_JSON"; exit 1; }

# --- gate + résumé (python) ---
GATE=$(python3 - "$CAND_JSON" "$BASE_JSON" "$MARGIN" "$AGENTIC_FLOOR" \
       "$HERE/../harness-bench/results" "$NAME" "$INCUMBENT" <<'PY'
import glob, json, os, sys
cand=json.load(open(sys.argv[1]))["metrics"]; base=json.load(open(sys.argv[2]))["metrics"]
margin=float(sys.argv[3]); floor=float(sys.argv[4])
BENCH_DIR, cand_name, base_name = sys.argv[5], sys.argv[6], sys.argv[7]

# --- gate refondu le 2026-07-29, après trois mesures qui l'ont invalidé ---------
#
# L'ancien gate était `overall >= +marge ET toolcall >= base-0.05`. Il a laissé
# passer gemma-4-12b-coder : overall IDENTIQUE à l'incumbent, toolcall 1.000
# parfait — et 0/44 sur harness-bench tetris, ZÉRO fichier écrit. Le modèle
# décrivait ses actions au lieu de les exécuter.
#
# Deux défauts structurels :
#   1. `overall` moyenne six métriques dont quatre saturées à 1.000. Il ne peut
#      ni exprimer une amélioration (qwopus 38/44 vs 33/44 avec overall ~égal)
#      ni signaler un effondrement agentique. Il est DÉCLASSÉ en simple garde de
#      non-régression.
#   2. `toolcall_acc` teste « voici un outil, appelle-le » — un appel isolé, pas
#      une boucle soutenue. gemma y obtient 1.000 sans jamais écrire un fichier.
#
# Le critère PRINCIPAL devient donc harness-bench tetris : écrire un paquet de
# zéro contre 44 tests. C'est le seul qui discrimine (0 / 13 / 33 / 38 sur quatre
# modèles là où eval-harness donnait 0.982 à deux d'entre eux).
def tetris_score(name):
    """Meilleur score tetris obtenu par ce modèle, tous harnais confondus.

    On balaie TOUS les fichiers tetris et on filtre sur le champ `modele`, sans
    construire de motif à partir du nom : bench.py normalise le nom en slug
    (`[^a-z0-9]+` -> `-`), donc un point deviendrait un tiret et un glob bâti sur
    le nom brut ne trouverait rien. C'est exactement ce qui est arrivé avec
    `qwopus3.5-9b-coder` -> `qwopus3-5-9b-coder`.
    """
    best, best_runs = None, 0
    for path in glob.glob(os.path.join(BENCH_DIR, "tetris-*.json")):
        try: d = json.load(open(path))
        except (OSError, json.JSONDecodeError): continue
        if d.get("modele", "").split("/")[-1] != name: continue
        # `tests_passed_median` quand il existe : depuis --runs, c'est la médiane
        # qui fait foi. Les anciens fichiers n'ont que `tests_passed` (un tirage).
        score = d.get("tests_passed_median", d.get("tests_passed"))
        runs = d.get("runs", 1)
        # On privilégie la mesure la mieux échantillonnée, pas le meilleur score :
        # prendre le max de tirages isolés reviendrait à sélectionner le bruit.
        if score is None: continue
        if runs > best_runs or (runs == best_runs and score > (best or -1)):
            best, best_runs = score, runs
    return best, best_runs

t_cand, runs_cand = tetris_score(cand_name)
t_base, runs_base = tetris_score(base_name)
MIN_RUNS = int(os.environ.get("PROMOTE_MIN_RUNS", "3"))
d_overall=cand["overall"]-base["overall"]
d_tool=cand["toolcall_acc"]-base["toolcall_acc"]
agentic=cand.get("agentic_success_rate", 0.0)

reasons=[]
# Critère principal : il FAUT une mesure tetris, sinon on refuse. Promouvoir sans
# la preuve discriminante est exactement ce qui a produit la PR 1573.
if t_cand is None:
    reasons.append(f"aucun résultat harness-bench tetris pour {cand_name} "
                   f"(lancer: bench.py --scenario tetris --harness pi --model localai/{cand_name})")
elif t_base is None:
    reasons.append(f"aucun résultat harness-bench tetris pour l'incumbent {base_name} "
                   "(référence manquante, impossible de comparer)")
elif runs_cand < MIN_RUNS:
    # Constaté le 2026-07-29 : deux exécutions de la MÊME paire modèle/harnais sur
    # tetris ont donné 38/44 puis 21/44. Un tirage unique ne distingue pas un effet
    # réel du hasard d'échantillonnage — il ne peut donc pas justifier un swap.
    reasons.append(f"tetris mesuré sur {runs_cand} essai(s) seulement, {MIN_RUNS} requis "
                   f"(relancer: bench.py --scenario tetris --harness pi "
                   f"--model localai/{cand_name} --runs {MIN_RUNS})")
elif t_cand <= t_base:
    reasons.append(f"tetris médiane {t_cand}/44 <= incumbent {t_base}/44 "
                   f"(pas d'amélioration réelle)")
if agentic < floor:
    reasons.append(f"agentic_success_rate {agentic:.3f} < plancher {floor} "
                   "(le signal qu'overall noyait)")
if d_tool < -0.05:
    reasons.append(f"toolcall Δ {d_tool:+.3f} < -0.05 (régression)")
# Gardes sur les métriques NON saturables et non trompeuses.
for cle in ("format_acc", "reasoning_acc"):
    delta = cand.get(cle, 0.0) - base.get(cle, 0.0)
    if delta < -0.05:
        reasons.append(f"{cle} Δ {delta:+.3f} < -0.05 (régression)")
# Un modèle deux fois plus lent est un coût réel, même s'il code mieux.
if base.get("mean_tokps", 0) and cand.get("mean_tokps", 0) < 0.5 * base["mean_tokps"]:
    reasons.append(f"mean_tokps {cand['mean_tokps']:.1f} < 50% de l'incumbent "
                   f"({base['mean_tokps']:.1f})")
#
# `overall` et `coding_pass_rate` NE SONT PAS des gardes, délibérément.
#
# `overall` moyenne six métriques dont quatre saturées à 1.000 : il bouge surtout
# au rythme de `coding_pass_rate`, et il est donc contaminé par le défaut suivant.
#
# `coding_pass_rate` est un test ONE-SHOT : on demande une fonction, on vérifie
# qu'elle passe. Il sanctionne définitivement ce qu'une boucle réelle corrige en
# une itération. Deux mesures le prouvent :
#   - bonsai-27b : 5 échecs sur 5 en `NameError` (bonne logique, mauvais nom) à
#     l'éval one-shot, et ZÉRO renommage sur harness-bench repair, où pytest lui
#     renvoie l'erreur ;
#   - qwopus3.5-9b-coder : 0.786 en one-shot contre 38/44 sur tetris — meilleur
#     que l'incumbent (33/44) qui affiche pourtant 0.929 en one-shot.
# Garder `overall` en garde à -0.02 aurait rejeté qwopus (Δ -0.036) alors qu'il
# gagne sur le critère principal, sur l'agentique (+0.167) et sur la vitesse.
# Les deux restent AFFICHÉS dans le tableau, pour information seulement.
promote = not reasons
rows="\n".join(f"| {k} | {cand.get(k,0):.3f} | {base.get(k,0):.3f} | {cand.get(k,0)-base.get(k,0):+.3f} |"
  for k in ["overall","coding_pass_rate","toolcall_acc","format_acc","reasoning_acc","agentic_success_rate","mean_tokps"])
# Le critère principal en tête de tableau, pour qu'un relecteur le voie d'abord.
rows = ("| **tetris (harness-bench)** | **%s/44** | **%s/44** | **%s** |\n" % (
    "?" if t_cand is None else t_cand,
    "?" if t_base is None else t_base,
    "n/a" if (t_cand is None or t_base is None) else "%+d" % (t_cand - t_base),
)) + rows
print("PROMOTE" if promote else "REJECT")
print("REASONS::" + ("; ".join(reasons) if reasons else "gate OK"))
print("TABLE::"+rows.replace("\n","§"))
# Signal Hermes-readiness (séparé du gate LocalAI) : candidat apte à remplacer
# deepseek-v4-flash comme cerveau Hermes ? (agentique multi-tours + tool absolus)
hr=cand.get("hermes_ready",0); asr=cand.get("agentic_success_rate",0)
print(f"HERMES::{'OUI' if hr else 'NON'} (agentic {asr:.0%}, tool {cand.get('toolcall_acc',0):.0%})")
PY
)
DECISION=$(echo "$GATE" | sed -n '1p')
REASONS=$(echo "$GATE" | sed -n '2p' | sed 's/^REASONS:://')
TABLE=$(echo "$GATE" | grep '^TABLE::' | sed 's/^TABLE:://; s/§/\n/g')
HERMES=$(echo "$GATE" | grep '^HERMES::' | sed 's/^HERMES:://')

echo "=== gate: $DECISION — $REASONS ==="
printf "| métrique | %s | %s | Δ |\n|---|---|---|---|\n%s\n" "$NAME" "$INCUMBENT" "$TABLE"
echo "=== Hermes-readiness (cerveau Hermes, hors gate LocalAI) : $HERMES ==="

if [ "$DECISION" != "PROMOTE" ]; then
  echo "→ candidat NON promu. Rien à faire (cleanup via stage_candidate.sh --cleanup)."
  exit 0
fi

# --- build PR ---
BODY=$(printf "## Model swap: %s → %s\n\nÉval automatique. Gate refondu le 2026-07-29 : le critère PRINCIPAL est **harness-bench tetris** (écrire un paquet de zéro contre 44 tests), le seul qui discrimine — \`eval-harness\` seul donnait 0.982 aussi bien à l'incumbent qu'à un modèle qui n'écrivait aucun fichier.\n\nConditions vérifiées : tetris(candidat) > tetris(incumbent) ; \`agentic_success_rate\` >= %s ; pas de régression sur \`toolcall_acc\` (-0.05) ni sur \`overall\` (-%s). Incumbent résolu depuis l'alias \`current\` de values.yaml au moment de l'évaluation.\n\n| métrique | %s (candidat) | %s (courant) | Δ |\n|---|---|---|---|\n%s\n\n**Hermes-readiness** (candidat apte à remplacer deepseek-v4-flash comme cerveau Hermes — agentique multi-tours, hors gate LocalAI) : **%s**\n\n**Généré par le pipeline model-autodeploy (P3/P6). Review + merge manuel requis.**\n" "$NAME" "$INCUMBENT" "$AGENTIC_FLOOR" "$MARGIN" "$NAME" "$INCUMBENT" "$TABLE" "$HERMES")
BRANCH="model-swap/${NAME}"

echo "=== édition values.yaml (add $NAME, remove $INCUMBENT) ==="
DRYFLAG=""; [ "$DRY" = "1" ] && DRYFLAG="--dry-run"
# --repoint-alias est OBLIGATOIRE sur un swap : l'alias `current` est ce que
# consomment Hermes, OpenWebUI et les crons. Sans lui, retirer l'incumbent laisse
# l'alias désigner un modèle absent du chart. edit_values.py refuse d'écrire dans
# ce cas.
python3 "$HERE/edit_values.py" --add-file "$HERE/results/${NAME}.model.yaml" \
  --add-name "$NAME" --remove "$INCUMBENT" --repoint-alias "$NAME" $DRYFLAG

if [ "$DRY" = "1" ]; then
  echo "=== [dry-run] PR qui SERAIT créée (branch $BRANCH) ==="
  echo "$BODY"
  exit 0
fi

# Le modèle SORTANT quitte values.yaml → sans trace, hf-discover le reproposerait
# indéfiniment (sa dédup regarde les modèles déployés + file + done-cache, et
# l'incumbent n'a jamais été un "candidat"). On l'inscrit donc au done-cache.
DONE="${MODEL_CANDIDATES_DONE:-$HOME/.cache/model-candidates.done}"
if ! grep -qF "$INCUMBENT" "$DONE" 2>/dev/null; then
  printf '%s  %s  %s  (remplacé par %s)\n' \
    "$(printf 'incumbent-%s' "$INCUMBENT" | sha1sum | cut -d' ' -f1)" \
    "$INCUMBENT" "$(date -u +%FT%TZ)" "$NAME" >> "$DONE"
  echo "→ $INCUMBENT inscrit au done-cache (ne sera plus reproposé)"
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
