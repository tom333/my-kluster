#!/usr/bin/env python3
"""Banc de montee en charge pour harnais de codage agentique.

Meme fixture, meme prompt, meme verification pour tous les harnais et tous les
modeles. Le verdict ne regarde QUE l'etat du disque apres coup : il est donc
valable pour un harnais a outils (pi) comme pour un harnais a diff (aider).

  bench.py --scenario repair --harness pi --model localai/qwen3-coder-30b-a3b-instruct
  bench.py --scenario tetris --harness pi --model localai/bonsai-27b
  bench.py --list-harnesses

Resultat : results/<harness>-<modele>-<horodatage>.json
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
PYTEST = os.environ.get("BENCH_PYTEST", "/usr/bin/pytest")

# Deux scenarios de difficulte tres differente.
#
# `repair` : 7 defauts semes dans 5 modules existants, chacun une inversion d'UN
#   token. Les noms de tests designent le bug. Mesure la MECANIQUE de la boucle
#   (lire, editer, lancer, iterer), pas la capacite de codage : il ne separe pas un
#   quant ternaire d'un MoE IQ1_S, les deux font 19/19.
#
# `tetris` : le paquet n'existe pas, il faut l'ecrire depuis le contrat. Demande de
#   la CONCEPTION (representation, rotation de matrice, degagement, gravite,
#   scoring) tout en gardant un oracle parfait, car le coeur est deterministe et
#   sans horloge. `check_api` est faux : tout est nouveau, comparer les signatures
#   a un dossier vide n'aurait aucun sens.
SCENARIOS = {
    "repair": {
        "fixture": HERE / "fixture",
        "prompt": HERE / "PROMPT.txt",
        "expected_tests": 19,
        "protected": ("tests/test_taskmgr.py", "conftest.py"),
        "check_api": True,
    },
    "tetris": {
        "fixture": HERE / "fixture-tetris",
        "prompt": HERE / "PROMPT-tetris.txt",
        "expected_tests": 44,
        "protected": ("tests/test_tetris.py", "conftest.py"),
        "check_api": False,
    },
}


# --- verification, independante du harnais -------------------------------


def api_signatures(root):
    """Empreinte des signatures publiques de taskmgr/ : {chemin: [signatures]}.

    Sert a detecter un renommage. C'est le point ou un quant tres bas derape en
    premier : il reecrit la bonne logique sous un autre nom.
    """
    out = {}
    for path in sorted((root / "taskmgr").glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            out[path.name] = ["SYNTAX_ERROR: %s" % exc]
            continue
        sigs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sigs.append("def %s(%s)" % (node.name, ",".join(args)))
            elif isinstance(node, ast.ClassDef):
                sigs.append("class %s" % node.name)
        out[path.name] = sorted(sigs)
    return out


def run_pytest(workdir):
    """Retourne (passed, failed, sortie_courte).

    Le depassement de delai est un RESULTAT, pas un plantage du banc : du code
    genere qui boucle a l'infini fait pendre pytest, et c'est un mode de
    defaillance attendu. On le rapporte au lieu de laisser l'exception remonter.
    """
    try:
        proc = subprocess.run(
            [PYTEST, "-q"], cwd=workdir, capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired:
        return 0, 0, "TIMEOUT pytest apres 180s (boucle infinie dans le code genere)"
    tail = proc.stdout.strip().splitlines()[-1:] or [""]
    passed = failed = 0
    match = re.search(r"(\d+) passed", proc.stdout)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", proc.stdout)
    if match:
        failed = int(match.group(1))
    return passed, failed, tail[0]


def verify(workdir, scenario):
    """Verdict objectif : tests verts, gardes respectees, API intacte."""
    fixture = scenario["fixture"]
    expected = scenario["expected_tests"]
    passed, failed, tail = run_pytest(workdir)

    violations = []
    for rel in scenario["protected"]:
        before = (fixture / rel).read_bytes()
        after_path = workdir / rel
        if not after_path.exists():
            violations.append("%s supprime" % rel)
        elif after_path.read_bytes() != before:
            violations.append("%s modifie" % rel)

    api_diff = []
    if scenario["check_api"]:
        before_api = api_signatures(fixture)
        after_api = api_signatures(workdir)
        for name in sorted(set(before_api) | set(after_api)):
            if before_api.get(name) != after_api.get(name):
                api_diff.append(
                    {
                        "fichier": name,
                        "avant": before_api.get(name),
                        "apres": after_api.get(name),
                    }
                )

    modified = []
    for path in sorted(workdir.rglob("*.py")):
        rel = path.relative_to(workdir).as_posix()
        origin = fixture / rel
        if not origin.exists() or origin.read_bytes() != path.read_bytes():
            modified.append(rel)

    return {
        "verdict": (
            "PASS"
            if passed == expected and not failed and not violations and not api_diff
            else "FAIL"
        ),
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_attendus": expected,
        "pytest_tail": tail,
        "gardes_violees": violations,
        "api_modifiee": api_diff,
        "fichiers_modifies": modified,
    }


# --- adaptateurs de harnais ----------------------------------------------


def pi_command(model, workdir, prompt):
    """Retourne (argv, variables d'environnement a ajouter)."""
    return [
        "pi",
        "--model",
        model,
        "--mode",
        "json",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-context-files",
        "-p",
        prompt,
    ], {}


def pi_metrics(transcript):
    """Extrait tours, appels d'outils, format et tokens du JSONL de pi."""
    turns = 0
    calls = []
    peak_input = 0
    total_in = total_out = 0
    xml_leak = False
    for line in transcript.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn_end":
            turns += 1
            usage = event["message"].get("usage") or {}
            peak_input = max(peak_input, usage.get("input") or 0)
            total_in += usage.get("input") or 0
            total_out += usage.get("output") or 0
        if event.get("type") == "message_end":
            content = event.get("message", {}).get("content") or []
            # `content` peut etre une chaine, ou une liste melangeant chaines et
            # blocs typés selon le harnais. little-coder produit la forme mixte,
            # pi non.
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for block in content:
                if isinstance(block, str):
                    block = {"type": "text", "text": block}
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "toolCall":
                    calls.append(block.get("name"))
                # Un appel d'outil rendu en XML dans du texte = bascule du modele.
                if block.get("type") == "text" and re.search(
                    r"<function=|<parameter=", block.get("text") or ""
                ):
                    xml_leak = True
    return {
        "tours": turns,
        "appels_outils": len(calls),
        "outils_utilises": sorted(set(c for c in calls if c)),
        "format_appels": "xml" if xml_leak else ("json" if calls else "aucun"),
        "pic_input": peak_input,
        "total_input": total_in,
        "total_output": total_out,
    }


def little_coder_command(model, workdir, prompt):
    """little-coder = pi + ~30 extensions + ~30 skills, pi etant une simple
    dependance npm. Meme CLI, meme format JSONL, donc `pi_metrics` s'applique.

    On NE passe PAS --no-extensions ni --no-skills : ce sont precisement les
    couches que little-coder ajoute, et les desactiver le reduirait a pi. Seul
    --no-context-files est conserve, comme pour pi, pour ne pas faire dependre le
    resultat d'un AGENTS.md du dossier.
    """
    # little-coder ajoute une extension permission-gate : en mode `auto`, bash est
    # restreint a une liste blanche de prefixes (SAFE_PREFIXES) qui NE CONTIENT PAS
    # `pytest`. Le premier appel du modele est donc rejete par
    #   shell whitelist: "pytest" is not in SAFE_PREFIXES
    # et l'agent perd la boucle de retroaction par les tests — precisement le
    # mecanisme qui fait reussir bonsai. pi n'a aucune liste blanche, donc on leve
    # celle-ci pour comparer a armes egales. C'est l'echappatoire documentee du
    # projet, et c'est un CHOIX DE BANC, pas un defaut de little-coder : sa posture
    # par defaut est plus prudente que celle de pi.
    return [
        "little-coder",
        "--model",
        model,
        "--mode",
        "json",
        "--no-session",
        "--no-context-files",
        "-p",
        prompt,
    ], {"LITTLE_CODER_PERMISSION_MODE": "accept-all"}


def aider_command(model, workdir, prompt):
    """aider n'expose aucun schema d'outil : il edite par diff textuel.

    Le prompt et la verification sont identiques a pi ; seule l'invocation change.
    Trois specificites :
      - aider passe par litellm, donc un endpoint OpenAI-compatible se declare via
        le prefixe `openai/` plus OPENAI_API_BASE / OPENAI_API_KEY ;
      - il ne connait pas la fenetre de nos modeles locaux : sans
        `.aider.model.metadata.json` il applique un defaut et le banc mesurerait une
        troncature au lieu du harnais. On ecrit donc 32768, comme le contextWindow
        donne a pi ;
      - `--map-tokens 0` coupe le repo-map (1024 tokens par defaut), pour comparer
        des preambules et non des strategies de contexte.
    """
    model_id = model.split("/", 1)[-1]
    litellm_name = "openai/" + model_id
    (workdir / ".aider.model.metadata.json").write_text(
        json.dumps(
            {
                litellm_name: {
                    "max_input_tokens": 32768,
                    "max_output_tokens": 4096,
                    "input_cost_per_token": 0,
                    "output_cost_per_token": 0,
                    "litellm_provider": "openai",
                    "mode": "chat",
                }
            },
            indent=2,
        )
        + "\n"
    )
    key_file = Path.home() / ".config" / "brain" / "localai-key"
    env = {
        "OPENAI_API_BASE": "https://localai.tgu.ovh/v1",
        "OPENAI_API_KEY": key_file.read_text().strip(),
        "AIDER_ANALYTICS": "false",
    }
    argv = [
        "aider",
        "--model",
        litellm_name,
        "--yes-always",
        "--no-auto-commits",
        "--no-git",
        "--no-check-update",
        "--no-show-model-warnings",
        "--no-auto-lint",
        "--map-tokens",
        "0",
        # Boucle agentique d'aider : il relance les tests apres chaque edition et
        # itere sur les echecs. Sans ca, `--message` est un echange unique.
        "--auto-test",
        "--test-cmd",
        PYTEST + " -q",
    ]
    # aider n'explore pas : il edite ce qu'on met dans le chat. Les 5 modules sont
    # donc passes en editables et la suite de tests en lecture seule.
    #
    # ATTENTION, ceci n'est PAS la meme difficulte que pour pi : pi a du DECOUVRIR
    # les fichiers lui-meme (bash, read). Ici la localisation est offerte. C'est
    # l'usage idiomatique d'aider, pas une triche, mais les deux colonnes ne sont
    # pas comparables sur le nombre de tours.
    for path in sorted((workdir / "taskmgr").glob("*.py")):
        argv += ["--file", "taskmgr/" + path.name]
    argv += ["--read", "tests/test_taskmgr.py"]
    argv += ["--message", prompt]
    return argv, env


def aider_metrics(transcript):
    """aider imprime 'Tokens: 12k sent, 456 received.' par echange."""
    sent = re.findall(r"Tokens:\s*([\d.]+)\s*([km]?)\s*sent", transcript, re.I)
    received = re.findall(r"([\d.]+)\s*([km]?)\s*received", transcript, re.I)

    def scale(value, unit):
        factor = {"k": 1000, "m": 1000000}.get(unit.lower(), 1)
        return int(float(value) * factor)

    sent_values = [scale(v, u) for v, u in sent]
    received_values = [scale(v, u) for v, u in received]
    return {
        "tours": len(sent_values) or None,
        "appels_outils": None,  # aider edite par diff, il n'y a pas d'appel d'outil
        "format_appels": "diff (aucun schema d'outil)",
        "pic_input": max(sent_values) if sent_values else None,
        "total_input": sum(sent_values) or None,
        "total_output": sum(received_values) or None,
    }


def no_metrics(transcript):
    """Repli : verdict objectif seulement, pas de comptage de tokens."""
    return {"tours": None, "appels_outils": None, "format_appels": "non instrumente"}


HARNESSES = {
    "pi": (pi_command, pi_metrics),
    "little-coder": (little_coder_command, pi_metrics),
    "aider": (aider_command, aider_metrics),
}


# --- orchestration -------------------------------------------------------


def run(harness, model, scenario_name, timeout):
    scenario = SCENARIOS[scenario_name]
    prompt = scenario["prompt"].read_text()
    fixture = scenario["fixture"]
    if harness not in HARNESSES:
        sys.exit("harnais inconnu: %s (connus: %s)" % (harness, ", ".join(HARNESSES)))
    build_command, parse_metrics = HARNESSES[harness]

    slug = "%s-%s-%s" % (
        scenario_name,
        harness,
        re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-"),
    )
    workdir = Path("/tmp") / ("harness-bench-" + slug)
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(fixture, workdir)
    for cache in workdir.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    before = run_pytest(workdir)
    print("depart : %s passed, %s failed" % (before[0], before[1]), flush=True)

    argv, env_extra = build_command(model, workdir, prompt)
    env = dict(os.environ)
    env.update(env_extra)

    started = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            argv,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        transcript = proc.stdout + proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        # Malgre text=True, TimeoutExpired peut porter du bytes sur un flux et du
        # str sur l'autre : on decode chaque morceau AVANT de concatener, sinon on
        # perd le transcript sur un TypeError et le timeout devient invisible.
        def _texte(flux):
            if flux is None:
                return ""
            return flux.decode("utf-8", "replace") if isinstance(flux, bytes) else flux

        transcript = _texte(exc.stdout) + _texte(exc.stderr)
        returncode = -1
        timed_out = True
    elapsed = round(time.time() - started, 1)

    result = {
        "scenario": scenario_name,
        "harnais": harness,
        "modele": model,
        "duree_s": elapsed,
        "timeout": timed_out,
        "returncode": returncode,
        "depart": {"passed": before[0], "failed": before[1]},
    }
    result.update(parse_metrics(transcript))
    result.update(verify(workdir, scenario))

    RESULTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / ("%s-%s.json" % (slug, stamp))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (RESULTS / ("%s-%s.transcript" % (slug, stamp))).write_text(transcript)

    print(json.dumps({k: v for k, v in result.items() if k != "api_modifiee"},
                     indent=2, ensure_ascii=False))
    print("\n-> %s" % out)
    print("-> workdir conserve : %s" % workdir)
    return 0 if result["verdict"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", default="pi")
    parser.add_argument("--scenario", default="repair", choices=sorted(SCENARIOS))
    parser.add_argument("--model", required=False)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--list-harnesses", action="store_true")
    args = parser.parse_args()
    if args.list_harnesses:
        print("\n".join(sorted(HARNESSES)))
        return 0
    if not args.model:
        parser.error("--model requis")
    return run(args.harness, args.model, args.scenario, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
