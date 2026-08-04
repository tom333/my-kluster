"""Lance nanocoder sur la fixture `columns` et le note avec le scoreur DU BANC.

Pourquoi ce script existe. La question posee est : le plafond mesure vient-il du
MODELE ou du HARNAIS ? Un tiers doit donc tourner sur le MEME serveur, la MEME
fixture, le MEME enonce, et etre note par le MEME oracle.

nanocoder est le bon candidat : c'est une boucle agentique a outils, donc elle
EXPLORE, comme `nu`. aider ne convient pas ici — il n'explore pas, il edite ce
qu'on lui met dans le chat, et sur une fixture vierge il faudrait lui donner
l'architecture en `--file`, ce qui biaiserait la comparaison (le banc le dit deja
pour `repair` : « la localisation est offerte »).

Egalite des conditions, explicite :
  - meme llama-server (127.0.0.1:8080), donc meme modele et meme drafter MTP ;
  - `contextWindow` = 49152, la fenetre de `nu` ;
  - timeouts desactives : une generation locale depasse les 120 s par defaut, et
    un timeout client mesurerait notre reseau, pas le harnais ;
  - `--mode auto-accept` (defaut du mode `run`) : pas de garde-fou interactif.

Ce que la comparaison ne dira PAS : nanocoder a un preambule, des skills et une
auto-compaction ; `nu` a zero preambule. On compare deux INSTALLATIONS, pas deux
boucles a preambule egal.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import bench

MODELE = "gemma-4-12b-qat-mtp"
FENETRE = 49152
BASE_URL = "http://127.0.0.1:8080/v1"

FOURNISSEURS = {
    "nanocoder": {
        "providers": [
            {
                "name": "llama-cpp",
                "baseUrl": BASE_URL,
                "models": [MODELE],
                "contextWindow": FENETRE,
                "requestTimeout": -1,
                "socketTimeout": -1,
            }
        ]
    }
}


def un_essai(numero, timeout):
    scenario = bench.SCENARIOS["columns"]
    workdir = Path("/tmp/nanocoder-columns-%d-%d" % (os.getpid(), numero))
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(scenario["fixture"], workdir)
    prompt = Path(scenario["prompt"]).read_text(encoding="utf-8")

    env = dict(os.environ, NANOCODER_PROVIDERS=json.dumps(FOURNISSEURS))
    argv = [
        "nanocoder",
        "--provider",
        "llama-cpp",
        "--model",
        MODELE,
        "--context-max",
        str(FENETRE),
        # `--json` sort en code 2 des le premier tour (mesure du 2026-08-04) ;
        # `--plain` seul tourne. Le score vient de pytest, pas de sa sortie.
        "--plain",
        "--trust-directory",
        # Mesure du 2026-08-04 : malgre la doc (« defaults to auto-accept for run
        # mode »), `execute_bash` reste bloque sur une demande d'autorisation et le
        # process sort en code 2 apres 17 s. `yolo` retire la garde, comme `nu` qui
        # n'en a aucune — sinon on comparerait un harnais bride a un harnais libre.
        "--mode",
        "yolo",
        "run",
        prompt,
    ]
    debut = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        sortie, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exp:
        sortie = (exp.stdout or "") + (exp.stderr or "")
        if isinstance(sortie, bytes):
            sortie = sortie.decode("utf-8", "replace")
        code = "timeout"
    duree = time.time() - debut

    passed, failed, court, issue = bench.run_pytest(
        workdir, cibles=scenario["protected"]
    )
    return {
        "essai": numero,
        "passed": passed,
        "failed": failed,
        "attendus": scenario["expected_tests"],
        "issue": issue,
        "duree_s": round(duree, 1),
        "returncode": code,
        "workdir": str(workdir),
        "sortie_queue": sortie[-2000:],
        "pytest_court": court,
    }


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
    resultats = []
    for numero in range(1, runs + 1):
        print("=== essai %d/%d ===" % (numero, runs), flush=True)
        r = un_essai(numero, timeout)
        resultats.append(r)
        print(
            "  %d/%d tests  %.0fs  issue=%s  code=%s"
            % (r["passed"], r["attendus"], r["duree_s"], r["issue"], r["returncode"]),
            flush=True,
        )
    scores = sorted(r["passed"] for r in resultats)
    print("\n=== agrégat nanocoder / columns / %s ===" % MODELE)
    print("  scores   : %s" % scores)
    print("  médiane  : %d/%d" % (scores[len(scores) // 2], resultats[0]["attendus"]))
    print("  durées   : %s" % [r["duree_s"] for r in resultats])
    Path("results").mkdir(exist_ok=True)
    cible = Path("results/nanocoder-columns-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    cible.write_text(json.dumps(resultats, indent=2, ensure_ascii=False))
    print("-> %s" % cible)


if __name__ == "__main__":
    main()
