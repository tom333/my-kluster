"""Index SQLite des campagnes — DERIVE des fichiers, jamais leur remplacement.

Les fichiers restent la source de verite : `results/*.json` (scores et compteurs
par tirage), `trajectoires/*.json` (messages complets), `logs-serveur/*.log`
(tokens par requete, acceptation du drafter, clamps). La base n'en est qu'un
index interrogeable, **reconstructible a tout moment** : supprimer le fichier
.sqlite et relancer `--reindexer` le regenere a l'identique.

C'est ce qui permet d'ajouter une metrique APRES coup, comme on l'a deja fait :
l'analyse des 172 tours du 2026-08-04 — 48 `pytest` separes, 7 `mkdir` inutiles,
29 enchainements `write -> write` — a ete calculee sur des trajectoires archivees
des semaines plus tot. Une colonne de plus, une reindexation, aucune mesure a
rejouer.

Ce que la base apporte que `grep` n'apportait pas :

1. **Une empreinte de configuration par campagne.** Le 2026-08-04, deux bras ont
   ete compares alors qu'ils differaient par `verify_cmd`, l'enonce ET des
   drapeaux serveur. L'empreinte rend cette faute detectable.
2. **`--comparer` ne produit JAMAIS de mediane globale** : il groupe par
   empreinte et affiche une mediane par groupe. L'instrument devient
   structurellement incapable de melanger des configurations differentes.
3. **Un chiffre qu'on interroge** au lieu d'un chiffre qu'on relit. Le meme jour,
   un debit consigne dans MESURES.md (63,4 tok/s) a ete dementi par la machine
   (13,6). La base ne corrige pas ca — mais elle rend la verification triviale.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BDD = HERE / "registre.sqlite"

# Compteurs remontes par tirage. Ajouter une entree ici + `--reindexer` suffit a
# enrichir tout l'historique : c'est la propriete qui justifie de garder les
# fichiers complets.
COLONNES_TIRAGE = (
    "tests_passed",
    "tests_failed",
    "tests_attendus",
    "tours",
    "pic_input",
    "total_input",
    "total_output",
    "duree_s",
    "lignes_ecrites",
    "stop_reason",
    "issue",
    "verdict",
    "retries_troncature",
    "compactions",
    "tests_auto",
    "tests_auto_ok",
    "writes_rattrapes",
    "caracteres_economises",
    "verifications",
    "verif_ok",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS configs (
    empreinte   TEXT PRIMARY KEY,
    scenario    TEXT,
    harnais     TEXT,
    modele      TEXT,
    prompt_sha  TEXT,
    commande    TEXT,
    config_env  TEXT,
    serveur     TEXT,
    serveur_log TEXT,
    -- Compte les `truncated = 1` sur TOUTE la session serveur, pas sur la seule
    -- campagne : un meme serveur peut servir plusieurs campagnes successives. La
    -- valeur est donc un majorant, et c'est dit plutot que suppose.
    serveur_tronque INTEGER
);
CREATE TABLE IF NOT EXISTS tirages (
    campagne    TEXT,
    essai       INTEGER,
    empreinte   TEXT REFERENCES configs(empreinte),
    horodatage  TEXT,
    %s,
    appels_outils TEXT,
    chemin_resultat TEXT,
    PRIMARY KEY (campagne, essai)
);
CREATE INDEX IF NOT EXISTS idx_tirages_empreinte ON tirages(empreinte);
""" % ",\n    ".join("%s TEXT" % c for c in COLONNES_TIRAGE)


def ouvre(chemin=BDD):
    conn = sqlite3.connect(chemin)
    conn.executescript(SCHEMA)
    return conn


def empreinte(res):
    """Hash des seuls elements qui rendent deux campagnes COMPARABLES.

    Y figurent l'enonce (par son sha), les variables HARNAIS_*, les drapeaux
    serveur — parce que `-n 16384` a invalide trois campagnes en silence — ET
    l'etiquette `--model`.

    Cette derniere n'est pas redondante : au rattrapage du 2026-08-04, l'exclure
    a fusionne 30 tirages de modeles differents sous une seule empreinte, parce
    que l'historique n'a pas de config serveur et que l'etiquette y est la seule
    information de modele. Le sur-decoupage est sans danger — il cree deux
    groupes ou un suffirait ; la fusion produit une mediane qui ne veut rien dire.
    """
    serveur = res.get("serveur_actif") or {}
    graine = json.dumps(
        {
            "scenario": res.get("scenario"),
            "harnais": res.get("harnais"),
            "prompt_sha": res.get("prompt_sha256"),
            # Le CONTRAT, distinct de l'enonce. Resserrer une docstring de test ne
            # changeait pas d'un bit l'empreinte : les tirages d'avant et d'apres se
            # melangeaient dans la meme mediane. Absent des campagnes anterieures au
            # 2026-08-05, donc None y fait un groupe a part — ce qui est correct.
            "contrat_sha": res.get("contrat_sha256"),
            "env": res.get("config_env"),
            "etiquette": res.get("modele"),
            "modele_servi": serveur.get("modele"),
            "drapeaux": serveur.get("drapeaux"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:16]


def indexe(conn, chemin):
    """Insere (ou remplace) les tirages d'un fichier de resultat. Idempotent."""
    res = json.loads(Path(chemin).read_text(encoding="utf-8"))
    emp = empreinte(res)
    serveur = res.get("serveur_actif")
    conn.execute(
        "INSERT OR REPLACE INTO configs VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            emp,
            res.get("scenario"),
            res.get("harnais"),
            res.get("modele"),
            res.get("prompt_sha256"),
            res.get("commande"),
            json.dumps(res.get("config_env"), ensure_ascii=False),
            json.dumps(serveur, ensure_ascii=False) if serveur else None,
            (serveur or {}).get("log"),
            serveur_tronque((serveur or {}).get("log")) if serveur else None,
        ),
    )
    nom = Path(chemin).name
    horo = nom.rsplit("-", 2)[-2] + "-" + nom.rsplit("-", 2)[-1].removesuffix(".json")
    n = 0
    for essai in res.get("essais") or []:
        valeurs = [
            str(essai.get(c)) if essai.get(c) is not None else None
            for c in COLONNES_TIRAGE
        ]
        conn.execute(
            "INSERT OR REPLACE INTO tirages VALUES (?,?,?,?,%s,?,?)"
            % ",".join("?" * len(COLONNES_TIRAGE)),
            [nom, essai.get("essai"), emp, horo]
            + valeurs
            + [json.dumps(essai.get("appels_outils"), ensure_ascii=False), str(chemin)],
        )
        n += 1
    conn.commit()
    return n


def serveur_tronque(chemin_log):
    """Nombre d'amputations d'historique par llama-server (`truncated = 1`).

    Metrique ajoutee le 2026-08-04, une heure apres la capture des logs : le
    serveur JETTE de l'historique quand la requete ne tient pas, et nos chiffres
    ne le voyaient pas — `peak_input_tokens` vient de `usage.prompt_tokens`, donc
    du prompt APRES coupe. Une campagne peut tourner avec une memoire trouee sans
    qu'aucun compteur ne l'indique (5 fois sur un bras d'Ornith).

    Rétroactif seulement a partir du 2026-08-04 : avant, les logs n'existaient pas.

    Seul un log ABSENT se degrade en None. Un `except Exception` global avalerait un
    bug d'appelant : c'est ainsi que `prompt_sha256` est reste a None dans tous les
    resultats du banc jusqu'au 2026-08-05, sans que rien ne le signale.
    """
    if not chemin_log:
        return None
    try:
        brut = Path(chemin_log).read_text(errors="replace")
    except OSError:
        return None
    return sum(1 for ligne in brut.splitlines() if "truncated = 1" in ligne)


def reindexe(conn, dossier=HERE / "results"):
    total = fichiers = 0
    for chemin in sorted(Path(dossier).glob("*.json")):
        try:
            total += indexe(conn, chemin)
            fichiers += 1
        except Exception as exc:
            print("  ignore %s : %s" % (chemin.name, exc), file=sys.stderr)
    return fichiers, total


def mediane(valeurs):
    v = sorted(x for x in valeurs if x is not None)
    return v[len(v) // 2] if v else None


def comparer(conn, scenario):
    """Une mediane PAR EMPREINTE, jamais une mediane globale.

    C'est le garde-fou : le 2026-08-04 j'ai compare des bras qui differaient par
    trois variables a la fois. Ici, deux configurations differentes ne peuvent
    pas se fondre dans le meme chiffre.
    """
    lignes = conn.execute(
        "SELECT empreinte, COUNT(*) FROM tirages WHERE empreinte IN "
        "(SELECT empreinte FROM configs WHERE scenario=?) GROUP BY empreinte "
        "ORDER BY COUNT(*) DESC",
        (scenario,),
    ).fetchall()
    if not lignes:
        print("aucun tirage pour le scenario %r" % scenario)
        return
    print("scenario %s — %d configurations distinctes\n" % (scenario, len(lignes)))
    for emp, nb in lignes:
        cfg = conn.execute(
            "SELECT modele, prompt_sha, config_env, serveur FROM configs WHERE empreinte=?",
            (emp,),
        ).fetchone()
        tirages = conn.execute(
            "SELECT tests_passed, tours, duree_s, stop_reason FROM tirages "
            "WHERE empreinte=?",
            (emp,),
        ).fetchall()
        scores = [int(t[0]) for t in tirages if t[0] is not None]
        tours = [int(t[1]) for t in tirages if t[1] is not None]
        anormaux = sum(1 for t in tirages if t[3] in ("error", "truncated"))
        # Mediane des RAPPORTS, comme bench.py — pas rapport des medianes. Les
        # deux divergent (0,684 contre 0,720 sur la campagne de compaction) et
        # deux chiffres pour la meme grandeur rendent tout journal incomparable.
        rapports = [
            int(t[1]) / int(t[0]) for t in tirages if t[0] and t[1] and int(t[0]) > 0
        ]
        cout = mediane(rapports)
        print("  %s  n=%d  modele=%s  prompt=%s" % (emp, nb, cfg[0], cfg[1]))
        print(
            "    scores=%s  mediane=%s  tours=%s  tours/test=%s  arrets anormaux=%d"
            % (
                sorted(scores),
                mediane(scores),
                mediane(tours),
                "%.3f" % cout if cout else "-",
                anormaux,
            )
        )
        serveur = json.loads(cfg[3]) if cfg[3] else None
        print(
            "    serveur=%s"
            % (" ".join(serveur.get("drapeaux") or []) if serveur else "NON ENREGISTRE")
        )
        print()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reindexer", action="store_true")
    p.add_argument("--comparer", metavar="SCENARIO")
    p.add_argument("--sql")
    args = p.parse_args()
    conn = ouvre()
    if args.reindexer:
        fichiers, total = reindexe(conn)
        print("%d campagnes indexees, %d tirages" % (fichiers, total))
    if args.comparer:
        comparer(conn, args.comparer)
    if args.sql:
        for ligne in conn.execute(args.sql):
            print(ligne)
    if not (args.reindexer or args.comparer or args.sql):
        p.print_help()


if __name__ == "__main__":
    main()
