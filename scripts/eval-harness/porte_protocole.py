#!/usr/bin/env python3
"""Porte ÉLIMINATOIRE de protocole d'outils, à passer AVANT toute campagne.

Motif, mesuré le 2026-09-09 sur lfm2.5-8b-a1b : ce modèle a rendu le meilleur relevé
du banc d'éval de la journée (overall 0.910, coding 16/18, toolcall 1.000) et 0/44 au
tetris sur NEUF essais répartis sur trois harnais, sans écrire une ligne. Il a son
propre protocole agentique — un objet JSON {analysis, plan, commands, edits} déposé
dans `content` — qu'aucun harnais à `tool_calls` ne peut exécuter. Vingt-cinq minutes
de campagne par essai pour un défaut que quelques requêtes suffisent à voir.

CE QUE MESURE CETTE PORTE, ET POURQUOI C'EST UN TAUX
Le défaut n'est pas catégorique, il est PROBABILISTE. Trois exécutions successives
d'une version booléenne de cette porte, même modèle, même contexte, ont rendu PASSE,
REJET, PASSE. Le modèle tient le protocole une fraction du temps. C'est ce qui rend le
défaut invisible à un test unique — et fatal en tâche longue : le tetris demande une
douzaine de tours consécutifs, donc un taux par tour p donne p**12 de chance
d'aboutir. À p = 0,7, c'est 1 %. Les neuf 0/44 de lfm ne sont pas une malchance.

On mesure donc p sur PORTE_ESSAIS tirages et on exige un taux PLEIN. Un modèle qui
échoue un tirage sur cinq ici n'ira jamais au bout d'une tâche réelle.

DEUX CONTEXTES, parce que l'un sans l'autre conclut faux :
  FROIDE : tâche ouverte, contexte vide. Mesure s'il ENGAGE l'outillage tout seul.
  CHAUDE : un appel d'outil et son résultat sont déjà dans le contexte, et ce
           résultat est le VRAI contrat du tetris. Une première version utilisait un
           faux contrat de même taille (180 `def test_regle_NNN` identiques) : elle
           faisait PASSER lfm à tous les coups. Ce n'est pas le poids qui fait
           basculer le modèle, c'est la DENSITÉ de la spécification. D'où le refus de
           conclure si le vrai fichier manque.

PIÈGE DU BUDGET, dans lequel je suis tombé deux fois. À budget serré, ce modèle rend
un `content` VIDE avec `finish_reason: length` : tout part en raisonnement. On lit
alors un défaut de protocole là où il n'y a qu'un budget trop court. Un tirage qui
épuise son budget sans un mot ne compte donc ni pour ni contre : on le rejoue au
double avant de le compter.

Codes de sortie :  0 = PASSE   3 = REJET   4 = INDÉTERMINÉ (réseau, contrat absent)
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("LOCALAI_URL", "https://localai.tgu.ovh/v1")
CLE = pathlib.Path(os.path.expanduser("~/.config/brain/localai-key"))
BUDGET = int(os.environ.get("PORTE_BUDGET_TOKENS", "4096"))
ESSAIS = int(os.environ.get("PORTE_ESSAIS", "5"))
# Nombre de tours qu'une tâche réelle demande, mesuré sur le tetris : 13 pour
# l'incumbent qwen3-coder-30b. Sert à projeter le taux en probabilité d'aboutir.
TOURS_TACHE_REELLE = int(os.environ.get("PORTE_TOURS", "13"))

# Surface d'outils réaliste : les 4 intégrés de pi plus les 2 que l'extension
# context7 enregistre. Assez pour que le choix de l'outil compte un peu.
OUTILS = [
    ("read", "Read file contents", {"path": {"type": "string"}}),
    (
        "write",
        "Create or overwrite a file",
        {"path": {"type": "string"}, "content": {"type": "string"}},
    ),
    (
        "edit",
        "Replace exact text in a file",
        {
            "path": {"type": "string"},
            "oldText": {"type": "string"},
            "newText": {"type": "string"},
        },
    ),
    ("bash", "Execute a shell command", {"command": {"type": "string"}}),
    (
        "resolve-library-id",
        "Resolve a package name to a documentation library id",
        {"libraryName": {"type": "string"}},
    ),
    (
        "query-docs",
        "Fetch documentation for a resolved library",
        {"libraryId": {"type": "string"}, "question": {"type": "string"}},
    ),
]

TACHE = (
    "Le paquet `tetris/` n'existe pas : ecris-le entierement pour que tous les "
    "tests de tests/test_tetris.py passent. Lance `pytest -q` pour verifier.\n"
)

CONTRAT_REEL = (
    pathlib.Path(__file__).resolve().parent.parent
    / "harness-bench"
    / "fixture-tetris-etendu"
    / "tests"
    / "test_tetris.py"
)


def outils_openai():
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": d,
                "parameters": {"type": "object", "properties": p, "required": list(p)},
            },
        }
        for n, d, p in OUTILS
    ]


def demande(modele, messages, budget):
    corps = {
        "model": modele,
        "messages": messages,
        "tools": outils_openai(),
        "max_tokens": budget,
        "temperature": 0.2,
    }
    entetes = {"Content-Type": "application/json"}
    if CLE.exists():
        entetes["Authorization"] = "Bearer " + CLE.read_text().strip()
    requete = urllib.request.Request(
        BASE.rstrip("/") + "/chat/completions",
        data=json.dumps(corps).encode(),
        headers=entetes,
    )
    with urllib.request.urlopen(requete, timeout=900) as rep:
        return json.loads(rep.read())


def tirage(modele, messages, budget):
    """Un tirage. Rend (conforme, motif, ambigu) ; ambigu = budget épuisé sans un mot,
    ce qui ne prouve rien et doit être rejoué plus large."""
    try:
        d = demande(modele, messages, budget)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print("  INDÉTERMINÉ : %s" % e)
        sys.exit(4)
    choix = d["choices"][0]
    msg = choix["message"]
    appels = msg.get("tool_calls") or []
    sortie = d.get("usage", {}).get("completion_tokens", 0)
    if appels:
        return True, ", ".join(a["function"]["name"] for a in appels), False
    texte = (msg.get("content") or "").strip()
    if choix.get("finish_reason") == "length" and not texte:
        return False, "budget %d epuise sans un mot" % budget, True
    if texte.startswith("{") or texte.startswith("```json"):
        return (
            False,
            "protocole PROPRE : JSON dans `content` (%d tokens)" % sortie,
            False,
        )
    return False, "prose sans appel (%d tokens) : %s" % (sortie, texte[:80]), False


def mesure(modele, messages, nom, contrat_octets):
    """Rend le taux de conformité sur ESSAIS tirages."""
    print("  %s (%d tirages)" % (nom, ESSAIS))
    conformes = 0
    for i in range(ESSAIS):
        ok, motif, ambigu = tirage(modele, messages, BUDGET)
        if ambigu:
            ok, motif, ambigu = tirage(modele, messages, BUDGET * 2)
            motif += " [rejoue au double]"
        conformes += ok
        print(
            "    %d/%d  %-8s %s" % (i + 1, ESSAIS, "conforme" if ok else "ECHEC", motif)
        )
    taux = conformes / ESSAIS
    print("    -> taux %d/%d = %.2f" % (conformes, ESSAIS, taux))
    return taux


def main():
    if len(sys.argv) < 2:
        print("usage: porte_protocole.py <nom-du-modele-servi>", file=sys.stderr)
        return 2
    modele = sys.argv[1]
    if not CONTRAT_REEL.is_file():
        print(
            "INDÉTERMINÉ : contrat introuvable (%s). La sonde chaude exige le VRAI "
            "fichier de tests ; un substitut synthétique donne un faux PASSE."
            % CONTRAT_REEL
        )
        return 4
    contrat = CONTRAT_REEL.read_text()
    print(
        "porte de protocole sur %s\n  %s, budget %d, contrat %d o, %d tirages"
        % (modele, BASE, BUDGET, len(contrat), ESSAIS)
    )
    froide = [{"role": "user", "content": TACHE}]
    chaude = froide + [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "p1",
                    "type": "function",
                    "function": {
                        "name": "read",
                        "arguments": json.dumps({"path": "tests/test_tetris.py"}),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "p1", "content": contrat},
    ]
    t_froide = mesure(modele, froide, "FROIDE : contexte vide", len(contrat))
    t_chaude = mesure(modele, chaude, "CHAUDE : contrat deja lu", len(contrat))
    pire = min(t_froide, t_chaude)
    survie = pire**TOURS_TACHE_REELLE
    print(
        "\ntaux le plus bas %.2f -> probabilite de tenir %d tours : %.4f"
        % (pire, TOURS_TACHE_REELLE, survie)
    )
    if pire >= 1.0:
        print(
            "VERDICT PASSE : protocole tenu sur tous les tirages, dans les deux "
            "contextes. La campagne peut suivre."
        )
        return 0
    print(
        "VERDICT REJET : le protocole n'est tenu que %.0f %% du temps. Sur une tache "
        "de %d tours cela donne %.2f %% de chances d'aboutir -- c'est le profil de "
        "lfm2.5-8b-a1b, dont les neuf essais tetris ont tous fait 0/44."
        % (pire * 100, TOURS_TACHE_REELLE, survie * 100)
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
