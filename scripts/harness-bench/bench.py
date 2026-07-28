#!/usr/bin/env python3
"""Banc de montee en charge pour harnais de codage agentique.

Meme fixture, meme prompt, meme verification pour tous les harnais et tous les
modeles. Le verdict ne regarde QUE l'etat du disque apres coup : il est donc
valable pour un harnais a outils (pi) comme pour un harnais a diff (aider).

  bench.py --harness pi --model localai/qwen3-coder-30b-a3b-instruct
  bench.py --harness pi --model localai/bonsai-27b
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
FIXTURE = HERE / "fixture"
PROMPT = (HERE / "PROMPT.txt").read_text()
RESULTS = HERE / "results"
PYTEST = os.environ.get("BENCH_PYTEST", "/usr/bin/pytest")
EXPECTED_TESTS = 19
# Fichiers que l'agent n'a pas le droit de toucher.
PROTECTED = ("tests/test_taskmgr.py", "conftest.py")


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
    """Retourne (passed, failed, sortie_courte)."""
    proc = subprocess.run(
        [PYTEST, "-q"], cwd=workdir, capture_output=True, text=True, timeout=180
    )
    tail = proc.stdout.strip().splitlines()[-1:] or [""]
    passed = failed = 0
    match = re.search(r"(\d+) passed", proc.stdout)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", proc.stdout)
    if match:
        failed = int(match.group(1))
    return passed, failed, tail[0]


def verify(workdir):
    """Verdict objectif : tests verts, gardes respectees, API intacte."""
    passed, failed, tail = run_pytest(workdir)

    violations = []
    for rel in PROTECTED:
        before = (FIXTURE / rel).read_bytes()
        after_path = workdir / rel
        if not after_path.exists():
            violations.append("%s supprime" % rel)
        elif after_path.read_bytes() != before:
            violations.append("%s modifie" % rel)

    before_api = api_signatures(FIXTURE)
    after_api = api_signatures(workdir)
    api_diff = []
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
        origin = FIXTURE / rel
        if not origin.exists() or origin.read_bytes() != path.read_bytes():
            modified.append(rel)

    return {
        "verdict": (
            "PASS"
            if passed == EXPECTED_TESTS and not failed and not violations and not api_diff
            else "FAIL"
        ),
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_attendus": EXPECTED_TESTS,
        "pytest_tail": tail,
        "gardes_violees": violations,
        "api_modifiee": api_diff,
        "fichiers_modifies": modified,
    }


# --- adaptateurs de harnais ----------------------------------------------


def pi_command(model, workdir):
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
        PROMPT,
    ]


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
            for block in event["message"].get("content") or []:
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


def aider_command(model, workdir):
    # aider n'utilise pas de schemas d'outils : il edite par diff. Le prompt et la
    # verification sont identiques, seule l'invocation change.
    return [
        "aider",
        "--model",
        model,
        "--yes",
        "--no-auto-commits",
        "--no-git",
        "--map-tokens",
        "0",
        "--message",
        PROMPT,
    ]


def no_metrics(transcript):
    """Repli : verdict objectif seulement, pas de comptage de tokens."""
    return {"tours": None, "appels_outils": None, "format_appels": "non instrumente"}


HARNESSES = {
    "pi": (pi_command, pi_metrics),
    "aider": (aider_command, no_metrics),
}


# --- orchestration -------------------------------------------------------


def run(harness, model, timeout):
    if harness not in HARNESSES:
        sys.exit("harnais inconnu: %s (connus: %s)" % (harness, ", ".join(HARNESSES)))
    build_command, parse_metrics = HARNESSES[harness]

    slug = "%s-%s" % (harness, re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-"))
    workdir = Path("/tmp") / ("harness-bench-" + slug)
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FIXTURE, workdir)
    for cache in workdir.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    before = run_pytest(workdir)
    print("depart : %s passed, %s failed" % (before[0], before[1]), flush=True)

    started = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            build_command(model, workdir),
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        transcript = proc.stdout + proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        transcript = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(transcript, bytes):
            transcript = transcript.decode("utf-8", "replace")
        returncode = -1
        timed_out = True
    elapsed = round(time.time() - started, 1)

    result = {
        "harnais": harness,
        "modele": model,
        "duree_s": elapsed,
        "timeout": timed_out,
        "returncode": returncode,
        "depart": {"passed": before[0], "failed": before[1]},
    }
    result.update(parse_metrics(transcript))
    result.update(verify(workdir))

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
    parser.add_argument("--model", required=False)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--list-harnesses", action="store_true")
    args = parser.parse_args()
    if args.list_harnesses:
        print("\n".join(sorted(HARNESSES)))
        return 0
    if not args.model:
        parser.error("--model requis")
    return run(args.harness, args.model, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
