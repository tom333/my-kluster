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
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
# Chaque essai produit des paires (contexte -> appel d'outil -> OK:/ERREUR:), qui
# sont le jeu d'entrainement du finetune de FORMAT (cf. generateur_traces.py). Ces
# transcripts vivaient dans /tmp et disparaissaient au redemarrage : 88 fichiers
# ont failli etre perdus le 2026-08-02. Les campagnes les archivent desormais
# elles-memes — mesurer et produire de la donnee coutent le meme GPU, autant
# garder les deux.
TRAJECTOIRES = HERE / "trajectoires"
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
    # Le trou de mesure que `tetris` et `repair` ne couvrent pas : LIRE du code
    # existant et l'etendre sans le casser. Les deux autres fixtures partent d'une
    # page blanche, et toutes deux sont SATUREES (44/44 sur 5/5 essais, 19/19
    # partout) — un score saturé ne discrimine plus rien.
    #
    # Le code existant est une solution 44/44 relue (essai 5 de la campagne
    # `contrat` du 2026-07-31, 5 modules). Deux defauts latents y ont ete reperes
    # et VOLONTAIREMENT conserves — c'est du vrai code, pas du code de vitrine :
    # `Piece._get_matrix` boucle sur la rotation brute (une rotation negative rend
    # une matrice non tournee) et remplit les cases vides de '' au lieu de '.'. Le
    # contrat d'extension oriente donc vers `cells()` plutot que `matrix`.
    "tetris-etendu": {
        "fixture": HERE / "fixture-tetris-etendu",
        "prompt": HERE / "PROMPT-tetris-etendu.txt",
        "expected_tests": 62,
        "protected": (
            "tests/test_tetris.py",
            "tests/test_extension.py",
            "conftest.py",
        ),
        "check_api": False,
        # Deux etages notes SEPAREMENT : « il a casse l'existant » n'est pas la
        # meme defaillance que « il n'a pas su etendre ». Chacun dans son propre
        # appel pytest, car une erreur d'import dans le fichier d'extension
        # interrompt la collecte de TOUTE la suite — le score de non-regression
        # serait perdu alors qu'il est precisement ce qu'on veut surveiller.
        "etages": (
            ("regression", "tests/test_tetris.py", 44),
            ("extension", "tests/test_extension.py", 18),
        ),
    },
    # Fixture 3 — reponse au diagnostic de CONTAMINATION du 2026-07-31 : `tetris`
    # (44/44 partout) et `repair` (19/19 partout) sont des exercices canoniques,
    # ecrits des milliers de fois, donc on y mesure en partie la RESTITUTION et non
    # la capacite. Grossir un tetris n'y change rien.
    #
    # Columns (Sega, 1990) est RARE — peu d'implementations publiques — tout en
    # restant plausible et algorithmiquement profond la ou tetris ne l'est pas :
    # alignements sur QUATRE axes, suppression simultanee, cascades en chaine.
    # Les details qui font l'oracle sont INVENTES (sens du cycle, alphabet des
    # tuiles, table des multiplicateurs, semantique de la simultaneite) : se
    # souvenir du jeu donne la forme, pas les reponses.
    #
    # Dix etages INDEPENDANTS, notes separement : c'est ce qui donne un score
    # GRADUE. `tetris` est binaire (les 44 tests importent tous le paquet, donc une
    # coquille donne 0/44), or un instrument tout-ou-rien sature ou s'effondre,
    # jamais entre les deux — il ne peut pas graduer.
    "columns": {
        "fixture": HERE / "fixture-columns",
        "prompt": HERE / "PROMPT-columns.txt",
        "expected_tests": 80,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
        ),
    },
    "columns-global": {
        "fixture": HERE / "fixture-columns",
        "prompt": HERE / "PROMPT-columns-global.txt",
        "expected_tests": 80,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
        ),
    },
    # Fixture 3bis — `columns` DEJA RESOLU, a etendre. Les dix etages d'origine sont
    # livres verts (une vraie solution 80/80, tirage 4 de a3b-iq4-e3) et servent de
    # NON-REGRESSION ; trois etages neufs decrivent une interface web.
    #
    # Ce que cette fixture mesure et qu'aucune autre ne mesure : LIRE du code
    # existant pour s'y raccrocher. `columns` part de zero, donc tout ce qui compte
    # y est dans l'enonce ; ici l'interface publique (Plateau, Colonne, Jeu) est sur
    # le disque, et l'etage 13 impose des choix aux etages 11 et 12 — c'est la forme
    # de tache ou l'ecart Opus/local etait le plus large (6 tours contre 35).
    #
    # Contrat verifie SATISFAISABLE avant tout tirage : une implementation de
    # reference a affiche 109 passed, puis a ete retiree. Sans elle, `pytest -q`
    # annonce « Interrupted: 3 errors during collection » et les 80 de regression ne
    # tournent meme pas — d'ou les etages separes, obligatoires ici.
    #
    # `colonnes/__init__.py` n'est PAS protege : l'etendre est permis, et les dix
    # etages de regression sont la garde qui punit une reecriture ratee.
    "columns-web": {
        "fixture": HERE / "fixture-columns-web",
        "prompt": HERE / "PROMPT-columns-web.txt",
        "expected_tests": 109,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "tests/test_11_rendu.py",
            "tests/test_12_etat.py",
            "tests/test_13_http.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
            ("rendu", "tests/test_11_rendu.py", 9),
            ("etat", "tests/test_12_etat.py", 8),
            ("http", "tests/test_13_http.py", 12),
        ),
    },
    # Fixture 4 — la SEULE qui puisse mesurer une phase de documentation. Les trois
    # autres sont en bibliotheque standard pure : une phase `chercheur` n'y serait
    # jamais sollicitee et ne couterait que ses schemas. On ne mesurerait rien.
    #
    # `attrs` a ete choisie apres une sonde, pas par intuition. Interroge sans
    # documentation, le modele produit du code PLAUSIBLE ET FAUX, de deux facons
    # independantes : `from attrs import validator` (le module est `validators`, au
    # pluriel -> ImportError) et `@couleur.validator` pose sur une annotation nue,
    # qui n'est pas un `field()` -> AttributeError. C'est exactement le regime que
    # la documentation corrige : le modele connait la FORME de la bibliotheque et se
    # trompe sur son API.
    #
    # Six modules INDEPENDANTS, un par etage : avec un module unique, le premier
    # mauvais import donnerait 0/38 et l'instrument redeviendrait binaire — le
    # defaut de `tetris`.
    "attrs": {
        "fixture": HERE / "fixture-attrs",
        "prompt": HERE / "PROMPT-attrs.txt",
        "expected_tests": 38,
        "protected": (
            "tests/test_1_piece.py",
            "tests/test_2_evolution.py",
            "tests/test_3_serialisation.py",
            "tests/test_4_gele.py",
            "tests/test_5_derive.py",
            "tests/test_6_introspection.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("piece", "tests/test_1_piece.py", 11),
            ("evolution", "tests/test_2_evolution.py", 7),
            ("serialisation", "tests/test_3_serialisation.py", 5),
            ("gele", "tests/test_4_gele.py", 6),
            ("derive", "tests/test_5_derive.py", 5),
            ("introspection", "tests/test_6_introspection.py", 4),
        ),
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
ISSUE_OK = "collecte_ok"  # les tests ont tourne : le score veut dire quelque chose
ISSUE_COLLECTE = (
    "erreur_collecte"  # SyntaxError / IndentationError / ModuleNotFoundError
)
ISSUE_PEND = "pytest_pend"  # boucle infinie : pytest ne rend jamais la main


def _fichiers_de_test(racine):
    """Ensemble des fichiers que pytest COLLECTE, ou qu'il soient dans l'arbre.

    Perimetre verifie sur le cas reel : le fichier ajoute qui a donne 46/44 etait
    `reproduce_test.py` a la RACINE du workdir, pas sous `tests/`. pytest collecte
    `test_*.py` et `*_test.py` depuis son rootdir — se limiter a `tests/` ne verrait
    rien.
    """
    return {
        p.relative_to(racine).as_posix()
        for p in racine.rglob("*.py")
        if p.is_file()
        and (p.name.startswith("test_") or p.name.endswith("_test.py"))
        and "__pycache__" not in p.parts
        and ".pytest_cache" not in p.parts
    }


def _sha_prompt(nom_scenario):
    """SHA-256 de l'enonce du scenario, ou None si le FICHIER est illisible.

    Un `except Exception` global avalait ici un bug d'appelant (le dict passe a la
    place du nom) : le champ est reste a None dans TOUS les resultats jusqu'au
    2026-08-05 sans que rien ne le signale. Un scenario inconnu est une erreur de
    programmation, elle doit crier ; seul un fichier absent se degrade en None.
    """
    import hashlib

    chemin = Path(SCENARIOS[nom_scenario]["prompt"])
    try:
        brut = chemin.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(brut).hexdigest()[:16]


def _sha_contrat(nom_scenario):
    """SHA-256 des fichiers de tests PROTEGES : le contrat que le modele doit tenir.

    Motif (2026-08-05) : `prompt_sha256` ne couvre que l'enonce, or le contrat vit
    dans les DOCSTRINGS et les assertions des tests. Un resserrement de la prose de
    `test_11_rendu.py` (les tuiles en chute occupent leur case au lieu d'etre ajoutees
    apres `</table>`) ne changeait pas d'un bit l'empreinte des campagnes — les
    tirages d'avant et d'apres se seraient melanges en silence dans la meme mediane.

    Les fichiers sont hashes dans l'ordre trie, chemin inclus : renommer un etage
    change l'empreinte, comme il se doit.
    """
    import hashlib

    sc = SCENARIOS[nom_scenario]
    h = hashlib.sha256()
    for rel in sorted(sc["protected"]):
        chemin = Path(sc["fixture"]) / rel
        try:
            brut = chemin.read_bytes()
        except OSError:
            continue
        h.update(rel.encode("utf-8"))
        h.update(brut)
    return h.hexdigest()[:16]


def _serveur_actif():
    """Contenu de logs-serveur/actif.json, ou None s'il n'existe pas.

    Ne leve jamais : une campagne lancee sans serveur.sh doit produire un
    resultat, simplement sans la config serveur — et l'absence est alors VISIBLE
    dans le JSON au lieu d'etre supposee.
    """
    try:
        return json.loads((HERE / "logs-serveur" / "actif.json").read_text())
    except Exception:
        return None


def run_pytest(workdir, cibles=()):
    """Retourne (passed, failed, sortie_courte, issue).

    Le depassement de delai est un RESULTAT, pas un plantage du banc : du code
    genere qui boucle a l'infini fait pendre pytest, et c'est un mode de
    defaillance attendu. On le rapporte au lieu de laisser l'exception remonter.

    `issue` distingue les trois classes ci-dessus. Sans elle, le banc ne peut pas
    comparer deux reglages voisins : les 0/44 de collecte noient le signal.

    `cibles` restreint la notation aux fichiers du CONTRAT. Motif (2026-07-30) : un
    essai a affiche 46/44 parce que le modele avait ecrit son propre
    `reproduce_test.py`, collecte par pytest. Ecrire un test de reproduction est un
    BON reflexe qu'on veut encourager — ce qu'il ne faut pas, c'est que ca gonfle le
    score et rende les tirages incomparables. On note donc le contrat, et le modele
    reste libre d'ajouter ce qu'il veut a cote.
    """
    # start_new_session + killpg : pytest peut avoir spawn des sous-process ;
    # sans groupe, le timeout les laisserait orphelins (cf. _tuer_groupe).
    proc = subprocess.Popen(
        [PYTEST, "-q", *cibles],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        _tuer_groupe(proc)
        proc.communicate()
        return (
            0,
            0,
            "TIMEOUT pytest apres 180s (boucle infinie dans le code genere)",
            ISSUE_PEND,
        )
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
    collecte_ratee = (
        "error during collection" in stdout or "errors during collection" in stdout
    )
    issue = ISSUE_COLLECTE if collecte_ratee else ISSUE_OK
    return passed, failed, tail[0], issue


def verify(workdir, scenario):
    """Verdict objectif : tests verts, gardes respectees, API intacte."""
    fixture = scenario["fixture"]
    expected = scenario["expected_tests"]
    # On note le CONTRAT : les fichiers de test proteges, et eux seuls. Un test que le
    # modele s'ecrit pour lui (reproduction, exploration) est un bon reflexe, pas une
    # infraction — il ne doit simplement pas entrer dans le score.
    contrat = [rel for rel in scenario["protected"] if "test" in Path(rel).name]
    etages = {}
    if scenario.get("etages"):
        # Un appel pytest PAR etage : une erreur d'import dans le fichier
        # d'extension interrompt la collecte de toute la suite, ce qui ferait
        # perdre le score de non-regression (mesure : un modele qui n'ecrit rien
        # afficherait 0/62 au lieu de 44/62).
        passed = failed = 0
        tail, issue = "", None
        for nom, fichier, attendu in scenario["etages"]:
            p, f, t, iss = run_pytest(workdir, cibles=[fichier])
            etages[nom] = {
                "passed": p,
                "failed": f,
                "attendus": attendu,
                "issue": iss,
                "verdict": "PASS" if p == attendu and not f else "FAIL",
            }
            passed += p
            failed += f
            if iss and issue is None:
                issue = iss
            if t:
                tail = ("%s\n[%s]\n%s" % (tail, nom, t)).strip()
    else:
        passed, failed, tail, issue = run_pytest(workdir, cibles=contrat)

    violations = []
    for rel in scenario["protected"]:
        before = (fixture / rel).read_bytes()
        after_path = workdir / rel
        if not after_path.exists():
            violations.append("%s supprime" % rel)
        elif after_path.read_bytes() != before:
            violations.append("%s modifie" % rel)

    # Les tests que le modele a ajoutes : PAS une violation, une observation. On les
    # remonte parce que c'est un comportement qu'on veut voir et peut-etre encourager.
    ajoutes = sorted(_fichiers_de_test(workdir) - _fichiers_de_test(fixture))

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
        # Vide hors scenario a deux etages. Sert a lire une defaillance : 44 en
        # regression et 0 en extension = « n'a pas su etendre » ; moins de 44 en
        # regression = « a casse l'existant », ce qui est bien plus grave.
        "etages": etages,
        "issue": issue,
        # Preuve qu'un "0/44" de collecte n'est pas une page blanche : on compte ce
        # qui a ete ecrit. 197 lignes + IndentationError != 0 ligne.
        "lignes_ecrites": sum(
            len(p.read_text(errors="replace").splitlines())
            for p in sorted(workdir.rglob("*.py"))
            if p.name != "conftest.py"
            and "tests/" not in p.relative_to(workdir).as_posix()
        ),
        "pytest_tail": tail,
        # Observation, pas sanction : les tests que le modele s'est ecrits.
        "tests_ajoutes": ajoutes,
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
    return argv[:i] + ["--append-system-prompt", INSTRUCTION_CHEMINS_ABSOLUS] + argv[
        i:
    ], env


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
    # P2 : la porte de vérification. Absente par défaut → le harnais reste le
    # témoin nu. HARNAIS_NU_VERIFY_CMD l'active sans toucher au code, pour mesurer
    # la règle contre le plancher du témoin.
    verify = []
    if os.environ.get("HARNAIS_NU_VERIFY_CMD"):
        verify = [
            "--verify-cmd",
            os.environ["HARNAIS_NU_VERIFY_CMD"],
            "--max-verify",
            os.environ.get("HARNAIS_NU_MAX_VERIFY", "3"),
        ]
    # Robustesse à la troncature, inerte par défaut (0) pour que le plancher du
    # témoin reste reproductible. 2 essais sur 6 sont morts d'un tool_call coupé.
    # Leviers d'hygiene de contexte, inertes par defaut. UN levier par campagne :
    # en activer plusieurs empeche d'attribuer l'effet (harnais-nu/MESURES.md).
    if os.environ.get("HARNAIS_NU_HYGIENE"):
        verify += ["--hygiene", os.environ["HARNAIS_NU_HYGIENE"]]
    if os.environ.get("HARNAIS_NU_MAX_RETRY_TRONCATURE"):
        verify += [
            "--max-retry-troncature",
            os.environ["HARNAIS_NU_MAX_RETRY_TRONCATURE"],
        ]
    # Edition structurelle (ast-grep) : un outil de plus dans le preambule, donc un
    # changement du temoin — a mesurer comme un levier, une variable a la fois.
    if os.environ.get("HARNAIS_NU_STRUCTURE"):
        verify += ["--structure"]
    # Porter le resultat des tests DANS le write/edit, au lieu d un `bash pytest`
    # separe. Levier sur le NOMBRE de tours : 48 des 61 `bash` mesures sur columns
    # etaient des pytest suivant une ecriture, et 100 % des tours ne portent qu un
    # seul appel d outil.
    if os.environ.get("HARNAIS_NU_TESTS_APRES_ECRITURE"):
        verify += ["--tests-apres-ecriture"]
        # Trois variants a departager (cf. MESURES.md) : `complet` fait -3 bash
        # mais +60 % de pic, `bilan` laisse le pic intact sans gain de tours,
        # `echecs` parie que les NOMS suffisent.
        if os.environ.get("HARNAIS_NU_TESTS_DETAIL"):
            verify += ["--tests-detail", os.environ["HARNAIS_NU_TESTS_DETAIL"]]
    # Compaction (harnais-nu/compaction.py), inerte sans --fenetre. Declarer une
    # fenetre PLUS PETITE que celle du serveur force le declenchement tot : c'est
    # ainsi qu'on teste la mecanique sur `repair` (93 s) au lieu d'attendre le mur.
    if os.environ.get("HARNAIS_NU_FENETRE"):
        verify += ["--fenetre", os.environ["HARNAIS_NU_FENETRE"]]
        if os.environ.get("HARNAIS_NU_SEUIL_COMPACTION"):
            verify += [
                "--seuil-compaction",
                os.environ["HARNAIS_NU_SEUIL_COMPACTION"],
            ]
    # Budget du CANAL DE PENSEE, envoye par requete. Sur `columns-web` un tour a
    # brule 26 161 caracteres de `reasoning_content` sans un seul tool_call, et
    # doubler le plafond par tour (4096 -> 8192) n'a fait que doubler le monologue :
    # ce n'est pas le meme levier, il faut borner la PENSEE et pas la reponse.
    # Deduplication des relectures RIGOUREUSEMENT identiques, mutee en place.
    # Cible revisee : elle ne sauve plus un run (le plafond desserre a fait
    # disparaitre les aneantissements), elle freine le VOLUME — un tirage du bras
    # gagnant a produit 41 705 tokens de sortie pour 8 tours.
    if os.environ.get("HARNAIS_NU_DEDUPE_RELECTURES"):
        verify += ["--dedupe-relectures"]
    # ECHANTILLONNAGE. Jusqu'au 2026-08-05 le harnais n'en envoyait AUCUN et le serveur
    # appliquait ses defauts : temp 1.0, min_p 0.05. Or la doc Qwen3.6 distingue deux
    # regimes en mode pensee — temp 1.0 pour les taches GENERALES, temp 0.6 pour le
    # CODE PRECIS — et ce banc ne fait que du code precis. Toutes les campagnes
    # anterieures ont donc tourne au mauvais regime, ce qui est le premier suspect pour
    # la variance qui a rendu chaque verdict penible (ecart 29, tours de 9 a 45 sur
    # reglage identique). Chaque variable absente = champ non envoye, donc temoin
    # inchange et historique toujours comparable.
    for var, drapeau in (
        ("HARNAIS_NU_TEMPERATURE", "--temperature"),
        ("HARNAIS_NU_MIN_P", "--min-p"),
        ("HARNAIS_NU_TOP_P", "--top-p"),
        ("HARNAIS_NU_TOP_K", "--top-k"),
        ("HARNAIS_NU_PRESENCE_PENALTY", "--presence-penalty"),
    ):
        if os.environ.get(var):
            verify += [drapeau, os.environ[var]]
    if os.environ.get("HARNAIS_NU_BUDGET_RAISONNEMENT"):
        verify += [
            "--budget-raisonnement",
            os.environ["HARNAIS_NU_BUDGET_RAISONNEMENT"],
        ]
    return [
        "uv",
        "run",
        "--project",
        str(HARNAIS_NU),
        str(HARNAIS_NU / "boucle.py"),
        "--task",
        prompt,
        "--workdir",
        str(workdir),
        "--base-url",
        base_url,
        "--model",
        model.split("/", 1)[-1],
        "--max-turns",
        os.environ.get("HARNAIS_NU_MAX_TURNS", "30"),
        "--max-tokens-per-turn",
        os.environ.get("HARNAIS_NU_MAX_TOKENS_PER_TURN", "4096"),
        "--max-total-tokens",
        os.environ.get("HARNAIS_NU_MAX_TOTAL_TOKENS", "100000"),
    ] + verify, {}


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
            # P2 : nombre de confrontations à la commande de vérification, et son
            # verdict. `verifications` est le prédicteur du score identifié dans
            # harnais-nu/MESURES.md — sans lui, la règle n'est pas mesurable.
            "verifications": m.get("verifications"),
            "verif_ok": m.get("verif_ok"),
            "retries_troncature": m.get("retries_troncature"),
            "hygiene": m.get("hygiene"),
            "caracteres_economises": m.get("caracteres_economises"),
            "writes_rattrapes": m.get("writes_rattrapes"),
            # `modes_compaction` distingue un resume reussi d'un repli mecanique :
            # sans lui, une campagne ou le modele echoue a resumer se lirait comme
            # une campagne de compaction par resume.
            "compactions": m.get("compactions"),
            "modes_compaction": m.get("modes_compaction"),
            # Deduplication : le COMPTE de relectures elaguees separe « le levier n a
            # pas mordu » de « il n y avait aucun doublon ». Sans lui, un bras sans
            # gain serait illisible — c est l erreur faite sur compactions=0.
            "dedups": m.get("dedups"),
            "dedup_economises": m.get("dedup_economises"),
            # `tests_auto` doit rester COMPARABLE au nombre de `bash pytest` qu il
            # remplace : s il le depasse largement, le levier gagne des tours et
            # paie du temps sur un paquet incomplet (risque predit, cf. MESURES.md).
            "tests_auto": m.get("tests_auto"),
            "tests_auto_ok": m.get("tests_auto_ok"),
        }
    return no_metrics(transcript)


def archive_trajectoire(workdir, etiquette):
    """Met le transcript de l'essai a l'abri, hors de /tmp.

    Ne leve JAMAIS : perdre une trace est sans gravite, perdre la campagne qui la
    produisait ne l'est pas. Meme discipline que le journal par tour.

    Seuls `nu` et `nu-contrat` ecrivent ce fichier ; les autres harnais (pi,
    aider) produisent des logs texte, inexploitables comme paires — on sort donc
    en silence plutot que de signaler une absence normale.

    ⚠️ L'etiquette porte le nom du SCENARIO : c'est ce qui permettra d'exclure
    `columns` du jeu d'entrainement. 62 % des traces en viennent, et c'est aussi
    l'instrument de mesure — s'entrainer dessus puis y mesurer ne mesurerait rien.
    """
    if not workdir:
        return
    source = Path(workdir) / ".harnais-nu-transcript.json"
    try:
        if not source.is_file():
            return
        TRAJECTOIRES.mkdir(exist_ok=True)
        shutil.copy2(source, TRAJECTOIRES / ("%s.json" % etiquette))
    except OSError:
        pass


def _nu_pipeline_command(model, workdir, prompt, graphe):
    """Pipeline à phases isolées (harnais-nu, sous-projet 1).

    Même serveur, même modèle et mêmes budgets que `nu` : la seule variable est
    le GRAPHE. C'est ce qui rend la comparaison au plancher (médiane 44/44, pic
    médian 34 515) interprétable.

    `graphe` est passé par le HARNAIS et non par variable d'environnement : le
    slug d'un essai vient du nom du harnais (`slug_de`), donc deux graphes sous
    un même nom se recouvriraient dans `results/` et rien dans les fichiers ne
    dirait lequel a produit quoi.
    """
    base_url = os.environ.get("HARNAIS_NU_BASE_URL", "http://127.0.0.1:8080/v1")
    commande = [
        "uv",
        "run",
        "--project",
        str(HARNAIS_NU),
        str(HARNAIS_NU / "pipeline.py"),
        "--task",
        prompt,
        "--workdir",
        str(workdir),
        "--base-url",
        base_url,
        "--model",
        model.split("/", 1)[-1],
        "--pipeline",
        graphe,
        "--verify-cmd",
        os.environ.get("HARNAIS_NU_VERIFY_CMD", PYTEST + " -q"),
        "--max-cycles",
        os.environ.get("HARNAIS_NU_MAX_CYCLES", "10"),
        # Le seul plafond qui morde sur `contrat` : son graphe ne repasse jamais
        # par sa phase de départ, donc --max-cycles y est inerte.
        "--max-etapes",
        os.environ.get("HARNAIS_NU_MAX_ETAPES", "24"),
    ]
    if graphe == "contrat":
        # Défaut VIDE, donc phase lint absente du graphe : le linter du harnais
        # n'est pas celui de la fixture mesurée, et l'ajouter changerait deux
        # variables au lieu d'une.
        commande += ["--lint-cmd", os.environ.get("HARNAIS_NU_LINT_CMD", "")]
    return commande, {}


def nu_pipeline_command(model, workdir, prompt):
    return _nu_pipeline_command(model, workdir, prompt, "neuf")


def nu_contrat_command(model, workdir, prompt):
    """Graphe `contrat` : comprendre → porte → implementer → (lint) → verifier.

    Une phase Agent de plus que le plancher, censée absorber l'exploration (les
    sorties d'outils font 35,8 % du contexte mesuré) et ne transmettre que ses
    notes. C'est cette hypothèse-là que l'essai tranche.
    """
    return _nu_pipeline_command(model, workdir, prompt, "contrat")


def nu_pipeline_metrics(transcript):
    """Le pipeline imprime son bilan en une ligne JSON sur stdout.

    On discrimine sur `"cycles"` et non sur `"turns"` : les deux harnais nu
    impriment `turns`, mais seul le pipeline compte des cycles et des étapes.

    `contradictions` compte les fois où le modèle a annoncé un succès démenti par
    l'oracle — l'auto-déclaration est le signal le moins fiable mesuré (cf.
    harnais-nu/MESURES.md), et cette clé le chiffre au lieu de le supposer.
    """
    for line in reversed(transcript.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and '"cycles"' in line):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {
            "tours": m.get("turns"),
            # Les appels d'outils sont comptés par phase, donc dans `journal`.
            "appels_outils": None,
            "format_appels": "phases isolées",
            "pic_input": m.get("peak_input_tokens"),
            "total_output": m.get("output_tokens_total"),
            "cycles": m.get("cycles"),
            "etapes": m.get("etapes"),
            "contradictions": m.get("contradictions"),
            "fin": m.get("fin"),
            "journal": m.get("journal"),
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
    "nu-pipeline": (nu_pipeline_command, nu_pipeline_metrics),
    "nu-contrat": (nu_contrat_command, nu_pipeline_metrics),
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

    # Par ETAGE quand le scenario en a : sur une fixture deja partiellement verte
    # (`columns-web` demarre a 80/109), un seul appel pytest annonce 0 passed, parce
    # que l'import manquant de l'etage a ecrire interrompt la collecte de TOUTE la
    # suite. Le verdict n'en dependait pas, mais la ligne se lisait « part de zero ».
    if scenario.get("etages"):
        p = f = 0
        for _, fichier, _ in scenario["etages"]:
            pe, fe, _, _ = run_pytest(workdir, cibles=[fichier])
            p += pe
            f += fe
        before = (p, f, "", None)
    else:
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
    """Mediane ARRONDIE a l'entier : on compte des tests, pas des fractions.

    L'algorithme vient de `statistics.median` (stdlib) plutot que d'une selection
    ecrite a la main — cette derniere avait fini par exister en DEUX exemplaires
    (`mediane` et `mediane_ratio`), et son arrondi code en dur avait failli
    ecraser un ratio (0,34 et 0,68 donnaient 1). Une seule implementation, deux
    politiques d'arrondi explicites."""
    propres = [v for v in valeurs if v is not None]
    return round(statistics.median(propres)) if propres else None


def mediane_ratio(valeurs, decimales=3):
    """Mediane d'un RATIO : meme calcul, mais l'arrondi garde des decimales.
    `mediane` ecraserait la valeur (0,34 et 0,68 donneraient 1)."""
    propres = [v for v in valeurs if v is not None]
    return round(statistics.median(propres), decimales) if propres else None


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
        print(
            "  %s  %s/%s tests  %s tours  pic %s  %ss"
            % (
                res["verdict"],
                res["tests_passed"],
                res["tests_attendus"],
                res.get("tours"),
                res.get("pic_input"),
                res["duree_s"],
            ),
            flush=True,
        )
        if res.get("etages"):
            # Les deux etages a l'ecran, pas seulement dans le JSON : « 44 en
            # regression, 0 en extension » et « 30 en regression » sont deux
            # defaillances tres differentes, et la seconde doit sauter aux yeux.
            print(
                "        %s"
                % "  ".join(
                    "%s %s/%s" % (nom, e["passed"], e["attendus"])
                    for nom, e in res["etages"].items()
                ),
                flush=True,
            )
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / ("%s-r%d.transcript" % (slug, i))).write_text(transcript)
        archive_trajectoire(res.get("workdir"), "%s-r%d" % (slug, i))

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
        # Metriques de COUT (regle ThinkingCap) : ce qui departage des scores
        # satures. Calculees sur les seuls essais COMPARABLES et a score non nul —
        # diviser par 0 test reussi n'a pas de sens, et un 0/44 de collecte
        # gonflerait artificiellement le ratio.
        #
        # ⚠️ Ne JAMAIS lire ces ratios sans le score absolu a cote : biais
        # d'abandon mesure (bonsai 3,8 tests/tour a 19/44 contre gemma 2,9 a
        # 41/44 — le plus « efficace » est celui qui a abandonne le plus tot).
        "sortie_par_test_median": mediane_ratio(
            [
                e["total_output"] / e["tests_passed"]
                for e in essais
                if e.get("issue") == ISSUE_OK
                and e.get("tests_passed")
                and e.get("total_output")
            ]
        ),
        "tours_par_test_median": mediane_ratio(
            [
                e["tours"] / e["tests_passed"]
                for e in essais
                if e.get("issue") == ISSUE_OK
                and e.get("tests_passed")
                and e.get("tours")
            ]
        ),
        # Piege 21 : les defauts de nu_command ne sont PAS la config de reference,
        # et un resultat qui ne porte pas sa config a produit une campagne
        # invalide sans que rien ne le signale (2026-07-31 : quatre reglages
        # differaient, diagnostique seulement apres coup). Chaque fichier de
        # resultat se decrit desormais lui-meme.
        "config_env": {
            cle: valeur
            for cle, valeur in sorted(os.environ.items())
            if cle.startswith("HARNAIS_")
        },
        "commande": " ".join(sys.argv),
        # Config SERVEUR active, publiee par serveur.sh. Sans elle, un drapeau
        # comme `-n 16384` plafonne le rejeu de troncature en silence : trois
        # campagnes d'Ornith ont ete invalidees ainsi le 2026-08-04, et l'argv
        # n'existait que dans l'historique du shell. Il voyage desormais avec
        # les scores.
        "serveur_actif": _serveur_actif(),
        # Hash de l'ENONCE tel qu'il etait AU MOMENT du run. `columns` et
        # `columns-global` ne different que par lui, et l'ecart mesure entre eux
        # (tours/test 0,470 -> 0,312) serait invisible sans ce champ.
        "prompt_sha256": _sha_prompt(scenario_name),
        # Le CONTRAT (docstrings + assertions des tests proteges). Distinct de
        # l'enonce : on peut resserrer l'un sans toucher l'autre, et l'empreinte doit
        # bouger dans les deux cas.
        "contrat_sha256": _sha_contrat(scenario_name),
        "format_appels": essais[-1].get("format_appels"),
        "essais": essais,
    }

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / ("%s-%s.json" % (slug, stamp))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    print("\n=== agrégat sur %d essai(s) ===" % runs)
    for i, e in enumerate(essais, 1):
        etiquette = {
            ISSUE_OK: "",
            ISSUE_COLLECTE: "  <- NE COMPILE PAS",
            ISSUE_PEND: "  <- pytest pend",
        }.get(e.get("issue"), "")
        print(
            "  essai %d : %2s/%s  %s lignes ecrites%s"
            % (i, e["tests_passed"], attendus, e.get("lignes_ecrites"), etiquette)
        )
    if notables:
        print(
            "  médiane sur %d essai(s) comparable(s) : %s/%s   (min %s, max %s, écart %s)"
            % (
                len(notables),
                med,
                attendus,
                result["tests_passed_min"],
                result["tests_passed_max"],
                result["tests_passed_ecart"],
            )
        )
    else:
        print("  ⚠️  AUCUN essai comparable : rien à médianiser")
    if n_collecte or n_pend:
        print(
            "  hors médiane : %d/%d ne compile(nt) pas, %d pend(ent)"
            % (n_collecte, runs, n_pend)
        )
        print(
            "     ⚠️  un 0/44 de collecte n'est PAS une page blanche (cf. lignes"
            " écrites) : c'est souvent une coquille qui annule tout le paquet."
        )
    print("  tours méd.  : %s" % result["tours_median"])
    print("  pic méd.    : %s" % result["pic_input_median"])
    # Cout par test reussi : ce qui departage des scores satures. Imprime SOUS la
    # mediane du score, jamais seul — un ratio sans le score absolu se lit a
    # l'envers (biais d'abandon : le plus « efficace » est souvent celui qui a
    # abandonne le plus tot).
    if result["tours_par_test_median"] is not None:
        print(
            "  cout méd.   : %s tours/test  %s tokens sortie/test  (a lire AVEC le score)"
            % (result["tours_par_test_median"], result["sortie_par_test_median"])
        )
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
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="nombre d'exécutions ; la MÉDIANE fait foi (défaut 3)",
    )
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
