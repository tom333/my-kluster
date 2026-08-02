"""Génère des traces d'appels d'outils, pour entraîner la DISCIPLINE DE FORMAT.

Pourquoi ce script existe, et pourquoi il n'a pas de tests
----------------------------------------------------------
La mesure du 2026-08-02 dit que la boucle rachète les erreurs de CONNAISSANCE
(pytest rend l'erreur, le modèle corrige) mais pas celles de FORMAT (un
`tool_call` malformé consomme le tour). Le format est un protocole, pas une
capacité : c'est la cible la moins chère pour un LoRA.

Or pour apprendre un protocole, **on n'a pas besoin d'oracle**. Le label est déjà
dans la sortie de l'outil : `OK:` ou `ERREUR:`. Pytest ne juge que la qualité du
RÉSULTAT, pas la validité de l'APPEL. D'où ce générateur, qui ne construit
aucune fixture et n'écrit aucun test — bâtir `attrs` avait coûté une matinée.

Ce qu'il vise, et pourquoi ces tâches-là
----------------------------------------
Le jeu déjà récolté est déséquilibré : bash 725, write 583, read 459, mais
`edit` 140 et `remplacer` 1. Or ce sont justement les outils où le format est
DIFFICILE (chaîne exacte à retrouver, motif AST valide) et où se concentrent les
refus (35 et 8). Un LoRA entraîné sur l'existant apprendrait surtout à écrire des
fichiers neufs — ce que le modèle sait déjà.

Les tâches ci-dessous sont donc toutes des MODIFICATIONS de code existant, et
volontairement courtes : on veut beaucoup de traces variées, pas quelques longues.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNAIS_NU = Path("/data/projets/perso/harnais-nu")
ARCHIVE = HERE / "trajectoires"

# Fichiers sources : du VRAI code, varié en style et en taille. Copiés à chaque
# fois — le modèle ne touche jamais l'original (il a `bash`, donc un dépôt réel
# monté en écriture serait une très mauvaise idée).
SOURCES = [
    "outils.py",
    "phases.py",
    "traces.py",
    "hygiene.py",
    "config.py",
    "tokens.py",
    "lint.py",
]

# Chaque tâche doit EXIGER une modification ciblée. Une formulation qui laisse la
# porte ouverte à « réécris le fichier » produirait des traces `write`, dont on a
# déjà 583.
TACHES = [
    "Ajoute un paramètre optionnel `silencieux=False` à la première fonction "
    "publique de {fichier}. Quand il vaut True, la fonction ne journalise rien. "
    "Ne modifie que cette fonction.",
    "Dans {fichier}, ajoute une garde en tête de la première fonction publique : "
    "si son premier argument est None, lève ValueError avec un message explicite. "
    "Ne touche à rien d'autre.",
    "Renomme la dernière fonction publique de {fichier} en lui ajoutant le "
    "suffixe `_v2`, et mets à jour tous ses appels dans le fichier.",
    "Dans {fichier}, remplace la première constante de module par une lecture de "
    "variable d'environnement du même nom, avec la valeur actuelle en défaut.",
    "Ajoute une docstring d'une ligne à chaque fonction de {fichier} qui n'en a "
    "pas. N'en modifie aucune qui en a déjà une.",
    "Dans {fichier}, extrais le corps de la fonction la plus longue dans une "
    "fonction privée `_aide`, appelée depuis l'originale.",
]


def prepare(racine, fichier):
    """Copie jetable. Le modèle dispose de `bash` : il ne travaille JAMAIS sur un
    dépôt réel, seulement sur une copie qu'on peut perdre."""
    racine.mkdir(parents=True, exist_ok=True)
    source = HARNAIS_NU / fichier
    if not source.is_file():
        return None
    shutil.copy2(source, racine / fichier)
    return racine / fichier


def lance(workdir, tache, journal, max_turns, base_url, modele):
    argv = [
        "uv",
        "run",
        "--project",
        str(HARNAIS_NU),
        str(HARNAIS_NU / "boucle.py"),
        "--task",
        tache,
        "--workdir",
        str(workdir),
        "--base-url",
        base_url,
        "--model",
        modele,
        "--max-turns",
        str(max_turns),
        "--max-tokens-per-turn",
        "16384",
        "--max-total-tokens",
        "120000",
        "--journal-tours",
        str(journal),
    ]
    # Pas de --verify-cmd : on ne juge pas le RÉSULTAT, seulement la validité des
    # appels. C'est tout l'intérêt — aucun test à écrire.
    return subprocess.run(argv, capture_output=True, text=True, timeout=900)


def compte(transcript):
    """(réussis, refusés) — le label est la sortie d'outil qui suit l'appel."""
    try:
        with open(transcript, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return 0, 0
    msgs = d if isinstance(d, list) else d.get("messages") or []
    ok = ko = 0
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        for _ in m.get("tool_calls") or []:
            suite = msgs[i + 1] if i + 1 < len(msgs) else None
            texte = (suite or {}).get("content") or ""
            if texte.startswith("ERREUR:"):
                ko += 1
            else:
                ok += 1
    return ok, ko


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tours", type=int, default=10, help="plafond par tâche")
    p.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    p.add_argument("--modele", default="default")
    p.add_argument("--sortie", default=str(ARCHIVE))
    p.add_argument(
        "--limite",
        type=int,
        default=0,
        help="nombre de tâches à lancer ; 0 = toutes les combinaisons",
    )
    p.add_argument(
        "--tuning-decide",
        action="store_true",
        help="obligatoire : atteste que la decision d'entrainer est PRISE",
    )
    args = p.parse_args()

    # Porte explicite. Generer des traces coute une heure de GPU exclusif, et ces
    # traces ne servent QU'A un finetune. Tant que la decision d'entrainer n'est
    # pas prise, c'est du GPU depense pour une hypothese.
    #
    # Et la prémisse s'est affaiblie le 2026-08-02 : le finetune visait la
    # DISCIPLINE DE FORMAT, motivee par un `format_acc` qui tombait de 1,00 a
    # 0,667 sur les petits modeles — sauf que cette metrique porte sur TROIS
    # items, donc l'ecart vaut UN item et ne prouve rien. Mesure faite depuis sur
    # notre propre harnais : Qwen3.5-4B emet des `tool_calls` natifs impeccables
    # et fait 19/19 sur `repair`. Il n'a pas de probleme de format a corriger.
    if not args.tuning_decide:
        print(
            "REFUS : passe --tuning-decide.\n"
            "  Ces traces ne servent qu'a un finetune, et une heure de GPU\n"
            "  exclusif pour une hypothese est du gaspillage. Verifie d'abord\n"
            "  qu'il reste un ecart de FORMAT a combler : Qwen3.5-4B n'en a pas."
        )
        return 0

    archive = Path(args.sortie)
    archive.mkdir(parents=True, exist_ok=True)
    base = Path("/tmp/traces-harnais")

    combinaisons = [(f, i, t) for f in SOURCES for i, t in enumerate(TACHES)]
    if args.limite:
        combinaisons = combinaisons[: args.limite]

    total_ok = total_ko = 0
    for n, (fichier, i, gabarit) in enumerate(combinaisons, 1):
        etiquette = "%s-t%d" % (fichier.replace(".py", ""), i)
        workdir = base / etiquette
        if workdir.exists():
            shutil.rmtree(workdir)
        if prepare(workdir, fichier) is None:
            print("  %s : source absente, ignoré" % etiquette, flush=True)
            continue

        debut = time.time()
        try:
            lance(
                workdir,
                gabarit.format(fichier=fichier),
                archive / ("journal-%s.jsonl" % etiquette),
                args.tours,
                args.base_url,
                args.modele,
            )
        except subprocess.TimeoutExpired:
            print("  %s : timeout" % etiquette, flush=True)
            continue

        transcript = workdir / ".harnais-nu-transcript.json"
        ok, ko = compte(transcript)
        total_ok += ok
        total_ko += ko
        if transcript.is_file():
            shutil.copy2(transcript, archive / ("traces-%s.json" % etiquette))
        print(
            "  [%2d/%2d] %-22s %3d OK / %2d refus  (%.0f s)"
            % (n, len(combinaisons), etiquette, ok, ko, time.time() - debut),
            flush=True,
        )

    print(
        "\ntotal : %d appels réussis, %d refusés (%d tâches)"
        % (total_ok, total_ko, len(combinaisons))
    )
    print("archivé dans %s" % archive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
