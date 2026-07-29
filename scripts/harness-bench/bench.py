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
import signal
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


def _tuer_groupe(proc):
    """Tue tout le groupe de processus (SIGTERM puis SIGKILL), pas juste l'enfant.

    Indispensable : un timeout qui ne tue que l'enfant direct laisse les
    petits-fils (bash -> pytest boucle infinie) tourner a 100% CPU en orphelins.
    """
    try:
        gid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(gid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


# Classes d'issue d'un essai. Introduites le 2026-07-29 apres avoir compris que le
# score seul MENT : les 44 tests importent tous le paquet, donc UNE erreur de syntaxe
# fait echouer la collecte, donc les 44 tests, donc 0/44. Exemple mesure : un essai a
# 0/44 avait ecrit 197 lignes et echouait sur `IndentationError: expected an indented
# block after 'if' statement on line 156`. Un caractere. Moyenner ce 0 avec un 41/44
# obtenu sur du code qui compile ne mesure pas le modele, ca mesure la probabilite
# d'une coquille — et sur 3 essais, la mediane est decidee par ce tirage.
ISSUE_OK = "collecte_ok"           # les tests ont tourne : le score veut dire quelque chose
ISSUE_COLLECTE = "erreur_collecte"  # SyntaxError / IndentationError / ModuleNotFoundError
ISSUE_PEND = "pytest_pend"          # boucle infinie : pytest ne rend jamais la main


def run_pytest(workdir):
    """Retourne (passed, failed, sortie_courte, issue).

    Le depassement de delai est un RESULTAT, pas un plantage du banc : du code
    genere qui boucle a l'infini fait pendre pytest, et c'est un mode de
    defaillance attendu. On le rapporte au lieu de laisser l'exception remonter.

    `issue` distingue les trois classes ci-dessus. Sans elle, le banc ne peut pas
    comparer deux reglages voisins : les 0/44 de collecte noient le signal.
    """
    # start_new_session + killpg : pytest peut avoir spawn des sous-process ;
    # sans groupe, le timeout les laisserait orphelins (cf. _tuer_groupe).
    proc = subprocess.Popen(
        [PYTEST, "-q"], cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        _tuer_groupe(proc)
        proc.communicate()
        return 0, 0, "TIMEOUT pytest apres 180s (boucle infinie dans le code genere)", ISSUE_PEND
    stdout = stdout or ""
    tail = stdout.strip().splitlines()[-1:] or [""]
    passed = failed = 0
    match = re.search(r"(\d+) passed", stdout)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", stdout)
    if match:
        failed = int(match.group(1))
    # "error during collection" = le paquet ne s'importe meme pas. pytest le dit
    # explicitement, on ne devine pas.
    collecte_ratee = ("error during collection" in stdout
                      or "errors during collection" in stdout)
    issue = ISSUE_COLLECTE if collecte_ratee else ISSUE_OK
    return passed, failed, tail[0], issue


def verify(workdir, scenario):
    """Verdict objectif : tests verts, gardes respectees, API intacte."""
    fixture = scenario["fixture"]
    expected = scenario["expected_tests"]
    passed, failed, tail, issue = run_pytest(workdir)

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
        "issue": issue,
        # Preuve qu'un "0/44" de collecte n'est pas une page blanche : on compte ce
        # qui a ete ecrit. 197 lignes + IndentationError != 0 ligne.
        "lignes_ecrites": sum(
            len(p.read_text(errors="replace").splitlines())
            for p in sorted(workdir.rglob("*.py"))
            if p.name != "conftest.py" and "tests/" not in p.relative_to(workdir).as_posix()
        ),
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


# Instruction testée le 2026-07-29. Motif : sur tetris, 2 des 3 appels `read` de
# qwopus3.5-9b-coder échouaient en ENOENT parce qu'il passait `tmp/...` au lieu de
# `/tmp/...` — le chemin, résolu depuis le cwd, se dédoublait. Le modèle connaît
# pourtant le chemin absolu, il l'utilise correctement dans `bash`. Il perdait ainsi
# 2 tours sur 9, puis contournait avec `cat`, ce qui remplaçait une lecture
# structurée par 5 Ko de sortie shell.
INSTRUCTION_CHEMINS_ABSOLUS = (
    "Pour les outils read, write et edit, utilise TOUJOURS un chemin ABSOLU "
    "commencant par une barre oblique. Un chemin relatif est resolu depuis le "
    "repertoire courant et echoue."
)


def pi_abspath_command(model, workdir, prompt):
    """pi + une instruction sur les chemins absolus. Variante d'A/B : tout le reste
    est identique à `pi`, seul ce ~30 tokens de préambule change.

    VERDICT 2026-07-29, 3 essais par côté : NON adopté, et l'hypothèse qui l'a
    motivé était fausse. Ce qui échouait n'était pas un chemin relatif — `pi` les
    résout correctement depuis son cwd (gemma-4-12b lit `tests/test_tetris.py` en
    relatif sans erreur). C'était un chemin absolu amputé de sa barre oblique de
    tête : qwopus émet `tmp/...` au lieu de `/tmp/...`, le chemin se dédouble et
    donne un ENOENT sur `<cwd>/tmp/<cwd sans slash>/...`. Un défaut d'émission sur
    un token, que cette instruction ne pouvait pas corriger.

    Effet mesuré nul et non concluant (médiane 20/44 contre 0/44, étendues 11-25 et
    0-25). Effet de bord réel : l'instruction nomme `edit`, et ça suffit à faire
    utiliser `edit` — jamais employé sans elle. Ses échecs (`No changes made […]
    replacement produced identical content`) sont une défaillance NOUVELLE, et le
    pic d'entrée médian passe de 15 850 à 28 754. Détail dans le README.
    """
    argv, env = pi_command(model, workdir, prompt)
    # Inséré avant `-p` pour ne pas casser l'ordre attendu par pi.
    i = argv.index("-p")
    return argv[:i] + ["--append-system-prompt", INSTRUCTION_CHEMINS_ABSOLUS] + argv[i:], env


# Instruction testée le 2026-07-29. Motif : gemma-4-12b-coder est le modèle qui a le
# mieux compris le contrat tetris — son code, extrait du transcript et noté hors ligne,
# fait 17/44 sans qu'il ait jamais lancé un test, contre 20/44 à qwopus après 12 tours
# d'itération. Mais il ne l'écrit jamais sur le disque : il l'affiche dans son message
# et s'arrête (2 tours, un seul `read`). PROMPT-tetris.txt dit déjà « Lance pytest -q »
# et « Tu as termine quand pytest -q affiche 44 passed » ; il l'ignore. L'hypothèse est
# qu'il croit répondre à un humain qui lira le code. On ne nomme QUE write et bash :
# l'A/B des chemins absolus a montré que nommer un outil suffit à le faire employer.
INSTRUCTION_AGIR = (
    "Ta reponse texte n'est lue par personne : un script automatique constate "
    "seulement l'etat du disque. Le code affiche dans un message n'existe pas. "
    "Cree chaque fichier avec l'outil write, puis lance pytest -q avec bash. "
    "N'arrete pas ton tour avant d'avoir fait les deux."
)


def pi_act_command(model, workdir, prompt):
    """pi + une instruction qui dit que la sortie texte n'est pas lue. Variante d'A/B :
    tout le reste est identique à `pi`, seul ce ~55 tokens de préambule change.

    VERDICT 2026-07-29 : NON adopté. La référence à n=3 confirme le défaut (0/44 trois
    fois, `write` 0, `bash` 0, 9 `read`) ; le nudge ne le corrige pas et en crée un
    autre. Sur 2 essais mesurés : 0/44 en 1 tour, puis 0/44 en **267 tours** jusqu'au
    timeout de 900 s. La dernière phrase — « N'arrete pas ton tour avant d'avoir fait
    les deux » — retire la condition d'arrêt sans donner la capacité d'agir. Troisième
    essai interrompu : la médiane de [0, 0, x] vaut 0 quel que soit x.

    Même faute que INSTRUCTION_CHEMINS_ABSOLUS : une instruction ajoutée pour corriger un
    comportement en fabrique un pire. Garder les deux comme témoins de ce piège.

    Ce que gemma-4-12b-coder fait à la place, `stopReason: stop`, 0 appel d'outil :
    soit il annonce le plan et s'arrête (« I will first read […], then implement […],
    and finally run pytest -q »), soit il déverse 5 246 caractères de code dans son
    message. Détail et A/B de la grammaire LocalAI dans le README.
    """
    argv, env = pi_command(model, workdir, prompt)
    i = argv.index("-p")
    return argv[:i] + ["--append-system-prompt", INSTRUCTION_AGIR] + argv[i:], env


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


HARNAIS_NU = Path("/data/projets/perso/harnais-nu")


def nu_command(model, workdir, prompt):
    """Harnais témoin à préambule ZÉRO (repo harnais-nu) : aucun message system,
    seulement les schémas de ses 4 outils. Plancher du banc — les autres harnais
    se lisent en écart par rapport à lui.

    Le serveur est un llama-server local (podman, cf. harnais-nu/serveur.md), PAS
    LocalAI : `model` ne sert qu'à remplir le champ de la requête. Base URL
    surchargée par HARNAIS_NU_BASE_URL. Les budgets du harnais sont en tours et
    en tokens ; le --timeout du banc reste un garde-fou externe, pas la limite
    de comparaison.

    Les trois budgets sont surchargeables par l'environnement pour balayer sans
    toucher au code — indispensable depuis la mesure du 2026-07-29 : à 4096 tokens
    par tour, gemma-4-12b dépense TOUT son plafond dans son canal de pensée et
    n'atteint jamais l'action (3/3 essais à 0/44, 2 tours, 0 ligne écrite).

        HARNAIS_NU_MAX_TURNS, HARNAIS_NU_MAX_TOKENS_PER_TURN, HARNAIS_NU_MAX_TOTAL_TOKENS
    """
    base_url = os.environ.get("HARNAIS_NU_BASE_URL", "http://127.0.0.1:8080/v1")
    return [
        "uv", "run", "--project", str(HARNAIS_NU),
        str(HARNAIS_NU / "boucle.py"),
        "--task", prompt,
        "--workdir", str(workdir),
        "--base-url", base_url,
        "--model", model.split("/", 1)[-1],
        "--max-turns", os.environ.get("HARNAIS_NU_MAX_TURNS", "30"),
        "--max-tokens-per-turn", os.environ.get("HARNAIS_NU_MAX_TOKENS_PER_TURN", "4096"),
        "--max-total-tokens", os.environ.get("HARNAIS_NU_MAX_TOTAL_TOKENS", "100000"),
    ], {}


def nu_metrics(transcript):
    """boucle.py imprime ses métriques en une ligne JSON sur stdout, et RIEN d'autre.

    Position dans le transcript : en tête, pas en queue — `run_once` concatene
    stdout PUIS stderr, et tout le journal de la boucle est sur stderr. Le
    balayage à l'envers traverse donc les lignes de log (aucune ne commence par
    `{`) avant d'atteindre la ligne de métriques.

    `appels_outils` est ici un dict {outil: compte} là où pi/little-coder rendent
    un entier : ne pas agréger cette clé entre harnais sans normaliser.
    """
    for line in reversed(transcript.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and '"turns"' in line):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {
            "tours": m.get("turns"),
            "appels_outils": m.get("tool_calls"),
            "format_appels": m.get("call_format"),
            "pic_input": m.get("peak_input_tokens"),
            "total_input": m.get("total_input_tokens"),
            "total_output": m.get("output_tokens_total"),
            "stop_reason": m.get("stop_reason"),
            # `stop_reason: error` + ce message = panne HTTP (contexte dépassé, 500,
            # backend évincé), PAS une contre-performance du modèle. Sans les lire on
            # noterait une panne d'instrument comme un score.
            "erreur": m.get("erreur"),
        }
    return no_metrics(transcript)


def no_metrics(transcript):
    """Repli : verdict objectif seulement, pas de comptage de tokens."""
    return {"tours": None, "appels_outils": None, "format_appels": "non instrumente"}


HARNESSES = {
    "pi": (pi_command, pi_metrics),
    "pi-abspath": (pi_abspath_command, pi_metrics),
    "pi-act": (pi_act_command, pi_metrics),
    "little-coder": (little_coder_command, pi_metrics),
    "aider": (aider_command, aider_metrics),
    "nu": (nu_command, nu_metrics),
}


# --- orchestration -------------------------------------------------------


def slug_de(scenario_name, harness, model):
    return "%s-%s-%s" % (
        scenario_name,
        harness,
        re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-"),
    )


def run_once(harness, model, scenario_name, timeout, essai=1, total=1):
    """Une seule exécution. Retourne (resultat, transcript), n'écrit rien."""
    scenario = SCENARIOS[scenario_name]
    prompt = scenario["prompt"].read_text()
    fixture = scenario["fixture"]
    build_command, parse_metrics = HARNESSES[harness]

    slug = slug_de(scenario_name, harness, model)
    # Un workdir par essai : chaque exécution part d'une copie fraîche, sinon le
    # second essai hériterait du code produit par le premier.
    suffixe = "" if total == 1 else "-r%d" % essai
    workdir = Path("/tmp") / ("harness-bench-" + slug + suffixe)
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

    # Malgre text=True, TimeoutExpired peut porter du bytes sur un flux et du
    # str sur l'autre : on decode chaque morceau AVANT de concatener, sinon on
    # perd le transcript sur un TypeError et le timeout devient invisible.
    def _texte(flux):
        if flux is None:
            return ""
        return flux.decode("utf-8", "replace") if isinstance(flux, bytes) else flux

    # start_new_session : le harnais devient chef d'un groupe de processus. Sans
    # ca, un timeout ne tue que le harnais lui-meme et les PETITS-FILS survivent
    # (l'agent teste lance `bash -c "... && pytest -q"` ; du code genere qui boucle
    # a l'infini laisse alors un pytest orphelin a 100% CPU, indefiniment).
    proc = subprocess.Popen(
        argv,
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        transcript = _texte(out) + _texte(err)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        _tuer_groupe(proc)
        out, err = proc.communicate()  # reap : le groupe est mort
        transcript = _texte(out) + _texte(err)
        returncode = -1
        timed_out = True
    elapsed = round(time.time() - started, 1)

    result = {
        "essai": essai,
        "duree_s": elapsed,
        "timeout": timed_out,
        "returncode": returncode,
        "depart": {"passed": before[0], "failed": before[1]},
        "workdir": str(workdir),
    }
    result.update(parse_metrics(transcript))
    result.update(verify(workdir, scenario))
    return result, transcript


def mediane(valeurs):
    propres = sorted(v for v in valeurs if v is not None)
    if not propres:
        return None
    milieu = len(propres) // 2
    if len(propres) % 2:
        return propres[milieu]
    # Moyenne des deux valeurs centrales, arrondie : on compte des tests, pas des
    # fractions de test.
    return round((propres[milieu - 1] + propres[milieu]) / 2)


def run(harness, model, scenario_name, timeout, runs=1):
    """Exécute `runs` fois et agrège.

    Pourquoi plusieurs essais : la température n'est pas nulle (0.6 dans nos
    configs), donc UNE exécution est un tirage, pas une mesure. Constaté le
    2026-07-29 : deux runs de la même paire modèle/harnais sur tetris ont donné
    38/44 puis 21/44 — un écart de 17 tests que rien ne permettait d'attribuer
    soit à un changement de prompt, soit au hasard. Le gate de promote.sh doit
    donc trancher sur la MÉDIANE, jamais sur un tirage.
    """
    if harness not in HARNESSES:
        sys.exit("harnais inconnu: %s (connus: %s)" % (harness, ", ".join(HARNESSES)))
    scenario = SCENARIOS[scenario_name]
    slug = slug_de(scenario_name, harness, model)

    essais = []
    for i in range(1, runs + 1):
        print("=== essai %d/%d ===" % (i, runs), flush=True)
        res, transcript = run_once(harness, model, scenario_name, timeout, i, runs)
        essais.append(res)
        print("  %s  %s/%s tests  %s tours  pic %s  %ss" % (
            res["verdict"], res["tests_passed"], res["tests_attendus"],
            res.get("tours"), res.get("pic_input"), res["duree_s"]), flush=True)
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / ("%s-r%d.transcript" % (slug, i))).write_text(transcript)

    scores = [e["tests_passed"] for e in essais]
    attendus = scenario["expected_tests"]

    # La médiane ne porte QUE sur les essais dont le code compile : mélanger un 0/44
    # de collecte avec un 41/44 ne compare pas deux performances, ça compare une
    # performance à une panne de l'instrument. Les deux autres classes sont rapportées
    # comme des TAUX — « 1 essai sur 3 ne compile pas » informe sur le modèle, mais
    # ce n'est pas un score de zéro.
    notables = [e["tests_passed"] for e in essais if e.get("issue") == ISSUE_OK]
    med = mediane(notables) if notables else None
    n_collecte = sum(1 for e in essais if e.get("issue") == ISSUE_COLLECTE)
    n_pend = sum(1 for e in essais if e.get("issue") == ISSUE_PEND)
    result = {
        "scenario": scenario_name,
        "harnais": harness,
        "modele": model,
        "runs": runs,
        # `tests_passed` reste présent et vaut la MÉDIANE : les consommateurs
        # existants (promote.sh) continuent de fonctionner et lisent d'emblée la
        # valeur agrégée plutôt qu'un tirage.
        "tests_passed": med,
        "tests_passed_median": med,
        "tests_passed_min": min(notables) if notables else None,
        "tests_passed_max": max(notables) if notables else None,
        "tests_passed_ecart": (max(notables) - min(notables)) if notables else None,
        # `_tous` garde TOUS les tirages, y compris les 0 de collecte, pour rester
        # relisible ; `_notables` est ce sur quoi la médiane est calculée.
        "tests_passed_tous": scores,
        "tests_passed_notables": notables,
        "essais_comparables": len(notables),
        "essais_erreur_collecte": n_collecte,
        "essais_pytest_pend": n_pend,
        "tests_attendus": attendus,
        "verdict": "PASS" if med == attendus else "FAIL",
        "tours_median": mediane([e.get("tours") for e in essais]),
        "pic_input_median": mediane([e.get("pic_input") for e in essais]),
        "duree_s_median": mediane([e.get("duree_s") for e in essais]),
        "format_appels": essais[-1].get("format_appels"),
        "essais": essais,
    }

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / ("%s-%s.json" % (slug, stamp))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    print("\n=== agrégat sur %d essai(s) ===" % runs)
    for i, e in enumerate(essais, 1):
        etiquette = {ISSUE_OK: "", ISSUE_COLLECTE: "  <- NE COMPILE PAS",
                     ISSUE_PEND: "  <- pytest pend"}.get(e.get("issue"), "")
        print("  essai %d : %2s/%s  %s lignes ecrites%s" % (
            i, e["tests_passed"], attendus, e.get("lignes_ecrites"), etiquette))
    if notables:
        print("  médiane sur %d essai(s) comparable(s) : %s/%s   (min %s, max %s, écart %s)" % (
            len(notables), med, attendus, result["tests_passed_min"],
            result["tests_passed_max"], result["tests_passed_ecart"]))
    else:
        print("  ⚠️  AUCUN essai comparable : rien à médianiser")
    if n_collecte or n_pend:
        print("  hors médiane : %d/%d ne compile(nt) pas, %d pend(ent)" % (
            n_collecte, runs, n_pend))
        print("     ⚠️  un 0/44 de collecte n'est PAS une page blanche (cf. lignes"
              " écrites) : c'est souvent une coquille qui annule tout le paquet.")
    print("  tours méd.  : %s" % result["tours_median"])
    print("  pic méd.    : %s" % result["pic_input_median"])
    print("  verdict     : %s" % result["verdict"])
    if runs == 1:
        print("  ⚠️  UN SEUL ESSAI : c'est un tirage, pas une mesure. --runs 3 minimum")
    print("-> %s" % out)
    return 0 if result["verdict"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", default="pi")
    parser.add_argument("--scenario", default="repair", choices=sorted(SCENARIOS))
    parser.add_argument("--model", required=False)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--runs", type=int, default=3,
                        help="nombre d'exécutions ; la MÉDIANE fait foi (défaut 3)")
    parser.add_argument("--list-harnesses", action="store_true")
    args = parser.parse_args()
    if args.list_harnesses:
        print("\n".join(sorted(HARNESSES)))
        return 0
    if not args.model:
        parser.error("--model requis")
    return run(args.harness, args.model, args.scenario, args.timeout, args.runs)


if __name__ == "__main__":
    sys.exit(main())
